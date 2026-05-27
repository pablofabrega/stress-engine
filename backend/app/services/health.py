from datetime import datetime, timezone

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine
from app.schemas.health import DataSourceHealth, DatabaseStatus, HealthResponse


def _check_database() -> DatabaseStatus:
    connected = False
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            connected = True
    except Exception:
        connected = False

    return DatabaseStatus(connected=connected, checked_at=datetime.now(timezone.utc))


def build_health_response() -> HealthResponse:
    settings = get_settings()
    database = _check_database()
    status = "ok" if database.connected else "degraded"

    sources = [
        DataSourceHealth(source_name=settings.data_provider, status="not_fetched"),
        DataSourceHealth(source_name="fred", status="not_fetched"),
    ]

    return HealthResponse(
        service=settings.app_name,
        status=status,
        database=database,
        data_sources=sources,
    )

