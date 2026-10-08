from typing import Literal
from pydantic import Field
from api_v1.editor.schemas import StrictModel, QuestionType


class PreviewOption(StrictModel):
    text: str
    is_correct: bool | None = None


class PreviewQuestion(StrictModel):
    number: int
    text: str
    question_type: QuestionType
    options: list[PreviewOption] = Field(default_factory=list)
    correct_answer: str = ''
    blanks: list[dict] = Field(default_factory=list)
    explanation: str = ''
    source_answer: str = ''
    warnings: list[str] = Field(default_factory=list)

    @property
    def needs_review(self) -> bool:
        return bool(self.warnings) or any(o.is_correct is None for o in self.options)


class Preview(StrictModel):
    title: str
    source: Literal['pdf_import', 'html_import', 'json_import']
    description: str = ''
    questions: list[PreviewQuestion]
    warnings: list[str] = Field(default_factory=list)

    def response(self) -> dict:
        return {**self.model_dump(), 'question_count': len(self.questions),
                'needs_review_count': sum(q.needs_review for q in self.questions),
                'questions': [{**q.model_dump(), 'needs_review': q.needs_review,
                    'correct_option_count': sum(o.is_correct is True for o in q.options)}
                    for q in self.questions]}
