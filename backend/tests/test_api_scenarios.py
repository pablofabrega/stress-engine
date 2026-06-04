from __future__ import annotations

import uuid

import pandas as pd
from fastapi.testclient import TestClient

from app.domain.portfolio.models import PortfolioHolding
from app.domain.scenarios.models import (
    HistoricalScenarioResult,
    HypotheticalScenarioResult,
)


def _create_portfolio(client: TestClient) -> str:
    response = client.post(
        "/api/v1/portfolios",
        json={"name": "P", "holdings": [{"ticker": "AAPL", "quantity": 1, "cost_basis": 100.0}]},
    )
    return response.json()["id"]


class FakeLoader:
    """Return non-empty holdings without touching the network."""

    def load_from_json(self, name, holdings_payload):
        from types import SimpleNamespace

        holdings = [
            PortfolioHolding(ticker=t, quantity=float(p["quantity"]), sector="Technology", asset_class="Equity")
            for t, p in holdings_payload.items()
        ]
        return SimpleNamespace(name=name, holdings=holdings)


class FakeHistoricalRunner:
    def run_scenario(self, holdings, scenario):
        index = pd.date_range("2008-09-01", periods=3, freq="D", name="date")
        labels = ["AAPL", "TLT"]
        before = pd.DataFrame([[1.0, 0.3], [0.3, 1.0]], index=labels, columns=labels)
        during = pd.DataFrame([[1.0, 0.6], [0.6, 1.0]], index=labels, columns=labels)
        return HistoricalScenarioResult(
            scenario=scenario,
            portfolio_path=pd.DataFrame(
                {
                    "portfolio_value": [100.0, 95.0, 90.0],
                    "pnl_dollars": [0.0, -5.0, -10.0],
                    "cumulative_return": [0.0, -0.05, -0.10],
                    "drawdown": [0.0, -0.05, -0.10],
                },
                index=index,
            ),
            comparison_path=pd.DataFrame(
                {
                    "spy_cumulative_return": [0.0, -0.04, -0.08],
                    "benchmark_60_40_cumulative_return": [0.0, -0.02, -0.05],
                },
                index=index,
            ),
            contributors=pd.DataFrame(
                [
                    {
                        "ticker": "AAPL",
                        "sector": "Technology",
                        "asset_class": "Equity",
                        "pnl_dollars": -10.0,
                        "pnl_pct_of_portfolio": -0.10,
                        "contribution_pct_of_total_pnl": 1.0,
                    }
                ]
            ),
            sector_breakdown=pd.DataFrame(
                [{"sector": "Technology", "pnl_dollars": -10.0, "contribution_pct_of_total_pnl": 1.0}]
            ),
            asset_class_breakdown=pd.DataFrame(
                [{"asset_class": "Equity", "pnl_dollars": -10.0, "contribution_pct_of_total_pnl": 1.0}]
            ),
            correlation_before=before,
            correlation_during=during,
            correlation_shift=during - before,
            significant_correlation_shifts=pd.DataFrame(),
            warnings=["fake warning"],
        )


class FakeHypotheticalRunner:
    def run_scenario(self, holdings, scenario, as_of_date=None):
        factor = pd.DataFrame(
            [{"alpha": 0.0, "market_beta": 1.1, "smb_exposure": 0.1, "hml_exposure": -0.2, "r_squared": 0.8, "observations": 252}]
        )
        return HypotheticalScenarioResult(
            scenario=scenario,
            holding_impacts=pd.DataFrame(
                [
                    {
                        "ticker": "AAPL",
                        "sector": "Technology",
                        "asset_class": "Equity",
                        "pre_shock_value": 100.0,
                        "shock_return": -0.2,
                        "pnl_dollars": -20.0,
                        "post_shock_value": 80.0,
                    }
                ]
            ),
            instantaneous_pnl_dollars=-20.0,
            instantaneous_return=-0.20,
            simulated_drawdown_path=pd.DataFrame(
                {"day": [0, 1], "projected_return": [-0.20, -0.22], "projected_value": [80.0, 78.0], "projected_drawdown": [0.0, -0.025]}
            ),
            factor_exposure_before=factor,
            factor_exposure_after=factor,
            liquidity_adjusted_loss=-20.0,
            liquidity_table=pd.DataFrame(
                [
                    {
                        "ticker": "AAPL",
                        "adv_30d": 1_000_000.0,
                        "position_pct_adv": 0.01,
                        "days_to_liquidate_10pct": 0.1,
                        "days_to_liquidate_20pct": 0.05,
                        "days_to_liquidate_30pct": 0.03,
                        "stressed_loss_dollars": -20.0,
                        "liquidity_haircut_dollars": 0.0,
                        "liquidity_adjusted_loss_dollars": -20.0,
                    }
                ]
            ),
            feature_vector={"equity_return": -0.2, "vol_change": 5.0},
            warnings=[],
        )


def test_list_scenarios_includes_historical_presets(client: TestClient) -> None:
    response = client.get("/api/v1/scenarios")

    assert response.status_code == 200
    scenarios = response.json()
    presets = {s["id"]: s for s in scenarios if s["source"] == "preset"}
    assert "2008-gfc" in presets
    assert "2020-covid-crash" in presets
    assert presets["2008-gfc"]["type"] == "historical"
    assert presets["2008-gfc"]["start_date"] is not None


