from pydantic import BaseModel, ConfigDict


class QuestionBase(BaseModel):
    test_id: int
    text: str
    correct_answer: str


class QuestionCreate(QuestionBase):
    model_config = ConfigDict(extra="forbid")
    pass


class QuestionUpdate(QuestionBase):
    model_config = ConfigDict(extra="forbid")
    pass


class QuestionUpdatePartial(BaseModel):
    model_config = ConfigDict(extra="forbid")
    test_id: int | None = None
    text: str | None = None
    correct_answer: str | None = None


class QuestionRead(QuestionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
