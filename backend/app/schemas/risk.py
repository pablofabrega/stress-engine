from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class DrawdownSummaryResponse(BaseModel):
    """Drawdown magnitude and recovery statistics."""

    max_drawdown: float
    peak_date: date | None = None
    trough_date: date | None = None
    recovery_date: date | None = None
    recovery_periods: int | None = None


class ConcentrationResponse(BaseModel):
    """Concentration summary derived from portfolio weights."""

    hhi: float
    top_3_weight: float
    top_5_weight: float


class FactorExposureResponse(BaseModel):
    """Fama-French factor exposure summary."""

    alpha: float
    alpha_t_stat: float
    market_beta: float
    market_beta_t_stat: float
    smb_exposure: float
    smb_t_stat: float
    hml_exposure: float
    hml_t_stat: float
    r_squared: float
    observations: int


class TailRiskConfidenceIntervalResponse(BaseModel):
    """Bootstrap percentile confidence interval for the 95% VaR and CVaR estimates."""

    var_low: float
    var_high: float
    cvar_low: float
    cvar_high: float
    ci_level: float
    n_bootstrap: int


class RiskSnapshotResponse(BaseModel):
    """Current risk snapshot for a portfolio over a lookback window."""

    start_date: date
    end_date: date
    var_95: float
    var_99: float
    cvar_95: float
    rolling_vol: float
    drawdown: DrawdownSummaryResponse
    concentration: ConcentrationResponse
    factor_exposure: FactorExposureResponse
    tail_risk_ci: TailRiskConfidenceIntervalResponse | None = None
    warnings: list[str] = []
