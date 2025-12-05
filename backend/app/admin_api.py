"""
Admin API endpoints for analytics, user management, and advanced features.
"""
import asyncio
import csv
import io
import json
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select, func, and_, or_, desc
from pydantic import BaseModel

from .database import async_session_maker
from .models import (
    User, Locker, Rent, MaintenanceLog, AuditLog,
    LockerStatus, EventType, LockerSize, PricingRule, RuleType,
    Incident, IncidentType, IncidentStatus, IncidentPriority,
    Shift, ShiftStatus, Task, TaskStatus, UserRole
)

# Import broadcast function from main - will be set after initialization
broadcast_locker_update = None

def set_broadcast_function(func):
    """Set the broadcast function from main.py"""
    global broadcast_locker_update
    broadcast_locker_update = func

router = APIRouter(prefix="/api/admin", tags=["admin"])


# Import broadcast function from main
# This will be set by main.py after app initialization
_broadcast_function = None

def set_broadcast_function(func):
    """Set the broadcast function to notify clients of changes."""
    global _broadcast_function
    _broadcast_function = func

async def notify_clients():
    """Notify all connected clients about data changes."""
    if _broadcast_function:
        await _broadcast_function()
    else:
        print("⚠️ Broadcast function not set!")


# ========== PYDANTIC MODELS ==========

class UserUpdate(BaseModel):
    phone: Optional[str] = None
    balance: Optional[float] = None
    is_blocked: Optional[bool] = None
    discount_percent: Optional[float] = None


class LockerUpdate(BaseModel):
    location_name: Optional[str] = None
    status: Optional[str] = None
    price_per_hour: Optional[float] = None
    battery_level: Optional[int] = None


class MaintenanceCreate(BaseModel):
    locker_id: int
    description: str
    performed_by: Optional[str] = None


class RentUpdate(BaseModel):
    comment: Optional[str] = None


# ========== ANALYTICS ENDPOINTS ==========

@router.get("/analytics/revenue")
async def get_revenue_analytics(period: str = "week"):
    """
    Get revenue analytics by period (day, week, month).
    """
    async with async_session_maker() as session:
        # Calculate date range
        now = datetime.now()
        if period == "day":
            start_date = now - timedelta(days=7)
            group_format = "day"
        elif period == "week":
            start_date = now - timedelta(weeks=12)
            group_format = "week"
        elif period == "month":
            start_date = now - timedelta(days=365)
            group_format = "month"
        else:
            start_date = now - timedelta(days=30)
            group_format = "day"

        # Get rents in period
        result = await session.execute(
            select(Rent).where(Rent.start_time >= start_date)
        )
        rents = result.scalars().all()

        # Group by period
        revenue_data = {}
        for rent in rents:
            if rent.start_time:
                if group_format == "day":
                    key = rent.start_time.strftime("%Y-%m-%d")
                elif group_format == "week":
                    key = f"Week {rent.start_time.isocalendar()[1]}, {rent.start_time.year}"
                else:  # month
                    key = rent.start_time.strftime("%Y-%m")
                
                if key not in revenue_data:
                    revenue_data[key] = {"period": key, "revenue": 0, "count": 0}
                revenue_data[key]["revenue"] += rent.cost
                revenue_data[key]["count"] += 1

        return {
            "period": period,
            "data": list(revenue_data.values())
        }


@router.get("/analytics/hourly")
async def get_hourly_statistics():
    """
    Get hourly usage statistics (peak hours).
    """
    async with async_session_maker() as session:
        # Get all rents from last 30 days
        thirty_days_ago = datetime.now() - timedelta(days=30)
        result = await session.execute(
            select(Rent).where(Rent.start_time >= thirty_days_ago)
        )
        rents = result.scalars().all()

        # Group by hour
        hourly_data = {hour: {"hour": hour, "count": 0, "revenue": 0} for hour in range(24)}
        
        for rent in rents:
            if rent.start_time:
                hour = rent.start_time.hour
                hourly_data[hour]["count"] += 1
                hourly_data[hour]["revenue"] += rent.cost

        return {
            "data": list(hourly_data.values())
        }


