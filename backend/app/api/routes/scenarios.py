from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.scenario import ScenarioCreateRequest, ScenarioDefinitionResponse
from app.services import scenario_service

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("", response_model=list[ScenarioDefinitionResponse])
def list_scenarios(db: Session = Depends(get_db)) -> list[ScenarioDefinitionResponse]:
    return scenario_service.list_scenarios(db)


@router.post("", response_model=ScenarioDefinitionResponse, status_code=status.HTTP_201_CREATED)
def create_scenario(request: ScenarioCreateRequest, db: Session = Depends(get_db)) -> ScenarioDefinitionResponse:
    scenario = scenario_service.create_scenario(db, request)
    return ScenarioDefinitionResponse(
        id=str(scenario.id),
        name=scenario.name,
        type=scenario.type,
        parameters=scenario.parameters,
        start_date=scenario.start_date,
        end_date=scenario.end_date,
        source="custom",
    )
