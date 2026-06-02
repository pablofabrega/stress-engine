from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from app.domain.data.models import FetchResult
from app.domain.portfolio.models import PortfolioHolding
from app.domain.risk.similar_periods import SimilarPeriodsFinder


class FakeHistoricalDataFetcher:
    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self.frames = frames

    def fetch(self, ticker: str, start_date: date, end_date: date) -> FetchResult:
        frame = self.frames.get(ticker)
        if frame is None or frame.empty:
            return FetchResult(
                data=pd.DataFrame(columns=["adj_close"]), source="fake", cache_hit=False, warnings=[]
            )
        sliced = frame.loc[(frame.index >= pd.Timestamp(start_date)) & (frame.index <= pd.Timestamp(end_date))].copy()
        return FetchResult(data=sliced, source="fake", cache_hit=False, warnings=[])


class FakeMacroDataFetcher:
    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame

    def fetch_default_macro_bundle(self, start_date: date, end_date: date) -> pd.DataFrame:
        return self.frame.loc[(self.frame.index >= pd.Timestamp(start_date)) & (self.frame.index <= pd.Timestamp(end_date))].copy()


def test_similar_periods_finder_returns_ranked_windows() -> None:
    index = pd.date_range("2024-01-01", periods=12, freq="D", name="date")
    spy = pd.DataFrame({"adj_close": [100, 99, 97, 95, 96, 98, 97, 95, 93, 92, 94, 96]}, index=index)
    bnd = pd.DataFrame({"adj_close": [100, 100.2, 100.1, 100.0, 99.9, 100.1, 100.0, 99.8, 99.7, 99.6, 99.8, 100.0]}, index=index)
    macro = pd.DataFrame(
        {
            "10y_treasury_yield": [4.0, 4.02, 4.05, 4.10, 4.08, 4.06, 4.09, 4.14, 4.20, 4.25, 4.18, 4.12],
            "vix": [15, 16, 18, 22, 21, 19, 20, 24, 28, 30, 25, 20],
            "hy_credit_spread": [3.0, 3.05, 3.10, 3.30, 3.20, 3.15, 3.18, 3.40, 3.60, 3.75, 3.50, 3.30],
        },
        index=index,
    )
    finder = SimilarPeriodsFinder(
        historical_data_fetcher=FakeHistoricalDataFetcher({"SPY": spy, "BND": bnd, "AAPL": spy}),
        macro_data_fetcher=FakeMacroDataFetcher(macro),
    )
    holdings = [PortfolioHolding(ticker="AAPL", quantity=1, market_value=100.0, weight=1.0, sector="Technology", asset_class="Equity")]

    periods = finder.find(
        shock_vector={
            "equity_return": -0.05,
            "vol_change": 6.0,
            "rate_change_10y": 0.15,
            "credit_spread_change": 0.35,
            "equity_bond_correlation_shift": 0.10,
        },
        holdings=holdings,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 12),
        window_days=3,
        top_k=3,
    )

    assert len(periods) == 3
    assert periods[0].similarity_score >= periods[1].similarity_score >= periods[2].similarity_score
    assert periods[0].portfolio_return is not None


SPY_PRICES = [100, 99, 97, 95, 96, 98, 97, 95, 93, 92, 94, 96]
BND_PRICES = [100, 100.2, 100.1, 100.0, 99.9, 100.1, 100.0, 99.8, 99.7, 99.6, 99.8, 100.0]
MACRO = {
    "10y_treasury_yield": [4.0, 4.02, 4.05, 4.10, 4.08, 4.06, 4.09, 4.14, 4.20, 4.25, 4.18, 4.12],
    "vix": [15, 16, 18, 22, 21, 19, 20, 24, 28, 30, 25, 20],
    "hy_credit_spread": [3.0, 3.05, 3.10, 3.30, 3.20, 3.15, 3.18, 3.40, 3.60, 3.75, 3.50, 3.30],
}
SHOCK = {
    "equity_return": -0.05,
    "vol_change": 6.0,
    "rate_change_10y": 0.15,
    "credit_spread_change": 0.35,
    "equity_bond_correlation_shift": 0.10,
}


