from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HoldingInput(BaseModel):
    """A single holding supplied when creating or updating a portfolio."""

    ticker: str = Field(min_length=1, max_length=32)
    quantity: float = Field(gt=0)
    cost_basis: float | None = Field(default=None, ge=0)
    asset_class: str | None = None
    sector: str | None = None


class PortfolioCreateRequest(BaseModel):
    """Request body for creating a portfolio."""

    name: str = Field(min_length=1, max_length=255)
    holdings: list[HoldingInput] = Field(default_factory=list)


class HoldingsUpdateRequest(BaseModel):
    """Request body for adding or updating holdings (upsert by ticker)."""

    holdings: list[HoldingInput] = Field(min_length=1)


class HoldingResponse(BaseModel):
    """Serialized holding as stored in the database."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticker: str
    quantity: float
    cost_basis: float | None = None
    asset_class: str | None = None
    sector: str | None = None


class PortfolioAnalyticsSummary(BaseModel):
    """Lightweight, deterministic analytics computed from stored holdings.

    Weights are nominal (notional = quantity x cost_basis when available,
    otherwise quantity), so this summary requires no market-data fetch.
    """

    total_notional: float
    holding_weights: dict[str, float]
    sector_weights: dict[str, float]


class PortfolioResponse(BaseModel):
    """Portfolio with holdings."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    created_at: datetime
    holdings: list[HoldingResponse]


class PortfolioDetailResponse(PortfolioResponse):
    """Portfolio with holdings and a nominal analytics summary."""

    analytics: PortfolioAnalyticsSummary
