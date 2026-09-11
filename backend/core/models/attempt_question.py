from sqlalchemy import ForeignKey, Integer, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class AttemptQuestion(Base):
    """Immutable question snapshot: editing/deleting the source cannot rewrite history."""
    __table_args__ = (UniqueConstraint("attempt_id", "position"),)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"), index=True)
    source_question_id: Mapped[int | None] = mapped_column(ForeignKey("questions.id", ondelete="SET NULL"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
