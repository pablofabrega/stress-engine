from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.portfolio.models import PortfolioHolding


class ScenarioRunner(ABC):
    """Base contract for reusable scenario engines."""

    @abstractmethod
    def run(self, holdings: list[PortfolioHolding], scenario_key: str):
        """Run a named scenario against a normalized portfolio."""

