"""
Authentication API for web clients.
Provides user registration, login, and token management.
"""
from datetime import datetime, timedelta
from typing import Optional
import secrets

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional as Opt

from .database import async_session_maker
from .models import User, UserRole

router = APIRouter(prefix="/api/auth", tags=["auth"])

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)

# Simple token storage (в продакшене использовать Redis или БД)
TOKEN_STORAGE: dict[str, dict] = {}


# ========== PYDANTIC MODELS ==========

class UserRegister(BaseModel):
    username: str
    email: Opt[str] = None
    phone: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: Optional[str] = None
    email: Optional[str] = None
    phone: str
    balance: float
    role: str

    class Config:
        from_attributes = True


class RentStartRequest(BaseModel):
    lock_id: int


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class RentStartRequest(BaseModel):
    lock_id: int


# ========== HELPER FUNCTIONS ==========

def generate_token() -> str:
    """Generate a simple token (в продакшене использовать JWT)."""
    return secrets.token_urlsafe(32)


async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> User:
    """Get current user from token."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Проверяем токен в хранилище
    token_data = TOKEN_STORAGE.get(token)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.id == token_data["user_id"])
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        
        return user


# ========== AUTH ENDPOINTS ==========

@router.post("/register", response_model=UserResponse)
async def register(user_data: UserRegister):
    """
    Регистрация нового пользователя.
    """
    async with async_session_maker() as session:
        # Проверяем уникальность телефона
        result = await session.execute(
            select(User).where(User.phone == user_data.phone)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Пользователь с таким телефоном уже существует"
            )
        
        # Создаем нового пользователя
        # В реальном приложении пароль должен быть хеширован
        new_user = User(
            phone=user_data.phone,
            balance=0.0,
            role=UserRole.USER,
            name=user_data.username,
        )
        
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
        
        return UserResponse(
            id=new_user.id,
            username=user_data.username,
            email=user_data.email,
            phone=new_user.phone,
            balance=new_user.balance,
            role=new_user.role.value,
        )


@router.post("/token", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Получение токена для входа (OAuth2 password flow).
    Использует username как phone и password (в демо режиме проверка упрощена).
    """
    async with async_session_maker() as session:
        # Ищем пользователя по телефону (username в форме)
        result = await session.execute(
            select(User).where(User.phone == form_data.username)
        )
        user = result.scalar_one_or_none()
        
        # Если пользователь не найден, создаем демо пользователя
        if not user:
            # В демо режиме создаем пользователя автоматически
            # ID будет сгенерирован автоматически
            user = User(
                phone=form_data.username.strip(),  # Убираем пробелы
                balance=5000.0,  # Стартовый баланс для демо
                role=UserRole.USER,
                name=form_data.username.strip(),
            )
            session.add(user)
            try:
                await session.commit()
                await session.refresh(user)
            except Exception as e:
                await session.rollback()
                # Если ошибка уникальности, попробуем найти пользователя снова
                result = await session.execute(
                    select(User).where(User.phone == form_data.username.strip())
                )
                user = result.scalar_one_or_none()
                if not user:
                    raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")
        
        # Генерируем токен
        token = generate_token()
        TOKEN_STORAGE[token] = {
            "user_id": user.id,
            "created_at": datetime.now(),
        }
        
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=UserResponse(
                id=user.id,
                username=user.name,
                email=None,
                phone=user.phone,
                balance=user.balance,
                role=user.role.value,
            ),
        )


