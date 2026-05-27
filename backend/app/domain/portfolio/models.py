from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass(slots=True)
class SecurityMetadata:
    """Describes instrument classification used for portfolio tagging."""

    ticker: str
    asset_class: str
    sector: str
    metadata_source: str


@dataclass(slots=True)
class PortfolioHolding:
    """Normalized holding with classification, valuation, and portfolio weight fields."""

    ticker: str
    quantity: float
    cost_basis: float | None = None
    asset_class: str = "Unknown"
    sector: str = "Unknown"
    current_price: float | None = None
    market_value: float = 0.0
    weight: float = 0.0
    metadata_source: str = "unknown"
    price_source: str = "unpriced"


@dataclass(slots=True)
class PortfolioLoadResult:
    """Loaded portfolio representation with normalized holdings and summary metrics."""

    name: str
    holdings: list[PortfolioHolding]
    total_market_value: float
    sector_weights: dict[str, float]
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PortfolioReturnHistory:
    """Portfolio-level return history with component panel and warning surface."""

    portfolio_returns: pd.Series
    component_returns: pd.DataFrame
    weights_used: dict[str, float]
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class FactorDecompositionResult:
    """OLS factor decomposition summary for a portfolio's excess returns."""

    alpha: float
    alpha_t_stat: float
    market_beta: float
    market_beta_t_stat: float
    smb_exposure: float
    smb_t_stat: float
    hml_exposure: float
    hml_t_stat: float
    r_squared: float
    observations: int
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PresetPortfolioDefinition:
    """Target-weight definition for a preset portfolio."""

    key: str
    name: str
    description: str
    target_weights: dict[str, float]
