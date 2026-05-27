from __future__ import annotations

from datetime import date
from io import StringIO

import pandas as pd
import pytest

from app.domain.data.models import FetchResult
from app.domain.portfolio.loader import PortfolioLoader
from app.domain.portfolio.metadata import SecurityMetadataResolver


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeMetadataResolver(SecurityMetadataResolver):
    """Return deterministic metadata without network calls."""

    def __init__(self) -> None:
        super().__init__(use_yfinance_fallback=False)


class FakeHistoricalDataFetcher:
    """Return a controlled latest price for any ticker."""

    def __init__(self, prices: dict[str, float] | None = None) -> None:
        self._prices = prices or {}

    def fetch(self, ticker: str, start_date: date, end_date: date) -> FetchResult:
        price = self._prices.get(ticker.upper())
        if price is None:
            return FetchResult(
                data=pd.DataFrame(columns=["adj_close"]),
                source="fake",
                cache_hit=False,
                warnings=[f"No historical data returned for ticker {ticker.upper()}."],
            )
        idx = pd.date_range(end_date, periods=1)
        frame = pd.DataFrame({"adj_close": [price]}, index=idx)
        frame.index.name = "date"
        return FetchResult(data=frame, source="fake", cache_hit=False)


def _loader(prices: dict[str, float] | None = None) -> PortfolioLoader:
    return PortfolioLoader(
        metadata_resolver=FakeMetadataResolver(),
        historical_data_fetcher=FakeHistoricalDataFetcher(prices or {"AAPL": 180.0, "MSFT": 400.0, "NVDA": 800.0, "TLT": 90.0, "GLD": 190.0}),
    )


# ---------------------------------------------------------------------------
# JSON loading
# ---------------------------------------------------------------------------

class TestLoadFromJson:
    def test_basic_json_loading(self) -> None:
        loader = _loader()
        result = loader.load_from_json("test", {"AAPL": {"quantity": 100, "cost_basis": 150.0}})

        assert result.name == "test"
        assert len(result.holdings) == 1
        assert result.holdings[0].ticker == "AAPL"
        assert result.holdings[0].quantity == 100.0

    def test_multiple_holdings(self) -> None:
        loader = _loader()
        result = loader.load_from_json("multi", {
            "AAPL": {"quantity": 50, "cost_basis": 150.0},
            "MSFT": {"quantity": 30, "cost_basis": 350.0},
        })
        assert len(result.holdings) == 2
        tickers = {h.ticker for h in result.holdings}
        assert tickers == {"AAPL", "MSFT"}

    def test_weights_sum_to_one(self) -> None:
        loader = _loader()
        result = loader.load_from_json("weighted", {
            "AAPL": {"quantity": 100, "cost_basis": None},
            "MSFT": {"quantity": 50, "cost_basis": None},
        })
        total_weight = sum(h.weight for h in result.holdings)
        assert total_weight == pytest.approx(1.0)

    def test_cost_basis_optional(self) -> None:
        loader = _loader()
        result = loader.load_from_json("no_cb", {"AAPL": {"quantity": 10, "cost_basis": None}})
        assert result.holdings[0].cost_basis is None

    def test_ticker_uppercased(self) -> None:
        loader = _loader()
        result = loader.load_from_json("case", {"aapl": {"quantity": 10, "cost_basis": None}})
        assert result.holdings[0].ticker == "AAPL"

    def test_market_value_calculated(self) -> None:
        loader = _loader({"AAPL": 200.0})
        result = loader.load_from_json("mv", {"AAPL": {"quantity": 50, "cost_basis": None}})
        assert result.holdings[0].market_value == pytest.approx(10000.0)
        assert result.total_market_value == pytest.approx(10000.0)

    def test_zero_quantity_raises(self) -> None:
        loader = _loader()
        with pytest.raises(ValueError, match="positive"):
            loader.load_from_json("bad", {"AAPL": {"quantity": 0, "cost_basis": None}})

    def test_negative_quantity_raises(self) -> None:
        loader = _loader()
        with pytest.raises(ValueError, match="positive"):
            loader.load_from_json("bad", {"AAPL": {"quantity": -10, "cost_basis": None}})


# ---------------------------------------------------------------------------
# CSV loading
# ---------------------------------------------------------------------------