@router.get("/analytics/average_duration")
async def get_average_duration():
    """
    Calculate average rental duration and statistics.
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(Rent).where(Rent.end_time.isnot(None))
        )
        completed_rents = result.scalars().all()

        if not completed_rents:
            return {
                "average_minutes": 0,
                "median_minutes": 0,
                "shortest_minutes": 0,
                "longest_minutes": 0,
                "total_completed": 0
            }

        durations = []
        for rent in completed_rents:
            if rent.start_time and rent.end_time:
                duration = (rent.end_time - rent.start_time).total_seconds() / 60
                durations.append(duration)

        durations.sort()
        
        return {
            "average_minutes": sum(durations) / len(durations),
            "median_minutes": durations[len(durations) // 2] if durations else 0,
            "shortest_minutes": min(durations) if durations else 0,
            "longest_minutes": max(durations) if durations else 0,
            "total_completed": len(completed_rents)
        }


@router.get("/analytics/size_popularity")
async def get_size_popularity():
    """
    Get popularity statistics for different locker sizes.
    """
    async with async_session_maker() as session:
        # Get all completed rents
        result = await session.execute(select(Rent))
        rents = result.scalars().all()

        # Get locker info
        locker_ids = [rent.locker_id for rent in rents]
        lockers_result = await session.execute(
            select(Locker).where(Locker.id.in_(locker_ids))
        )
        lockers = {locker.id: locker for locker in lockers_result.scalars().all()}

        # Count by size
        size_stats = {
            "S": {"size": "Small", "rentals": 0, "revenue": 0},
            "M": {"size": "Medium", "rentals": 0, "revenue": 0},
            "L": {"size": "Large", "rentals": 0, "revenue": 0}
        }

        for rent in rents:
            locker = lockers.get(rent.locker_id)
            if locker:
                size_stats[locker.size.value]["rentals"] += 1
                size_stats[locker.size.value]["revenue"] += rent.cost

        return {"data": list(size_stats.values())}


@router.get("/analytics/user_retention")
async def get_user_retention():
    """
    Calculate user retention and conversion metrics.
    """
    async with async_session_maker() as session:
        # Get all users
        users_result = await session.execute(select(User))
        all_users = users_result.scalars().all()

        # Get users with rentals
        rents_result = await session.execute(select(Rent))
        all_rents = rents_result.scalars().all()

        # Calculate metrics
        users_with_rentals = len(set(rent.user_id for rent in all_rents))
        returning_users = 0
        one_time_users = 0
        
        user_rent_counts = {}
        for rent in all_rents:
            user_rent_counts[rent.user_id] = user_rent_counts.get(rent.user_id, 0) + 1

        for user_id, count in user_rent_counts.items():
            if count > 1:
                returning_users += 1
            else:
                one_time_users += 1

        return {
            "total_users": len(all_users),
            "users_with_rentals": users_with_rentals,
            "returning_users": returning_users,
            "one_time_users": one_time_users,
            "retention_rate": (returning_users / users_with_rentals * 100) if users_with_rentals > 0 else 0,
            "conversion_rate": (users_with_rentals / len(all_users) * 100) if len(all_users) > 0 else 0
        }


# ========== USER MANAGEMENT ENDPOINTS ==========

@router.get("/users")
async def get_all_users():
    """
    Get all users with their statistics.
    """
    async with async_session_maker() as session:
        users_result = await session.execute(select(User))
        users = users_result.scalars().all()

        users_data = []
        for user in users:
            # Get user's rentals
            rents_result = await session.execute(
                select(Rent).where(Rent.user_id == user.id)
            )
            rents = rents_result.scalars().all()
            
            active_rentals = sum(1 for r in rents if r.end_time is None)
            total_spent = sum(r.cost for r in rents)

            users_data.append({
                "id": user.id,
                "phone": user.phone,
                "balance": user.balance,
                "is_blocked": user.is_blocked,
                "discount_percent": user.discount_percent,
                "total_rentals": len(rents),
                "active_rentals": active_rentals,
                "total_spent": total_spent,
                "created_at": user.created_at.isoformat()
            })

        return {"users": users_data, "total": len(users_data)}


@router.get("/users/{user_id}")
async def get_user_details(user_id: int):
    """
    Get detailed information about a specific user.
    """
    async with async_session_maker() as session:
        user_result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get user's rental history
        rents_result = await session.execute(
            select(Rent).where(Rent.user_id == user_id).order_by(desc(Rent.start_time))
        )
        rents = rents_result.scalars().all()

        rental_history = []
        for rent in rents:
            locker_result = await session.execute(
                select(Locker).where(Locker.id == rent.locker_id)
            )
            locker = locker_result.scalar_one_or_none()

            rental_history.append({
                "id": rent.id,
                "locker": {
                    "id": locker.id if locker else None,
                    "location_name": locker.location_name if locker else "Unknown",
                    "size": locker.size.value if locker else None
                },
                "start_time": rent.start_time.isoformat(),
                "end_time": rent.end_time.isoformat() if rent.end_time else None,
                "cost": rent.cost,
                "is_active": rent.end_time is None
            })

        return {
            "user": {
                "id": user.id,
                "phone": user.phone,
                "balance": user.balance,
                "is_blocked": user.is_blocked,
                "discount_percent": user.discount_percent,
                "created_at": user.created_at.isoformat()
            },
            "rental_history": rental_history,
            "stats": {
                "total_rentals": len(rental_history),
                "active_rentals": sum(1 for r in rental_history if r["is_active"]),
                "total_spent": sum(r["cost"] for r in rental_history)
            }
        }


@router.patch("/users/{user_id}")
async def update_user(user_id: int, user_update: UserUpdate):
    """
    Update user information (balance, block status, discount, etc.).
    """
    async with async_session_maker() as session:
        user_result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Update fields
        if user_update.phone is not None:
            user.phone = user_update.phone
        if user_update.balance is not None:
            old_balance = user.balance
            user.balance = user_update.balance
            # Log balance change
            log = AuditLog(
                event_type=EventType.BALANCE_ADDED,
                user_id=user_id,
                description=f"Balance changed from {old_balance} to {user_update.balance}"
            )
            session.add(log)
        if user_update.is_blocked is not None:
            user.is_blocked = user_update.is_blocked
            log = AuditLog(
                event_type=EventType.USER_BLOCKED if user_update.is_blocked else EventType.USER_UNBLOCKED,
                user_id=user_id,
                description=f"User {'blocked' if user_update.is_blocked else 'unblocked'}"
            )
            session.add(log)
        if user_update.discount_percent is not None:
            user.discount_percent = user_update.discount_percent

        await session.commit()

        return {
            "status": "success",
            "message": "User updated successfully",
            "user": {
                "id": user.id,
                "phone": user.phone,
                "balance": user.balance,
                "is_blocked": user.is_blocked,
                "discount_percent": user.discount_percent
            }
        }


# ========== LOCKER MANAGEMENT ENDPOINTS ==========

@router.patch("/lockers/{locker_id}")
async def update_locker(locker_id: int, locker_update: LockerUpdate):
    """
    Update locker configuration (price, status, location, etc.).
    """
    async with async_session_maker() as session:
        locker_result = await session.execute(
            select(Locker).where(Locker.id == locker_id)
        )
        locker = locker_result.scalar_one_or_none()

        if not locker:
            raise HTTPException(status_code=404, detail="Locker not found")

        # Update fields
        if locker_update.location_name is not None:
            locker.location_name = locker_update.location_name
        if locker_update.status is not None:
            try:
                locker.status = LockerStatus(locker_update.status)
                if locker_update.status == "maintenance":
                    locker.last_maintenance = datetime.now()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid status")
        if locker_update.price_per_hour is not None:
            old_price = locker.price_per_hour
            locker.price_per_hour = locker_update.price_per_hour
            # Log price change
            log = AuditLog(
                event_type=EventType.PRICE_CHANGED,
                locker_id=locker_id,
                description=f"Price changed from {old_price} to {locker_update.price_per_hour}"
            )
            session.add(log)
        if locker_update.battery_level is not None:
            locker.battery_level = locker_update.battery_level

        await session.commit()

        # 🔥 Broadcast update to all connected clients!
        asyncio.create_task(notify_clients())
        print(f"📡 Broadcasting locker update to clients (locker #{locker_id})")

        return {
            "status": "success",
            "message": "Locker updated successfully",
            "locker": {
                "id": locker.id,
                "location_name": locker.location_name,
                "status": locker.status.value,
                "price_per_hour": locker.price_per_hour,
                "battery_level": locker.battery_level
            }
        }


@router.post("/lockers/{locker_id}/maintenance")
async def add_maintenance_log(maintenance: MaintenanceCreate):
    """
    Add a maintenance log entry for a locker.
    """
    async with async_session_maker() as session:
        # Check if locker exists
        locker_result = await session.execute(
            select(Locker).where(Locker.id == maintenance.locker_id)
        )
        locker = locker_result.scalar_one_or_none()

        if not locker:
            raise HTTPException(status_code=404, detail="Locker not found")

        # Create maintenance log
        log = MaintenanceLog(
            locker_id=maintenance.locker_id,
            description=maintenance.description,
            performed_by=maintenance.performed_by
        )
        session.add(log)

        # Update locker status and last maintenance
        locker.last_maintenance = datetime.now()
        locker.status = LockerStatus.MAINTENANCE

        # Add audit log
        audit = AuditLog(
            event_type=EventType.LOCKER_MAINTENANCE,
            locker_id=maintenance.locker_id,
            description=f"Maintenance performed: {maintenance.description}"
        )
        session.add(audit)

        await session.commit()

        # 🔥 Broadcast update to clients
        asyncio.create_task(notify_clients())
        print(f"📡 Broadcasting maintenance update to clients")

        return {
            "status": "success",
            "message": "Maintenance log added successfully"
        }


@router.get("/lockers/{locker_id}/maintenance")
async def get_maintenance_history(locker_id: int):
    """
    Get maintenance history for a specific locker.
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(MaintenanceLog)
            .where(MaintenanceLog.locker_id == locker_id)
            .order_by(desc(MaintenanceLog.performed_at))
        )
        logs = result.scalars().all()

        return {
            "locker_id": locker_id,
            "maintenance_logs": [
                {
                    "id": log.id,
                    "description": log.description,
                    "performed_by": log.performed_by,
                    "performed_at": log.performed_at.isoformat()
                }
                for log in logs
            ]
        }


