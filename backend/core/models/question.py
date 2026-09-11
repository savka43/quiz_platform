from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text, String, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .attempt_answer import AttemptAnswer
    from .test import Test


class Question(Base):
    test_id: Mapped[int] = mapped_column(
        ForeignKey("tests.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text)
    correct_answer: Mapped[str] = mapped_column(Text, default="", server_default="")
    question_type: Mapped[str] = mapped_column(String(20), default="text", server_default="text")
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    explanation: Mapped[str] = mapped_column(Text, default="", server_default="")
    blanks: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")
    options = relationship("AnswerOption", back_populates="question", cascade="all, delete-orphan", lazy="selectin")

    test: Mapped[Test] = relationship(back_populates="questions")
    attempt_answers: Mapped[list[AttemptAnswer]] = relationship(
        back_populates="question", passive_deletes="all"
    )
