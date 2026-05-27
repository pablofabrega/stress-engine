from __future__ import annotations

from functools import lru_cache

import yfinance as yf

from app.domain.portfolio.models import SecurityMetadata

STATIC_SECURITY_METADATA: dict[str, SecurityMetadata] = {
    "AAPL": SecurityMetadata("AAPL", "Equity", "Technology", "static_lookup"),
    "AMZN": SecurityMetadata("AMZN", "Equity", "Consumer Discretionary", "static_lookup"),
    "BND": SecurityMetadata("BND", "Fixed Income ETF", "Fixed Income", "static_lookup"),
    "GLD": SecurityMetadata("GLD", "Commodity ETF", "Precious Metals", "static_lookup"),
    "HYG": SecurityMetadata("HYG", "Credit ETF", "Fixed Income", "static_lookup"),
    "IEMG": SecurityMetadata("IEMG", "Equity ETF", "International Equity", "static_lookup"),
    "JNK": SecurityMetadata("JNK", "Credit ETF", "Fixed Income", "static_lookup"),
    "LQD": SecurityMetadata("LQD", "Credit ETF", "Fixed Income", "static_lookup"),
    "MSFT": SecurityMetadata("MSFT", "Equity", "Technology", "static_lookup"),
    "NVDA": SecurityMetadata("NVDA", "Equity", "Technology", "static_lookup"),
    "QQQ": SecurityMetadata("QQQ", "Equity ETF", "Technology", "static_lookup"),
    "SH": SecurityMetadata("SH", "Inverse ETF", "Equity Hedge", "static_lookup"),
    "SPY": SecurityMetadata("SPY", "Equity ETF", "Broad Market", "static_lookup"),
    "TLT": SecurityMetadata("TLT", "Treasury ETF", "Fixed Income", "static_lookup"),
    "TIPS": SecurityMetadata("TIPS", "Treasury ETF", "Fixed Income", "static_lookup"),
    "VNQ": SecurityMetadata("VNQ", "Real Estate ETF", "Real Estate", "static_lookup"),
    "VTI": SecurityMetadata("VTI", "Equity ETF", "Broad Market", "static_lookup"),
    "VYD": SecurityMetadata("VYD", "Dividend ETF", "Defensive Equity", "static_lookup"),
    "XLP": SecurityMetadata("XLP", "Sector ETF", "Consumer Staples", "static_lookup"),
    "XLU": SecurityMetadata("XLU", "Sector ETF", "Utilities", "static_lookup"),
}


class SecurityMetadataResolver:
    """Resolve holding metadata via static lookup first, then yfinance fallback."""

    def __init__(self, use_yfinance_fallback: bool = True) -> None:
        self.use_yfinance_fallback = use_yfinance_fallback

    def resolve(self, ticker: str) -> SecurityMetadata:
        symbol = ticker.upper()
        if symbol in STATIC_SECURITY_METADATA:
            return STATIC_SECURITY_METADATA[symbol]

        if self.use_yfinance_fallback:
            metadata = self._resolve_with_yfinance(symbol)
            if metadata is not None:
                return metadata

        return SecurityMetadata(
            ticker=symbol,
            asset_class="Unknown",
            sector="Unknown",
            metadata_source="fallback_unknown",
        )

    @lru_cache(maxsize=256)
    def _resolve_with_yfinance(self, ticker: str) -> SecurityMetadata | None:
        try:
            info = yf.Ticker(ticker).info
        except Exception:
            return None

        if not info:
            return None

        sector = info.get("sectorDisp") or info.get("sector") or "Unknown"
        quote_type = str(info.get("quoteType", "")).lower()
        asset_class = self._infer_asset_class(quote_type=quote_type, sector=sector)
        return SecurityMetadata(
            ticker=ticker,
            asset_class=asset_class,
            sector=sector,
            metadata_source="yfinance_info",
        )

    def _infer_asset_class(self, quote_type: str, sector: str) -> str:
        if "etf" in quote_type:
            if sector == "Fixed Income":
                return "Fixed Income ETF"
            return "ETF"
        if quote_type in {"mutualfund", "fund"}:
            return "Fund"
        if quote_type in {"equity", "stock"}:
            return "Equity"
        if sector == "Fixed Income":
            return "Fixed Income"
        return "Unknown"

