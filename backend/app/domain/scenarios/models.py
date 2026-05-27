from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd


@dataclass(slots=True)
class HistoricalScenarioDefinition:
    """Replay window definition for a named historical stress event."""

    key: str
    name: str
    start_date: date
    end_date: date
    description: str


@dataclass(slots=True)
class HistoricalScenarioResult:
    """Scenario replay output for a portfolio over a historical stress window."""

    scenario: HistoricalScenarioDefinition
    portfolio_path: pd.DataFrame
    comparison_path: pd.DataFrame
    contributors: pd.DataFrame
    sector_breakdown: pd.DataFrame
    asset_class_breakdown: pd.DataFrame
    correlation_before: pd.DataFrame
    correlation_during: pd.DataFrame
    correlation_shift: pd.DataFrame
    significant_correlation_shifts: pd.DataFrame
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class HypotheticalScenarioDefinition:
    """Reusable typed definition for a hypothetical shock scenario."""

    key: str
    name: str
    scenario_type: str
    parameters: dict[str, float | str]
    description: str


@dataclass(slots=True)
class HypotheticalScenarioResult:
    """Result bundle for an instantaneous hypothetical shock scenario."""

    scenario: HypotheticalScenarioDefinition
    holding_impacts: pd.DataFrame
    instantaneous_pnl_dollars: float
    instantaneous_return: float
    simulated_drawdown_path: pd.DataFrame
    factor_exposure_before: pd.DataFrame
    factor_exposure_after: pd.DataFrame
    liquidity_adjusted_loss: float
    liquidity_table: pd.DataFrame
    feature_vector: dict[str, float]
    warnings: list[str] = field(default_factory=list)
