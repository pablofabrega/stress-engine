from __future__ import annotations

import pytest

from app.domain.portfolio.metadata import STATIC_SECURITY_METADATA, SecurityMetadataResolver
from app.domain.portfolio.presets import PRESET_PORTFOLIOS, get_preset_portfolio, get_preset_portfolios


# ---------------------------------------------------------------------------
# SecurityMetadataResolver
# ---------------------------------------------------------------------------

class TestSecurityMetadataResolver:
    def test_static_lookup_for_known_ticker(self) -> None:
        resolver = SecurityMetadataResolver(use_yfinance_fallback=False)
        meta = resolver.resolve("AAPL")

        assert meta.ticker == "AAPL"
        assert meta.asset_class == "Equity"
        assert meta.sector == "Technology"
        assert meta.metadata_source == "static_lookup"

    def test_case_insensitive(self) -> None:
        resolver = SecurityMetadataResolver(use_yfinance_fallback=False)
        meta = resolver.resolve("aapl")
        assert meta.ticker == "AAPL"

    def test_unknown_ticker_returns_fallback(self) -> None:
        resolver = SecurityMetadataResolver(use_yfinance_fallback=False)
        meta = resolver.resolve("ZZZZZZ")

        assert meta.ticker == "ZZZZZZ"
        assert meta.asset_class == "Unknown"
        assert meta.sector == "Unknown"
        assert meta.metadata_source == "fallback_unknown"

    def test_all_preset_tickers_in_static_table(self) -> None:
        """Every ticker referenced in preset portfolios should have static metadata."""
        all_preset_tickers: set[str] = set()
        for preset in PRESET_PORTFOLIOS.values():
            all_preset_tickers.update(preset.target_weights.keys())

        for ticker in all_preset_tickers:
            assert ticker in STATIC_SECURITY_METADATA, f"{ticker} missing from static metadata table"

    def test_known_etf_classifications(self) -> None:
        resolver = SecurityMetadataResolver(use_yfinance_fallback=False)

        spy = resolver.resolve("SPY")
        assert spy.asset_class == "Equity ETF"

        bnd = resolver.resolve("BND")
        assert bnd.asset_class == "Fixed Income ETF"

        gld = resolver.resolve("GLD")
        assert gld.asset_class == "Commodity ETF"

        tlt = resolver.resolve("TLT")
        assert tlt.asset_class == "Treasury ETF"

    def test_static_table_completeness(self) -> None:
        expected = {"AAPL", "AMZN", "MSFT", "NVDA", "SPY", "BND", "TLT", "GLD", "HYG", "QQQ", "VTI"}
        for ticker in expected:
            assert ticker in STATIC_SECURITY_METADATA


# ---------------------------------------------------------------------------
# Preset portfolio definitions
# ---------------------------------------------------------------------------

class TestPresetPortfolios:
    def test_four_presets_exist(self) -> None:
        presets = get_preset_portfolios()
        assert len(presets) == 4

    def test_concentrated_tech(self) -> None:
        preset = get_preset_portfolio("concentrated-tech")
        assert preset.name == "Concentrated Tech"
        assert set(preset.target_weights.keys()) == {"AAPL", "NVDA", "MSFT", "AMZN"}
        assert sum(preset.target_weights.values()) == pytest.approx(1.0)

    def test_classic_60_40(self) -> None:
        preset = get_preset_portfolio("classic-60-40")
        assert set(preset.target_weights.keys()) == {"SPY", "BND"}
        assert preset.target_weights["SPY"] == pytest.approx(0.60)
        assert preset.target_weights["BND"] == pytest.approx(0.40)

    def test_growth_diversified(self) -> None:
        preset = get_preset_portfolio("growth-diversified")
        assert set(preset.target_weights.keys()) == {"QQQ", "VTI", "IEMG", "VNQ", "GLD", "TLT", "HYG"}
        assert sum(preset.target_weights.values()) == pytest.approx(1.0)

    def test_defensive(self) -> None:
        preset = get_preset_portfolio("defensive")
        assert set(preset.target_weights.keys()) == {"VYD", "XLU", "XLP", "TLT", "GLD"}
        assert sum(preset.target_weights.values()) == pytest.approx(1.0)

    def test_all_preset_weights_sum_to_one(self) -> None:
        for key, preset in PRESET_PORTFOLIOS.items():
            total = sum(preset.target_weights.values())
            assert total == pytest.approx(1.0), f"Preset '{key}' weights sum to {total}, not 1.0"

    def test_all_presets_have_description(self) -> None:
        for key, preset in PRESET_PORTFOLIOS.items():
            assert preset.description, f"Preset '{key}' has no description"

    def test_preset_key_matches_dict_key(self) -> None:
        for dict_key, preset in PRESET_PORTFOLIOS.items():
            assert preset.key == dict_key

    def test_unknown_preset_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            get_preset_portfolio("does-not-exist")

    def test_preset_weights_match_agents_md(self) -> None:
        """Verify preset allocations match the spec in AGENTS.md."""
        tech = get_preset_portfolio("concentrated-tech")
        assert tech.target_weights["AAPL"] == pytest.approx(0.40)
        assert tech.target_weights["NVDA"] == pytest.approx(0.25)
        assert tech.target_weights["MSFT"] == pytest.approx(0.20)
        assert tech.target_weights["AMZN"] == pytest.approx(0.15)
