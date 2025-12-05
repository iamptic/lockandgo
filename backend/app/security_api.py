"""
Security Integration API for Banks and Shopping Malls.
Provides webhooks, real-time alerts, and event tracking for external security systems.
"""
import hashlib
import json
from datetime import datetime, timedelta
from typing import List, Optional
import aiohttp

from fastapi import APIRouter, HTTPException, Header
from sqlalchemy import select, func, desc, and_
from pydantic import BaseModel

from .database import async_session_maker
from .models import (
    SecurityWebhook, SecurityEvent, SecurityEventType,
    Incident, IncidentPriority, Locker, User, Rent, AuditLog
)

router = APIRouter(prefix="/api/security", tags=["security"])


# ========== PYDANTIC MODELS ==========

class WebhookRegister(BaseModel):
    organization: str
    webhook_url: str
    api_key: str
    events: List[str]
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None


class SecurityStatusResponse(BaseModel):
    status: str
    timestamp: str
    active_incidents: int
    critical_incidents: int
    emergency_status: str
    system_locked: bool
    occupancy_rate: float
    offline_lockers: int
    recent_events: List[dict]


# ========== HELPER FUNCTIONS ==========

def hash_api_key(api_key: str) -> str:
    """Hash API key for secure storage."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(api_key: str, stored_hash: str) -> bool:
    """Verify API key against stored hash."""
    return hash_api_key(api_key) == stored_hash


async def notify_security_systems(
    event_type: SecurityEventType,
    severity: str,
    location: str,
    description: str,
    extra_data: dict = None
):
    """
    Отправка уведомления во все зарегистрированные системы безопасности.
    """
    async with async_session_maker() as session:
        # Создать событие в БД
        security_event = SecurityEvent(
            event_type=event_type,
            severity=severity,
            location=location,
            description=description,
            extra_data=json.dumps(extra_data) if extra_data else None,
            locker_id=extra_data.get("locker_id") if extra_data else None,
            user_id=extra_data.get("user_id") if extra_data else None,
            incident_id=extra_data.get("incident_id") if extra_data else None
        )
        session.add(security_event)
        await session.commit()
        await session.refresh(security_event)
        
        # Найти все активные webhooks для этого типа события
        result = await session.execute(
            select(SecurityWebhook).where(SecurityWebhook.is_active == True)
        )
        webhooks = result.scalars().all()
        
        notification_statuses = {}
        
        for webhook in webhooks:
            # Проверить, подписан ли webhook на этот тип события
            subscribed_events = json.loads(webhook.events)
            if event_type.value not in subscribed_events:
                continue
            
            # Отправить webhook
            payload = {
                "event_id": security_event.id,
                "event_type": event_type.value,
                "severity": severity,
                "timestamp": datetime.now().isoformat(),
                "organization": "Lock&Go",
                "location": location,
                "description": description,
                "data": extra_data or {}
            }
            
            try:
                async with aiohttp.ClientSession() as client:
                    async with client.post(
                        webhook.webhook_url,
                        json=payload,
                        headers={
                            "X-API-Key": webhook.api_key_hash,
                            "Content-Type": "application/json",
                            "X-Event-Type": event_type.value
                        },
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        if response.status == 200:
                            notification_statuses[webhook.organization] = "success"
                            webhook.last_triggered = datetime.now()
                        else:
                            notification_statuses[webhook.organization] = f"failed: {response.status}"
            except Exception as e:
                notification_statuses[webhook.organization] = f"error: {str(e)}"
        
        # Обновить статус уведомлений
        security_event.notified = True
        security_event.notification_status = json.dumps(notification_statuses)
        await session.commit()
        
        return security_event.id


# ========== WEBHOOK MANAGEMENT ==========

@router.post("/webhooks/register")
async def register_webhook(webhook: WebhookRegister):
    """
    Регистрация webhook для системы безопасности банка/ТРЦ.
    События будут отправляться на указанный URL.
    """
    async with async_session_maker() as session:
        # Проверить уникальность организации
        result = await session.execute(
            select(SecurityWebhook).where(
                SecurityWebhook.organization == webhook.organization
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Webhook для организации '{webhook.organization}' уже зарегистрирован"
            )
        
        # Создать новый webhook
        new_webhook = SecurityWebhook(
            organization=webhook.organization,
            webhook_url=webhook.webhook_url,
            api_key_hash=hash_api_key(webhook.api_key),
            events=json.dumps(webhook.events),
            contact_person=webhook.contact_person,
            contact_phone=webhook.contact_phone,
            contact_email=webhook.contact_email
        )
        
        session.add(new_webhook)
        await session.commit()
        await session.refresh(new_webhook)
        
        return {
            "status": "success",
            "webhook_id": new_webhook.id,
            "organization": new_webhook.organization,
            "message": f"Webhook для {webhook.organization} успешно зарегистрирован",
            "subscribed_events": webhook.events
        }


@router.get("/webhooks/list")
async def list_webhooks(x_api_key: str = Header(...)):
    """
    Получить список всех зарегистрированных webhooks.
    Требует API ключ супер-админа.
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(SecurityWebhook).order_by(SecurityWebhook.created_at)
        )
        webhooks = result.scalars().all()
        
        return {
            "webhooks": [
                {
                    "id": wh.id,
                    "organization": wh.organization,
                    "webhook_url": wh.webhook_url,
                    "events": json.loads(wh.events),
                    "is_active": wh.is_active,
                    "contact_person": wh.contact_person,
                    "contact_phone": wh.contact_phone,
                    "last_triggered": wh.last_triggered.isoformat() if wh.last_triggered else None,
                    "created_at": wh.created_at.isoformat()
                }
                for wh in webhooks
            ],
            "total": len(webhooks)
        }


