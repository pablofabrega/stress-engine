// Typed client for the Stress Workbench FastAPI backend.
//
// The base URL comes from NEXT_PUBLIC_API_URL (set in .env / docker-compose),
// falling back to localhost for bare `npm run dev`. Every helper returns parsed,
// typed JSON and throws ApiError on a non-2xx response so callers can render a
// consistent error/retry state.

import type {
  HealthResponse,
  HedgeSuggestion,
  Portfolio,
  PortfolioDetail,
  PresetPortfolio,
  Recommendations,
  RiskSnapshot,
  ScenarioDefinition,
  ScenarioRun,
  SimilarPeriodsResponse,
  HoldingInput,
} from "./types";

const API_ROOT = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const API_BASE = `${API_ROOT}/api/v1`;

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(`Could not reach the API at ${API_BASE}. Is the backend running?`, 0);
  }

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  // Portfolios
  listPortfolios: () => request<Portfolio[]>("/portfolios"),
  getPortfolio: (id: string) => request<PortfolioDetail>(`/portfolios/${id}`),
  listPresetPortfolios: () => request<PresetPortfolio[]>("/portfolios/presets"),
  createPortfolio: (name: string, holdings: HoldingInput[]) =>
    request<Portfolio>("/portfolios", { method: "POST", body: JSON.stringify({ name, holdings }) }),
  updateHoldings: (id: string, holdings: HoldingInput[]) =>
    request<Portfolio>(`/portfolios/${id}/holdings`, { method: "POST", body: JSON.stringify({ holdings }) }),
  deletePortfolio: (id: string) => request<{ detail: string }>(`/portfolios/${id}`, { method: "DELETE" }),

  // Risk + recommendations
  getRisk: (id: string) => request<RiskSnapshot>(`/portfolios/${id}/risk`),
  getRecommendations: (id: string) => request<Recommendations>(`/portfolios/${id}/recommendations`),

  // Scenarios
  listScenarios: () => request<ScenarioDefinition[]>("/scenarios"),
  createScenario: (payload: Pick<ScenarioDefinition, "name" | "type" | "parameters">) =>
    request<ScenarioDefinition>("/scenarios", { method: "POST", body: JSON.stringify(payload) }),
  createScenarioRun: (portfolioId: string, scenarioId: string) =>
    request<ScenarioRun>("/scenario-runs", {
      method: "POST",
      body: JSON.stringify({ portfolio_id: portfolioId, scenario_id: scenarioId }),
    }),
  getScenarioRun: (runId: string) => request<ScenarioRun>(`/scenario-runs/${runId}`),

  // Similar periods
  similarPeriods: (shockVector: Record<string, number>, portfolioId?: string, topK = 3) =>
    request<SimilarPeriodsResponse>("/similar-periods", {
      method: "POST",
      body: JSON.stringify({ shock_vector: shockVector, portfolio_id: portfolioId ?? null, top_k: topK }),
    }),

  // Health / data status
  health: () => request<HealthResponse>("/health"),
  dataStatus: () => request<HealthResponse>("/data-status"),
};

export type { HedgeSuggestion };
