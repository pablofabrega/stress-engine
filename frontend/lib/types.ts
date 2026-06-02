// TypeScript mirrors of the FastAPI Pydantic response shapes plus the scenario
// result payloads serialized by app/services/serialization.py.

export interface Holding {
  id: string;
  ticker: string;
  quantity: number;
  cost_basis: number | null;
  asset_class: string | null;
  sector: string | null;
}

export interface PortfolioAnalyticsSummary {
  total_notional: number;
  holding_weights: Record<string, number>;
  sector_weights: Record<string, number>;
}

export interface Portfolio {
  id: string;
  name: string;
  created_at: string;
  holdings: Holding[];
}

export interface PortfolioDetail extends Portfolio {
  analytics: PortfolioAnalyticsSummary;
}

export interface PresetPortfolio {
  key: string;
  name: string;
  description: string;
  target_weights: Record<string, number>;
}

export interface HoldingInput {
  ticker: string;
  quantity: number;
  cost_basis?: number | null;
  asset_class?: string | null;
  sector?: string | null;
}

export interface DrawdownSummary {
  max_drawdown: number;
  peak_date: string | null;
  trough_date: string | null;
  recovery_date: string | null;
  recovery_periods: number | null;
}

export interface Concentration {
  hhi: number;
  top_3_weight: number;
  top_5_weight: number;
}

export interface FactorExposure {
  alpha: number;
  alpha_t_stat: number;
  market_beta: number;
  market_beta_t_stat: number;
  smb_exposure: number;
  smb_t_stat: number;
  hml_exposure: number;
  hml_t_stat: number;
  r_squared: number;
  observations: number;
}

export interface RiskSnapshot {
  start_date: string;
  end_date: string;
  var_95: number;
  var_99: number;
  cvar_95: number;
  rolling_vol: number;
  drawdown: DrawdownSummary;
  concentration: Concentration;
  factor_exposure: FactorExposure;
  warnings: string[];
}

export interface HedgeSuggestion {
  instrument: string;
  rationale: string;
  severity: string;
  hedge_ratio: number;
  hedge_ratio_steps: string[];
  estimated_annual_cost_bps: number;
  historical_effectiveness: number | null;
  weakness_citation: string;
}

export interface Recommendations {
  portfolio_id: string;
  suggestions: HedgeSuggestion[];
}

export interface ScenarioDefinition {
  id: string;
  name: string;
  type: "historical" | "hypothetical";
  parameters: Record<string, unknown>;
  start_date: string | null;
  end_date: string | null;
  source: "preset" | "custom";
  description: string | null;
}

export interface ScenarioRun {
  id: string;
  portfolio_id: string;
  scenario_id: string;
  status: string;
  result: ScenarioResult | { error?: string } | Record<string, never>;
  created_at: string;
}

export interface CorrelationMatrix {
  labels: string[];
  matrix: (number | null)[][];
}

export interface HistoricalResult {
  type: "historical";
  scenario: { key: string; name: string; start_date: string; end_date: string; description: string };
  summary: {
    initial_value?: number;
    final_pnl_dollars?: number;
    final_return?: number;
    max_drawdown?: number;
    spy_final_return?: number;
    benchmark_final_return?: number;
  };
  portfolio_path: Array<Record<string, number | string>>;
  comparison_path: Array<Record<string, number | string>>;
  worst_contributors: Array<Record<string, number | string>>;
  best_contributors: Array<Record<string, number | string>>;
  sector_breakdown: Array<Record<string, number | string>>;
  asset_class_breakdown: Array<Record<string, number | string>>;
  correlation_before: CorrelationMatrix;
  correlation_during: CorrelationMatrix;
  correlation_shift: CorrelationMatrix;
  significant_correlation_shifts: Array<{ pair_a: string; pair_b: string; shift: number }>;
  warnings: string[];
}

export interface HypotheticalResult {
  type: "hypothetical";
  scenario: { key: string; name: string; scenario_type: string; parameters: Record<string, unknown>; description: string };
  summary: {
    instantaneous_pnl_dollars: number;
    instantaneous_return: number;
    liquidity_adjusted_loss: number;
    total_pre_value: number;
  };
  holding_impacts: Array<Record<string, number | string>>;
  simulated_drawdown_path: Array<Record<string, number | string>>;
  factor_exposure_before: Record<string, number>;
  factor_exposure_after: Record<string, number>;
  liquidity_table: Array<Record<string, number | string>>;
  feature_vector: Record<string, number>;
  warnings: string[];
}

export type ScenarioResult = HistoricalResult | HypotheticalResult;

export interface SimilarPeriod {
  start_date: string;
  end_date: string;
  similarity_score: number;
  feature_vector: Record<string, number>;
  portfolio_return: number | null;
  outcome_narrative: string;
}

export interface SimilarPeriodsResponse {
  periods: SimilarPeriod[];
}

export interface DataSourceHealth {
  source_name: string;
  status: string;
  last_fetched: string | null;
  error_message: string | null;
}

export interface HealthResponse {
  service: string;
  status: string;
  database: { connected: boolean; checked_at: string };
  data_sources: DataSourceHealth[];
}
