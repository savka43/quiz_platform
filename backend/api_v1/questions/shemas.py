from pydantic import BaseModel, ConfigDict, Field
from api_v1.editor.schemas import QuestionInput, OptionInput, BlankInput, QuestionType


class QuestionCreate(QuestionInput):
    test_id: int = Field(gt=0)


class QuestionUpdate(QuestionCreate):
    pass


class QuestionUpdatePartial(BaseModel):
    model_config = ConfigDict(extra="forbid")
    test_id: int | None = None
    text: str | None = None
    correct_answer: str | None = None
    question_type: QuestionType | None = None
    options: list[OptionInput] | None = None
    blanks: list[BlankInput] | None = None
    explanation: str | None = None


class OptionRead(OptionInput):
    model_config = ConfigDict(from_attributes=True)
    id: int
    position: int


class QuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    test_id: int
    text: str
    question_type: QuestionType
    correct_answer: str
    explanation: str
    position: int
    blanks: list[BlankInput]
    options: list[OptionRead]
