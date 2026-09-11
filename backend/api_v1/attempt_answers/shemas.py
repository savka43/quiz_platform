from pydantic import BaseModel, ConfigDict, Field
from api_v1.practice.schemas import AnswerInput


class AttemptAnswerCreate(AnswerInput):
    attempt_id: int = Field(gt=0)


class AttemptAnswerUpdatePartial(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_answer: str = Field(default="", max_length=20000)
    selected_option_ids: list[int] = Field(default_factory=list, max_length=100)
    blank_answers: list[str] = Field(default_factory=list, max_length=100)


class AttemptAnswerUpdate(AttemptAnswerUpdatePartial):
    pass


class AttemptAnswerRead(BaseModel):
    id: int
    attempt_id: int
    question_id: int | None
    attempt_question_id: int | None
    user_answer: str
    selected_option_ids: list[int]
    blank_answers: list[str]
    is_correct: bool | None
