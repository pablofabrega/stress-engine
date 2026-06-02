from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    app_env: str = Field(default="development", alias="APP_ENV")
    app_name: str = Field(default="Market Scenario and Stress Testing Workbench", alias="APP_NAME")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    database_url: str = Field(
        default="postgresql+psycopg://stress_user:stress_password@localhost:5432/stress_workbench",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    celery_broker_url: str = Field(default="redis://localhost:6379/0", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/1", alias="CELERY_RESULT_BACKEND")

    # "sync" runs the scenario engine inline in the request (works out of the box,
    # ideal for the demo); "celery" enqueues a background task for a worker.
    scenario_execution_mode: str = Field(default="sync", alias="SCENARIO_EXECUTION_MODE")

    data_provider: str = Field(default="yfinance", alias="DATA_PROVIDER")
    data_cache_dir: str = Field(default="data/cache", alias="DATA_CACHE_DIR")
    data_stale_after_hours: int = Field(default=24, alias="DATA_STALE_AFTER_HOURS")
    yfinance_timeout_seconds: int = Field(default=30, alias="YFINANCE_TIMEOUT_SECONDS")
    polygon_api_key: str | None = Field(default=None, alias="POLYGON_API_KEY")
    polygon_base_url: str = Field(default="https://api.polygon.io", alias="POLYGON_BASE_URL")
    alpaca_api_key: str | None = Field(default=None, alias="ALPACA_API_KEY")
    alpaca_api_secret: str | None = Field(default=None, alias="ALPACA_API_SECRET")
    alpaca_base_url: str = Field(default="https://data.alpaca.markets", alias="ALPACA_BASE_URL")
    fred_api_key: str | None = Field(default=None, alias="FRED_API_KEY")
    fred_base_url: str = Field(default="https://fred.stlouisfed.org", alias="FRED_BASE_URL")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
