from datetime import datetime
import enum

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class LockerSize(str, enum.Enum):
    """Locker size enumeration."""
    SMALL = "S"
    MEDIUM = "M"
    LARGE = "L"


class LockerStatus(str, enum.Enum):
    """Locker operational status."""
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"
    BROKEN = "broken"


class EventType(str, enum.Enum):
    """Event types for audit log."""
    RENT_START = "rent_start"
    RENT_END = "rent_end"
    LOCKER_OPEN = "locker_open"
    LOCKER_MAINTENANCE = "locker_maintenance"
    USER_BLOCKED = "user_blocked"
    USER_UNBLOCKED = "user_unblocked"
    BALANCE_ADDED = "balance_added"
    EMERGENCY_STOP = "emergency_stop"
    PRICE_CHANGED = "price_changed"
    SYSTEM_ERROR = "system_error"


class UserRole(str, enum.Enum):
    """User roles for access control."""
    SUPER_ADMIN = "super_admin"  # Полный доступ ко всему
    MANAGER = "manager"          # Просмотр + инциденты
    TECHNICIAN = "technician"    # Только инциденты
    ACCOUNTANT = "accountant"    # Только финансы
    USER = "user"                # Обычный пользователь (не админ)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    phone: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    balance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    discount_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_rentals: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Role for access control
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole),
        default=UserRole.USER,
        nullable=False
    )
    name: Mapped[str | None] = mapped_column(String, nullable=True)  # Full name for staff
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    rents: Mapped[list["Rent"]] = relationship(back_populates="user")


class Locker(Base):
    __tablename__ = "lockers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    mac_address: Mapped[str] = mapped_column(
        String,
        unique=True,
        index=True,
        nullable=False,
    )
    location_name: Mapped[str] = mapped_column(String, nullable=False)
    is_occupied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[LockerStatus] = mapped_column(
        Enum(LockerStatus), 
        default=LockerStatus.ACTIVE, 
        nullable=False
    )
    size: Mapped[LockerSize] = mapped_column(Enum(LockerSize), nullable=False)
    price_per_hour: Mapped[float] = mapped_column(Float, nullable=False)
    access_code: Mapped[str | None] = mapped_column(String, nullable=True)
    battery_level: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-100
    last_maintenance: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_uses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    rents: Mapped[list["Rent"]] = relationship(back_populates="locker")


class Rent(Base):
    __tablename__ = "rents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    locker_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("lockers.id", ondelete="CASCADE"),
        nullable=False,
    )

    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    discount_applied: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship(back_populates="rents")
    locker: Mapped[Locker] = relationship(back_populates="rents")


class MaintenanceLog(Base):
    __tablename__ = "maintenance_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    locker_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("lockers.id", ondelete="CASCADE"),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    performed_by: Mapped[str | None] = mapped_column(String, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_type: Mapped[EventType] = mapped_column(Enum(EventType), nullable=False)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    locker_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    extra_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class RuleType(str, enum.Enum):
    """Pricing rule type."""
    HOURLY = "hourly"  # По часам (пиковые/непопулярные)
    SEASONAL = "seasonal"  # Сезонные (даты)
    DAY_OF_WEEK = "day_of_week"  # По дням недели
    DURATION = "duration"  # По длительности аренды


class IncidentType(str, enum.Enum):
    """Incident types."""
    WONT_OPEN = "wont_open"
    WONT_CLOSE = "wont_close"
    DAMAGED = "damaged"
    LOCK_PROBLEM = "lock_problem"
    OTHER = "other"


