from __future__ import annotations

from pydantic import BaseModel


class HedgeSuggestionResponse(BaseModel):
    """An explainable hedge recommendation tied to a portfolio weakness."""

    instrument: str
    rationale: str
    severity: str
    hedge_ratio: float
    hedge_ratio_steps: list[str]
    estimated_annual_cost_bps: float
    historical_effectiveness: float | None = None
    weakness_citation: str


class RecommendationsResponse(BaseModel):
    """Ordered list of hedge suggestions for a portfolio."""

    portfolio_id: str
    suggestions: list[HedgeSuggestionResponse]
