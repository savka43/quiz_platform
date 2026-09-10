from pydantic import BaseModel, ConfigDict


class AttemptAnswerBase(BaseModel):
    attempt_id: int
    question_id: int
    user_answer: str
    is_correct: bool


class AttemptAnswerCreate(AttemptAnswerBase):
    model_config = ConfigDict(extra="forbid")
    pass


class AttemptAnswerUpdate(AttemptAnswerBase):
    model_config = ConfigDict(extra="forbid")
    pass


class AttemptAnswerUpdatePartial(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attempt_id: int | None = None
    question_id: int | None = None
    user_answer: str | None = None
    is_correct: bool | None = None


class AttemptAnswerRead(AttemptAnswerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