def _market_frames(periods: int = 12):
    index = pd.date_range("2024-01-01", periods=periods, freq="D", name="date")
    spy = pd.DataFrame({"adj_close": SPY_PRICES[:periods]}, index=index)
    bnd = pd.DataFrame({"adj_close": BND_PRICES[:periods]}, index=index)
    macro = pd.DataFrame({k: v[:periods] for k, v in MACRO.items()}, index=index)
    return spy, bnd, macro


def _finder(spy=None, bnd=None, macro=None) -> SimilarPeriodsFinder:
    default_spy, default_bnd, default_macro = _market_frames()
    spy = default_spy if spy is None else spy
    bnd = default_bnd if bnd is None else bnd
    macro = default_macro if macro is None else macro
    return SimilarPeriodsFinder(
        historical_data_fetcher=FakeHistoricalDataFetcher({"SPY": spy, "BND": bnd}),
        macro_data_fetcher=FakeMacroDataFetcher(macro),
    )


def _find(finder: SimilarPeriodsFinder, shock=None, **kwargs):
    params = {"start_date": date(2024, 1, 1), "end_date": date(2024, 1, 12), "window_days": 3}
    params.update(kwargs)
    return finder.find(shock_vector=SHOCK if shock is None else shock, **params)


def test_feature_vector_has_expected_keys_and_recomputable_equity_return() -> None:
    spy, _, _ = _market_frames()
    top = _find(_finder(), top_k=1)[0]

    assert set(top.feature_vector) == set(SimilarPeriodsFinder.FEATURE_ORDER)
    window = spy.loc[top.start_date : top.end_date, "adj_close"]
    expected = window.iloc[-1] / window.iloc[0] - 1.0
    assert top.feature_vector["equity_return"] == pytest.approx(expected)


def test_portfolio_return_is_none_without_holdings() -> None:
    periods = _find(_finder(), top_k=3)

    assert all(period.portfolio_return is None for period in periods)


def test_top_k_is_respected_and_capped_at_available_windows() -> None:
    finder = _finder()

    assert len(_find(finder, top_k=1)) == 1
    # window_days=3 over 11 return-rows yields 6 windows; requesting more returns all 6
    assert len(_find(finder, top_k=99)) == 6


def test_empty_price_data_returns_no_periods() -> None:
    finder = SimilarPeriodsFinder(
        historical_data_fetcher=FakeHistoricalDataFetcher({}),
        macro_data_fetcher=FakeMacroDataFetcher(_market_frames()[2]),
    )

    assert _find(finder) == []


def test_insufficient_history_returns_no_periods() -> None:
    # window_days * 2 exceeds available rows -> no windows can be built
    assert _find(_finder(), window_days=6) == []


def test_similarity_scores_are_within_cosine_range_and_descending() -> None:
    periods = _find(_finder(), top_k=6)

    scores = [period.similarity_score for period in periods]
    assert scores == sorted(scores, reverse=True)
    assert all(-1.0 - 1e-9 <= score <= 1.0 + 1e-9 for score in scores)


def test_outcome_narrative_reflects_window_features() -> None:
    periods = _find(_finder(), top_k=6)
    narratives = {period.start_date.date(): period.outcome_narrative for period in periods}

    # The 2024-01-07 window pairs a VIX jump with a correlation regime shift.
    assert "volatility rose sharply" in narratives[date(2024, 1, 7)]
    # The calmest window produces the muted fallback narrative.
    assert any("muted cross-asset adjustment" in narrative for narrative in narratives.values())


def test_shock_direction_changes_ranking() -> None:
    finder = _finder()
    base = _find(finder, shock=SHOCK, top_k=6)
    flipped = _find(finder, shock={k: -v for k, v in SHOCK.items()}, top_k=6)

    assert base[0].start_date != flipped[0].start_date


def test_results_are_deterministic() -> None:
    finder = _finder()
    first = _find(finder, top_k=3)
    second = _find(finder, top_k=3)

    assert [(p.start_date, p.end_date, p.similarity_score) for p in first] == [
        (p.start_date, p.end_date, p.similarity_score) for p in second
    ]
