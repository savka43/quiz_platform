from pydantic import BaseModel, ConfigDict


class QuestionBase(BaseModel):
    test_id: int
    text: str
    correct_answer: str


class QuestionCreate(QuestionBase):
    pass


class QuestionUpdate(QuestionBase):
    pass


class QuestionUpdatePartial(BaseModel):
    test_id: int | None = None
    text: str | None = None
    correct_answer: str | None = None


class QuestionRead(QuestionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
