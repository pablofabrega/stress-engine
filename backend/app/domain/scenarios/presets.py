from __future__ import annotations

from datetime import date

from app.domain.scenarios.models import HistoricalScenarioDefinition, HypotheticalScenarioDefinition

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


# Ready-to-run hypothetical shock presets. Each maps to a ``scenario_type``
# understood by ``HypotheticalScenarioRunner`` plus its typed parameters, so the
# frontend can offer one-click macro shocks alongside fully custom ones.
HYPOTHETICAL_SCENARIOS: dict[str, HypotheticalScenarioDefinition] = {
    "equity-down-20": HypotheticalScenarioDefinition(
        key="equity-down-20",
        name="Equity market -20%",
        scenario_type="equity_market",
        parameters={"shock": -0.20},
        description="A broad 20% equity drawdown applied through each holding's market beta.",
    ),
    "rates-up-100bps": HypotheticalScenarioDefinition(
        key="rates-up-100bps",
        name="Rates +100 bps",
        scenario_type="rates",
        parameters={"bps_change": 100.0},
        description="A 100 basis point parallel rate rise repricing bonds by duration and equities by rate sensitivity.",
    ),
    "tech-selloff-25": HypotheticalScenarioDefinition(
        key="tech-selloff-25",
        name="Tech selloff -25%",
        scenario_type="tech_selloff",
        parameters={"shock": -0.25},
        description="A 25% technology-sector shock with correlation-based spillover into other equities.",
    ),
    "vix-spike-40": HypotheticalScenarioDefinition(
        key="vix-spike-40",
        name="VIX spike to 40",
        scenario_type="vix_spike",
        parameters={"current_vix": 18.0, "target_vix": 40.0},
        description="A volatility spike from 18 to 40 estimating equity drag and VIX-linked gains.",
    ),
    "oil-up-50": HypotheticalScenarioDefinition(
        key="oil-up-50",
        name="Oil +50%",
        scenario_type="oil_shock",
        parameters={"shock": 0.50},
        description="A 50% oil price jump benefiting energy while pressuring rate-sensitive holdings.",
    ),
    "hy-credit-300bps": HypotheticalScenarioDefinition(
        key="hy-credit-300bps",
        name="HY credit +300 bps",
        scenario_type="hy_credit_selloff",
        parameters={"spread_change_bps": 300.0},
        description="A 300 basis point high-yield spread widening with contagion to equities.",
    ),
}


def list_hypothetical_scenarios() -> list[HypotheticalScenarioDefinition]:
    """Return the ready-to-run hypothetical shock presets."""

    return list(HYPOTHETICAL_SCENARIOS.values())


def get_hypothetical_scenario(key: str) -> HypotheticalScenarioDefinition:
    """Return a named hypothetical scenario definition."""

    return HYPOTHETICAL_SCENARIOS[key]