@router.get("/lockers/{locker_id}/diagnostics")
async def get_locker_diagnostics(locker_id: int):
    """
    Get diagnostic information for a locker (battery, status, usage stats).
    """
    async with async_session_maker() as session:
        locker_result = await session.execute(
            select(Locker).where(Locker.id == locker_id)
        )
        locker = locker_result.scalar_one_or_none()

        if not locker:
            raise HTTPException(status_code=404, detail="Locker not found")

        # Get usage statistics
        rents_result = await session.execute(
            select(Rent).where(Rent.locker_id == locker_id)
        )
        rents = rents_result.scalars().all()

        return {
            "locker_id": locker.id,
            "mac_address": locker.mac_address,
            "status": locker.status.value,
            "battery_level": locker.battery_level,
            "last_maintenance": locker.last_maintenance.isoformat() if locker.last_maintenance else None,
            "total_uses": len(rents),
            "current_occupancy": locker.is_occupied,
            "health_status": "good" if (locker.battery_level or 100) > 20 else "warning"
        }


# ========== RENTAL MANAGEMENT ENDPOINTS ==========

@router.post("/rentals/{rental_id}/end")
async def force_end_rental(rental_id: int):
    """
    Manually end an active rental.
    """
    async with async_session_maker() as session:
        rent_result = await session.execute(
            select(Rent).where(Rent.id == rental_id)
        )
        rent = rent_result.scalar_one_or_none()

        if not rent:
            raise HTTPException(status_code=404, detail="Rental not found")

        if rent.end_time is not None:
            raise HTTPException(status_code=400, detail="Rental already ended")

        # End the rental
        rent.end_time = datetime.now()
        
        # Calculate cost
        duration_hours = (rent.end_time - rent.start_time).total_seconds() / 3600
        locker_result = await session.execute(
            select(Locker).where(Locker.id == rent.locker_id)
        )
        locker = locker_result.scalar_one_or_none()
        
        if locker:
            rent.cost = duration_hours * locker.price_per_hour
            locker.is_occupied = False

        # Add audit log
        log = AuditLog(
            event_type=EventType.RENT_END,
            user_id=rent.user_id,
            locker_id=rent.locker_id,
            description=f"Rental #{rental_id} manually ended. Cost: {rent.cost}"
        )
        session.add(log)

        await session.commit()

        # 🔥 Broadcast update to clients (locker is now free)
        asyncio.create_task(notify_clients())
        print(f"📡 Broadcasting rental end to clients")

        return {
            "status": "success",
            "message": "Rental ended successfully",
            "cost": rent.cost
        }