class IncidentStatus(str, enum.Enum):
    """Incident status."""
    NEW = "new"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class IncidentPriority(str, enum.Enum):
    """Incident priority."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ShiftStatus(str, enum.Enum):
    """Shift status."""
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskStatus(str, enum.Enum):
    """Task status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class PricingRule(Base):
    """Правила динамического ценообразования."""
    __tablename__ = "pricing_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)  # Название правила
    rule_type: Mapped[RuleType] = mapped_column(Enum(RuleType), nullable=False)
    
    # Множитель цены (1.5 = +50%, 0.8 = -20%)
    price_multiplier: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Для hourly: начальный и конечный час (0-23)
    start_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Для seasonal: даты начала и конца
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Для day_of_week: JSON массив дней [0=пн, 6=вс]
    days_of_week: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: [0,6]
    
    # Размеры ячеек (JSON массив или null для всех)
    locker_sizes: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: ["S","M"]
    
    # Приоритет (чем больше, тем выше)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Incident(Base):
    """Инциденты с ячейками."""
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    locker_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("lockers.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    rent_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("rents.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    incident_type: Mapped[IncidentType] = mapped_column(Enum(IncidentType), nullable=False)
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus),
        default=IncidentStatus.NEW,
        nullable=False
    )
    priority: Mapped[IncidentPriority] = mapped_column(
        Enum(IncidentPriority),
        default=IncidentPriority.MEDIUM,
        nullable=False
    )
    
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)  # Решение
    
    reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    assigned_to: Mapped[str | None] = mapped_column(String, nullable=True)  # Ответственный админ
    resolved_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Кто решил
    
    # Автоблокировка ячейки при создании инцидента
    auto_block_locker: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Shift(Base):
    """Рабочие смены персонала."""
    __tablename__ = "shifts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    status: Mapped[ShiftStatus] = mapped_column(
        Enum(ShiftStatus),
        default=ShiftStatus.ACTIVE,
        nullable=False
    )
    
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    station: Mapped[str | None] = mapped_column(String, nullable=True)  # На какой станции
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # Заметки


class Task(Base):
    """Задачи и чек-листы для персонала."""
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    shift_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("shifts.id", ondelete="CASCADE"),
        nullable=True,
    )
    assigned_to_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_type: Mapped[str] = mapped_column(String, nullable=False)  # "check", "clean", "repair", etc.
    
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus),
        default=TaskStatus.PENDING,
        nullable=False
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    locker_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("lockers.id", ondelete="CASCADE"),
        nullable=True,
    )  # Если задача связана с конкретной ячейкой


class SecurityEventType(str, enum.Enum):
    """Security event types for external systems."""
    EMERGENCY_OPEN = "emergency_open"  # Аварийное открытие всех ячеек
    INCIDENT_CRITICAL = "incident_critical"  # Критический инцидент
    LOCKER_FORCED_OPEN = "locker_forced_open"  # Принудительное открытие
    SYSTEM_LOCKED = "system_locked"  # Система заблокирована
    SYSTEM_UNLOCKED = "system_unlocked"  # Система разблокирована
    SUSPICIOUS_ACTIVITY = "suspicious_activity"  # Подозрительная активность
    MULTIPLE_FAILED_ATTEMPTS = "multiple_failed_attempts"  # Множественные неудачные попытки
    OFFLINE_ALERT = "offline_alert"  # Множественные ячейки оффлайн
    FIRE_ALARM = "fire_alarm"  # Пожарная тревога
    EVACUATION = "evacuation"  # Эвакуация


class SecurityWebhook(Base):
    """Webhooks для интеграции с системами безопасности банков/ТРЦ."""
    __tablename__ = "security_webhooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization: Mapped[str] = mapped_column(String, nullable=False)  # "Сбербанк", "ТРЦ Авиапарк"
    webhook_url: Mapped[str] = mapped_column(String, nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String, nullable=False)  # Хэш API ключа
    
    # JSON массив событий ["emergency_open", "incident_critical"]
    events: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Дополнительные настройки
    contact_person: Mapped[str | None] = mapped_column(String, nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String, nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String, nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_triggered: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class SecurityEvent(Base):
    """Журнал событий безопасности для СБ."""
    __tablename__ = "security_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_type: Mapped[SecurityEventType] = mapped_column(
        Enum(SecurityEventType),
        nullable=False,
        index=True
    )
    
    severity: Mapped[str] = mapped_column(String, nullable=False)  # "low", "medium", "high", "critical"
    location: Mapped[str] = mapped_column(String, nullable=False)  # Локация события
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Связанные сущности
    locker_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    incident_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Дополнительные данные (JSON)
    extra_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Был ли отправлен в внешние системы
    notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notification_status: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: статусы отправки
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
