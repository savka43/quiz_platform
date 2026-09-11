from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Nonempty = Annotated[str, Field(min_length=1, max_length=20000)]
QuestionType = Literal['single_choice', 'multiple_choice', 'text', 'fill_blank', 'matching']


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class OptionInput(StrictModel):
    text: Nonempty
    is_correct: bool


class BlankInput(StrictModel):
    prompt: Nonempty
    correct_answer: Nonempty
    choices: list[Nonempty] = Field(default_factory=list, max_length=100)


class QuestionInput(StrictModel):
    id: int | None = Field(default=None, gt=0)
    text: Nonempty
    question_type: QuestionType = 'text'
    options: list[OptionInput] = Field(default_factory=list, max_length=100)
    correct_answer: str = Field(default='', max_length=20000)
    blanks: list[BlankInput] = Field(default_factory=list, max_length=100)
    explanation: str = Field(default='', max_length=20000)

    @model_validator(mode='after')
    def coherent_answer(self):
        if self.question_type in ('single_choice', 'multiple_choice'):
            if len(self.options) < 2:
                raise ValueError('Choice question requires at least two options')
            correct = sum(o.is_correct for o in self.options)
            if correct < 1 or (self.question_type == 'single_choice' and correct != 1):
                raise ValueError('Select the correct option(s) for this question type')
            if self.correct_answer or self.blanks:
                raise ValueError('Choice question uses options only')
        elif self.question_type == 'text':
            if not self.correct_answer.strip() or self.options or self.blanks:
                raise ValueError('Text question requires correct_answer and no options/blanks')
        elif not self.blanks or self.options or self.correct_answer:
            raise ValueError('Fill-blank question requires blanks only')
        if self.question_type == 'matching' and any(not b.choices or b.correct_answer not in b.choices for b in self.blanks):
            raise ValueError('Matching answers must be selected from each row choices')
        return self


class TestDocument(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=20000)
    questions: list[QuestionInput] = Field(min_length=1, max_length=1000)

    @model_validator(mode='after')
    def unique_ids(self):
        ids = [q.id for q in self.questions if q.id is not None]
        if len(ids) != len(set(ids)):
            raise ValueError('Question IDs must not be repeated')
        return self
