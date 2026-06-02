from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.scenario import ScenarioRunCreateRequest, ScenarioRunResponse
from app.services import portfolio_service, scenario_service

router = APIRouter(prefix="/scenario-runs", tags=["scenario-runs"])


def _to_response(run) -> ScenarioRunResponse:
    return ScenarioRunResponse(
        id=run.id,
        portfolio_id=run.portfolio_id,
        scenario_id=str(run.scenario_id),
        status=run.status,
        result=run.result,
        created_at=run.created_at,
    )


@router.post("", response_model=ScenarioRunResponse, status_code=status.HTTP_202_ACCEPTED)
def create_scenario_run(request: ScenarioRunCreateRequest, db: Session = Depends(get_db)) -> ScenarioRunResponse:
    portfolio = portfolio_service.get_portfolio(db, request.portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found.")

    scenario = scenario_service.resolve_scenario(db, request.scenario_id)
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found.")

    run = scenario_service.create_run(db, portfolio_id=portfolio.id, scenario=scenario)
    return _to_response(run)


@router.get("/{run_id}", response_model=ScenarioRunResponse)
def get_scenario_run(run_id: uuid.UUID, db: Session = Depends(get_db)) -> ScenarioRunResponse:
    run = scenario_service.get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario run not found.")
    return _to_response(run)