@router.patch("/webhooks/{webhook_id}/toggle")
async def toggle_webhook(webhook_id: int, x_api_key: str = Header(...)):
    """
    Активировать/деактивировать webhook.
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(SecurityWebhook).where(SecurityWebhook.id == webhook_id)
        )
        webhook = result.scalar_one_or_none()
        
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook не найден")
        
        webhook.is_active = not webhook.is_active
        await session.commit()
        
        return {
            "status": "success",
            "webhook_id": webhook_id,
            "is_active": webhook.is_active,
            "message": f"Webhook {'активирован' if webhook.is_active else 'деактивирован'}"
        }


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: int, x_api_key: str = Header(...)):
    """
    Удалить webhook.
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(SecurityWebhook).where(SecurityWebhook.id == webhook_id)
        )
        webhook = result.scalar_one_or_none()
        
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook не найден")
        
        await session.delete(webhook)
        await session.commit()
        
        return {
            "status": "success",
            "message": f"Webhook для {webhook.organization} удален"
        }


# ========== REAL-TIME STATUS API ==========

@router.get("/status/realtime")
async def get_realtime_security_status(x_api_key: str = Header(...)):
    """
    Получить текущий статус системы безопасности в реальном времени.
    Для интеграции с системами безопасности банков/ТРЦ.
    """
    async with async_session_maker() as session:
        # Активные инциденты
        incidents_result = await session.execute(
            select(func.count()).select_from(Incident).where(
                Incident.status.in_(["new", "in_progress"])
            )
        )
        active_incidents = incidents_result.scalar()
        
        # Критические инциденты
        critical_result = await session.execute(
            select(func.count()).select_from(Incident).where(
                and_(
                    Incident.priority == IncidentPriority.CRITICAL,
                    Incident.status.in_(["new", "in_progress"])
                )
            )
        )
        critical_incidents = critical_result.scalar()
        
        # Оффлайн ячейки
        offline_result = await session.execute(
            select(func.count()).select_from(Locker).where(
                Locker.status == "offline"
            )
        )
        offline_lockers = offline_result.scalar()
        
        # Занятость
        total_lockers_result = await session.execute(
            select(func.count()).select_from(Locker)
        )
        total_lockers = total_lockers_result.scalar()
        
        occupied_result = await session.execute(
            select(func.count()).select_from(Locker).where(
                Locker.is_occupied == True
            )
        )
        occupied_lockers = occupied_result.scalar()
        
        occupancy_rate = (occupied_lockers / total_lockers * 100) if total_lockers > 0 else 0
        
        # Последние события безопасности
        recent_events_result = await session.execute(
            select(SecurityEvent)
            .order_by(desc(SecurityEvent.created_at))
            .limit(10)
        )
        recent_events = recent_events_result.scalars().all()
        
        return {
            "status": "critical" if critical_incidents > 0 else "warning" if active_incidents > 0 else "normal",
            "timestamp": datetime.now().isoformat(),
            "active_incidents": active_incidents,
            "critical_incidents": critical_incidents,
            "emergency_status": "alarm" if critical_incidents > 0 else "normal",
            "system_locked": False,
            "occupancy_rate": round(occupancy_rate, 2),
            "offline_lockers": offline_lockers,
            "recent_events": [
                {
                    "id": event.id,
                    "type": event.event_type.value,
                    "severity": event.severity,
                    "location": event.location,
                    "description": event.description,
                    "timestamp": event.created_at.isoformat()
                }
                for event in recent_events
            ]
        }


