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
    "2022-rate-tightening": HistoricalScenarioDefinition(
        key="2022-rate-tightening",
        name="2022 Rate Tightening",
        start_date=date(2022, 1, 1),
        end_date=date(2022, 12, 31),
        description="Replay of the 2022 calendar year as the Federal Reserve raised rates aggressively.",
    ),
    "2018-q4-selloff": HistoricalScenarioDefinition(
        key="2018-q4-selloff",
        name="2018 Q4 Selloff",
        start_date=date(2018, 10, 1),
        end_date=date(2018, 12, 24),
        description="Replay of the fourth-quarter 2018 equity selloff into the Christmas Eve trough.",
    ),
    "2000-dot-com": HistoricalScenarioDefinition(
        key="2000-dot-com",
        name="2000 Dot-Com Bust",
        start_date=date(2000, 3, 10),
        end_date=date(2002, 10, 9),
        description="Optional replay of the dot-com unwind from the March 2000 peak through the October 2002 trough.",
    ),
}


def list_historical_scenarios() -> list[HistoricalScenarioDefinition]:
    """Return the currently implemented historical stress presets."""

    return list(HISTORICAL_SCENARIOS.values())


def get_historical_scenario(key: str) -> HistoricalScenarioDefinition:
    """Return a named historical scenario definition."""

    return HISTORICAL_SCENARIOS[key]

