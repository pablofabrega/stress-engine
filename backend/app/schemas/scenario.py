from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ScenarioDefinitionResponse(BaseModel):
    """A scenario definition (preset or custom)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    type: Literal["historical", "hypothetical"]
    parameters: dict[str, Any] = Field(default_factory=dict)
    start_date: date | None = None
    end_date: date | None = None
    source: Literal["preset", "custom"] = "custom"
    description: str | None = None


class ScenarioCreateRequest(BaseModel):
    """Request body for creating a custom scenario definition."""

    name: str = Field(min_length=1, max_length=255)
    type: Literal["historical", "hypothetical"]
    parameters: dict[str, Any] = Field(default_factory=dict)
    start_date: date | None = None
    end_date: date | None = None


class ScenarioRunCreateRequest(BaseModel):
    """Request body for enqueuing a scenario run."""

    portfolio_id: uuid.UUID
    scenario_id: str


class ScenarioRunResponse(BaseModel):
    """A scenario run record with status and (when complete) result."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    portfolio_id: uuid.UUID
    scenario_id: str
    status: str
    result: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
