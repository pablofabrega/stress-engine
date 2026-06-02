"""Serialize scenario-engine results (rich pandas objects) into JSON-safe dicts.

Scenario engines return dataclasses packed with ``pandas`` DataFrames, numpy
scalars, ``NaN``/``inf`` values, and ``Timestamp`` indices. None of those are
valid JSON. The helpers here flatten those structures into plain Python
primitives so the result can be persisted in the ``scenario_runs.result`` JSON
column and consumed directly by the frontend.

Two frame shapes are handled distinctly:

* tabular frames (paths, contributors, breakdowns) -> list of row dicts, with a
  ``DatetimeIndex`` promoted to an ISO ``date`` field;
* square correlation matrices -> ``{"labels": [...], "matrix": [[...]]}`` so the
  frontend can render a labelled heatmap without re-deriving axes.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

from app.domain.scenarios.models import HistoricalScenarioResult, HypotheticalScenarioResult


def json_safe(value: Any) -> Any:
    """Recursively coerce numpy/pandas/NaN values into JSON-serializable primitives."""

    if value is None:
        return None
    if isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return pd.Timestamp(value).date().isoformat()
    if isinstance(value, np.ndarray):
        return [json_safe(item) for item in value.tolist()]
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if value is pd.NaT:
        return None
    try:
        if pd.isna(value):  # scalar NaN-likes not caught above
            return None
    except (TypeError, ValueError):
        pass
    return value


def frame_to_records(frame: pd.DataFrame, index_name: str | None = None) -> list[dict[str, Any]]:
    """Convert a DataFrame to JSON-safe row dicts, promoting a non-default index to a column."""

    if frame is None or frame.empty:
        return []
    working = frame.copy()
    if not isinstance(working.index, pd.RangeIndex):
        name = index_name or working.index.name or "index"
        working = working.reset_index().rename(columns={working.index.name or "index": name})
    return [json_safe(row) for row in working.to_dict(orient="records")]


def matrix_to_payload(frame: pd.DataFrame) -> dict[str, Any]:
    """Convert a square correlation-style matrix into labelled heatmap payload."""

    if frame is None or frame.empty:
        return {"labels": [], "matrix": []}
    labels = [str(label) for label in frame.columns]
    matrix = [[json_safe(cell) for cell in row] for row in frame.to_numpy()]
    return {"labels": labels, "matrix": matrix}


def _significant_shifts(shift_frame: pd.DataFrame, threshold: float = 0.2) -> list[dict[str, Any]]:
    """Flatten the upper triangle of a correlation-shift matrix into notable pairs."""

    if shift_frame is None or shift_frame.empty:
        return []
    rows: list[dict[str, Any]] = []
    labels = list(shift_frame.columns)
    for i, left in enumerate(labels):
        for right in labels[i + 1 :]:
            try:
                value = float(shift_frame.loc[left, right])
            except (KeyError, TypeError, ValueError):
                continue
            if math.isfinite(value) and abs(value) > threshold:
                rows.append({"pair_a": str(left), "pair_b": str(right), "shift": value})
    return sorted(rows, key=lambda item: abs(item["shift"]), reverse=True)


def serialize_historical_result(result: HistoricalScenarioResult) -> dict[str, Any]:
    """Flatten a historical replay result into a JSON-safe payload for storage/UI."""

    path = result.portfolio_path
    comparison = result.comparison_path
    summary: dict[str, Any] = {}
    if not path.empty:
        final = path.iloc[-1]
        summary["initial_value"] = json_safe(path["portfolio_value"].iloc[0] - final["pnl_dollars"])
        summary["final_pnl_dollars"] = json_safe(final.get("pnl_dollars"))
        summary["final_return"] = json_safe(final.get("cumulative_return"))
        summary["max_drawdown"] = json_safe(path["drawdown"].min())
    if not comparison.empty:
        last = comparison.iloc[-1]
        summary["spy_final_return"] = json_safe(last.get("spy_cumulative_return"))
        summary["benchmark_final_return"] = json_safe(last.get("benchmark_60_40_cumulative_return"))

    return {
        "type": "historical",
        "scenario": {
            "key": result.scenario.key,
            "name": result.scenario.name,
            "start_date": json_safe(result.scenario.start_date),
            "end_date": json_safe(result.scenario.end_date),
            "description": result.scenario.description,
        },
        "summary": summary,
        "portfolio_path": frame_to_records(path, index_name="date"),
        "comparison_path": frame_to_records(comparison, index_name="date"),
        "worst_contributors": frame_to_records(result.contributors.sort_values("pnl_dollars").head(5)),
        "best_contributors": frame_to_records(
            result.contributors.sort_values("pnl_dollars", ascending=False).head(5)
        ),
        "sector_breakdown": frame_to_records(result.sector_breakdown),
        "asset_class_breakdown": frame_to_records(result.asset_class_breakdown),
        "correlation_before": matrix_to_payload(result.correlation_before),
        "correlation_during": matrix_to_payload(result.correlation_during),
        "correlation_shift": matrix_to_payload(result.correlation_shift),
        "significant_correlation_shifts": _significant_shifts(result.correlation_shift),
        "warnings": list(result.warnings),
    }


def serialize_hypothetical_result(result: HypotheticalScenarioResult) -> dict[str, Any]:
    """Flatten a hypothetical shock result into a JSON-safe payload for storage/UI."""

    impacts = result.holding_impacts
    total_pre = float(impacts["pre_shock_value"].sum()) if not impacts.empty else 0.0
    factor_before = frame_to_records(result.factor_exposure_before)
    factor_after = frame_to_records(result.factor_exposure_after)

    return {
        "type": "hypothetical",
        "scenario": {
            "key": result.scenario.key,
            "name": result.scenario.name,
            "scenario_type": result.scenario.scenario_type,
            "parameters": json_safe(result.scenario.parameters),
            "description": result.scenario.description,
        },
        "summary": {
            "instantaneous_pnl_dollars": json_safe(result.instantaneous_pnl_dollars),
            "instantaneous_return": json_safe(result.instantaneous_return),
            "liquidity_adjusted_loss": json_safe(result.liquidity_adjusted_loss),
            "total_pre_value": json_safe(total_pre),
        },
        "holding_impacts": frame_to_records(impacts),
        "simulated_drawdown_path": frame_to_records(result.simulated_drawdown_path),
        "factor_exposure_before": factor_before[0] if factor_before else {},
        "factor_exposure_after": factor_after[0] if factor_after else {},
        "liquidity_table": frame_to_records(result.liquidity_table),
        "feature_vector": json_safe(result.feature_vector),
        "warnings": list(result.warnings),
    }
