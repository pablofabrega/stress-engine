from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.domain.data.fetchers import HistoricalDataFetcher, MacroDataFetcher
from app.domain.data.returns import ReturnsCalculator
from app.domain.portfolio.analytics import PortfolioAnalytics
from app.domain.portfolio.models import PortfolioHolding
from app.domain.risk.models import SimilarHistoricalPeriod


class SimilarPeriodsFinder:
    """Find the nearest historical 30-day periods to a hypothetical shock vector."""

    FEATURE_ORDER = [
        "equity_return",
        "vol_change",
        "rate_change_10y",
        "credit_spread_change",
        "equity_bond_correlation_shift",
    ]

    def __init__(
        self,
        historical_data_fetcher: HistoricalDataFetcher | None = None,
        macro_data_fetcher: MacroDataFetcher | None = None,
        portfolio_analytics: PortfolioAnalytics | None = None,
    ) -> None:
        self.historical_data_fetcher = historical_data_fetcher or HistoricalDataFetcher()
        self.macro_data_fetcher = macro_data_fetcher or MacroDataFetcher()
        self.portfolio_analytics = portfolio_analytics or PortfolioAnalytics(historical_data_fetcher=self.historical_data_fetcher)

    def find(
        self,
        shock_vector: dict[str, float],
        holdings: list[PortfolioHolding] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        window_days: int = 30,
        top_k: int = 3,
    ) -> list[SimilarHistoricalPeriod]:
        """
        Rank historical windows by cosine similarity against a z-scored shock feature vector.

        Each historical window is represented by:
        [equity_return, vol_change, rate_change_10y, credit_spread_change, equity_bond_correlation_shift].
        """

        end_date = end_date or date.today()
        start_date = start_date or (end_date - timedelta(days=365 * 10))

        market = self._build_market_frame(start_date=start_date, end_date=end_date)
        features = self._historical_feature_windows(market=market, window_days=window_days)
        if features.empty:
            return []

        feature_frame = features[self.FEATURE_ORDER]
        means = feature_frame.mean()
        stds = feature_frame.std(ddof=0).replace(0.0, 1.0)
        z_features = (feature_frame - means) / stds
        shock_series = pd.Series({name: float(shock_vector.get(name, 0.0)) for name in self.FEATURE_ORDER}, dtype=float)
        z_shock = (shock_series - means) / stds
        shock_norm = float(np.linalg.norm(z_shock.values))
        if shock_norm == 0:
            z_shock = pd.Series(np.zeros(len(self.FEATURE_ORDER)), index=self.FEATURE_ORDER)
            shock_norm = 1.0

        feature_norms = np.linalg.norm(z_features.values, axis=1)
        similarities = z_features.values @ z_shock.values / (feature_norms * shock_norm + 1e-12)
        ranked = features.assign(similarity_score=similarities).sort_values("similarity_score", ascending=False).head(top_k)

        results: list[SimilarHistoricalPeriod] = []
        for _, row in ranked.iterrows():
            portfolio_return = None
            if holdings:
                return_history = self.portfolio_analytics.portfolio_return_history(
                    holdings=holdings,
                    start_date=row["start_date"].date(),
                    end_date=row["end_date"].date(),
                )
                if not return_history.portfolio_returns.dropna().empty:
                    portfolio_return = float((1.0 + return_history.portfolio_returns.dropna()).prod() - 1.0)

            results.append(
                SimilarHistoricalPeriod(
                    start_date=row["start_date"],
                    end_date=row["end_date"],
                    similarity_score=float(row["similarity_score"]),
                    feature_vector={name: float(row[name]) for name in self.FEATURE_ORDER},
                    portfolio_return=portfolio_return,
                    outcome_narrative=self._narrative(row),
                )
            )

        return results

    def _build_market_frame(self, start_date: date, end_date: date) -> pd.DataFrame:
        spy = self.historical_data_fetcher.fetch("SPY", start_date=start_date, end_date=end_date)
        bnd = self.historical_data_fetcher.fetch("BND", start_date=start_date, end_date=end_date)
        macro = self.macro_data_fetcher.fetch_default_macro_bundle(start_date=start_date, end_date=end_date)

        frames: list[pd.DataFrame] = []
        for label, result in [("spy_price", spy), ("bnd_price", bnd)]:
            if result.data.empty:
                continue
            price_column = "adj_close" if "adj_close" in result.data.columns else "close"
            frames.append(result.data[[price_column]].rename(columns={price_column: label}))

        if not frames:
            return pd.DataFrame()

        market = pd.concat(frames + [macro], axis=1).sort_index()
        market = market.ffill().dropna()
        market["spy_return"] = ReturnsCalculator.simple_returns(market["spy_price"])
        market["bnd_return"] = ReturnsCalculator.simple_returns(market["bnd_price"])
        return market.dropna(subset=["spy_return", "bnd_return"])

    def _historical_feature_windows(self, market: pd.DataFrame, window_days: int) -> pd.DataFrame:
        if market.empty or len(market) < window_days * 2:
            return pd.DataFrame()

        rows: list[dict[str, object]] = []
        for end_idx in range(window_days * 2 - 1, len(market)):
            prev_window = market.iloc[end_idx - window_days * 2 + 1 : end_idx - window_days + 1]
            window = market.iloc[end_idx - window_days + 1 : end_idx + 1]
            assert prev_window.index.max() < window.index.min(), "Lookahead assertion failed for similar-period feature construction."

            window_corr = window[["spy_return", "bnd_return"]].corr().iloc[0, 1]
            prev_corr = prev_window[["spy_return", "bnd_return"]].corr().iloc[0, 1]
            rows.append(
                {
                    "start_date": window.index[0],
                    "end_date": window.index[-1],
                    "equity_return": float(window["spy_price"].iloc[-1] / window["spy_price"].iloc[0] - 1.0),
                    "vol_change": float(window["vix"].iloc[-1] - window["vix"].iloc[0]) if "vix" in window.columns else 0.0,
                    "rate_change_10y": float(window["10y_treasury_yield"].iloc[-1] - window["10y_treasury_yield"].iloc[0])
                    if "10y_treasury_yield" in window.columns
                    else 0.0,
                    "credit_spread_change": float(window["hy_credit_spread"].iloc[-1] - window["hy_credit_spread"].iloc[0])
                    if "hy_credit_spread" in window.columns
                    else 0.0,
                    "equity_bond_correlation_shift": float(window_corr - prev_corr),
                }
            )

        return pd.DataFrame(rows)

    def _narrative(self, row: pd.Series) -> str:
        parts: list[str] = []
        if row["equity_return"] < -0.05:
            parts.append("equities sold off materially")
        if row["vol_change"] > 5:
            parts.append("volatility rose sharply")
        if row["rate_change_10y"] > 0.25:
            parts.append("rates repriced higher")
        elif row["rate_change_10y"] < -0.25:
            parts.append("rates rallied lower")
        if row["credit_spread_change"] > 0.50:
            parts.append("credit spreads widened")
        if abs(row["equity_bond_correlation_shift"]) > 0.20:
            parts.append("equity-bond correlation regime shifted")
        if not parts:
            return "The window resembled a muted cross-asset adjustment with limited regime stress."
        return "During this window, " + ", ".join(parts) + "."
