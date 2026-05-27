from __future__ import annotations

from datetime import date

import pandas as pd
import statsmodels.api as sm

from app.domain.data.fama_french import FamaFrenchLoader
from app.domain.data.fetchers import HistoricalDataFetcher
from app.domain.data.returns import ReturnsCalculator
from app.domain.portfolio.models import (
    DV01Result,
    FactorDecompositionResult,
    PortfolioDV01Summary,
    PortfolioHolding,
    PortfolioReturnHistory,
)

FIXED_INCOME_DURATION_ESTIMATES: dict[str, float] = {
    "BND": 6.5,
    "TLT": 17.0,
    "IEF": 7.5,
    "SHY": 1.9,
    "AGG": 6.2,
    "TIPS": 7.0,
    "LQD": 8.5,
    "HYG": 3.8,
    "JNK": 3.5,
    "VCIT": 6.3,
    "VCSH": 2.8,
    "MUB": 5.8,
    "TIP": 6.9,
    "VGSH": 1.9,
    "VGIT": 5.2,
    "VGLT": 16.5,
    "GOVT": 6.0,
    "IGIB": 6.5,
    "IGSB": 2.6,
    "EMB": 7.2,
}


class PortfolioAnalytics:
    """Portfolio-level valuation and return analytics built from normalized holdings."""

    def __init__(
        self,
        historical_data_fetcher: HistoricalDataFetcher | None = None,
        fama_french_loader: FamaFrenchLoader | None = None,
    ) -> None:
        self.historical_data_fetcher = historical_data_fetcher or HistoricalDataFetcher()
        self.fama_french_loader = fama_french_loader or FamaFrenchLoader()

    def current_market_value(self, holdings: list[PortfolioHolding]) -> float:
        """Return the total marked-to-market value of the portfolio."""

        return float(sum(holding.market_value for holding in holdings))

    def holding_weights(self, holdings: list[PortfolioHolding]) -> dict[str, float]:
        """Return a ticker-to-weight mapping from normalized holdings."""

        return {holding.ticker: holding.weight for holding in holdings}

    def sector_weights(self, holdings: list[PortfolioHolding]) -> dict[str, float]:
        """Return sector aggregate weights from normalized holdings."""

        aggregates: dict[str, float] = {}
        for holding in holdings:
            aggregates[holding.sector] = aggregates.get(holding.sector, 0.0) + holding.weight
        return dict(sorted(aggregates.items(), key=lambda item: item[0]))

    def portfolio_return_history(
        self,
        holdings: list[PortfolioHolding],
        start_date: date,
        end_date: date,
    ) -> PortfolioReturnHistory:
        """
        Compute portfolio daily return history as the weighted sum of holding simple returns.

        Each holding's daily return is computed from adjusted close prices when available, otherwise close prices.
        """

        component_returns: list[pd.Series] = []
        effective_weights: dict[str, float] = {}
        warnings: list[str] = []

        for holding in holdings:
            result = self.historical_data_fetcher.fetch(holding.ticker, start_date=start_date, end_date=end_date)
            if result.data.empty:
                warnings.extend(result.warnings)
                continue

            price_column = "adj_close" if "adj_close" in result.data.columns else "close"
            series = ReturnsCalculator.simple_returns(result.data[price_column]).rename(holding.ticker)
            component_returns.append(series)
            effective_weights[holding.ticker] = holding.weight

        if not component_returns:
            empty_series = pd.Series(dtype=float, name="portfolio_return")
            empty_frame = pd.DataFrame()
            return PortfolioReturnHistory(
                portfolio_returns=empty_series,
                component_returns=empty_frame,
                weights_used={},
                warnings=warnings,
            )

        component_frame = pd.concat(component_returns, axis=1).sort_index()
        weight_series = pd.Series(effective_weights, dtype=float)
        weight_series = weight_series / weight_series.sum()
        component_frame = component_frame[weight_series.index]
        portfolio_returns = component_frame.mul(weight_series, axis=1).sum(axis=1, min_count=1)
        portfolio_returns.name = "portfolio_return"

        return PortfolioReturnHistory(
            portfolio_returns=portfolio_returns,
            component_returns=component_frame,
            weights_used=weight_series.to_dict(),
            warnings=warnings,
        )

    def factor_decomposition(
        self,
        holdings: list[PortfolioHolding],
        start_date: date,
        end_date: date,
    ) -> FactorDecompositionResult:
        """
        Estimate Fama-French 3-factor exposures from portfolio excess returns.

        The regression specification is:
        R_p,t - R_f,t = alpha + beta_m * (Mkt-RF)_t + beta_s * SMB_t + beta_v * HML_t + epsilon_t
        """

        return_history = self.portfolio_return_history(holdings, start_date=start_date, end_date=end_date)
        factors = self.fama_french_loader.load(start_date=start_date, end_date=end_date)
        return self.factor_decomposition_from_returns(
            portfolio_returns=return_history.portfolio_returns,
            fama_french_factors=factors,
            base_warnings=return_history.warnings,
        )

    def factor_decomposition_from_returns(
        self,
        portfolio_returns: pd.Series,
        fama_french_factors: pd.DataFrame,
        base_warnings: list[str] | None = None,
    ) -> FactorDecompositionResult:
        """
        Run OLS on aligned portfolio returns and Fama-French factors.

        Portfolio excess returns are regressed on market excess return, size, and value factors using ordinary
        least squares. Inputs are aligned by date intersection and rows with missing values are removed.
        """

        warnings = list(base_warnings or [])
        required_columns = {"mkt_rf", "smb", "hml", "rf"}
        missing_columns = required_columns.difference(fama_french_factors.columns)
        if missing_columns:
            raise ValueError(f"Fama-French factors are missing required columns: {', '.join(sorted(missing_columns))}.")

        aligned = pd.concat(
            [
                portfolio_returns.rename("portfolio_return"),
                fama_french_factors[["mkt_rf", "smb", "hml", "rf"]],
            ],
            axis=1,
            join="inner",
        ).dropna()

        if aligned.empty:
            warnings.append("No overlapping observations were available for factor decomposition.")
            return self._empty_factor_result(warnings=warnings)

        excess_returns = aligned["portfolio_return"] - aligned["rf"]
        design_matrix = sm.add_constant(aligned[["mkt_rf", "smb", "hml"]], has_constant="add")
        regression = sm.OLS(excess_returns, design_matrix).fit()

        return FactorDecompositionResult(
            alpha=float(regression.params.get("const", float("nan"))),
            alpha_t_stat=float(regression.tvalues.get("const", float("nan"))),
            market_beta=float(regression.params.get("mkt_rf", float("nan"))),
            market_beta_t_stat=float(regression.tvalues.get("mkt_rf", float("nan"))),
            smb_exposure=float(regression.params.get("smb", float("nan"))),
            smb_t_stat=float(regression.tvalues.get("smb", float("nan"))),
            hml_exposure=float(regression.params.get("hml", float("nan"))),
            hml_t_stat=float(regression.tvalues.get("hml", float("nan"))),
            r_squared=float(regression.rsquared),
            observations=int(regression.nobs),
            warnings=warnings,
        )

    def estimate_dv01(self, holdings: list[PortfolioHolding]) -> PortfolioDV01Summary:
        """
        Estimate DV01 for fixed-income holdings using a modified-duration approximation.

        DV01 (dollar value of one basis point) measures how much a bond's market
        value changes for a 1 bp parallel shift in yield:

            DV01 = market_value × modified_duration × 0.0001

        Duration estimates come from a static lookup table of common fixed-income
        ETFs. Holdings not recognized as fixed-income are skipped.
        """

        fi_asset_classes = {"Fixed Income ETF", "Credit ETF", "Treasury ETF", "Fixed Income"}
        results: list[DV01Result] = []
        warnings: list[str] = []

        for holding in holdings:
            if holding.asset_class not in fi_asset_classes:
                continue

            duration = FIXED_INCOME_DURATION_ESTIMATES.get(holding.ticker)
            if duration is None:
                warnings.append(
                    f"No duration estimate available for {holding.ticker}; using default 5.0 years."
                )
                duration = 5.0

            mv = holding.market_value
            dv01 = mv * duration * 0.0001
            results.append(
                DV01Result(
                    ticker=holding.ticker,
                    market_value=mv,
                    estimated_duration=duration,
                    dv01=dv01,
                )
            )

        total_dv01 = sum(r.dv01 for r in results)
        return PortfolioDV01Summary(holdings=results, total_dv01=total_dv01, warnings=warnings)

    def _empty_factor_result(self, warnings: list[str]) -> FactorDecompositionResult:
        return FactorDecompositionResult(
            alpha=float("nan"),
            alpha_t_stat=float("nan"),
            market_beta=float("nan"),
            market_beta_t_stat=float("nan"),
            smb_exposure=float("nan"),
            smb_t_stat=float("nan"),
            hml_exposure=float("nan"),
            hml_t_stat=float("nan"),
            r_squared=float("nan"),
            observations=0,
            warnings=warnings,
        )
