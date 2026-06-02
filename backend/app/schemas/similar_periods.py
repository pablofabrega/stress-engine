from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, Field


class SimilarPeriodsRequest(BaseModel):
    """Request body for the similar-periods finder.

    ``shock_vector`` keys should be a subset of the canonical feature names:
    equity_return, vol_change, rate_change_10y, credit_spread_change,
    equity_bond_correlation_shift. Missing features default to 0.0.
    """

    shock_vector: dict[str, float] = Field(min_length=1)
    portfolio_id: uuid.UUID | None = None
    top_k: int = Field(default=3, ge=1, le=20)


class SimilarPeriodResponse(BaseModel):
    """A single nearest historical analog window."""

    start_date: date
    end_date: date
    similarity_score: float
    feature_vector: dict[str, float]
    portfolio_return: float | None = None
    outcome_narrative: str


class SimilarPeriodsResponse(BaseModel):
    """Ranked list of similar historical periods."""

    periods: list[SimilarPeriodResponse]
