from fastapi import APIRouter

from app.schemas.health import HealthResponse
from app.services.health import build_health_response

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return build_health_response()


@router.get("/data-status", response_model=HealthResponse)
def data_status() -> HealthResponse:
    return build_health_response()