@router.patch("/rentals/{rental_id}")
async def update_rental(rental_id: int, rent_update: RentUpdate):
    """
    Update rental information (add comment, etc.).
    """
    async with async_session_maker() as session:
        rent_result = await session.execute(
            select(Rent).where(Rent.id == rental_id)
        )
        rent = rent_result.scalar_one_or_none()

        if not rent:
            raise HTTPException(status_code=404, detail="Rental not found")

        if rent_update.comment is not None:
            rent.comment = rent_update.comment

        await session.commit()

        return {
            "status": "success",
            "message": "Rental updated successfully"
        }


# ========== AUDIT LOG ENDPOINTS ==========

@router.get("/audit-log")
async def get_audit_log(limit: int = 100):
    """
    Get system audit log (last N entries).
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(AuditLog).order_by(desc(AuditLog.timestamp)).limit(limit)
        )
        logs = result.scalars().all()

        return {
            "logs": [
                {
                    "id": log.id,
                    "event_type": log.event_type.value,
                    "user_id": log.user_id,
                    "locker_id": log.locker_id,
                    "description": log.description,
                    "timestamp": log.timestamp.isoformat()
                }
                for log in logs
            ]
        }


# ========== EXPORT ENDPOINTS ==========

@router.get("/export/rentals/csv")
async def export_rentals_csv():
    """
    Export all rentals to CSV format.
    """
    async with async_session_maker() as session:
        # Get all rentals
        rents_result = await session.execute(select(Rent))
        rents = rents_result.scalars().all()

        # Get users and lockers
        users_result = await session.execute(select(User))
        users = {user.id: user for user in users_result.scalars().all()}

        lockers_result = await session.execute(select(Locker))
        lockers = {locker.id: locker for locker in lockers_result.scalars().all()}

        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            "ID", "User Phone", "Locker Location", "Locker Size",
            "Start Time", "End Time", "Duration (min)", "Cost", "Status"
        ])

        # Data
        for rent in rents:
            user = users.get(rent.user_id)
            locker = lockers.get(rent.locker_id)
            
            duration = None
            if rent.end_time:
                duration = int((rent.end_time - rent.start_time).total_seconds() / 60)

            writer.writerow([
                rent.id,
                user.phone if user else "Unknown",
                locker.location_name if locker else "Unknown",
                locker.size.value if locker else "Unknown",
                rent.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                rent.end_time.strftime("%Y-%m-%d %H:%M:%S") if rent.end_time else "Active",
                duration or "Active",
                rent.cost,
                "Completed" if rent.end_time else "Active"
            ])

        # Return CSV as response
        output.seek(0)
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=rentals_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )


@router.get("/export/users/csv")
async def export_users_csv():
    """
    Export all users to CSV format.
    """
    async with async_session_maker() as session:
        users_result = await session.execute(select(User))
        users = users_result.scalars().all()

        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            "ID", "Phone", "Balance", "Is Blocked", "Discount %",
            "Total Rentals", "Created At"
        ])

        # Data
        for user in users:
            writer.writerow([
                user.id,
                user.phone,
                user.balance,
                "Yes" if user.is_blocked else "No",
                user.discount_percent,
                user.total_rentals,
                user.created_at.strftime("%Y-%m-%d %H:%M:%S")
            ])

        output.seek(0)
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=users_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )


@router.get("/export/revenue/csv")
async def export_revenue_csv(start_date: Optional[str] = None, end_date: Optional[str] = None):
    """
    Export revenue report to CSV format.
    """
    async with async_session_maker() as session:
        query = select(Rent)
        
        if start_date:
            start_dt = datetime.fromisoformat(start_date)
            query = query.where(Rent.start_time >= start_dt)
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date)
            query = query.where(Rent.start_time <= end_dt)

        rents_result = await session.execute(query)
        rents = rents_result.scalars().all()

        # Get lockers for station info
        lockers_result = await session.execute(select(Locker))
        lockers = {locker.id: locker for locker in lockers_result.scalars().all()}

        # Group by date and station
        revenue_by_date = {}
        
        for rent in rents:
            if rent.end_time:  # Only completed rentals
                date_key = rent.start_time.strftime("%Y-%m-%d")
                locker = lockers.get(rent.locker_id)
                station = locker.location_name.split(" - ")[0] if locker else "Unknown"
                
                key = f"{date_key}_{station}"
                if key not in revenue_by_date:
                    revenue_by_date[key] = {
                        "date": date_key,
                        "station": station,
                        "revenue": 0,
                        "rentals": 0
                    }
                
                revenue_by_date[key]["revenue"] += rent.cost
                revenue_by_date[key]["rentals"] += 1

        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow(["Date", "Station", "Revenue", "Number of Rentals"])
        
        for data in sorted(revenue_by_date.values(), key=lambda x: x["date"]):
            writer.writerow([
                data["date"],
                data["station"],
                f"{data['revenue']:.2f}",
                data["rentals"]
            ])

        output.seek(0)
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=revenue_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )


# ========== DYNAMIC PRICING RULES ==========

@router.get("/pricing-rules")
async def get_pricing_rules():
    """
    Get all pricing rules.
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(PricingRule).order_by(desc(PricingRule.priority))
        )
        rules = result.scalars().all()
        
        # Parse JSON fields
        rules_data = []
        for rule in rules:
            rule_dict = {
                "id": rule.id,
                "name": rule.name,
                "rule_type": rule.rule_type.value,
                "price_multiplier": rule.price_multiplier,
                "start_hour": rule.start_hour,
                "end_hour": rule.end_hour,
                "start_date": rule.start_date.isoformat() if rule.start_date else None,
                "end_date": rule.end_date.isoformat() if rule.end_date else None,
                "days_of_week": json.loads(rule.days_of_week) if rule.days_of_week else None,
                "locker_sizes": json.loads(rule.locker_sizes) if rule.locker_sizes else None,
                "priority": rule.priority,
                "is_active": rule.is_active,
                "created_at": rule.created_at.isoformat(),
            }
            rules_data.append(rule_dict)
        
        return {"rules": rules_data, "total": len(rules_data)}


