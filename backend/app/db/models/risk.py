import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import json_column_type, uuid_column_type


class RiskSnapshot(Base):
    __tablename__ = "risk_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(uuid_column_type(), primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_portfolios.id", ondelete="CASCADE"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    var_95: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    var_99: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    cvar_95: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    max_drawdown: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    rolling_vol: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    concentration_metrics: Mapped[dict] = mapped_column(json_column_type(), nullable=False, default=dict)

