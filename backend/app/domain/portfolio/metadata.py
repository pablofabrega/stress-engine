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
    # Common single-name equities (so manual entry resolves without a network call).
    "GOOGL": SecurityMetadata("GOOGL", "Equity", "Communication Services", "static_lookup"),
    "GOOG": SecurityMetadata("GOOG", "Equity", "Communication Services", "static_lookup"),
    "META": SecurityMetadata("META", "Equity", "Communication Services", "static_lookup"),
    "NFLX": SecurityMetadata("NFLX", "Equity", "Communication Services", "static_lookup"),
    "TSLA": SecurityMetadata("TSLA", "Equity", "Consumer Discretionary", "static_lookup"),
    "AVGO": SecurityMetadata("AVGO", "Equity", "Technology", "static_lookup"),
    "AMD": SecurityMetadata("AMD", "Equity", "Technology", "static_lookup"),
    "INTC": SecurityMetadata("INTC", "Equity", "Technology", "static_lookup"),
    "CRM": SecurityMetadata("CRM", "Equity", "Technology", "static_lookup"),
    "ADBE": SecurityMetadata("ADBE", "Equity", "Technology", "static_lookup"),
    "ORCL": SecurityMetadata("ORCL", "Equity", "Technology", "static_lookup"),
    "JPM": SecurityMetadata("JPM", "Equity", "Financials", "static_lookup"),
    "BAC": SecurityMetadata("BAC", "Equity", "Financials", "static_lookup"),
    "V": SecurityMetadata("V", "Equity", "Financials", "static_lookup"),
    "MA": SecurityMetadata("MA", "Equity", "Financials", "static_lookup"),
    "BRK-B": SecurityMetadata("BRK-B", "Equity", "Financials", "static_lookup"),
    "JNJ": SecurityMetadata("JNJ", "Equity", "Healthcare", "static_lookup"),
    "UNH": SecurityMetadata("UNH", "Equity", "Healthcare", "static_lookup"),
    "LLY": SecurityMetadata("LLY", "Equity", "Healthcare", "static_lookup"),
    "PFE": SecurityMetadata("PFE", "Equity", "Healthcare", "static_lookup"),
    "XOM": SecurityMetadata("XOM", "Equity", "Energy", "static_lookup"),
    "CVX": SecurityMetadata("CVX", "Equity", "Energy", "static_lookup"),
    "WMT": SecurityMetadata("WMT", "Equity", "Consumer Staples", "static_lookup"),
    "PG": SecurityMetadata("PG", "Equity", "Consumer Staples", "static_lookup"),
    "KO": SecurityMetadata("KO", "Equity", "Consumer Staples", "static_lookup"),
    "PEP": SecurityMetadata("PEP", "Equity", "Consumer Staples", "static_lookup"),
    "COST": SecurityMetadata("COST", "Equity", "Consumer Staples", "static_lookup"),
    "HD": SecurityMetadata("HD", "Equity", "Consumer Discretionary", "static_lookup"),
    "DIS": SecurityMetadata("DIS", "Equity", "Communication Services", "static_lookup"),
    # Common ETFs.
    "VOO": SecurityMetadata("VOO", "Equity ETF", "Broad Market", "static_lookup"),
    "IVV": SecurityMetadata("IVV", "Equity ETF", "Broad Market", "static_lookup"),
    "VEA": SecurityMetadata("VEA", "Equity ETF", "International Equity", "static_lookup"),
    "VWO": SecurityMetadata("VWO", "Equity ETF", "International Equity", "static_lookup"),
    "AGG": SecurityMetadata("AGG", "Fixed Income ETF", "Fixed Income", "static_lookup"),
    "SCHD": SecurityMetadata("SCHD", "Dividend ETF", "Defensive Equity", "static_lookup"),
    "IWM": SecurityMetadata("IWM", "Equity ETF", "Broad Market", "static_lookup"),
    "DIA": SecurityMetadata("DIA", "Equity ETF", "Broad Market", "static_lookup"),
    "SLV": SecurityMetadata("SLV", "Commodity ETF", "Precious Metals", "static_lookup"),
    "XLF": SecurityMetadata("XLF", "Sector ETF", "Financials", "static_lookup"),
    "XLK": SecurityMetadata("XLK", "Sector ETF", "Technology", "static_lookup"),
    "XLE": SecurityMetadata("XLE", "Sector ETF", "Energy", "static_lookup"),
    "XLV": SecurityMetadata("XLV", "Sector ETF", "Healthcare", "static_lookup"),
    "XLY": SecurityMetadata("XLY", "Sector ETF", "Consumer Discretionary", "static_lookup"),
    "XLI": SecurityMetadata("XLI", "Sector ETF", "Industrials", "static_lookup"),
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