@router.post("/pricing-rules")
async def create_pricing_rule(
    name: str,
    rule_type: str,
    price_multiplier: float,
    start_hour: Optional[int] = None,
    end_hour: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    days_of_week: Optional[str] = None,  # JSON string
    locker_sizes: Optional[str] = None,  # JSON string
    priority: int = 0,
    is_active: bool = True
):
    """
    Create a new pricing rule.
    """
    async with async_session_maker() as session:
        # Parse dates
        start_date_obj = datetime.fromisoformat(start_date) if start_date else None
        end_date_obj = datetime.fromisoformat(end_date) if end_date else None
        
        new_rule = PricingRule(
            name=name,
            rule_type=RuleType(rule_type),
            price_multiplier=price_multiplier,
            start_hour=start_hour,
            end_hour=end_hour,
            start_date=start_date_obj,
            end_date=end_date_obj,
            days_of_week=days_of_week,
            locker_sizes=locker_sizes,
            priority=priority,
            is_active=is_active
        )
        
        session.add(new_rule)
        await session.commit()
        await session.refresh(new_rule)
        
        return {"status": "success", "rule_id": new_rule.id, "message": f"Правило '{name}' создано"}


@router.patch("/pricing-rules/{rule_id}")
async def update_pricing_rule(
    rule_id: int,
    name: Optional[str] = None,
    price_multiplier: Optional[float] = None,
    start_hour: Optional[int] = None,
    end_hour: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    days_of_week: Optional[str] = None,
    locker_sizes: Optional[str] = None,
    priority: Optional[int] = None,
    is_active: Optional[bool] = None
):
    """
    Update a pricing rule.
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(PricingRule).where(PricingRule.id == rule_id)
        )
        rule = result.scalar_one_or_none()
        
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        
        if name is not None:
            rule.name = name
        if price_multiplier is not None:
            rule.price_multiplier = price_multiplier
        if start_hour is not None:
            rule.start_hour = start_hour
        if end_hour is not None:
            rule.end_hour = end_hour
        if start_date is not None:
            rule.start_date = datetime.fromisoformat(start_date)
        if end_date is not None:
            rule.end_date = datetime.fromisoformat(end_date)
        if days_of_week is not None:
            rule.days_of_week = days_of_week
        if locker_sizes is not None:
            rule.locker_sizes = locker_sizes
        if priority is not None:
            rule.priority = priority
        if is_active is not None:
            rule.is_active = is_active
        
        await session.commit()
        
        return {"status": "success", "message": "Правило обновлено"}


@router.delete("/pricing-rules/{rule_id}")
async def delete_pricing_rule(rule_id: int):
    """
    Delete a pricing rule.
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(PricingRule).where(PricingRule.id == rule_id)
        )
        rule = result.scalar_one_or_none()
        
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        
        await session.delete(rule)
        await session.commit()
        
        return {"status": "success", "message": "Правило удалено"}


