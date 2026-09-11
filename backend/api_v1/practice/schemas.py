from pydantic import Field, model_validator
from api_v1.editor.schemas import StrictModel


class PracticeStart(StrictModel):
    question_ids: list[int] = Field(min_length=1, max_length=1000)

    @model_validator(mode='after')
    def valid_ids(self):
        if len(self.question_ids) != len(set(self.question_ids)) or any(i <= 0 for i in self.question_ids):
            raise ValueError('Question IDs must be positive and unique')
        return self


class AnswerInput(StrictModel):
    attempt_question_id: int | None = Field(default=None, gt=0)
    question_id: int | None = Field(default=None, gt=0)
    selected_option_ids: list[int] = Field(default_factory=list, max_length=100)
    user_answer: str = Field(default='', max_length=20000)
    blank_answers: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode='after')
    def target(self):
        if (self.attempt_question_id is None) == (self.question_id is None):
            raise ValueError('Provide exactly one of attempt_question_id and question_id')
        if len(self.selected_option_ids) != len(set(self.selected_option_ids)):
            raise ValueError('Repeated option IDs')
        if any(len(value) > 20000 for value in self.blank_answers):
            raise ValueError('Blank answer too long')
        return self
