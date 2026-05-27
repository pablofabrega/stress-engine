from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from app.domain.data.fetchers import HistoricalDataFetcher
from app.domain.portfolio.models import PortfolioHolding
from app.domain.risk.constants import DEFAULT_HEDGE_COST_BPS, FIXED_INCOME_DURATIONS
from app.domain.risk.models import HedgeSuggestion, RiskAnalyticsResult


class HedgeSuggestionEngine:
    """Generate explainable hedge suggestions from portfolio risk metrics and scenario results."""

    def __init__(self, historical_data_fetcher: HistoricalDataFetcher | None = None) -> None:
        self.historical_data_fetcher = historical_data_fetcher or HistoricalDataFetcher()

    def suggest(
        self,
        holdings: list[PortfolioHolding],
        risk_summary: RiskAnalyticsResult,
        scenario_result=None,
        as_of_date: date | None = None,
    ) -> list[HedgeSuggestion]:
        portfolio_value = float(sum(self._base_position_value(holding) for holding in holdings))
        if portfolio_value <= 0:
            return []

        suggestions: list[HedgeSuggestion] = []
        market_beta = risk_summary.factor_exposure_summary.market_beta
        tech_weight = sum(holding.weight for holding in holdings if holding.sector == "Technology")
        credit_weight = sum(holding.weight for holding in holdings if holding.ticker.upper() in {"HYG", "JNK"})
        duration_dv01 = self._portfolio_dv01(holdings)

        if np.isfinite(market_beta) and market_beta > 1.1:
            hedge_ratio = market_beta - 1.0
            effectiveness = self._inverse_equity_effectiveness(
                instrument="SH",
                hedge_ratio=hedge_ratio,
                portfolio_value=portfolio_value,
                scenario_result=scenario_result,
            )
            suggestions.append(
                HedgeSuggestion(
                    instrument="SH",
                    rationale="Your portfolio beta is above 1.1, so an inverse equity hedge offsets the excess broad-market sensitivity.",
                    severity="high" if market_beta > 1.3 else "medium",
                    hedge_ratio=hedge_ratio,
                    hedge_ratio_steps=[
                        f"Portfolio market beta = {market_beta:.2f}.",
                        "Target the excess beta above 1.00 rather than fully neutralizing all market exposure.",
                        f"Excess beta hedge ratio = {market_beta:.2f} - 1.00 = {hedge_ratio:.2f}.",
                    ],
                    estimated_annual_cost_bps=DEFAULT_HEDGE_COST_BPS["SH"],
                    historical_effectiveness=effectiveness,
                    weakness_citation=f"Market beta is {market_beta:.2f}, which implies amplified losses in broad equity selloffs.",
                )
            )

        if abs(duration_dv01) > portfolio_value * 0.00035:
            hedge_ratio = duration_dv01 / (portfolio_value * FIXED_INCOME_DURATIONS["TLT"] * 0.0001)
            effectiveness = self._short_duration_effectiveness(
                instrument="TLT",
                hedge_ratio=hedge_ratio,
                portfolio_value=portfolio_value,
                scenario_result=scenario_result,
            )
            suggestions.append(
                HedgeSuggestion(
                    instrument="TLT",
                    rationale="The portfolio carries meaningful rate sensitivity, so a duration hedge can offset losses when yields rise.",
                    severity="high" if abs(duration_dv01) > portfolio_value * 0.0006 else "medium",
                    hedge_ratio=hedge_ratio,
                    hedge_ratio_steps=[
                        f"Portfolio DV01 = {duration_dv01:.4f} dollars per 1 bp move.",
                        f"TLT DV01 per dollar of notional is approximately {FIXED_INCOME_DURATIONS['TLT'] * 0.0001:.6f}.",
                        f"Hedge ratio = portfolio DV01 / hedge DV01 per dollar / portfolio value = {hedge_ratio:.2f}.",
                    ],
                    estimated_annual_cost_bps=DEFAULT_HEDGE_COST_BPS["TLT"],
                    historical_effectiveness=effectiveness,
                    weakness_citation="Long-duration fixed-income exposure is large enough to materially hurt the portfolio in a rate shock.",
                )
            )

        if tech_weight > 0.40:
            hedge_ratio = tech_weight
            effectiveness = self._inverse_equity_effectiveness(
                instrument="QQQ",
                hedge_ratio=hedge_ratio,
                portfolio_value=portfolio_value,
                scenario_result=scenario_result,
                inverse=False,
            )
            suggestions.append(
                HedgeSuggestion(
                    instrument="QQQ",
                    rationale="Technology concentration above 40% leaves the portfolio exposed to a single growth style regime.",
                    severity="high",
                    hedge_ratio=hedge_ratio,
                    hedge_ratio_steps=[
                        f"Technology weight = {tech_weight:.2%}.",
                        "Use the concentrated sector weight as the first-pass hedge notional ratio.",
                        f"Sector beta offset ratio = {tech_weight:.2f}.",
                    ],
                    estimated_annual_cost_bps=DEFAULT_HEDGE_COST_BPS["QQQ"],
                    historical_effectiveness=effectiveness,
                    weakness_citation=f"Technology concentration is {tech_weight:.2%}, above the 40% trigger threshold.",
                )
            )

        if credit_weight > 0.10:
            hedge_ratio = credit_weight
            effectiveness = self._credit_rotation_effectiveness(
                hedge_ratio=hedge_ratio,
                portfolio_value=portfolio_value,
                scenario_result=scenario_result,
            )
            suggestions.append(
                HedgeSuggestion(
                    instrument="LQD",
                    rationale="High-yield exposure makes the portfolio vulnerable to spread widening, so rotating or hedging into investment grade can reduce credit beta.",
                    severity="medium",
                    hedge_ratio=hedge_ratio,
                    hedge_ratio_steps=[
                        f"High-yield sleeve weight = {credit_weight:.2%}.",
                        "Use the full high-yield sleeve as the first-pass hedge or rotation amount.",
                        f"Credit hedge ratio = {hedge_ratio:.2f}.",
                    ],
                    estimated_annual_cost_bps=DEFAULT_HEDGE_COST_BPS["LQD"],
                    historical_effectiveness=effectiveness,
                    weakness_citation=f"HYG/JNK exposure is {credit_weight:.2%}, creating direct spread risk.",
                )
            )

        if np.isfinite(risk_summary.cvar_95) and np.isfinite(risk_summary.latest_rolling_vol) and risk_summary.cvar_95 > 0.02:
            cash_buffer = min(max((risk_summary.cvar_95 / max(risk_summary.latest_rolling_vol**2, 1e-6)) * 0.01, 0.05), 0.25)
            avoided_loss = None
            if scenario_result is not None and not scenario_result.portfolio_path.empty:
                scenario_loss = abs(float(scenario_result.portfolio_path["pnl_dollars"].iloc[-1]))
                avoided_loss = (cash_buffer * scenario_loss) / scenario_loss if scenario_loss > 0 else None
            suggestions.append(
                HedgeSuggestion(
                    instrument="Cash / T-Bills",
                    rationale="Elevated CVaR indicates material tail risk, so a conservative Kelly-style cash buffer reduces exposure to the left tail.",
                    severity="medium",
                    hedge_ratio=cash_buffer,
                    hedge_ratio_steps=[
                        f"CVaR 95 = {risk_summary.cvar_95:.2%}.",
                        f"Latest rolling volatility = {risk_summary.latest_rolling_vol:.2%}.",
                        f"Conservative Kelly-style cash buffer = min(max(CVaR / vol^2 * 1%, 5%), 25%) = {cash_buffer:.2%}.",
                    ],
                    estimated_annual_cost_bps=DEFAULT_HEDGE_COST_BPS["Cash / T-Bills"],
                    historical_effectiveness=avoided_loss,
                    weakness_citation=f"CVaR 95 is {risk_summary.cvar_95:.2%}, indicating severe average losses in the worst tail outcomes.",
                )
            )

        return suggestions[:5]

    def _portfolio_dv01(self, holdings: list[PortfolioHolding]) -> float:
        total = 0.0
        for holding in holdings:
            duration = FIXED_INCOME_DURATIONS.get(holding.ticker.upper())
            if duration is None:
                continue
            total += self._base_position_value(holding) * duration * 0.0001
        return total

    def _inverse_equity_effectiveness(
        self,
        instrument: str,
        hedge_ratio: float,
        portfolio_value: float,
        scenario_result,
        inverse: bool = True,
    ) -> float | None:
        if scenario_result is None or scenario_result.comparison_path.empty:
            return None
        if "spy_cumulative_return" not in scenario_result.comparison_path.columns:
            return None
        benchmark_return = float(scenario_result.comparison_path["spy_cumulative_return"].iloc[-1])
        hedge_return = -benchmark_return if inverse else -benchmark_return
        offset = hedge_ratio * hedge_return * portfolio_value
        scenario_loss = abs(float(scenario_result.portfolio_path["pnl_dollars"].iloc[-1]))
        return offset / scenario_loss if scenario_loss > 0 else None

    def _short_duration_effectiveness(self, instrument: str, hedge_ratio: float, portfolio_value: float, scenario_result) -> float | None:
        if scenario_result is None:
            return None
        scenario = getattr(scenario_result, "scenario", None)
        if scenario is None:
            return None
        result = self.historical_data_fetcher.fetch(instrument, start_date=scenario.start_date, end_date=scenario.end_date)
        if result.data.empty:
            return None
        price_column = "adj_close" if "adj_close" in result.data.columns else "close"
        series = result.data[price_column].astype(float)
        hedge_return = float(series.iloc[-1] / series.iloc[0] - 1.0)
        offset = -hedge_ratio * hedge_return * portfolio_value
        scenario_loss = abs(float(scenario_result.portfolio_path["pnl_dollars"].iloc[-1]))
        return offset / scenario_loss if scenario_loss > 0 else None

    def _credit_rotation_effectiveness(self, hedge_ratio: float, portfolio_value: float, scenario_result) -> float | None:
        if scenario_result is None:
            return None
        scenario = getattr(scenario_result, "scenario", None)
        if scenario is None:
            return None
        lqd = self.historical_data_fetcher.fetch("LQD", start_date=scenario.start_date, end_date=scenario.end_date)
        hyg = self.historical_data_fetcher.fetch("HYG", start_date=scenario.start_date, end_date=scenario.end_date)
        if lqd.data.empty or hyg.data.empty:
            return None
        lqd_prices = lqd.data["adj_close" if "adj_close" in lqd.data.columns else "close"].astype(float)
        hyg_prices = hyg.data["adj_close" if "adj_close" in hyg.data.columns else "close"].astype(float)
        lqd_return = float(lqd_prices.iloc[-1] / lqd_prices.iloc[0] - 1.0)
        hyg_return = float(hyg_prices.iloc[-1] / hyg_prices.iloc[0] - 1.0)
        improvement = hedge_ratio * (lqd_return - hyg_return) * portfolio_value
        scenario_loss = abs(float(scenario_result.portfolio_path["pnl_dollars"].iloc[-1]))
        return improvement / scenario_loss if scenario_loss > 0 else None

    def _base_position_value(self, holding: PortfolioHolding) -> float:
        if holding.market_value > 0:
            return float(holding.market_value)
        reference_price = holding.current_price or holding.cost_basis or 1.0
        return float(holding.quantity * reference_price)

