"""Database seeder to populate lockers for production simulation."""

import uuid

from sqlalchemy import delete, select

from .database import async_session_maker
from .models import Locker, LockerSize, User


async def seed_lockers():
    """
    Clear existing lockers and create 96 lockers across 3 stations in Moscow.
    
    Stations:
    - ТЦ Авиапарк (32 ячейки)
    - ТЦ Метрополис (32 ячейки)
    - ТЦ Афимолл (32 ячейки)
    
    Each station has:
    - 16 Small (S) lockers - 100₽/час
    - 10 Medium (M) lockers - 150₽/час
    - 6 Large (L) lockers - 250₽/час
    """
    async with async_session_maker() as session:
        # Clear existing lockers
        result = await session.execute(delete(Locker))
        await session.commit()
        print(f"Cleared {result.rowcount} existing lockers")
        
        lockers_to_create = []
        
        # Define 3 stations
        stations = [
            {"name": "ТЦ Авиапарк", "floor": "2 этаж", "zone": "Food Court", "prefix": "AV"},
            {"name": "ТЦ Метрополис", "floor": "1 этаж", "zone": "Главный вход", "prefix": "MT"},
            {"name": "ТЦ Афимолл", "floor": "3 этаж", "zone": "Зона отдыха", "prefix": "AF"}
        ]
        
        # Create lockers for each station
        for station in stations:
            location_full = f"{station['name']}, {station['floor']}"
            
            # Small lockers (16 per station) - A-01 to B-08
            for i in range(1, 9):
                locker_name = f"{station['prefix']}-A{i:02d}"
                lockers_to_create.append(
                    Locker(
                        mac_address=f"locker_{locker_name.lower().replace('-', '_')}",
                        location_name=location_full,
                        is_occupied=False,
                        size=LockerSize.SMALL,
                        price_per_hour=100.0,
                        access_code=str(uuid.uuid4()),
                    )
                )
            
            for i in range(1, 9):
                locker_name = f"{station['prefix']}-B{i:02d}"
                lockers_to_create.append(
                    Locker(
                        mac_address=f"locker_{locker_name.lower().replace('-', '_')}",
                        location_name=location_full,
                        is_occupied=False,
                        size=LockerSize.SMALL,
                        price_per_hour=100.0,
                        access_code=str(uuid.uuid4()),
                    )
                )
            
            # Medium lockers (10 per station) - C-01 to C-10
            for i in range(1, 11):
                locker_name = f"{station['prefix']}-C{i:02d}"
                lockers_to_create.append(
                    Locker(
                        mac_address=f"locker_{locker_name.lower().replace('-', '_')}",
                        location_name=location_full,
                        is_occupied=False,
                        size=LockerSize.MEDIUM,
                        price_per_hour=150.0,
                        access_code=str(uuid.uuid4()),
                    )
                )
            
            # Large lockers (6 per station) - D-01 to D-06
            for i in range(1, 7):
                locker_name = f"{station['prefix']}-D{i:02d}"
                lockers_to_create.append(
                    Locker(
                        mac_address=f"locker_{locker_name.lower().replace('-', '_')}",
                        location_name=location_full,
                        is_occupied=False,
                        size=LockerSize.LARGE,
                        price_per_hour=250.0,
                        access_code=str(uuid.uuid4()),
                    )
                )
        
        # Add all lockers to session
        session.add_all(lockers_to_create)
        await session.commit()
        
        print(f"✅ Created {len(lockers_to_create)} lockers across 3 stations:")
        print(f"   📍 ТЦ Авиапарк - 32 ячейки")
        print(f"   📍 ТЦ Метрополис - 32 ячейки")
        print(f"   📍 ТЦ Афимолл - 32 ячейки")
        print(f"   Итого на каждой станции:")
        print(f"   - 16 Small (S) at 100₽/час")
        print(f"   - 10 Medium (M) at 150₽/час")
        print(f"   - 6 Large (L) at 250₽/час")
        
        # Ensure demo user exists (for simulation/testing)
        result = await session.execute(select(User).where(User.id == 1))
        demo_user = result.scalar_one_or_none()
        
        if not demo_user:
            demo_user = User(
                id=1,
                phone="+79990000000",
                balance=5000.0,
            )
            session.add(demo_user)
            await session.commit()
            print("✅ Created demo user (id=1, phone=+79990000000, balance=5000.0)")
        else:
            print(f"ℹ️  Demo user already exists (id=1, phone={demo_user.phone})")