def test_list_scenarios_includes_hypothetical_presets(client: TestClient) -> None:
    scenarios = client.get("/api/v1/scenarios").json()
    presets = {s["id"]: s for s in scenarios if s["source"] == "preset"}
    assert "equity-down-20" in presets
    assert presets["equity-down-20"]["type"] == "hypothetical"
    assert presets["equity-down-20"]["parameters"]["scenario_type"] == "equity_market"


def test_create_custom_scenario_then_appears_in_list(client: TestClient) -> None:
    create = client.post(
        "/api/v1/scenarios",
        json={"name": "My Shock", "type": "hypothetical", "parameters": {"equity_market": -0.2}},
    )
    assert create.status_code == 201
    body = create.json()
    assert body["source"] == "custom"
    assert uuid.UUID(body["id"])

    listing = client.get("/api/v1/scenarios").json()
    custom = [s for s in listing if s["source"] == "custom"]
    assert any(s["id"] == body["id"] and s["parameters"] == {"equity_market": -0.2} for s in custom)


def test_create_scenario_rejects_invalid_type(client: TestClient) -> None:
    response = client.post("/api/v1/scenarios", json={"name": "X", "type": "nonsense"})

    assert response.status_code == 422


def test_materialized_preset_is_not_listed_twice(client: TestClient, override_analytics) -> None:
    """Running a preset materializes a definition row; it must not double-list.

    The run creates a ScenarioDefinition row so the FK is valid. That row is a
    preset (carries parameters["key"]) and must be filtered from the listing so
    the preset still appears exactly once, under its canonical key id.
    """

    override_analytics(loader=FakeLoader(), historical_runner=FakeHistoricalRunner())
    portfolio_id = _create_portfolio(client)

    run = client.post("/api/v1/scenario-runs", json={"portfolio_id": portfolio_id, "scenario_id": "2008-gfc"})
    assert run.status_code == 202

    scenarios = client.get("/api/v1/scenarios").json()
    gfc = [s for s in scenarios if s["name"] == "2008 Global Financial Crisis"]
    assert len(gfc) == 1
    assert gfc[0]["id"] == "2008-gfc"
    assert gfc[0]["source"] == "preset"
    # No custom row should leak in for the materialized preset.
    assert not any(s["source"] == "custom" and s["name"] == "2008 Global Financial Crisis" for s in scenarios)


def test_scenario_run_executes_preset_synchronously(client: TestClient, override_analytics) -> None:
    override_analytics(loader=FakeLoader(), historical_runner=FakeHistoricalRunner())
    portfolio_id = _create_portfolio(client)

    run = client.post(
        "/api/v1/scenario-runs",
        json={"portfolio_id": portfolio_id, "scenario_id": "2008-gfc"},
    )
    assert run.status_code == 202
    run_body = run.json()
    assert run_body["status"] == "completed"
    assert uuid.UUID(run_body["scenario_id"])

    result = run_body["result"]
    assert result["type"] == "historical"
    assert result["summary"]["final_return"] == -0.10
    assert len(result["portfolio_path"]) == 3
    assert result["portfolio_path"][0]["date"] == "2008-09-01"
    assert result["correlation_during"]["labels"] == ["AAPL", "TLT"]
    # off-diagonal correlation shifted 0.3 (>0.2) -> one significant pair
    assert len(result["significant_correlation_shifts"]) == 1

    polled = client.get(f"/api/v1/scenario-runs/{run_body['id']}")
    assert polled.status_code == 200
    assert polled.json()["status"] == "completed"


def test_scenario_run_executes_custom_hypothetical(client: TestClient, override_analytics) -> None:
    override_analytics(loader=FakeLoader(), hypothetical_runner=FakeHypotheticalRunner())
    portfolio_id = _create_portfolio(client)
    scenario_id = client.post(
        "/api/v1/scenarios",
        json={"name": "Custom", "type": "hypothetical", "parameters": {"equity_market": -0.2}},
    ).json()["id"]

    run = client.post(
        "/api/v1/scenario-runs",
        json={"portfolio_id": portfolio_id, "scenario_id": scenario_id},
    )
    assert run.status_code == 202
    body = run.json()
    assert body["status"] == "completed"
    assert body["result"]["type"] == "hypothetical"
    assert body["result"]["summary"]["instantaneous_return"] == -0.20
    assert len(body["result"]["holding_impacts"]) == 1


def test_scenario_run_unknown_portfolio_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/v1/scenario-runs",
        json={"portfolio_id": str(uuid.uuid4()), "scenario_id": "2008-gfc"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Portfolio not found."


def test_scenario_run_unknown_scenario_returns_404(client: TestClient) -> None:
    portfolio_id = _create_portfolio(client)

    response = client.post(
        "/api/v1/scenario-runs",
        json={"portfolio_id": portfolio_id, "scenario_id": "does-not-exist"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Scenario not found."


def test_get_unknown_scenario_run_returns_404(client: TestClient) -> None:
    assert client.get(f"/api/v1/scenario-runs/{uuid.uuid4()}").status_code == 404
