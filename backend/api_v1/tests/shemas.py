from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TestBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=20000)


class TestCreate(TestBase):
    model_config = ConfigDict(extra="forbid")


class TestUpdate(TestBase):
    model_config = ConfigDict(extra="forbid")
    pass


class TestUpdatePartial(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=20000)


class TestRead(TestBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    user_id: int
