import asyncio
import uuid
import json
from datetime import datetime, timezone
from typing import List

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
import aiomqtt
import os

from .database import Base, engine, async_session_maker
from .mqtt import listen_mqtt
from .models import Locker, Rent
from .schemas import LockerRead, RentStart
from .seed import seed_lockers
from .admin_api import router as admin_router, set_broadcast_function
from .security_api import router as security_router
from .auth_api import router as auth_router


app = FastAPI(title="Lock&Go Backend", version="MVP 1.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(security_router)

MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "mosquitto")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))

# Global system lock for emergency stop
SYSTEM_LOCKED = False

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"✅ WebSocket client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(f"❌ WebSocket client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        """Broadcast message to all connected clients"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"⚠️ Failed to send to client: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            if conn in self.active_connections:
                self.active_connections.remove(conn)

manager = ConnectionManager()


@app.on_event("startup")
async def on_startup() -> None:
    # Initialize database schema
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Set up admin broadcast function
    set_broadcast_function(broadcast_locker_update)
    print("✅ Admin API broadcast function configured")

    # Start MQTT listener as a background task
    asyncio.create_task(listen_mqtt())


@app.get("/")
async def root_status() -> dict[str, str]:
    return {"status": "System Operational", "version": "MVP 1.0"}


@app.get("/api/lockers", response_model=List[LockerRead])
async def get_lockers() -> List[LockerRead]:
    """Get all lockers from the database."""
    async with async_session_maker() as session:
        result = await session.execute(select(Locker))
        lockers = result.scalars().all()
        return [LockerRead.model_validate(locker) for locker in lockers]


@app.websocket("/ws/lockers")
async def websocket_lockers(websocket: WebSocket):
    """
    WebSocket endpoint for real-time locker updates.
    Clients connect here to receive live updates instead of polling.
    """
    await manager.connect(websocket)
    
    try:
        # Send initial state immediately
        async with async_session_maker() as session:
            result = await session.execute(select(Locker))
            lockers = result.scalars().all()
            lockers_data = [LockerRead.model_validate(l).model_dump() for l in lockers]
            await websocket.send_text(json.dumps(lockers_data))
        
        # Keep connection alive and handle client messages
        while True:
            data = await websocket.receive_text()
            
            # Handle ping/pong for keep-alive
            if data == "ping":
                await websocket.send_text("pong")
            
            # Client can request refresh
            elif data == "refresh":
                async with async_session_maker() as session:
                    result = await session.execute(select(Locker))
                    lockers = result.scalars().all()
                    lockers_data = [LockerRead.model_validate(l).model_dump() for l in lockers]
                    await websocket.send_text(json.dumps(lockers_data))
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        manager.disconnect(websocket)


async def broadcast_locker_update():
    """
    Broadcast locker updates to all connected WebSocket clients.
    Call this function after any locker state change.
    """
    if not manager.active_connections:
        return
    
    try:
        async with async_session_maker() as session:
            result = await session.execute(select(Locker))
            lockers = result.scalars().all()
            lockers_data = [LockerRead.model_validate(l).model_dump() for l in lockers]
            message = json.dumps(lockers_data)
            await manager.broadcast(message)
            print(f"📡 Broadcasted update to {len(manager.active_connections)} clients")
    except Exception as e:
        print(f"❌ Broadcast error: {e}")


@app.post("/api/reset_simulation")
async def reset_simulation() -> dict[str, str]:
    """Reset the simulation by seeding 32 clean lockers."""
    try:
        await seed_lockers()
        return {
            "status": "success",
            "message": "Simulation reset: 96 lockers created across 3 stations",
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset simulation: {exc!r}",
        )


async def _find_locker_by_identifier(session, identifier: str) -> Locker | None:
    """Helper function to find a locker by ID, mac_address, or partial match."""
    locker = None
    
    # Try to find locker by ID first (if identifier is numeric)
    if identifier.isdigit():
        result = await session.execute(
            select(Locker).where(Locker.id == int(identifier))
        )
        locker = result.scalar_one_or_none()
    
    # If not found by ID, try mac_address
    if not locker:
        # Normalize identifier to match mac_address format
        normalized_id = identifier.lower().replace("-", "_")
        if not normalized_id.startswith("locker_"):
            normalized_id = f"locker_{normalized_id}"
        
        result = await session.execute(
            select(Locker).where(Locker.mac_address == normalized_id)
        )
        locker = result.scalar_one_or_none()
    
    # If still not found, try partial match on mac_address
    if not locker:
        result = await session.execute(
            select(Locker).where(Locker.mac_address.contains(identifier.lower()))
        )
        locker = result.scalar_one_or_none()
    
    return locker


@app.post("/api/rent", response_model=dict)
async def rent_locker_body(rent_data: RentStart) -> dict:
    """
    Rent a locker using locker_mac from request body.
    Compatible with frontend that sends { user_id, locker_mac }.
    """
    async with async_session_maker() as session:
        locker = await _find_locker_by_identifier(session, rent_data.locker_mac)
        
        if not locker:
            raise HTTPException(
                status_code=404,
                detail=f"Locker with mac {rent_data.locker_mac} not found",
            )
        
        if locker.is_occupied:
            raise HTTPException(
                status_code=400,
                detail=f"Locker {locker.mac_address} is already occupied",
            )
        
        # Set locker as occupied
        locker.is_occupied = True
        
        # Create a Rent record (simplified for MVP)
        rent = Rent(
            user_id=rent_data.user_id,
            locker_id=locker.id,
            cost=0.0,  # Will be calculated when rent ends
        )
        session.add(rent)
        await session.commit()
        
        return {
            "status": "success",
            "message": f"Locker {locker.mac_address} rented successfully",
            "locker_id": locker.id,
            "rent_id": rent.id,
        }


@app.post("/api/rent/{locker_id}")
async def rent_locker(locker_id: str) -> dict:
    """
    Rent a locker by ID, mac_address, or location_name.
    Sets is_occupied to True, generates access_code, and creates a Rent record.
    """
    # Check system lock
    if SYSTEM_LOCKED:
        raise HTTPException(
            status_code=503,
            detail="System is in emergency lockdown. Rentals are temporarily disabled.",
        )
    
    async with async_session_maker() as session:
        locker = await _find_locker_by_identifier(session, locker_id)
        
        if not locker:
            raise HTTPException(
                status_code=404,
                detail=f"Locker {locker_id} not found",
            )
        
        if locker.is_occupied:
            raise HTTPException(
                status_code=400,
                detail=f"Locker {locker_id} is already occupied",
            )
        
        # Generate unique access code
        access_code = str(uuid.uuid4())
        
        # Set locker as occupied and assign access code
        locker.is_occupied = True
        locker.access_code = access_code
        
        # Create a Rent record (user_id=1 for MVP - in production this would come from auth)
        rent = Rent(
            user_id=1,  # Demo user
            locker_id=locker.id,
            cost=0.0,  # Will be calculated when rent ends
        )
        session.add(rent)
        await session.commit()
        
        # Refresh to get the latest data
        await session.refresh(locker)
        
        return {
            "status": "success",
            "message": f"Locker {locker_id} rented successfully",
            "locker": {
                "id": locker.id,
                "mac_address": locker.mac_address,
                "location_name": locker.location_name,
                "size": locker.size.value,
                "price_per_hour": locker.price_per_hour,
                "is_occupied": locker.is_occupied,
                "access_code": locker.access_code,
            },
            "rent_id": rent.id,
        }


@app.post("/api/release/{locker_id}")
async def release_locker(locker_id: str) -> dict[str, str]:
    """
    Release a locker (set is_occupied to False and clear access_code).
    Also ends the active rent record.
    """
    async with async_session_maker() as session:
        locker = await _find_locker_by_identifier(session, locker_id)
        
        if not locker:
            raise HTTPException(
                status_code=404,
                detail=f"Locker {locker_id} not found",
            )
        
        # Find and end active rent
        result = await session.execute(
            select(Rent).where(
                Rent.locker_id == locker.id,
                Rent.end_time.is_(None),  # Active rent
            )
        )
        active_rent = result.scalar_one_or_none()
        
        if active_rent:
            # Calculate rent duration and cost
            active_rent.end_time = datetime.now(timezone.utc)
            duration_hours = (active_rent.end_time - active_rent.start_time).total_seconds() / 3600
            active_rent.cost = duration_hours * locker.price_per_hour
        
        # Set locker as free and regenerate access_code (for security)
        locker.is_occupied = False
        locker.access_code = str(uuid.uuid4())  # Generate new code for next rent
        
        await session.commit()
        
        # Broadcast update to WebSocket clients
        asyncio.create_task(broadcast_locker_update())
        
        return {
            "status": "success",
            "message": f"Locker {locker_id} released successfully",
        }


@app.post("/api/open/{locker_id}")
async def open_locker(locker_id: str) -> dict[str, str]:
    """
    Publish an MQTT command to open the given locker.
    Checks if the locker exists and is rented by the user (mock check for MVP).
    """
    async with async_session_maker() as session:
        # Find locker by mac_address (locker_id format: "locker_a_01" or "a_01")
        # Normalize locker_id to match our naming convention
        normalized_id = locker_id.lower().replace("-", "_")
        if not normalized_id.startswith("locker_"):
            normalized_id = f"locker_{normalized_id}"
        
        # Query locker
        result = await session.execute(
            select(Locker).where(Locker.mac_address == normalized_id)
        )
        locker = result.scalar_one_or_none()
        
        if not locker:
            raise HTTPException(
                status_code=404,
                detail=f"Locker {locker_id} not found",
            )
        
        # Mock check: Verify locker is occupied (rented)
        # In production, we'd check if the current user has an active rent for this locker
        if not locker.is_occupied:
            raise HTTPException(
                status_code=403,
                detail=f"Locker {locker_id} is not currently rented",
            )
        
        # Mock check: Verify user has access (for MVP, we'll just check if there's an active rent)
        # In production, we'd verify the user_id from the session/token matches the rent
        result = await session.execute(
            select(Rent).where(
                Rent.locker_id == locker.id,
                Rent.end_time.is_(None),  # Active rent (not ended)
            )
        )
        active_rent = result.scalar_one_or_none()
        
        if not active_rent:
            raise HTTPException(
                status_code=403,
                detail=f"No active rental found for locker {locker_id}",
            )
    
    # Publish MQTT command
    topic = f"lockngo/{locker_id}/command"
    payload = "OPEN"
    
    try:
        async with aiomqtt.Client(
            hostname=MQTT_BROKER_HOST,
            port=MQTT_BROKER_PORT,
        ) as client:
            await client.publish(topic, payload)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send command to {locker_id}: {exc!r}",
        )
    
    return {
        "status": "success",
        "message": f"Command sent to {locker_id}",
    }


# ========== ADMIN PANEL ENDPOINTS ==========

@app.get("/api/admin/dashboard")
async def admin_dashboard() -> dict:
    """Admin dashboard with system metrics."""
    async with async_session_maker() as session:
        # Get all lockers
        lockers_result = await session.execute(select(Locker))
        all_lockers = lockers_result.scalars().all()
        
        # Get all rents
        rents_result = await session.execute(select(Rent))
        all_rents = rents_result.scalars().all()
        
        # Calculate metrics
        total_lockers = len(all_lockers)
        occupied_lockers = sum(1 for l in all_lockers if l.is_occupied)
        occupancy_rate = (occupied_lockers / total_lockers * 100) if total_lockers > 0 else 0
        
        # Mock revenue calculation
        total_revenue = sum(r.cost for r in all_rents)
        
        # Mock active incidents
        active_incidents = 0
        
        # Recent transactions (last 10 rents)
        recent_rents = sorted(all_rents, key=lambda r: r.start_time, reverse=True)[:10]
        recent_transactions = [
            {
                "id": r.id,
                "locker_id": r.locker_id,
                "user_id": r.user_id,
                "start_time": r.start_time.isoformat(),
                "cost": r.cost,
            }
            for r in recent_rents
        ]
        
        return {
            "total_revenue": total_revenue,
            "occupancy_rate": round(occupancy_rate, 2),
            "active_incidents": active_incidents,
            "recent_transactions": recent_transactions,
            "total_lockers": total_lockers,
            "occupied_lockers": occupied_lockers,
            "system_locked": SYSTEM_LOCKED,
        }


@app.post("/api/admin/force_open/{locker_id}")
async def admin_force_open(locker_id: str) -> dict[str, str]:
    """Admin force open - bypasses payment checks."""
    async with async_session_maker() as session:
        locker = await _find_locker_by_identifier(session, locker_id)
        
        if not locker:
            raise HTTPException(
                status_code=404,
                detail=f"Locker {locker_id} not found",
            )
    
    # Publish MQTT command with admin flag
    topic = f"lockngo/{locker_id}/command"
    payload = "OPEN_ADMIN"
    
    try:
        async with aiomqtt.Client(
            hostname=MQTT_BROKER_HOST,
            port=MQTT_BROKER_PORT,
        ) as client:
            await client.publish(topic, payload)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send admin command to {locker_id}: {exc!r}",
        )
    
    return {
        "status": "success",
        "message": f"Admin force open command sent to {locker_id}",
    }


@app.post("/api/admin/emergency_stop")
async def admin_emergency_stop() -> dict[str, str]:
    """Emergency stop - locks the entire system."""
    global SYSTEM_LOCKED
    SYSTEM_LOCKED = True
    return {
        "status": "success",
        "message": "System locked. All user rents are now rejected.",
    }


@app.post("/api/admin/emergency_release")
async def admin_emergency_release() -> dict[str, str]:
    """Release emergency stop."""
    global SYSTEM_LOCKED
    SYSTEM_LOCKED = False
    return {
        "status": "success",
        "message": "System unlocked. Normal operations resumed.",
    }


@app.get("/api/admin/stations")
async def admin_get_stations() -> dict:
    """Get all lockers grouped by station with current rental info."""
    async with async_session_maker() as session:
        # Get all lockers
        lockers_result = await session.execute(select(Locker))
        all_lockers = lockers_result.scalars().all()
        
        # Get all active rents
        active_rents_result = await session.execute(
            select(Rent).where(Rent.end_time.is_(None))
        )
        active_rents = {rent.locker_id: rent for rent in active_rents_result.scalars().all()}
        
        # Get all users
        from .models import User
        users_result = await session.execute(select(User))
        users = {user.id: user for user in users_result.scalars().all()}
        
        # Group lockers by station (extract station from location_name)
        stations = {}
        for locker in all_lockers:
            # Extract station name (e.g., "ТЦ Авиапарк" from "ТЦ Авиапарк, 2 этаж")
            station_name = locker.location_name.split(",")[0].strip() if "," in locker.location_name else locker.location_name
            
            if station_name not in stations:
                stations[station_name] = {
                    "name": station_name,
                    "lockers": [],
                    "total_lockers": 0,
                    "occupied": 0,
                    "available": 0,
                }
            
            # Get active rent info if exists
            active_rent = active_rents.get(locker.id)
            renter_info = None
            if active_rent and active_rent.user_id in users:
                user = users[active_rent.user_id]
                renter_info = {
                    "user_id": user.id,
                    "phone": user.phone,
                    "start_time": active_rent.start_time.isoformat(),
                    "rent_id": active_rent.id,
                }
            
            locker_info = {
                "id": locker.id,
                "mac_address": locker.mac_address,
                "location_name": locker.location_name,
                "is_occupied": locker.is_occupied,
                "size": locker.size.value,
                "price_per_hour": locker.price_per_hour,
                "renter": renter_info,
            }
            
            stations[station_name]["lockers"].append(locker_info)
            stations[station_name]["total_lockers"] += 1
            if locker.is_occupied:
                stations[station_name]["occupied"] += 1
            else:
                stations[station_name]["available"] += 1
        
        return {
            "stations": list(stations.values()),
            "total_stations": len(stations),
        }


@app.get("/api/admin/rentals")
async def admin_get_rentals() -> dict:
    """Get detailed information about all rentals (active and completed)."""
    async with async_session_maker() as session:
        # Get all rents
        rents_result = await session.execute(
            select(Rent).order_by(Rent.start_time.desc())
        )
        all_rents = rents_result.scalars().all()
        
        # Get all users
        from .models import User
        users_result = await session.execute(select(User))
        users = {user.id: user for user in users_result.scalars().all()}
        
        # Get all lockers
        lockers_result = await session.execute(select(Locker))
        lockers = {locker.id: locker for locker in lockers_result.scalars().all()}
        
        # Build rental details
        active_rentals = []
        completed_rentals = []
        
        for rent in all_rents:
            user = users.get(rent.user_id)
            locker = lockers.get(rent.locker_id)
            
            if not user or not locker:
                continue
            
            # Calculate duration
            duration_minutes = None
            if rent.end_time:
                delta = rent.end_time - rent.start_time
                duration_minutes = int(delta.total_seconds() / 60)
            else:
                # For active rents, calculate current duration
                delta = datetime.now() - rent.start_time.replace(tzinfo=None)
                duration_minutes = int(delta.total_seconds() / 60)
            
            rental_info = {
                "id": rent.id,
                "user": {
                    "id": user.id,
                    "phone": user.phone,
                    "balance": user.balance,
                },
                "locker": {
                    "id": locker.id,
                    "mac_address": locker.mac_address,
                    "location_name": locker.location_name,
                    "size": locker.size.value,
                    "price_per_hour": locker.price_per_hour,
                },
                "start_time": rent.start_time.isoformat(),
                "end_time": rent.end_time.isoformat() if rent.end_time else None,
                "duration_minutes": duration_minutes,
                "cost": rent.cost,
                "is_active": rent.end_time is None,
            }
            
            if rent.end_time is None:
                active_rentals.append(rental_info)
            else:
                completed_rentals.append(rental_info)
        
        return {
            "active_rentals": active_rentals,
            "completed_rentals": completed_rentals,
            "total_active": len(active_rentals),
            "total_completed": len(completed_rentals),
        }


# ========== USER RENTAL HISTORY ENDPOINTS ==========

@app.get("/api/user/{user_id}/rents")
async def get_user_rents(user_id: int) -> dict:
    """Get all rental history for a specific user (both active and completed)."""
    async with async_session_maker() as session:
        # Get all rents for this user, ordered by most recent first
        result = await session.execute(
            select(Rent)
            .where(Rent.user_id == user_id)
            .order_by(Rent.start_time.desc())
        )
        rents = result.scalars().all()
        
        # Get locker details for each rent
        rent_history = []
        for rent in rents:
            # Fetch the locker details
            locker_result = await session.execute(
                select(Locker).where(Locker.id == rent.locker_id)
            )
            locker = locker_result.scalar_one_or_none()
            
            if locker:
                # Calculate duration if rent is completed
                duration_minutes = None
                if rent.end_time:
                    delta = rent.end_time - rent.start_time
                    duration_minutes = int(delta.total_seconds() / 60)
                
                rent_history.append({
                    "id": rent.id,
                    "locker_id": locker.id,
                    "locker_mac": locker.mac_address,
                    "locker_name": locker.location_name,
                    "locker_size": locker.size.value,
                    "access_code": locker.access_code,
                    "price_per_hour": locker.price_per_hour,
                    "location_name": locker.location_name,
                    "size": locker.size.value,
                    "start_time": rent.start_time.isoformat(),
                    "end_time": rent.end_time.isoformat() if rent.end_time else None,
                    "duration_minutes": duration_minutes,
                    "cost": rent.cost,
                    "is_active": rent.end_time is None,
                })
        
        return {
            "user_id": user_id,
            "total_rents": len(rent_history),
            "active_rents": sum(1 for r in rent_history if r["is_active"]),
            "completed_rents": sum(1 for r in rent_history if not r["is_active"]),
            "rents": rent_history,
        }


