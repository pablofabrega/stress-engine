from __future__ import annotations

from app.domain.portfolio.models import PresetPortfolioDefinition

PRESET_PORTFOLIOS: dict[str, PresetPortfolioDefinition] = {
    "concentrated-tech": PresetPortfolioDefinition(
        key="concentrated-tech",
        name="Concentrated Tech",
        description="A high-growth large-cap technology portfolio with significant single-sector concentration.",
        target_weights={"AAPL": 0.40, "NVDA": 0.25, "MSFT": 0.20, "AMZN": 0.15},
    ),
    "classic-60-40": PresetPortfolioDefinition(
        key="classic-60-40",
        name="Classic 60/40",
        description="A traditional balanced portfolio split between US equities and core bonds.",
        target_weights={"SPY": 0.60, "BND": 0.40},
    ),
    "growth-diversified": PresetPortfolioDefinition(
        key="growth-diversified",
        name="Growth Diversified",
        description="A growth-oriented cross-asset allocation with international, real estate, gold, duration, and credit exposure.",
        target_weights={"QQQ": 0.20, "VTI": 0.15, "IEMG": 0.15, "VNQ": 0.15, "GLD": 0.10, "TLT": 0.10, "HYG": 0.15},
    ),
    "defensive": PresetPortfolioDefinition(
        key="defensive",
        name="Defensive",
        description="A lower-beta allocation emphasizing dividends, defensives, long duration, and gold.",
        target_weights={"VYD": 0.30, "XLU": 0.20, "XLP": 0.20, "TLT": 0.15, "GLD": 0.15},
    ),
}


def get_preset_portfolios() -> list[PresetPortfolioDefinition]:
    """Return all preset portfolio definitions."""

    return list(PRESET_PORTFOLIOS.values())


def get_preset_portfolio(key: str) -> PresetPortfolioDefinition:
    """Return a named preset portfolio definition."""

    return PRESET_PORTFOLIOS[key]

