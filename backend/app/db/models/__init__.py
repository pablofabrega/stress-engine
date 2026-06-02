"""ORM model registry.

Importing the model modules here ensures their tables are registered on
``Base.metadata`` whenever ``app.db.models`` is imported (used by Alembic and
by the test suite's ``create_all``).
"""

from app.db.models.portfolio import DataSourceStatus, Holding, UserPortfolio
from app.db.models.recommendation import Recommendation
from app.db.models.risk import RiskSnapshot
from app.db.models.scenario import ScenarioDefinition, ScenarioRun

__all__ = [
    "DataSourceStatus",
    "Holding",
    "Recommendation",
    "RiskSnapshot",
    "ScenarioDefinition",
    "ScenarioRun",
    "UserPortfolio",
]