@router.get("/pricing/calculate")
async def calculate_dynamic_price(locker_id: int):
    """
    Calculate current dynamic price for a locker.
    Returns base price and applicable rules with final price.
    """
    async with async_session_maker() as session:
        # Get locker
        result = await session.execute(
            select(Locker).where(Locker.id == locker_id)
        )
        locker = result.scalar_one_or_none()
        
        if not locker:
            raise HTTPException(status_code=404, detail="Locker not found")
        
        base_price = locker.price_per_hour
        
        # Get all active rules
        result = await session.execute(
            select(PricingRule)
            .where(PricingRule.is_active == True)
            .order_by(desc(PricingRule.priority))
        )
        all_rules = result.scalars().all()
        
        # Check which rules apply
        now = datetime.now()
        current_hour = now.hour
        current_day_of_week = now.weekday()  # 0=Monday, 6=Sunday
        
        applicable_rules = []
        total_multiplier = 1.0
        
        for rule in all_rules:
            applies = False
            
            # Check locker size
            if rule.locker_sizes:
                sizes = json.loads(rule.locker_sizes)
                if locker.size.value not in sizes:
                    continue
            
            # Check rule type
            if rule.rule_type == RuleType.HOURLY:
                if rule.start_hour is not None and rule.end_hour is not None:
                    if rule.start_hour <= current_hour < rule.end_hour:
                        applies = True
            
            elif rule.rule_type == RuleType.SEASONAL:
                if rule.start_date and rule.end_date:
                    if rule.start_date <= now <= rule.end_date:
                        applies = True
            
            elif rule.rule_type == RuleType.DAY_OF_WEEK:
                if rule.days_of_week:
                    days = json.loads(rule.days_of_week)
                    if current_day_of_week in days:
                        applies = True
            
            if applies:
                applicable_rules.append({
                    "id": rule.id,
                    "name": rule.name,
                    "multiplier": rule.price_multiplier
                })
                total_multiplier *= rule.price_multiplier
        
        final_price = base_price * total_multiplier
        
        return {
            "locker_id": locker_id,
            "locker_size": locker.size.value,
            "base_price": base_price,
            "applicable_rules": applicable_rules,
            "total_multiplier": total_multiplier,
            "final_price": round(final_price, 2),
            "discount_percent": round((1 - total_multiplier) * 100, 1) if total_multiplier < 1 else 0,
            "surcharge_percent": round((total_multiplier - 1) * 100, 1) if total_multiplier > 1 else 0
        }


# ========== INCIDENT MANAGEMENT ==========

@router.get("/incidents")
async def get_incidents(status: Optional[str] = None, priority: Optional[str] = None):
    """
    Get all incidents with optional filters.
    """
    async with async_session_maker() as session:
        query = select(Incident).order_by(desc(Incident.reported_at))
        
        if status:
            query = query.where(Incident.status == IncidentStatus(status))
        if priority:
            query = query.where(Incident.priority == IncidentPriority(priority))
        
        result = await session.execute(query)
        incidents = result.scalars().all()
        
        # Fetch related data
        incidents_data = []
        for inc in incidents:
            # Get locker info
            locker_result = await session.execute(
                select(Locker).where(Locker.id == inc.locker_id)
            )
            locker = locker_result.scalar_one_or_none()
            
            # Get user info if exists
            user_phone = None
            if inc.user_id:
                user_result = await session.execute(
                    select(User).where(User.id == inc.user_id)
                )
                user = user_result.scalar_one_or_none()
                if user:
                    user_phone = user.phone
            
            incidents_data.append({
                "id": inc.id,
                "locker_id": inc.locker_id,
                "locker_location": locker.location_name if locker else "Unknown",
                "locker_size": locker.size.value if locker else "?",
                "user_id": inc.user_id,
                "user_phone": user_phone,
                "rent_id": inc.rent_id,
                "incident_type": inc.incident_type.value,
                "status": inc.status.value,
                "priority": inc.priority.value,
                "title": inc.title,
                "description": inc.description,
                "resolution": inc.resolution,
                "reported_at": inc.reported_at.isoformat(),
                "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
                "closed_at": inc.closed_at.isoformat() if inc.closed_at else None,
                "assigned_to": inc.assigned_to,
                "auto_block_locker": inc.auto_block_locker
            })
        
        return {"incidents": incidents_data, "total": len(incidents_data)}


