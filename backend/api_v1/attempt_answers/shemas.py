from pydantic import BaseModel, ConfigDict


class AttemptAnswerBase(BaseModel):
    attempt_id: int
    question_id: int
    user_answer: str
    is_correct: bool


class AttemptAnswerCreate(AttemptAnswerBase):
    pass


class AttemptAnswerUpdate(AttemptAnswerBase):
    pass


class AttemptAnswerUpdatePartial(BaseModel):
    attempt_id: int | None = None
    question_id: int | None = None
    user_answer: str | None = None
    is_correct: bool | None = None


class AttemptAnswerRead(AttemptAnswerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
