from __future__ import annotations

import math
import uuid
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd

from app.domain.data.models import FetchResult
from app.domain.portfolio.models import PortfolioHolding
from app.domain.scenarios.historical import HistoricalScenarioRunner
from app.domain.scenarios.models import HistoricalScenarioDefinition
from app.services import scenario_executor, serialization


def _scenario(**kwargs) -> SimpleNamespace:
    base = {
        "id": uuid.uuid4(),
        "name": "Test",
        "type": "hypothetical",
        "parameters": {},
        "start_date": None,
        "end_date": None,
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_build_hypothetical_definition_canonical_form() -> None:
    scenario = _scenario(parameters={"scenario_type": "equity_market", "shock": -0.2})

    definition = scenario_executor.build_hypothetical_definition(scenario)

    assert definition.scenario_type == "equity_market"
    assert definition.parameters == {"shock": -0.2}


def test_build_hypothetical_definition_shorthand_form() -> None:
    scenario = _scenario(parameters={"equity_market": -0.2})

    definition = scenario_executor.build_hypothetical_definition(scenario)

    assert definition.scenario_type == "equity_market"
    assert definition.parameters == {"shock": -0.2}


def test_build_hypothetical_definition_vix_shorthand_defaults_current() -> None:
    scenario = _scenario(parameters={"vix_spike": 40.0})

    definition = scenario_executor.build_hypothetical_definition(scenario)

    assert definition.scenario_type == "vix_spike"
    assert definition.parameters == {"target_vix": 40.0, "current_vix": 20.0}


def test_build_hypothetical_definition_empty_is_zero_impact_custom() -> None:
    scenario = _scenario(parameters={})

    definition = scenario_executor.build_hypothetical_definition(scenario)

    assert definition.scenario_type == "custom"
    assert definition.parameters == {"factor": "", "magnitude": 0.0}


def test_build_historical_definition_uses_stored_window() -> None:
    scenario = _scenario(
        type="historical",
        parameters={"key": "2008-gfc"},
        start_date=date(2008, 9, 1),
        end_date=date(2009, 3, 31),
    )

    definition = scenario_executor.build_historical_definition(scenario)

    assert definition.key == "2008-gfc"
    assert definition.start_date == date(2008, 9, 1)
    assert definition.end_date == date(2009, 3, 31)


def test_json_safe_handles_nan_inf_and_timestamps() -> None:
    assert serialization.json_safe(float("nan")) is None
    assert serialization.json_safe(np.inf) is None
    assert serialization.json_safe(np.int64(3)) == 3
    assert serialization.json_safe(pd.Timestamp("2020-03-23")) == "2020-03-23"
    assert serialization.json_safe({"a": np.float64(1.5), "b": [np.int64(2)]}) == {"a": 1.5, "b": [2]}


def test_frame_to_records_promotes_datetime_index() -> None:
    frame = pd.DataFrame({"value": [1.0, 2.0]}, index=pd.date_range("2020-01-01", periods=2, name="date"))

    records = serialization.frame_to_records(frame, index_name="date")

    assert records == [{"date": "2020-01-01", "value": 1.0}, {"date": "2020-01-02", "value": 2.0}]


def test_matrix_to_payload_builds_labelled_heatmap() -> None:
    frame = pd.DataFrame([[1.0, 0.5], [0.5, 1.0]], index=["A", "B"], columns=["A", "B"])

    payload = serialization.matrix_to_payload(frame)

    assert payload["labels"] == ["A", "B"]
    assert payload["matrix"] == [[1.0, 0.5], [0.5, 1.0]]


def test_matrix_to_payload_sanitizes_nan_cells() -> None:
    frame = pd.DataFrame([[1.0, math.nan], [math.nan, 1.0]], index=["A", "B"], columns=["A", "B"])

    payload = serialization.matrix_to_payload(frame)

    assert payload["matrix"][0][1] is None


class _FakeFetcher:
    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self.frames = frames

    def fetch(self, ticker: str, start_date, end_date) -> FetchResult:
        frame = self.frames.get(ticker)
        if frame is None or frame.empty:
            return FetchResult(data=pd.DataFrame(columns=["adj_close"]), source="fake", cache_hit=False, warnings=[])
        sliced = frame.loc[(frame.index >= pd.Timestamp(start_date)) & (frame.index <= pd.Timestamp(end_date))].copy()
        return FetchResult(data=sliced, source="fake", cache_hit=False, warnings=[])


def _prices(returns: list[float], initial: float = 100.0) -> list[float]:
    levels = [initial]
    for r in returns:
        levels.append(levels[-1] * (1.0 + r))
    return levels


def test_serialize_real_historical_engine_output_is_json_safe() -> None:
    """The real engine's DataFrame shapes must round-trip through the serializer."""

    index = pd.date_range("2020-02-17", periods=6, freq="D", name="date")
    frames = {
        "AAPL": pd.DataFrame({"adj_close": _prices([0.02, 0.01, -0.10, -0.05, 0.02])}, index=index),
        "TLT": pd.DataFrame({"adj_close": _prices([0.01, 0.00, 0.03, 0.02, -0.01])}, index=index),
        "SPY": pd.DataFrame({"adj_close": _prices([0.02, 0.01, -0.10, -0.05, 0.02])}, index=index),
        "BND": pd.DataFrame({"adj_close": _prices([0.01, 0.00, 0.03, 0.02, -0.01])}, index=index),
    }
    runner = HistoricalScenarioRunner(historical_data_fetcher=_FakeFetcher(frames), correlation_window=2)
    scenario = HistoricalScenarioDefinition(
        key="mini",
        name="Mini window",
        start_date=date(2020, 2, 20),
        end_date=date(2020, 2, 22),
        description="test",
    )
    holdings = [
        PortfolioHolding(ticker="AAPL", quantity=1, sector="Technology", asset_class="Equity", market_value=600.0, weight=0.6),
        PortfolioHolding(ticker="TLT", quantity=1, sector="Fixed Income", asset_class="Treasury ETF", market_value=400.0, weight=0.4),
    ]

    result = runner.run_scenario(holdings=holdings, scenario=scenario)
    payload = serialization.serialize_historical_result(result)

    assert payload["type"] == "historical"
    assert payload["portfolio_path"]
    assert all(isinstance(row["date"], str) for row in payload["portfolio_path"])
    assert payload["correlation_during"]["labels"] == ["AAPL", "TLT"]
    # the whole payload must be JSON-serializable (no NaN/Timestamp/numpy leaks)
    import json

    json.dumps(payload)
