from pydantic import BaseModel
from typing import Optional


class LockerBase(BaseModel):
    location_name: str
    mac_address: str
    size: str
    price_per_hour: float


class LockerRead(LockerBase):
    id: int
    is_occupied: bool
    access_code: Optional[str] = None

    class Config:
        from_attributes = True
        use_enum_values = True


class RentStart(BaseModel):
    """Request model for starting a rent."""
    user_id: int
    locker_mac: str