@router.post("/incidents")
async def create_incident(
    locker_id: int,
    incident_type: str,
    title: str,
    description: str,
    user_id: Optional[int] = None,
    rent_id: Optional[int] = None,
    priority: str = "medium",
    auto_block_locker: bool = True
):
    """
    Create a new incident.
    """
    async with async_session_maker() as session:
        # Check if locker exists
        result = await session.execute(
            select(Locker).where(Locker.id == locker_id)
        )
        locker = result.scalar_one_or_none()
        if not locker:
            raise HTTPException(status_code=404, detail="Locker not found")
        
        # Create incident
        new_incident = Incident(
            locker_id=locker_id,
            user_id=user_id,
            rent_id=rent_id,
            incident_type=IncidentType(incident_type),
            priority=IncidentPriority(priority),
            title=title,
            description=description,
            auto_block_locker=auto_block_locker
        )
        
        session.add(new_incident)
        
        # Auto-block locker if requested
        if auto_block_locker:
            locker.status = LockerStatus.MAINTENANCE
        
        await session.commit()
        await session.refresh(new_incident)
        
        return {
            "status": "success",
            "incident_id": new_incident.id,
            "message": f"Инцидент #{new_incident.id} создан",
            "locker_blocked": auto_block_locker
        }


@router.patch("/incidents/{incident_id}")
async def update_incident(
    incident_id: int,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    resolution: Optional[str] = None,
    assigned_to: Optional[str] = None
):
    """
    Update incident status/priority/resolution.
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(Incident).where(Incident.id == incident_id)
        )
        incident = result.scalar_one_or_none()
        
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        now = datetime.now()
        
        if status:
            old_status = incident.status
            incident.status = IncidentStatus(status)
            
            if status == "resolved" and old_status != IncidentStatus.RESOLVED:
                incident.resolved_at = now
            elif status == "closed" and old_status != IncidentStatus.CLOSED:
                incident.closed_at = now
        
        if priority:
            incident.priority = IncidentPriority(priority)
        
        if resolution:
            incident.resolution = resolution
        
        if assigned_to is not None:
            incident.assigned_to = assigned_to
        
        await session.commit()
        
        return {"status": "success", "message": "Инцидент обновлен"}


@router.delete("/incidents/{incident_id}")
async def delete_incident(incident_id: int):
    """
    Delete an incident.
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(Incident).where(Incident.id == incident_id)
        )
        incident = result.scalar_one_or_none()
        
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        await session.delete(incident)
        await session.commit()
        
        return {"status": "success", "message": "Инцидент удален"}


@router.get("/incidents/stats")
async def get_incidents_stats():
    """
    Get incident statistics.
    """
    async with async_session_maker() as session:
        # Total incidents
        total_result = await session.execute(select(func.count()).select_from(Incident))
        total = total_result.scalar()
        
        # By status
        new_result = await session.execute(
            select(func.count()).select_from(Incident).where(Incident.status == IncidentStatus.NEW)
        )
        new_count = new_result.scalar()
        
        in_progress_result = await session.execute(
            select(func.count()).select_from(Incident).where(Incident.status == IncidentStatus.IN_PROGRESS)
        )
        in_progress_count = in_progress_result.scalar()
        
        resolved_result = await session.execute(
            select(func.count()).select_from(Incident).where(Incident.status == IncidentStatus.RESOLVED)
        )
        resolved_count = resolved_result.scalar()
        
        # By priority
        critical_result = await session.execute(
            select(func.count()).select_from(Incident).where(Incident.priority == IncidentPriority.CRITICAL)
        )
        critical_count = critical_result.scalar()
        
        high_result = await session.execute(
            select(func.count()).select_from(Incident).where(Incident.priority == IncidentPriority.HIGH)
        )
        high_count = high_result.scalar()
        
        return {
            "total": total,
            "by_status": {
                "new": new_count,
                "in_progress": in_progress_count,
                "resolved": resolved_count
            },
            "by_priority": {
                "critical": critical_count,
                "high": high_count
            },
            "pending": new_count + in_progress_count
        }

# Добавить в конец admin_api.py после всех incidents endpoints:


# ========== SHIFTS & STAFF MANAGEMENT ==========

@router.get("/shifts/active")
async def get_active_shifts():
    """Get all currently active shifts."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Shift, User)
            .join(User, Shift.user_id == User.id)
            .where(Shift.status == ShiftStatus.ACTIVE)
            .order_by(desc(Shift.start_time))
        )
        shifts_data = []
        for shift, user in result:
            shifts_data.append({
                "id": shift.id,
                "user_id": user.id,
                "user_name": user.name or user.phone,
                "user_role": user.role.value,
                "start_time": shift.start_time.isoformat(),
                "station": shift.station,
                "duration_minutes": int((datetime.now() - shift.start_time).total_seconds() / 60)
            })
        return {"active_shifts": shifts_data, "total": len(shifts_data)}


@router.post("/shifts/start")
async def start_shift(user_id: int, station: Optional[str] = None):
    """Start a new shift for a user."""
    async with async_session_maker() as session:
        # Check if user already has active shift
        result = await session.execute(
            select(Shift).where(
                Shift.user_id == user_id,
                Shift.status == ShiftStatus.ACTIVE
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="User already has active shift")
        
        new_shift = Shift(
            user_id=user_id,
            station=station,
            status=ShiftStatus.ACTIVE
        )
        session.add(new_shift)
        await session.commit()
        await session.refresh(new_shift)
        
        return {
            "status": "success",
            "shift_id": new_shift.id,
            "message": "Смена начата"
        }


@router.post("/shifts/{shift_id}/end")
async def end_shift(shift_id: int, notes: Optional[str] = None):
    """End a shift."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Shift).where(Shift.id == shift_id)
        )
        shift = result.scalar_one_or_none()
        if not shift:
            raise HTTPException(status_code=404, detail="Shift not found")
        
        shift.status = ShiftStatus.COMPLETED
        shift.end_time = datetime.now()
        if notes:
            shift.notes = notes
        
        await session.commit()
        
        duration = (shift.end_time - shift.start_time).total_seconds() / 3600
        return {
            "status": "success",
            "duration_hours": round(duration, 2),
            "message": "Смена завершена"
        }


