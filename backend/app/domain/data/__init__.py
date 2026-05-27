"""Phase 2 home for provider abstraction, fetchers, and return calculations."""

from app.domain.data.fama_french import FamaFrenchLoader
from app.domain.data.fetchers import HistoricalDataFetcher, MacroDataFetcher
from app.domain.data.returns import ReturnsCalculator

__all__ = [
    "FamaFrenchLoader",
    "HistoricalDataFetcher",
    "MacroDataFetcher",
    "ReturnsCalculator",
]
