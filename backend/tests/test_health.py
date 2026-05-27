from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_returns_shape() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "Market Scenario and Stress Testing Workbench"
    assert payload["status"] in {"ok", "degraded"}
    assert "database" in payload
    assert len(payload["data_sources"]) == 2

