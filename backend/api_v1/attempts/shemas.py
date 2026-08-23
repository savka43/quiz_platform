from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AttemptBase(BaseModel):
    user_id: int
    test_id: int


class AttemptCreate(AttemptBase):
    pass


class AttemptUpdate(AttemptBase):
    finished_at: datetime | None = None


class AttemptUpdatePartial(BaseModel):
    user_id: int | None = None
    test_id: int | None = None
    finished_at: datetime | None = None


class AttemptRead(AttemptBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime
    finished_at: datetime | None