# ========== TASKS & CHECKLISTS ==========

@router.get("/tasks")
async def get_tasks(status: Optional[str] = None, user_id: Optional[int] = None):
    """Get tasks with optional filters."""
    async with async_session_maker() as session:
        query = select(Task).order_by(desc(Task.created_at))
        
        if status:
            query = query.where(Task.status == TaskStatus(status))
        if user_id:
            query = query.where(Task.assigned_to_user_id == user_id)
        
        result = await session.execute(query)
        tasks = result.scalars().all()
        
        tasks_data = []
        for task in tasks:
            tasks_data.append({
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "task_type": task.task_type,
                "status": task.status.value,
                "assigned_to_user_id": task.assigned_to_user_id,
                "locker_id": task.locker_id,
                "created_at": task.created_at.isoformat(),
                "completed_at": task.completed_at.isoformat() if task.completed_at else None
            })
        
        return {"tasks": tasks_data, "total": len(tasks_data)}


@router.post("/tasks")
async def create_task(
    title: str,
    task_type: str,
    description: Optional[str] = None,
    assigned_to_user_id: Optional[int] = None,
    locker_id: Optional[int] = None
):
    """Create a new task."""
    async with async_session_maker() as session:
        new_task = Task(
            title=title,
            description=description,
            task_type=task_type,
            assigned_to_user_id=assigned_to_user_id,
            locker_id=locker_id
        )
        
        session.add(new_task)
        await session.commit()
        await session.refresh(new_task)
        
        return {
            "status": "success",
            "task_id": new_task.id,
            "message": "Задача создана"
        }


@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: int,
    status: Optional[str] = None,
    completed_by_user_id: Optional[int] = None
):
    """Update task status."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Task).where(Task.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if status:
            task.status = TaskStatus(status)
            if status == "completed":
                task.completed_at = datetime.now()
                if completed_by_user_id:
                    task.completed_by_user_id = completed_by_user_id
        
        await session.commit()
        return {"status": "success", "message": "Задача обновлена"}


# ========== STAFF & ROLES ==========

@router.get("/staff")
async def get_staff():
    """Get all staff members (non-USER roles)."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.role != UserRole.USER).order_by(User.name)
        )
        users = result.scalars().all()
        
        staff_data = []
        for user in users:
            # Get active shift
            shift_result = await session.execute(
                select(Shift).where(
                    Shift.user_id == user.id,
                    Shift.status == ShiftStatus.ACTIVE
                )
            )
            active_shift = shift_result.scalar_one_or_none()
            
            staff_data.append({
                "id": user.id,
                "name": user.name or user.phone,
                "phone": user.phone,
                "role": user.role.value,
                "is_on_shift": active_shift is not None,
                "created_at": user.created_at.isoformat()
            })
        
        return {"staff": staff_data, "total": len(staff_data)}


@router.patch("/users/{user_id}/role")
async def update_user_role(user_id: int, role: str):
    """Update user's role."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user.role = UserRole(role)
        await session.commit()
        
        return {"status": "success", "message": "Роль обновлена"}


# ========== PRICING MANAGEMENT ==========

@router.post("/pricing/bulk-update")
async def bulk_update_prices(prices: dict):
    """
    Bulk update prices for locker sizes.
    Expected format: {"small": 100, "medium": 150, "large": 250}
    """
    async with async_session_maker() as session:
        size_mapping = {
            "small": LockerSize.SMALL,
            "medium": LockerSize.MEDIUM,
            "large": LockerSize.LARGE
        }
        
        updated_count = 0
        
        for size_key, new_price in prices.items():
            if size_key not in size_mapping:
                continue
            
            locker_size = size_mapping[size_key]
            
            # Update all lockers of this size
            result = await session.execute(
                select(Locker).where(Locker.size == locker_size)
            )
            lockers = result.scalars().all()
            
            for locker in lockers:
                locker.price_per_hour = new_price
                updated_count += 1
        
        await session.commit()
        
        # Broadcast update to WebSocket clients
        if broadcast_locker_update:
            asyncio.create_task(broadcast_locker_update())
            print(f"📡 Bulk price update: {updated_count} lockers updated, broadcasting to clients")
        else:
            print("⚠️ Broadcast function not set")
        
        return {
            "status": "success",
            "message": f"Обновлено {updated_count} ячеек",
            "updated_count": updated_count
        }


@router.post("/settings/update")
async def update_system_settings(settings: dict):
    """
    Update system settings.
    This is a placeholder - in production, store in a Settings table.
    """
    # For now, just log the settings
    print(f"⚙️ System settings updated: {settings}")
    
    return {
        "status": "success",
        "message": "Настройки сохранены",
        "settings": settings
    }

