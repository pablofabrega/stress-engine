"""Celery tasks for long-running scenario execution.

When ``SCENARIO_EXECUTION_MODE=celery`` the API enqueues
``execute_scenario_run`` instead of running inline. The task owns its own DB
session and engine instances (workers run in a separate process from the API)
and delegates the actual work to :func:`app.services.scenario_executor.execute_run`,
so the synchronous and asynchronous paths share identical logic.
"""

from __future__ import annotations

import uuid

from app.db.models.scenario import ScenarioRun
from app.db.session import SessionLocal
from app.domain.portfolio.loader import PortfolioLoader
from app.domain.scenarios.historical import HistoricalScenarioRunner
from app.domain.scenarios.hypothetical import HypotheticalScenarioRunner
from app.services import scenario_executor
from app.workers.celery_app import celery_app


@celery_app.task(name="scenario.execute_run")
def execute_scenario_run(run_id: str) -> str:
    """Execute a previously-created scenario run by id and persist its result."""

    db = SessionLocal()
    try:
        run = db.get(ScenarioRun, uuid.UUID(run_id))
        if run is None:
            return "missing"
        from app.db.models.scenario import ScenarioDefinition

        scenario = db.get(ScenarioDefinition, run.scenario_id)
        if scenario is None:
            run.status = "failed"
            run.result = {"error": "Scenario definition no longer exists."}
            db.add(run)
            db.commit()
            return "failed"

        scenario_executor.execute_run(
            db,
            run,
            scenario,
            loader=PortfolioLoader(),
            historical_runner=HistoricalScenarioRunner(),
            hypothetical_runner=HypotheticalScenarioRunner(),
        )
        return run.status
    finally:
        db.close()