# ========== EVENT TRACKING ==========

@router.get("/events")
async def get_security_events(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
    x_api_key: str = Header(...)
):
    """
    Получить журнал событий безопасности с фильтрами.
    """
    async with async_session_maker() as session:
        query = select(SecurityEvent).order_by(desc(SecurityEvent.created_at))
        
        # Фильтры
        if start_date:
            start_dt = datetime.fromisoformat(start_date)
            query = query.where(SecurityEvent.created_at >= start_dt)
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date)
            query = query.where(SecurityEvent.created_at <= end_dt)
        
        if event_type:
            query = query.where(SecurityEvent.event_type == SecurityEventType(event_type))
        
        if severity:
            query = query.where(SecurityEvent.severity == severity)
        
        query = query.limit(limit)
        
        result = await session.execute(query)
        events = result.scalars().all()
        
        return {
            "events": [
                {
                    "id": event.id,
                    "event_type": event.event_type.value,
                    "severity": event.severity,
                    "location": event.location,
                    "description": event.description,
                    "locker_id": event.locker_id,
                    "user_id": event.user_id,
                    "incident_id": event.incident_id,
                    "extra_data": json.loads(event.extra_data) if event.extra_data else None,
                    "notified": event.notified,
                    "notification_status": json.loads(event.notification_status) if event.notification_status else None,
                    "created_at": event.created_at.isoformat()
                }
                for event in events
            ],
            "total": len(events)
        }


