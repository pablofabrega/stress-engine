from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from app.domain.data.fetchers import HistoricalDataFetcher
from app.domain.portfolio.models import PortfolioHolding
from app.domain.risk.models import LiquidityAnalysisResult, LiquidityHoldingResult


class LiquidityRiskAnalyzer:
    """Estimate liquidation capacity and apply a liquidity haircut to stressed losses."""

    def __init__(self, historical_data_fetcher: HistoricalDataFetcher | None = None) -> None:
        self.historical_data_fetcher = historical_data_fetcher or HistoricalDataFetcher()

    def analyze(
        self,
        holdings: list[PortfolioHolding],
        stressed_losses: dict[str, float],
        as_of_date: date,
        participation_rates: tuple[float, float, float] = (0.10, 0.20, 0.30),
        haircut_multiplier: float = 0.02,
    ) -> LiquidityAnalysisResult:
        """
        Compute ADV-based liquidation metrics and apply haircuts to stressed losses.

        For losses with days-to-liquidate above five days at the 10% participation rate, the haircut is:
        (days_to_liquidate / 5) * haircut_multiplier * abs(stressed_loss).
        """

        lookback_start = as_of_date - timedelta(days=45)
        rows: list[LiquidityHoldingResult] = []
        warnings: list[str] = []

        for holding in holdings:
            result = self.historical_data_fetcher.fetch(holding.ticker, start_date=lookback_start, end_date=as_of_date)
            if result.data.empty or "volume" not in result.data.columns:
                warnings.extend(result.warnings or [f"No volume data returned for ticker {holding.ticker}."])
                adv = float("nan")
            else:
                volume = result.data["volume"].astype(float).dropna().tail(30)
                adv = float(volume.mean()) if not volume.empty else float("nan")

            stressed_loss = float(stressed_losses.get(holding.ticker, 0.0))
            quantity = float(holding.quantity)
            position_pct_adv = quantity / adv if pd.notna(adv) and adv > 0 else float("nan")
            days_10 = quantity / (adv * participation_rates[0]) if pd.notna(adv) and adv > 0 else float("nan")
            days_20 = quantity / (adv * participation_rates[1]) if pd.notna(adv) and adv > 0 else float("nan")
            days_30 = quantity / (adv * participation_rates[2]) if pd.notna(adv) and adv > 0 else float("nan")

            haircut = 0.0
            if stressed_loss < 0 and pd.notna(days_10) and days_10 > 5:
                haircut = (days_10 / 5.0) * haircut_multiplier * abs(stressed_loss)

            adjusted_loss = stressed_loss - haircut if stressed_loss < 0 else stressed_loss
            rows.append(
                LiquidityHoldingResult(
                    ticker=holding.ticker,
                    adv_30d=adv,
                    position_pct_adv=position_pct_adv,
                    days_to_liquidate_10pct=days_10,
                    days_to_liquidate_20pct=days_20,
                    days_to_liquidate_30pct=days_30,
                    stressed_loss_dollars=stressed_loss,
                    liquidity_haircut_dollars=haircut,
                    liquidity_adjusted_loss_dollars=adjusted_loss,
                )
            )

        holdings_ranked = sorted(
            rows,
            key=lambda item: item.days_to_liquidate_10pct if pd.notna(item.days_to_liquidate_10pct) else float("-inf"),
            reverse=True,
        )
        stressed_total = float(sum(item.stressed_loss_dollars for item in holdings_ranked))
        haircut_total = float(sum(item.liquidity_haircut_dollars for item in holdings_ranked))
        adjusted_total = float(sum(item.liquidity_adjusted_loss_dollars for item in holdings_ranked))

        return LiquidityAnalysisResult(
            holdings=holdings_ranked,
            stressed_loss_dollars=stressed_total,
            total_liquidity_haircut_dollars=haircut_total,
            liquidity_adjusted_loss_dollars=adjusted_total,
            warnings=warnings,
        )
