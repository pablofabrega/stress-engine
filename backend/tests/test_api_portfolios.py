from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _create(client: TestClient, **overrides) -> dict:
    payload = {
        "name": "Test Portfolio",
        "holdings": [
            {"ticker": "AAPL", "quantity": 10, "cost_basis": 100.0, "sector": "Technology"},
            {"ticker": "BND", "quantity": 20, "cost_basis": 50.0, "sector": "Fixed Income"},
        ],
    }
    payload.update(overrides)
    response = client.post("/api/v1/portfolios", json=payload)
    return response.json() if response.status_code < 400 else {"_status": response.status_code, "_body": response.json()}


def test_create_portfolio_persists_holdings(client: TestClient) -> None:
    response = client.post(
        "/api/v1/portfolios",
        json={"name": "Growth", "holdings": [{"ticker": "aapl", "quantity": 5, "cost_basis": 120.0}]},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Growth"
    assert uuid.UUID(body["id"])
    assert len(body["holdings"]) == 1
    assert body["holdings"][0]["ticker"] == "AAPL"  # normalized to upper-case


def test_get_portfolio_returns_nominal_analytics(client: TestClient) -> None:
    created = _create(client)

    response = client.get(f"/api/v1/portfolios/{created['id']}")

    assert response.status_code == 200
    analytics = response.json()["analytics"]
    # AAPL notional = 10*100 = 1000, BND notional = 20*50 = 1000 -> equal weights
    assert analytics["total_notional"] == 2000.0
    assert analytics["holding_weights"] == {"AAPL": 0.5, "BND": 0.5}
    assert analytics["sector_weights"] == {"Technology": 0.5, "Fixed Income": 0.5}


def test_get_unknown_portfolio_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/portfolios/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Portfolio not found."


def test_create_portfolio_rejects_invalid_holding(client: TestClient) -> None:
    response = client.post(
        "/api/v1/portfolios",
        json={"name": "Bad", "holdings": [{"ticker": "AAPL", "quantity": 0}]},
    )

    assert response.status_code == 422


def test_update_holdings_upserts_by_ticker(client: TestClient) -> None:
    created = _create(client)
    portfolio_id = created["id"]

    response = client.post(
        f"/api/v1/portfolios/{portfolio_id}/holdings",
        json={"holdings": [{"ticker": "AAPL", "quantity": 99, "cost_basis": 100.0}, {"ticker": "MSFT", "quantity": 3}]},
    )

    assert response.status_code == 200
    holdings = {h["ticker"]: h for h in response.json()["holdings"]}
    assert holdings["AAPL"]["quantity"] == 99  # updated in place
    assert "MSFT" in holdings  # newly added
    assert len(holdings) == 3


def test_update_holdings_on_unknown_portfolio_returns_404(client: TestClient) -> None:
    response = client.post(
        f"/api/v1/portfolios/{uuid.uuid4()}/holdings",
        json={"holdings": [{"ticker": "AAPL", "quantity": 1}]},
    )

    assert response.status_code == 404


def test_delete_portfolio_removes_it(client: TestClient) -> None:
    created = _create(client)
    portfolio_id = created["id"]

    deleted = client.delete(f"/api/v1/portfolios/{portfolio_id}")
    assert deleted.status_code == 200
    assert deleted.json()["detail"] == "Portfolio deleted."

    assert client.get(f"/api/v1/portfolios/{portfolio_id}").status_code == 404


def test_delete_unknown_portfolio_returns_404(client: TestClient) -> None:
    assert client.delete(f"/api/v1/portfolios/{uuid.uuid4()}").status_code == 404
