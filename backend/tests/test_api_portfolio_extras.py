from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.portfolio import Holding, UserPortfolio
from app.services import portfolio_service


def test_list_portfolios_returns_created(client: TestClient) -> None:
    assert client.get("/api/v1/portfolios").json() == []

    client.post("/api/v1/portfolios", json={"name": "Alpha", "holdings": []})
    client.post("/api/v1/portfolios", json={"name": "Beta", "holdings": []})

    listing = client.get("/api/v1/portfolios")
    assert listing.status_code == 200
    names = [p["name"] for p in listing.json()]
    assert names == ["Alpha", "Beta"]


def test_create_portfolio_tags_sector_when_omitted(client: TestClient) -> None:
    # Builder sends no sector; ingestion should resolve it (NVDA -> Technology).
    created = client.post(
        "/api/v1/portfolios",
        json={"name": "Manual", "holdings": [{"ticker": "NVDA", "quantity": 10, "cost_basis": 100.0}]},
    ).json()

    detail = client.get(f"/api/v1/portfolios/{created['id']}").json()
    holding = detail["holdings"][0]
    assert holding["sector"] == "Technology"
    assert holding["asset_class"] == "Equity"
    assert detail["analytics"]["sector_weights"] == {"Technology": 1.0}


def test_backfill_holding_metadata_fills_unknown(db_session: Session) -> None:
    # Simulate legacy holdings stored before ingestion-time tagging existed.
    portfolio = UserPortfolio(name="Legacy")
    portfolio.holdings.append(Holding(ticker="NVDA", quantity=1, sector=None, asset_class=None))
    portfolio.holdings.append(Holding(ticker="MSFT", quantity=1, sector="Unknown", asset_class="Unknown"))
    portfolio.holdings.append(Holding(ticker="AAPL", quantity=1, sector="Custom", asset_class="Equity"))
    db_session.add(portfolio)
    db_session.commit()

    updated = portfolio_service.backfill_holding_metadata(db_session)

    assert updated == 2  # NVDA + MSFT; AAPL's explicit "Custom" sector is preserved
    db_session.refresh(portfolio)
    by_ticker = {h.ticker: h for h in portfolio.holdings}
    assert by_ticker["NVDA"].sector == "Technology"
    assert by_ticker["NVDA"].asset_class == "Equity"
    assert by_ticker["MSFT"].sector == "Technology"
    assert by_ticker["AAPL"].sector == "Custom"  # untouched


def test_list_preset_portfolios(client: TestClient) -> None:
    response = client.get("/api/v1/portfolios/presets")

    assert response.status_code == 200
    presets = {p["key"]: p for p in response.json()}
    assert "concentrated-tech" in presets
    assert "classic-60-40" in presets
    assert presets["classic-60-40"]["target_weights"]["SPY"] == 0.60
