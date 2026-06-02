from __future__ import annotations

import uuid

from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.domain.portfolio.models import FactorDecompositionResult, PortfolioHolding
from app.domain.risk.models import (
    ConcentrationMetrics,
    DrawdownSummary,
    HedgeSuggestion,
    RiskAnalyticsResult,
    SimilarHistoricalPeriod,
)


class FakeLoader:
    def load_from_json(self, name, holdings_payload):
        holdings = [
            PortfolioHolding(ticker=ticker, quantity=float(p["quantity"]), weight=1.0 / len(holdings_payload))
            for ticker, p in holdings_payload.items()
        ]
        return SimpleNamespace(name=name, holdings=holdings)


def _risk_result() -> RiskAnalyticsResult:
    return RiskAnalyticsResult(
        var_95=-0.021,
        var_99=-0.040,
        cvar_95=-0.031,
        latest_rolling_vol=0.18,
        drawdown=DrawdownSummary(
            max_drawdown=-0.25,
            peak_date=pd.Timestamp("2022-01-03"),
            trough_date=pd.Timestamp("2022-06-16"),
            recovery_date=None,
            recovery_periods=None,
        ),
        concentration=ConcentrationMetrics(hhi=0.34, top_3_weight=0.8, top_5_weight=1.0),
        latest_correlation_matrix=pd.DataFrame(),
        rolling_correlation_matrix=pd.DataFrame(),
        factor_exposure_summary=FactorDecompositionResult(
            alpha=0.0001,
            alpha_t_stat=0.5,
            market_beta=1.2,
            market_beta_t_stat=8.0,
            smb_exposure=0.1,
            smb_t_stat=1.1,
            hml_exposure=-0.2,
            hml_t_stat=-1.5,
            r_squared=0.85,
            observations=252,
        ),
        warnings=["sample warning"],
    )


class FakeRiskAnalytics:
    def analyze_portfolio(self, holdings, start_date, end_date, **kwargs):
        self.seen = (holdings, start_date, end_date)
        return _risk_result()


class FakeHedgeEngine:
    def suggest(self, holdings, risk_summary, as_of_date=None, **kwargs):
        return [
            HedgeSuggestion(
                instrument="SH",
                rationale="High equity beta of 1.2 amplifies market drawdowns.",
                severity="high",
                hedge_ratio=0.2,
                hedge_ratio_steps=["beta = 1.2", "hedge_ratio = beta - 1 = 0.2"],
                estimated_annual_cost_bps=85.0,
                historical_effectiveness=0.6,
                weakness_citation="Market beta 1.2 (t=8.0).",
            )
        ]


class FakeFinder:
    def find(self, shock_vector, holdings=None, top_k=3, **kwargs):
        self.seen = (shock_vector, holdings, top_k)
        return [
            SimilarHistoricalPeriod(
                start_date=pd.Timestamp("2008-09-15"),
                end_date=pd.Timestamp("2008-10-15"),
                similarity_score=0.93,
                feature_vector={"equity_return": -0.2, "vol_change": 1.5},
                portfolio_return=-0.18 if holdings else None,
                outcome_narrative="Sharp equity drawdown with spiking volatility.",
            )
        ]


@pytest.fixture()
def portfolio_id(client: TestClient) -> str:
    response = client.post(
        "/api/v1/portfolios",
        json={"name": "P", "holdings": [{"ticker": "AAPL", "quantity": 10, "cost_basis": 100.0}]},
    )
    return response.json()["id"]


def test_risk_endpoint_serializes_snapshot(client: TestClient, portfolio_id: str, override_analytics) -> None:
    override_analytics(loader=FakeLoader(), risk_analytics=FakeRiskAnalytics())

    response = client.get(f"/api/v1/portfolios/{portfolio_id}/risk")

    assert response.status_code == 200
    body = response.json()
    assert body["var_95"] == -0.021
    assert body["cvar_95"] == -0.031
    assert body["rolling_vol"] == 0.18
    assert body["drawdown"]["max_drawdown"] == -0.25
    assert body["drawdown"]["recovery_date"] is None
    assert body["concentration"]["hhi"] == 0.34
    assert body["factor_exposure"]["market_beta"] == 1.2
    assert body["warnings"] == ["sample warning"]


def test_risk_endpoint_unknown_portfolio_404(client: TestClient, override_analytics) -> None:
    override_analytics(loader=FakeLoader(), risk_analytics=FakeRiskAnalytics())

    assert client.get(f"/api/v1/portfolios/{uuid.uuid4()}/risk").status_code == 404


def test_recommendations_endpoint(client: TestClient, portfolio_id: str, override_analytics) -> None:
    override_analytics(loader=FakeLoader(), risk_analytics=FakeRiskAnalytics(), hedge_engine=FakeHedgeEngine())

    response = client.get(f"/api/v1/portfolios/{portfolio_id}/recommendations")

    assert response.status_code == 200
    body = response.json()
    assert body["portfolio_id"] == portfolio_id
    assert len(body["suggestions"]) == 1
    suggestion = body["suggestions"][0]
    assert suggestion["instrument"] == "SH"
    assert suggestion["severity"] == "high"
    assert suggestion["historical_effectiveness"] == 0.6


def test_similar_periods_without_portfolio(client: TestClient, override_analytics) -> None:
    override_analytics(similar_periods_finder=FakeFinder())

    response = client.post(
        "/api/v1/similar-periods",
        json={"shock_vector": {"equity_return": -0.2, "vol_change": 1.5}, "top_k": 1},
    )

    assert response.status_code == 200
    periods = response.json()["periods"]
    assert len(periods) == 1
    assert periods[0]["similarity_score"] == 0.93
    assert periods[0]["portfolio_return"] is None  # no holdings provided


def test_similar_periods_with_portfolio(client: TestClient, portfolio_id: str, override_analytics) -> None:
    override_analytics(loader=FakeLoader(), similar_periods_finder=FakeFinder())

    response = client.post(
        "/api/v1/similar-periods",
        json={"shock_vector": {"equity_return": -0.2}, "portfolio_id": portfolio_id},
    )

    assert response.status_code == 200
    periods = response.json()["periods"]
    assert periods[0]["portfolio_return"] == -0.18  # holdings were loaded and passed through


def test_similar_periods_unknown_portfolio_404(client: TestClient, override_analytics) -> None:
    override_analytics(loader=FakeLoader(), similar_periods_finder=FakeFinder())

    response = client.post(
        "/api/v1/similar-periods",
        json={"shock_vector": {"equity_return": -0.2}, "portfolio_id": str(uuid.uuid4())},
    )

    assert response.status_code == 404


def test_similar_periods_requires_shock_vector(client: TestClient, override_analytics) -> None:
    override_analytics(similar_periods_finder=FakeFinder())

    response = client.post("/api/v1/similar-periods", json={"shock_vector": {}})

    assert response.status_code == 422
