from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text
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
    correct_answer: Mapped[str] = mapped_column(Text)

    test: Mapped[Test] = relationship(back_populates="questions")
    attempt_answers: Mapped[list[AttemptAnswer]] = relationship(
        back_populates="question"
    )
