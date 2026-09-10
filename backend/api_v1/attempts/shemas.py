from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AttemptBase(BaseModel):
    user_id: int
    test_id: int


class AttemptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    test_id: int


class AttemptUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    finished_at: datetime | None = None


class AttemptUpdatePartial(BaseModel):
    model_config = ConfigDict(extra="forbid")
    test_id: int | None = None
    finished_at: datetime | None = None


class AttemptRead(AttemptBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime
    finished_at: datetime | None
