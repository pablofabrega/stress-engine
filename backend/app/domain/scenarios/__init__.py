"""Home for historical and hypothetical scenario runners."""

from app.domain.scenarios.historical import HistoricalScenarioRunner
from app.domain.scenarios.hypothetical import HypotheticalScenarioRunner
from app.domain.scenarios.models import (
    HistoricalScenarioDefinition,
    HistoricalScenarioResult,
    HypotheticalScenarioDefinition,
    HypotheticalScenarioResult,
)
from app.domain.scenarios.presets import get_historical_scenario, list_historical_scenarios

__all__ = [
    "HistoricalScenarioDefinition",
    "HistoricalScenarioResult",
    "HistoricalScenarioRunner",
    "HypotheticalScenarioDefinition",
    "HypotheticalScenarioResult",
    "HypotheticalScenarioRunner",
    "get_historical_scenario",
    "list_historical_scenarios",
]
