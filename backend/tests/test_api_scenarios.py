from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _create_portfolio(client: TestClient) -> str:
    response = client.post(
        "/api/v1/portfolios",
        json={"name": "P", "holdings": [{"ticker": "AAPL", "quantity": 1, "cost_basis": 100.0}]},
    )
    return response.json()["id"]


def test_list_scenarios_includes_historical_presets(client: TestClient) -> None:
    response = client.get("/api/v1/scenarios")

    assert response.status_code == 200
    scenarios = response.json()
    presets = {s["id"]: s for s in scenarios if s["source"] == "preset"}
    assert "2008-gfc" in presets
    assert "2020-covid-crash" in presets
    assert presets["2008-gfc"]["type"] == "historical"
    assert presets["2008-gfc"]["start_date"] is not None


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


def test_scenario_run_lifecycle_for_preset(client: TestClient) -> None:
    portfolio_id = _create_portfolio(client)

    run = client.post(
        "/api/v1/scenario-runs",
        json={"portfolio_id": portfolio_id, "scenario_id": "2008-gfc"},
    )
    assert run.status_code == 202
    run_body = run.json()
    assert run_body["status"] == "pending"
    assert run_body["portfolio_id"] == portfolio_id
    assert uuid.UUID(run_body["scenario_id"])  # preset materialized to a real definition

    polled = client.get(f"/api/v1/scenario-runs/{run_body['id']}")
    assert polled.status_code == 200
    assert polled.json()["status"] == "pending"


def test_scenario_run_with_custom_scenario(client: TestClient) -> None:
    portfolio_id = _create_portfolio(client)
    scenario_id = client.post(
        "/api/v1/scenarios",
        json={"name": "Custom", "type": "hypothetical", "parameters": {}},
    ).json()["id"]

    run = client.post(
        "/api/v1/scenario-runs",
        json={"portfolio_id": portfolio_id, "scenario_id": scenario_id},
    )
    assert run.status_code == 202
    assert run.json()["scenario_id"] == scenario_id


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
