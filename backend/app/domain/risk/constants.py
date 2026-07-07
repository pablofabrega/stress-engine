from app.domain.instrument_reference import FIXED_INCOME_DURATIONS

__all__ = [
    "DEFAULT_HEDGE_COST_BPS",
    "EQUITY_RATE_SENSITIVITY",
    "FIXED_INCOME_DURATIONS",
    "VIX_POSITIVE_TICKERS",
]

DEFAULT_HEDGE_COST_BPS = {
    "GLD": 40.0,
    "SH": 90.0,
    "TIP": 19.0,
    "TLT": 15.0,
    "XLU": 9.0,
    "QQQ": 20.0,
    "LQD": 14.0,
    "Cash / T-Bills": 5.0,
}

EQUITY_RATE_SENSITIVITY = {
    "Technology": 12.0,
    "Consumer Discretionary": 10.0,
    "Real Estate": 14.0,
    "Utilities": 7.0,
    "Consumer Staples": 6.0,
    "Broad Market": 8.5,
    "International Equity": 8.0,
    "Defensive Equity": 6.0,
    "Energy": 5.0,
    "Unknown": 8.0,
}

VIX_POSITIVE_TICKERS = {"VIXY", "UVXY", "VXX"}

