from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from io import StringIO, TextIOBase
from pathlib import Path

import pandas as pd

from app.domain.data.fetchers import HistoricalDataFetcher
from app.domain.portfolio.metadata import SecurityMetadataResolver
from app.domain.portfolio.models import PortfolioHolding, PortfolioLoadResult
from app.domain.portfolio.presets import get_preset_portfolio


class PortfolioLoader:
    """Load and normalize portfolios from JSON payloads, CSV files, or preset definitions."""

    def __init__(
        self,
        metadata_resolver: SecurityMetadataResolver | None = None,
        historical_data_fetcher: HistoricalDataFetcher | None = None,
    ) -> None:
        self.metadata_resolver = metadata_resolver or SecurityMetadataResolver()
        self.historical_data_fetcher = historical_data_fetcher or HistoricalDataFetcher()

    def load_from_json(self, name: str, holdings_payload: Mapping[str, Mapping[str, float | None]]) -> PortfolioLoadResult:
        normalized_rows = [
            {
                "ticker": ticker.upper(),
                "quantity": float(payload["quantity"]),
                "cost_basis": self._optional_float(payload.get("cost_basis")),
            }
            for ticker, payload in holdings_payload.items()
        ]
        frame = pd.DataFrame(normalized_rows)
        return self._build_portfolio(name=name, holdings_frame=frame)

    def load_from_csv(self, name: str, csv_source: str | Path | TextIOBase) -> PortfolioLoadResult:
        frame = self._read_csv(csv_source)
        required_columns = {"ticker", "quantity"}
        missing_columns = required_columns.difference(frame.columns.str.lower())
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"CSV is missing required columns: {missing}.")

        lower_columns = {column.lower(): column for column in frame.columns}
        normalized = pd.DataFrame(
            {
                "ticker": frame[lower_columns["ticker"]].astype(str).str.upper().str.strip(),
                "quantity": frame[lower_columns["quantity"]].astype(float),
                "cost_basis": frame[lower_columns["cost_basis"]].astype(float)
                if "cost_basis" in lower_columns
                else pd.Series([pd.NA] * len(frame), dtype="float64"),
            }
        )
        return self._build_portfolio(name=name, holdings_frame=normalized)

    def load_preset(self, preset_key: str, total_notional: float = 1_000_000.0) -> PortfolioLoadResult:
        preset = get_preset_portfolio(preset_key)
        pricing_end = date.today()
        pricing_start = pricing_end - timedelta(days=14)

        rows: list[dict[str, float | None | str]] = []
        warnings: list[str] = []
        for ticker, target_weight in preset.target_weights.items():
            latest_price, warning = self._resolve_latest_price(ticker=ticker, start_date=pricing_start, end_date=pricing_end)
            if warning:
                warnings.append(warning)
            price_basis = latest_price or 100.0
            quantity = (total_notional * target_weight) / price_basis
            rows.append({"ticker": ticker, "quantity": quantity, "cost_basis": latest_price})

        result = self._build_portfolio(name=preset.name, holdings_frame=pd.DataFrame(rows))
        result.warnings.extend(warnings)
        return result

    def _build_portfolio(self, name: str, holdings_frame: pd.DataFrame) -> PortfolioLoadResult:
        cleaned = holdings_frame.copy()
        cleaned["ticker"] = cleaned["ticker"].astype(str).str.upper().str.strip()
        cleaned["quantity"] = cleaned["quantity"].astype(float)
        cleaned["cost_basis"] = cleaned["cost_basis"].astype(float)

        if (cleaned["quantity"] <= 0).any():
            raise ValueError("All holding quantities must be positive.")

        aggregated = self._aggregate_duplicate_tickers(cleaned)
        pricing_end = date.today()
        pricing_start = pricing_end - timedelta(days=14)

        holdings: list[PortfolioHolding] = []
        warnings: list[str] = []
        estimated_notionals: dict[str, float] = {}

        for row in aggregated.to_dict(orient="records"):
            ticker = str(row["ticker"])
            metadata = self.metadata_resolver.resolve(ticker)
            latest_price, warning = self._resolve_latest_price(ticker=ticker, start_date=pricing_start, end_date=pricing_end)
            if warning:
                warnings.append(warning)
            quantity = float(row["quantity"])
            cost_basis = self._optional_float(row.get("cost_basis"))

            market_value = quantity * latest_price if latest_price is not None else 0.0
            estimated_notional = self._estimate_notional(quantity=quantity, current_price=latest_price, cost_basis=cost_basis)
            estimated_notionals[ticker] = estimated_notional
            holdings.append(
                PortfolioHolding(
                    ticker=ticker,
                    quantity=quantity,
                    cost_basis=cost_basis,
                    asset_class=metadata.asset_class,
                    sector=metadata.sector,
                    current_price=latest_price,
                    market_value=market_value,
                    metadata_source=metadata.metadata_source,
                    price_source="market_data" if latest_price is not None else "estimated",
                )
            )

        total_market_value = sum(holding.market_value for holding in holdings)
        total_estimated_notional = sum(estimated_notionals.values())

        for holding in holdings:
            denominator = total_market_value if total_market_value > 0 else total_estimated_notional
            if denominator <= 0:
                holding.weight = 0.0
                continue
            numerator = holding.market_value if total_market_value > 0 else estimated_notionals[holding.ticker]
            holding.weight = numerator / denominator

        sector_weights = self._compute_sector_weights(holdings)
        return PortfolioLoadResult(
            name=name,
            holdings=holdings,
            total_market_value=total_market_value,
            sector_weights=sector_weights,
            warnings=warnings,
        )

    def _read_csv(self, csv_source: str | Path | TextIOBase) -> pd.DataFrame:
        if isinstance(csv_source, TextIOBase):
            return pd.read_csv(csv_source)
        path = Path(csv_source)
        if path.exists():
            return pd.read_csv(path)
        return pd.read_csv(StringIO(str(csv_source)))

    def _aggregate_duplicate_tickers(self, holdings_frame: pd.DataFrame) -> pd.DataFrame:
        def weighted_cost_basis(group: pd.DataFrame) -> float | None:
            valid = group.dropna(subset=["cost_basis"])
            if valid.empty:
                return None
            return float((valid["quantity"] * valid["cost_basis"]).sum() / valid["quantity"].sum())

        aggregated = (
            holdings_frame.groupby("ticker", as_index=False)
            .agg(quantity=("quantity", "sum"))
            .merge(
                holdings_frame.groupby("ticker").apply(weighted_cost_basis, include_groups=False).rename("cost_basis"),
                on="ticker",
                how="left",
            )
        )
        return aggregated.sort_values("ticker").reset_index(drop=True)

    def _resolve_latest_price(self, ticker: str, start_date: date, end_date: date) -> tuple[float | None, str | None]:
        result = self.historical_data_fetcher.fetch(ticker=ticker, start_date=start_date, end_date=end_date)
        if result.data.empty:
            warning = result.warnings[0] if result.warnings else f"No market data found for ticker {ticker}."
            return None, warning

        price_column = "adj_close" if "adj_close" in result.data.columns else "close"
        latest_price = float(result.data[price_column].dropna().iloc[-1])
        return latest_price, None

    def _estimate_notional(self, quantity: float, current_price: float | None, cost_basis: float | None) -> float:
        reference_price = current_price or cost_basis or 1.0
        return quantity * reference_price

    def _compute_sector_weights(self, holdings: list[PortfolioHolding]) -> dict[str, float]:
        sector_weights: dict[str, float] = {}
        for holding in holdings:
            sector_weights[holding.sector] = sector_weights.get(holding.sector, 0.0) + holding.weight
        return dict(sorted(sector_weights.items(), key=lambda item: item[0]))

    def _optional_float(self, value: object) -> float | None:
        if value is None or pd.isna(value):
            return None
        return float(value)

