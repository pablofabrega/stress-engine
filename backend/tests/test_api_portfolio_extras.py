from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_portfolios_returns_created(client: TestClient) -> None:
    assert client.get("/api/v1/portfolios").json() == []

    client.post("/api/v1/portfolios", json={"name": "Alpha", "holdings": []})
    client.post("/api/v1/portfolios", json={"name": "Beta", "holdings": []})

    listing = client.get("/api/v1/portfolios")
    assert listing.status_code == 200
    names = [p["name"] for p in listing.json()]
    assert names == ["Alpha", "Beta"]


def test_list_preset_portfolios(client: TestClient) -> None:
    response = client.get("/api/v1/portfolios/presets")

    assert response.status_code == 200
    presets = {p["key"]: p for p in response.json()}
    assert "concentrated-tech" in presets
    assert "classic-60-40" in presets
    assert presets["classic-60-40"]["target_weights"]["SPY"] == 0.60
