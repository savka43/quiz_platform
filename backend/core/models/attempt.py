from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .mixins import UserRelationMixin

if TYPE_CHECKING:
    from .attempt_answer import AttemptAnswer
    from .test import Test


class Attempt(UserRelationMixin, Base):
    _user_back_populates = "attempts"

    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    test: Mapped[Test] = relationship(back_populates="attempts")
    answers: Mapped[list[AttemptAnswer]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )
