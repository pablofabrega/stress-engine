from __future__ import annotations

from datetime import date

from app.domain.scenarios.models import HistoricalScenarioDefinition

HISTORICAL_SCENARIOS: dict[str, HistoricalScenarioDefinition] = {
    "2008-gfc": HistoricalScenarioDefinition(
        key="2008-gfc",
        name="2008 Global Financial Crisis",
        start_date=date(2008, 9, 1),
        end_date=date(2009, 3, 31),
        description="Replay of the crisis window from September 2008 through March 2009.",
    ),
    "2020-covid-crash": HistoricalScenarioDefinition(
        key="2020-covid-crash",
        name="March 2020 COVID Crash",
        start_date=date(2020, 2, 19),
        end_date=date(2020, 3, 23),
        description="Replay of the initial pandemic selloff from the February 2020 peak through the March trough.",
    ),
}


def list_historical_scenarios() -> list[HistoricalScenarioDefinition]:
    """Return the currently implemented historical stress presets."""

    return list(HISTORICAL_SCENARIOS.values())


def get_historical_scenario(key: str) -> HistoricalScenarioDefinition:
    """Return a named historical scenario definition."""

    return HISTORICAL_SCENARIOS[key]

