"""Execute a persisted scenario run against the domain scenario engines.

This is the bridge that was previously missing: ``ScenarioRun`` rows used to be
created in a ``pending`` state and never executed. ``execute_run`` loads the
portfolio's priced holdings, dispatches to the historical replay or hypothetical
shock engine based on the scenario type, serializes the rich result into the
``scenario_runs.result`` JSON column, and transitions the run to ``completed``
(or ``failed`` with a captured error). Both the synchronous API path and the
Celery worker call this same function.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.models.scenario import ScenarioDefinition, ScenarioRun
from app.domain.portfolio.loader import PortfolioLoader
from app.domain.scenarios.historical import HistoricalScenarioRunner
from app.domain.scenarios.hypothetical import HypotheticalScenarioRunner
from app.domain.scenarios.models import HistoricalScenarioDefinition, HypotheticalScenarioDefinition
from app.services import analytics_service, portfolio_service
from app.services.serialization import serialize_historical_result, serialize_hypothetical_result

logger = logging.getLogger(__name__)

# Top-level shorthand keys accepted on custom hypothetical scenarios, mapped to
# the canonical typed parameter expected by ``HypotheticalScenarioRunner``.
_SHORTHAND_PARAM = {
    "equity_market": "shock",
    "tech_selloff": "shock",
    "oil_shock": "shock",
    "oil": "shock",
    "rates": "bps_change",
    "vix_spike": "target_vix",
    "hy_credit_selloff": "spread_change_bps",
}


def build_historical_definition(scenario: ScenarioDefinition) -> HistoricalScenarioDefinition:
    """Reconstruct a historical replay window from a persisted scenario definition."""

    if scenario.start_date is None or scenario.end_date is None:
        raise ValueError("Historical scenarios require both a start and end date.")
    key = str((scenario.parameters or {}).get("key") or scenario.id)
    return HistoricalScenarioDefinition(
        key=key,
        name=scenario.name,
        start_date=scenario.start_date,
        end_date=scenario.end_date,
        description=scenario.name,
    )


def build_hypothetical_definition(scenario: ScenarioDefinition) -> HypotheticalScenarioDefinition:
    """Map a persisted hypothetical definition into an engine-ready typed shock.

    Accepts either the canonical form ``{"scenario_type": "equity_market",
    "shock": -0.2}`` or a lenient shorthand such as ``{"equity_market": -0.2}``.
    An empty/unknown payload degrades to a zero-impact custom shock so a run
    always produces a valid (if uneventful) result rather than erroring.
    """

    params = dict(scenario.parameters or {})
    key = str(params.pop("key", None) or scenario.id)

    scenario_type = params.pop("scenario_type", None)
    if scenario_type:
        return HypotheticalScenarioDefinition(
            key=key,
            name=scenario.name,
            scenario_type=str(scenario_type),
            parameters=params,
            description=scenario.name,
        )

    for shorthand, canonical in _SHORTHAND_PARAM.items():
        if shorthand in params:
            shock_params: dict[str, float | str] = {canonical: float(params[shorthand])}
            if shorthand == "vix_spike":
                shock_params.setdefault("current_vix", 20.0)
            return HypotheticalScenarioDefinition(
                key=key,
                name=scenario.name,
                scenario_type="oil_shock" if shorthand == "oil" else shorthand,
                parameters=shock_params,
                description=scenario.name,
            )

    if "factor" in params or "magnitude" in params:
        return HypotheticalScenarioDefinition(
            key=key,
            name=scenario.name,
            scenario_type="custom",
            parameters={"factor": str(params.get("factor", "")), "magnitude": float(params.get("magnitude", 0.0))},
            description=scenario.name,
        )

    return HypotheticalScenarioDefinition(
        key=key,
        name=scenario.name,
        scenario_type="custom",
        parameters={"factor": "", "magnitude": 0.0},
        description=scenario.name,
    )


def execute_run(
    db: Session,
    run: ScenarioRun,
    scenario: ScenarioDefinition,
    *,
    loader: PortfolioLoader,
    historical_runner: HistoricalScenarioRunner,
    hypothetical_runner: HypotheticalScenarioRunner,
) -> ScenarioRun:
    """Run a scenario against its portfolio and persist the serialized result."""

    try:
        portfolio = portfolio_service.get_portfolio(db, run.portfolio_id)
        if portfolio is None:
            raise ValueError("Portfolio no longer exists for this run.")
        holdings = analytics_service.build_holdings(portfolio, loader)
        if not holdings:
            raise ValueError("Portfolio has no holdings to stress.")

        if scenario.type == "historical":
            definition = build_historical_definition(scenario)
            result = historical_runner.run_scenario(holdings=holdings, scenario=definition)
            payload = serialize_historical_result(result)
        else:
            definition = build_hypothetical_definition(scenario)
            result = hypothetical_runner.run_scenario(holdings=holdings, scenario=definition)
            payload = serialize_hypothetical_result(result)

        run.status = "completed"
        run.result = payload
    except Exception as exc:  # noqa: BLE001 - surface failure into the run record, not a 500
        logger.exception("scenario run %s failed", run.id)
        run.status = "failed"
        run.result = {"error": str(exc)}

    db.add(run)
    db.commit()
    db.refresh(run)
    return run