class TestLoadFromCsv:
    def test_basic_csv(self) -> None:
        csv_text = "ticker,quantity,cost_basis\nAAPL,100,150.0\nMSFT,50,350.0"
        loader = _loader()
        result = loader.load_from_csv("csv_test", StringIO(csv_text))

        assert len(result.holdings) == 2
        tickers = {h.ticker for h in result.holdings}
        assert tickers == {"AAPL", "MSFT"}

    def test_csv_without_cost_basis(self) -> None:
        csv_text = "ticker,quantity\nAAPL,100\nNVDA,25"
        loader = _loader()
        result = loader.load_from_csv("no_cb", StringIO(csv_text))
        assert len(result.holdings) == 2

    def test_csv_missing_required_columns_raises(self) -> None:
        csv_text = "name,shares\nAAPL,100"
        loader = _loader()
        with pytest.raises(ValueError, match="missing required columns"):
            loader.load_from_csv("bad", StringIO(csv_text))

    def test_csv_case_insensitive_columns(self) -> None:
        csv_text = "Ticker,Quantity,Cost_Basis\nAAPL,100,150.0"
        loader = _loader()
        result = loader.load_from_csv("caps", StringIO(csv_text))
        assert result.holdings[0].ticker == "AAPL"

    def test_csv_weights_sum_to_one(self) -> None:
        csv_text = "ticker,quantity\nAAPL,100\nMSFT,50\nNVDA,25"
        loader = _loader()
        result = loader.load_from_csv("w", StringIO(csv_text))
        total = sum(h.weight for h in result.holdings)
        assert total == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Preset loading
# ---------------------------------------------------------------------------

class TestLoadPreset:
    def test_concentrated_tech_preset(self) -> None:
        prices = {"AAPL": 180.0, "NVDA": 800.0, "MSFT": 400.0, "AMZN": 180.0}
        loader = _loader(prices)
        result = loader.load_preset("concentrated-tech", total_notional=100_000.0)

        assert result.name == "Concentrated Tech"
        tickers = {h.ticker for h in result.holdings}
        assert tickers == {"AAPL", "NVDA", "MSFT", "AMZN"}

    def test_preset_weights_sum_to_one(self) -> None:
        prices = {"SPY": 500.0, "BND": 70.0}
        loader = _loader(prices)
        result = loader.load_preset("classic-60-40", total_notional=100_000.0)

        total = sum(h.weight for h in result.holdings)
        assert total == pytest.approx(1.0)

    def test_unknown_preset_raises(self) -> None:
        loader = _loader()
        with pytest.raises(KeyError):
            loader.load_preset("nonexistent-preset")

    def test_preset_market_value_near_notional(self) -> None:
        prices = {"SPY": 500.0, "BND": 70.0}
        loader = _loader(prices)
        result = loader.load_preset("classic-60-40", total_notional=1_000_000.0)
        assert result.total_market_value == pytest.approx(1_000_000.0, rel=0.01)


# ---------------------------------------------------------------------------
# Metadata tagging
# ---------------------------------------------------------------------------

class TestMetadataTagging:
    def test_known_ticker_gets_static_metadata(self) -> None:
        loader = _loader()
        result = loader.load_from_json("tag", {"AAPL": {"quantity": 10, "cost_basis": None}})
        holding = result.holdings[0]
        assert holding.sector == "Technology"
        assert holding.asset_class == "Equity"

    def test_unknown_ticker_gets_fallback(self) -> None:
        loader = _loader({"ZZZZ": 50.0})
        result = loader.load_from_json("unk", {"ZZZZ": {"quantity": 10, "cost_basis": None}})
        holding = result.holdings[0]
        assert holding.asset_class == "Unknown"
        assert holding.sector == "Unknown"

    def test_sector_weights_computed(self) -> None:
        loader = _loader()
        result = loader.load_from_json("sw", {
            "AAPL": {"quantity": 100, "cost_basis": None},
            "MSFT": {"quantity": 50, "cost_basis": None},
        })
        assert "Technology" in result.sector_weights
        assert result.sector_weights["Technology"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Duplicate ticker aggregation
# ---------------------------------------------------------------------------

class TestDuplicateAggregation:
    def test_duplicate_tickers_aggregated(self) -> None:
        csv_text = "ticker,quantity,cost_basis\nAAPL,50,150.0\nAAPL,50,160.0"
        loader = _loader()
        result = loader.load_from_csv("dup", StringIO(csv_text))
        assert len(result.holdings) == 1
        assert result.holdings[0].quantity == 100.0


# ---------------------------------------------------------------------------
# Missing price handling
# ---------------------------------------------------------------------------

class TestMissingPriceHandling:
    def test_missing_price_generates_warning(self) -> None:
        loader = _loader({"MSFT": 400.0})  # AAPL intentionally absent
        result = loader.load_from_json("empty", {"AAPL": {"quantity": 10, "cost_basis": None}})
        assert len(result.warnings) > 0
        assert any("AAPL" in w for w in result.warnings)
