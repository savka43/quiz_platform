from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Text, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .attempt import Attempt
    from .question import Question


class AttemptAnswer(Base):
    __table_args__ = (UniqueConstraint("attempt_id", "question_id"), UniqueConstraint("attempt_question_id"),)

    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("attempts.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[int | None] = mapped_column(ForeignKey("questions.id", ondelete="SET NULL"), index=True)
    attempt_question_id: Mapped[int | None] = mapped_column(ForeignKey("attempt_questions.id", ondelete="CASCADE"))
    selected_option_ids: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")
    blank_answers: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")
    user_answer: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean)

    attempt: Mapped[Attempt] = relationship(back_populates="answers")
    question: Mapped[Question | None] = relationship(back_populates="attempt_answers")
