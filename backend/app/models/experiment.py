from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExperimentCompareRun(Base):
    """实验对照一次运行的完整快照（按用户隔离）。"""

    __tablename__ = "experiment_compare_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    legal_domain: Mapped[str] = mapped_column(String(64), default="")
    preset_ids: Mapped[list] = mapped_column(JSON, default=list)
    llm_score_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    best_balanced_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