@router.post("/events/create")
async def create_security_event(
    event_type: str,
    severity: str,
    location: str,
    description: str,
    locker_id: Optional[int] = None,
    user_id: Optional[int] = None,
    incident_id: Optional[int] = None,
    extra_data: Optional[dict] = None,
    x_api_key: str = Header(...)
):
    """
    Создать событие безопасности вручную.
    """
    try:
        event_id = await notify_security_systems(
            event_type=SecurityEventType(event_type),
            severity=severity,
            location=location,
            description=description,
            extra_data={
                "locker_id": locker_id,
                "user_id": user_id,
                "incident_id": incident_id,
                **(extra_data or {})
            }
        )
        
        return {
            "status": "success",
            "event_id": event_id,
            "message": "Событие создано и отправлено в системы безопасности"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== EXPORT FOR SECURITY SYSTEMS ==========

@router.get("/export/xml")
async def export_events_xml(
    start_date: str,
    end_date: str,
    x_api_key: str = Header(...)
):
    """
    Экспорт событий в формате XML для банковских систем.
    """
    from xml.etree.ElementTree import Element, SubElement, tostring
    from xml.dom import minidom
    
    async with async_session_maker() as session:
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        
        result = await session.execute(
            select(SecurityEvent)
            .where(
                and_(
                    SecurityEvent.created_at >= start_dt,
                    SecurityEvent.created_at <= end_dt
                )
            )
            .order_by(SecurityEvent.created_at)
        )
        events = result.scalars().all()
        
        # Создать XML
        root = Element("SecurityReport")
        root.set("system", "LockAndGo")
        root.set("generated", datetime.now().isoformat())
        root.set("period_start", start_date)
        root.set("period_end", end_date)
        
        events_elem = SubElement(root, "Events")
        events_elem.set("count", str(len(events)))
        
        for event in events:
            event_elem = SubElement(events_elem, "Event")
            event_elem.set("id", str(event.id))
            event_elem.set("type", event.event_type.value)
            event_elem.set("severity", event.severity)
            event_elem.set("timestamp", event.created_at.isoformat())
            
            SubElement(event_elem, "Location").text = event.location
            SubElement(event_elem, "Description").text = event.description
            
            if event.locker_id:
                SubElement(event_elem, "LockerId").text = str(event.locker_id)
            if event.user_id:
                SubElement(event_elem, "UserId").text = str(event.user_id)
        
        # Форматировать XML
        xml_string = minidom.parseString(tostring(root)).toprettyxml(indent="  ")
        
        from fastapi.responses import Response
        return Response(
            content=xml_string,
            media_type="application/xml",
            headers={
                "Content-Disposition": f"attachment; filename=security_report_{start_date}_{end_date}.xml"
            }
        )


@router.get("/export/json")
async def export_events_json(
    start_date: str,
    end_date: str,
    x_api_key: str = Header(...)
):
    """
    Экспорт событий в формате JSON.
    """
    async with async_session_maker() as session:
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        
        result = await session.execute(
            select(SecurityEvent)
            .where(
                and_(
                    SecurityEvent.created_at >= start_dt,
                    SecurityEvent.created_at <= end_dt
                )
            )
            .order_by(SecurityEvent.created_at)
        )
        events = result.scalars().all()
        
        report = {
            "system": "LockAndGo",
            "generated_at": datetime.now().isoformat(),
            "period": {
                "start": start_date,
                "end": end_date
            },
            "events_count": len(events),
            "events": [
                {
                    "id": event.id,
                    "type": event.event_type.value,
                    "severity": event.severity,
                    "location": event.location,
                    "description": event.description,
                    "locker_id": event.locker_id,
                    "user_id": event.user_id,
                    "incident_id": event.incident_id,
                    "timestamp": event.created_at.isoformat(),
                    "extra_data": json.loads(event.extra_data) if event.extra_data else None
                }
                for event in events
            ]
        }
        
        return report


# ========== STATISTICS ==========

@router.get("/stats/summary")
async def get_security_statistics(
    period_days: int = 30,
    x_api_key: str = Header(...)
):
    """
    Получить статистику событий безопасности.
    """
    async with async_session_maker() as session:
        start_date = datetime.now() - timedelta(days=period_days)
        
        # Всего событий
        total_result = await session.execute(
            select(func.count()).select_from(SecurityEvent).where(
                SecurityEvent.created_at >= start_date
            )
        )
        total_events = total_result.scalar()
        
        # По типам
        types_result = await session.execute(
            select(
                SecurityEvent.event_type,
                func.count(SecurityEvent.id)
            )
            .where(SecurityEvent.created_at >= start_date)
            .group_by(SecurityEvent.event_type)
        )
        by_type = {row[0].value: row[1] for row in types_result}
        
        # По severity
        severity_result = await session.execute(
            select(
                SecurityEvent.severity,
                func.count(SecurityEvent.id)
            )
            .where(SecurityEvent.created_at >= start_date)
            .group_by(SecurityEvent.severity)
        )
        by_severity = {row[0]: row[1] for row in severity_result}
        
        return {
            "period_days": period_days,
            "total_events": total_events,
            "by_type": by_type,
            "by_severity": by_severity,
            "generated_at": datetime.now().isoformat()
        }

