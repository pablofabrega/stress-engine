from datetime import datetime

from pydantic import BaseModel


class DatabaseStatus(BaseModel):
    connected: bool
    checked_at: datetime


class DataSourceHealth(BaseModel):
    source_name: str
    status: str
    last_fetched: datetime | None = None
    error_message: str | None = None


class HealthResponse(BaseModel):
    service: str
    status: str
    database: DatabaseStatus
    data_sources: list[DataSourceHealth]

