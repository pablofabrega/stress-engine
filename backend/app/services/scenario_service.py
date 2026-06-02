"""Scenario definitions (presets + custom) and scenario-run lifecycle."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.scenario import ScenarioDefinition, ScenarioRun
from app.domain.scenarios.presets import HISTORICAL_SCENARIOS
from app.schemas.scenario import ScenarioCreateRequest, ScenarioDefinitionResponse


def list_scenarios(db: Session) -> list[ScenarioDefinitionResponse]:
    """Return historical presets followed by custom scenario definitions."""

    presets = [
        ScenarioDefinitionResponse(
            id=preset.key,
            name=preset.name,
            type="historical",
            parameters={"key": preset.key},
            start_date=preset.start_date,
            end_date=preset.end_date,
            source="preset",
            description=preset.description,
        )
        for preset in HISTORICAL_SCENARIOS.values()
    ]

    custom_rows = db.execute(select(ScenarioDefinition).order_by(ScenarioDefinition.created_at)).scalars().all()
    custom = [
        ScenarioDefinitionResponse(
            id=str(row.id),
            name=row.name,
            type=row.type,
            parameters=row.parameters,
            start_date=row.start_date,
            end_date=row.end_date,
            source="custom",
        )
        for row in custom_rows
    ]
    return presets + custom


def create_scenario(db: Session, request: ScenarioCreateRequest) -> ScenarioDefinition:
    """Persist a custom scenario definition."""

    scenario = ScenarioDefinition(
        name=request.name,
        type=request.type,
        parameters=request.parameters,
        start_date=request.start_date,
        end_date=request.end_date,
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return scenario


def resolve_scenario(db: Session, scenario_id: str) -> ScenarioDefinition | None:
    """Resolve a scenario id to a persisted definition.

    Accepts either a custom definition UUID or a historical preset key. Preset
    keys are materialized into ``scenario_definitions`` on first use so that the
    scenario-run foreign key remains valid.
    """

    parsed = _maybe_uuid(scenario_id)
    if parsed is not None:
        existing = db.get(ScenarioDefinition, parsed)
        if existing is not None:
            return existing

    preset = HISTORICAL_SCENARIOS.get(scenario_id)
    if preset is None:
        return None
    return _materialize_preset(db, scenario_id)


def create_run(db: Session, portfolio_id: uuid.UUID, scenario: ScenarioDefinition) -> ScenarioRun:
    """Create a pending scenario run. Execution is handled asynchronously (step 12)."""

    run = ScenarioRun(portfolio_id=portfolio_id, scenario_id=scenario.id, status="pending", result={})
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def get_run(db: Session, run_id: uuid.UUID) -> ScenarioRun | None:
    """Return a scenario run by id, or ``None``."""

    return db.get(ScenarioRun, run_id)


def _materialize_preset(db: Session, preset_key: str) -> ScenarioDefinition:
    preset = HISTORICAL_SCENARIOS[preset_key]
    stmt = select(ScenarioDefinition).where(
        ScenarioDefinition.type == "historical",
        ScenarioDefinition.name == preset.name,
    )
    existing = db.execute(stmt).scalars().first()
    if existing is not None:
        return existing

    scenario = ScenarioDefinition(
        name=preset.name,
        type="historical",
        parameters={"key": preset.key},
        start_date=preset.start_date,
        end_date=preset.end_date,
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return scenario


def _maybe_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        return None
