import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import uuid_column_type


class UserPortfolio(Base):
    __tablename__ = "user_portfolios"

    id: Mapped[uuid.UUID] = mapped_column(uuid_column_type(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # Read-only starter portfolios (the seeded presets). The UI surfaces a
    # "Duplicate to edit" action instead of inline editing for these.
    is_template: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())

    holdings: Mapped[list["Holding"]] = relationship(back_populates="portfolio", cascade="all, delete-orphan")


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[uuid.UUID] = mapped_column(uuid_column_type(), primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_portfolios.id", ondelete="CASCADE"), index=True)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    cost_basis: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    asset_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(128), nullable=True)

    portfolio: Mapped[UserPortfolio] = relationship(back_populates="holdings")


class DataSourceStatus(Base):
    __tablename__ = "data_source_statuses"

    id: Mapped[uuid.UUID] = mapped_column(uuid_column_type(), primary_key=True, default=uuid.uuid4)
    source_name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    last_fetched: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)