@router.get("/users/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Получить информацию о текущем пользователе.
    """
    return UserResponse(
        id=current_user.id,
        username=current_user.name,
        email=None,
        phone=current_user.phone,
        balance=current_user.balance,
        role=current_user.role.value,
    )


@router.post("/logout")
async def logout(token: str = Depends(oauth2_scheme)):
    """
    Выход из системы (удаление токена).
    """
    if token and token in TOKEN_STORAGE:
        del TOKEN_STORAGE[token]
    return {"status": "success", "message": "Logged out"}


# ========== LOCKER ENDPOINTS ==========

@router.get("/locks")
async def get_locks(current_user: User = Depends(get_current_user)):
    """
    Получить список всех замков.
    """
    from .models import Locker
    from .schemas import LockerRead
    
    async with async_session_maker() as session:
        from sqlalchemy import select
        result = await session.execute(select(Locker))
        lockers = result.scalars().all()
        return [LockerRead.model_validate(locker) for locker in lockers]


@router.get("/locks/{lock_id}")
async def get_lock(lock_id: int, current_user: User = Depends(get_current_user)):
    """
    Получить информацию о конкретном замке.
    """
    from .models import Locker
    from .schemas import LockerRead
    
    async with async_session_maker() as session:
        from sqlalchemy import select
        result = await session.execute(select(Locker).where(Locker.id == lock_id))
        locker = result.scalar_one_or_none()
        
        if not locker:
            raise HTTPException(status_code=404, detail="Lock not found")
        
        return LockerRead.model_validate(locker)


@router.post("/rentals/start")
async def start_rental(request: RentStartRequest, current_user: User = Depends(get_current_user)):
    """
    Начать аренду замка.
    """
    from .models import Locker, Rent
    from datetime import datetime, timezone
    import uuid
    
    async with async_session_maker() as session:
        from sqlalchemy import select
        
        # Найти замок
        result = await session.execute(select(Locker).where(Locker.id == request.lock_id))
        locker = result.scalar_one_or_none()
        
        if not locker:
            raise HTTPException(status_code=404, detail="Lock not found")
        
        if locker.is_occupied:
            raise HTTPException(status_code=400, detail="Lock is already occupied")
        
        # Создать аренду
        rent = Rent(
            user_id=current_user.id,
            locker_id=locker.id,
            start_time=datetime.now(timezone.utc),
            cost=0.0,  # Будет рассчитано при завершении
        )
        
        # Обновить замок
        locker.is_occupied = True
        locker.access_code = str(uuid.uuid4())
        
        session.add(rent)
        await session.commit()
        await session.refresh(rent)
        await session.refresh(locker)
        
        return {
            "id": rent.id,
            "lock_id": rent.locker_id,
            "user_id": rent.user_id,
            "start_time": rent.start_time.isoformat(),
            "status": "active",
            "access_code": locker.access_code,
        }


@router.post("/rentals/{rental_id}/end")
async def end_rental(rental_id: int, current_user: User = Depends(get_current_user)):
    """
    Завершить аренду.
    """
    from .models import Rent, Locker
    from datetime import datetime, timezone
    
    async with async_session_maker() as session:
        from sqlalchemy import select
        
        # Найти аренду
        result = await session.execute(select(Rent).where(Rent.id == rental_id))
        rent = result.scalar_one_or_none()
        
        if not rent:
            raise HTTPException(status_code=404, detail="Rental not found")
        
        if rent.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not your rental")
        
        if rent.end_time:
            raise HTTPException(status_code=400, detail="Rental already ended")
        
        # Найти замок
        result = await session.execute(select(Locker).where(Locker.id == rent.locker_id))
        locker = result.scalar_one_or_none()
        
        # Рассчитать стоимость
        rent.end_time = datetime.now(timezone.utc)
        duration_hours = (rent.end_time - rent.start_time).total_seconds() / 3600
        rent.cost = duration_hours * (locker.price_per_hour if locker else 100.0)
        
        # Обновить баланс пользователя
        if current_user.balance >= rent.cost:
            current_user.balance -= rent.cost
        else:
            # Если недостаточно средств, списываем что есть
            rent.cost = current_user.balance
            current_user.balance = 0.0
        
        # Освободить замок
        if locker:
            locker.is_occupied = False
        
        await session.commit()
        await session.refresh(rent)
        
        return {
            "id": rent.id,
            "lock_id": rent.locker_id,
            "user_id": rent.user_id,
            "start_time": rent.start_time.isoformat(),
            "end_time": rent.end_time.isoformat(),
            "total_cost": rent.cost,
            "status": "completed",
        }


@router.get("/rentals/active")
async def get_active_rental(current_user: User = Depends(get_current_user)):
    """
    Получить активную аренду текущего пользователя.
    """
    from .models import Rent
    from datetime import timezone
    
    async with async_session_maker() as session:
        from sqlalchemy import select
        
        result = await session.execute(
            select(Rent).where(
                Rent.user_id == current_user.id,
                Rent.end_time.is_(None)
            )
        )
        rent = result.scalar_one_or_none()
        
        if not rent:
            raise HTTPException(status_code=404, detail="No active rental")
        
        return {
            "id": rent.id,
            "lock_id": rent.locker_id,
            "user_id": rent.user_id,
            "start_time": rent.start_time.isoformat(),
            "status": "active",
        }


@router.get("/rentals/history")
async def get_rental_history(current_user: User = Depends(get_current_user)):
    """
    Получить историю аренд текущего пользователя.
    """
    from .models import Rent
    
    async with async_session_maker() as session:
        from sqlalchemy import select, desc
        
        result = await session.execute(
            select(Rent)
            .where(Rent.user_id == current_user.id)
            .order_by(desc(Rent.start_time))
        )
        rents = result.scalars().all()
        
        return [
            {
                "id": rent.id,
                "lock_id": rent.locker_id,
                "user_id": rent.user_id,
                "start_time": rent.start_time.isoformat(),
                "end_time": rent.end_time.isoformat() if rent.end_time else None,
                "total_cost": rent.cost,
                "cost": rent.cost,
                "status": "completed" if rent.end_time else "active",
                "duration_minutes": int((rent.end_time - rent.start_time).total_seconds() / 60) if rent.end_time else None,
            }
            for rent in rents
        ]

