from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserBase(BaseModel):
    email: str
    active: bool


class UserCreate(UserBase):
    hashed_password: str


class UserUpdate(UserBase):
    hashed_password: str


class UserUpdatePartial(BaseModel):
    email: str | None = None
    hashed_password: str | None = None


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
