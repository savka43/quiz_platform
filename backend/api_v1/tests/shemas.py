from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TestBase(BaseModel):
    title: str


class TestCreate(TestBase):
    pass


class TestUpdate(TestBase):
    pass


class TestUpdatePartial(BaseModel):
    title: str | None = None


class TestRead(TestBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    user_id: int
