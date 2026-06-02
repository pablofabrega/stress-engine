from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.portfolios import router as portfolios_router
from app.api.routes.scenario_runs import router as scenario_runs_router
from app.api.routes.scenarios import router as scenarios_router
from app.api.routes.similar_periods import router as similar_periods_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(portfolios_router)
api_router.include_router(scenarios_router)
api_router.include_router(scenario_runs_router)
api_router.include_router(similar_periods_router)
