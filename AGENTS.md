## Session protocol
- Always read this entire file before writing any code
- State which phase and module you are currently working on
- Do not proceed to the next phase without explicit confirmation
- If a validation step fails (regime classifier, lookahead assertion), stop and report it

---

You are a senior staff engineer and quantitative developer. Build a polished, production-quality portfolio project called:

Market Scenario and Stress Testing Workbench

## Goal
A full-stack web application where a user inputs a portfolio, runs historical and hypothetical stress scenarios using real market data, analyzes portfolio losses and exposures, views hedge suggestions, and understands the drivers of risk. This should feel like a serious institutional-style decision-support tool, not a toy demo.

## Recruiting context
This project is built by a CS student recruiting for new-grad SWE, quant, and consulting roles. The code will be shown in interviews. Prioritize correctness, interpretability, and engineering quality over complexity. Every quant method used must be explainable from first principles.

## Non-negotiable requirements
- All scenario analysis must use real historical price data — no synthetic generation
- Build a working end-to-end app: backend, frontend, analytics engine, documentation
- Make it something a technically sophisticated user would actually want to use

---

## Tech stack

Backend: FastAPI (Python)
Frontend: Next.js + TypeScript + Tailwind CSS
Charts: Recharts
Data / analytics: pandas, numpy, scipy, statsmodels, scikit-learn, cvxpy
Database: PostgreSQL (portfolios, scenarios, results metadata)
Caching: Redis (optional but scaffold the interface)
Background jobs: Celery for long-running scenario runs
Deployment: Docker + docker-compose
Testing: pytest (backend), Playwright (key frontend flows)

Data sources:
- Primary: Polygon.io or Alpaca for equity/ETF price data
- Macro: FRED API (rates, VIX, credit spreads, yield curve)
- Dev fallback: yfinance — but architect behind an abstract DataProvider interface so the source is swappable
- All credentials via environment variables; include a .env.example

---

## Backend domain model

UserPortfolio: id, name, created_at, holdings[]
Holding: ticker, quantity, cost_basis (optional), asset_class, sector
ScenarioDefinition: id, name, type (historical|hypothetical), parameters (JSON), date_range
ScenarioRun: id, portfolio_id, scenario_id, status, result (JSON), created_at
RiskSnapshot: portfolio_id, timestamp, var_95, cvar_95, max_drawdown, rolling_vol, concentration_metrics
Recommendation: portfolio_id, scenario_run_id, type, rationale, severity
DataSourceStatus: source_name, last_fetched, status, error_message

---

## Module 1: Data layer (build this first — shared foundation)

HistoricalDataFetcher:
- Fetches daily OHLCV for any ticker from the configured provider
- Caches locally as parquet files keyed by (ticker, date_range)
- On cache miss: fetch and store; on cache hit: return immediately
- Graceful handling if a ticker has no data: log warning, skip, surface to caller

MacroDataFetcher (FRED):
- 10Y Treasury yield: DGS10
- 2Y Treasury yield: DGS2
- 10Y-2Y spread: T10Y2Y
- VIX: VIXCLS
- HY credit spread: BAMLH0A0HYM2
- USD index: DTWEXBGS

ReturnsCalculator:
- Log returns and simple returns
- Rolling realized volatility (annualized)
- Rolling correlation matrix with configurable window
- All computations fully vectorized — no Python loops over time series

Fama-French loader:
- Download Fama-French 3-factor data from Ken French data library
- Parse and align to calendar — used for factor decomposition

---

## Module 2: Portfolio engine

PortfolioLoader:
- Accepts JSON { "AAPL": { "quantity": 100, "cost_basis": 145.00 }, ... } or CSV upload
- Normalizes weights
- Tags each holding with sector and asset class via yfinance .info or a static lookup table

PortfolioAnalytics:
- Current market value, weight per holding, sector weights
- Portfolio-level daily return history
- Factor decomposition: OLS regression of portfolio returns against Fama-French 3 factors
  → outputs market beta, size (SMB) exposure, value (HML) exposure with t-stats
- Estimated duration for fixed-income holdings using DV01 approximation

Preset demo portfolios (seed data):
- Concentrated tech: 40% AAPL, 25% NVDA, 20% MSFT, 15% AMZN
- Classic 60/40: 60% SPY, 40% BND
- Growth diversified: 20% QQQ, 15% VTI, 15% IEMG, 15% VNQ, 10% GLD, 10% TLT, 15% HYG
- Defensive: 30% VYD, 20% XLU, 20% XLP, 15% TLT, 15% GLD

---

## Module 3: Historical stress scenario engine

Implement replay-based scenarios using actual daily returns over these exact windows:

2008 GFC: Sep 1 2008 – Mar 31 2009
March 2020 COVID crash: Feb 19 2020 – Mar 23 2020
2022 rate tightening: Jan 1 2022 – Dec 31 2022
2018 Q4 selloff: Oct 1 2018 – Dec 24 2018
2000 dot-com (optional): Mar 10 2000 – Oct 9 2002

For each scenario compute:
- Day-by-day portfolio PnL path in dollars and percent
- Drawdown path (cumulative from peak)
- Comparison path: same scenario applied to SPY and to 60/40 benchmark
- Top 5 worst contributors and top 5 best contributors with PnL attribution
- Sector and asset-class contribution breakdown (% of total loss from each)
- Correlation matrix before the scenario window vs during — highlight cells that shifted by more than 0.2

---

## Module 4: Hypothetical shock engine

Design a ScenarioDefinition framework: scenarios are reusable objects with typed parameters, not hardcoded page logic.

Implement these shocks as instantaneous factor shifts applied to portfolio holdings:

Equity market -X%: scale equity positions by (1 + shock * beta) where beta is from module 2
Rates +X bps: reprice bonds using duration (DV01 * bps_change); reprice equities using DCF sensitivity approximation (earnings yield sensitivity to discount rate)
Tech selloff -X%: identify tech holdings by sector tag, apply shock; estimate second-order effects on other sectors using historical cross-sector correlations
VIX spike to X: estimate equity vol drag; if user holds VIX-correlated instruments, apply accordingly
Oil +X%: apply shock to energy sector; estimate inflation pass-through effect on rate-sensitive holdings
HY credit selloff: apply to HYG/JNK proxies; estimate contagion to equities using historical beta of SPY to HY spread widening
Custom shock: user-defined { factor: "AAPL", magnitude: -0.15 } applied to any holding or macro factor

For each hypothetical shock compute:
- Instantaneous estimated PnL
- Simulated 30-day drawdown path using portfolio historical vol scaled to the shock magnitude
- Factor exposure changes post-shock
- Liquidity-adjusted loss estimate (see module 5)

---

## Module 5: Liquidity-adjusted risk

For each holding:
- Fetch 30-day average daily volume (ADV) from price data
- Compute position size as % of ADV
- Compute days-to-liquidate at 10%, 20%, 30% ADV participation rates
- If days-to-liquidate > 5, apply a liquidity haircut to the stressed loss:
  haircut = (days_to_liquidate / 5) * 0.02 * stressed_loss (parameterize this)
- Output: liquidity-adjusted drawdown estimate, table of holdings ranked by days-to-liquidate

---

## Module 6: Risk analytics

Historical VaR (95%, 99%) using empirical quantile of portfolio return distribution
CVaR (95%): mean of returns below VaR threshold
Rolling 21-day realized volatility (annualized)
Maximum drawdown and recovery time
Concentration metrics: Herfindahl-Hirschman Index on weights, top-3 and top-5 weight sums
Rolling 63-day correlation matrix between holdings
Factor exposure summary (from module 2 OLS)

All analytics functions must have:
- docstrings explaining the method and formula
- unit tests in pytest
- deterministic behavior (no randomness unless seeded)

---

## Module 7: Hedge suggestion engine

After running any scenario, analyze the portfolio's dominant risk exposures and suggest 3–5 hedges. Each suggestion must include:
- Instrument (e.g. TLT, VIX calls, GLD, XLU, SH)
- Plain-English rationale
- Approximate hedge ratio calculation shown step by step
- Estimated annual cost in bps
- Historical effectiveness: how much of the stress loss this hedge would have offset during the scenario window

Trigger conditions and instruments:
- High equity beta (>1.1) → long GLD or short SH; show beta-offset calculation
- High duration exposure → short TLT or long TIPS; show DV01 offset
- Tech concentration (>40% of portfolio) → long XLU or short QQQ; show sector beta offset
- Credit risk (HYG/JNK exposure) → long LQD puts or shift to investment grade; show spread sensitivity
- General high CVaR → suggest cash buffer sizing using Kelly criterion approximation

Each suggestion must cite the specific portfolio weakness: e.g. "Your portfolio loses 2.3x the SPY benchmark during the 2022 rate shock. Duration exposure accounts for 58% of the underperformance."

---

## Module 8: Similar historical periods finder

Given a hypothetical shock, find the 3 most similar 30-day historical windows using cosine similarity on a feature vector:
[ equity_return, vol_change, rate_change_10y, credit_spread_change, equity_bond_correlation_shift ]

Normalize each feature to z-scores before computing similarity.
Return: the 3 most similar periods with dates, similarity score, what happened to the portfolio, and outcome narrative.

---

## API design (FastAPI)

POST   /portfolios                    — create portfolio
GET    /portfolios/{id}               — load portfolio with holdings and analytics
POST   /portfolios/{id}/holdings      — add or update holdings
DELETE /portfolios/{id}               — delete portfolio

GET    /scenarios                     — list all scenario definitions
POST   /scenarios                     — create custom scenario definition
POST   /scenario-runs                 — { portfolio_id, scenario_id } → enqueue run, return run_id
GET    /scenario-runs/{run_id}        — poll status and retrieve result when complete

GET    /portfolios/{id}/risk          — current risk snapshot (VaR, CVaR, vol, drawdown, concentration)
GET    /portfolios/{id}/recommendations — list recommendations with rationale
POST   /similar-periods               — { shock_vector } → 3 similar historical windows

GET    /health                        — service status + data source freshness
GET    /data-status                   — last fetch timestamps for each data source

---

## Frontend pages (Next.js)

Each page must have: loading skeleton, error state with retry, and tooltip/info icons explaining every metric.

1. Overview dashboard
   - Portfolio summary: total value, today's change, top 5 holdings, sector pie
   - Risk summary cards: VaR, CVaR, max drawdown, portfolio beta
   - Quick scenario cards: run any preset scenario in one click, see summary result
   - Active alerts / recommendations banner

2. Portfolio builder
   - Manual entry: ticker + quantity + optional cost basis
   - CSV upload with column mapping UI
   - Preset portfolio selector
   - Live preview: weights chart, sector breakdown, Fama-French factor exposures, estimated beta

3. Historical scenario page
   - Scenario selector (cards with SPY sparkline thumbnail for each period)
   - Results: cumulative PnL chart (portfolio vs SPY vs 60/40), drawdown chart, contributors table, sector breakdown, correlation shift heatmaps

4. Hypothetical scenario builder
   - Shock sliders: SPY %, rates bps, VIX target, oil %, custom per-ticker
   - Live estimated impact as sliders move (debounced, uses fast approximation)
   - Full run button → detailed results with simulated drawdown path, factor exposure changes, liquidity-adjusted estimate, similar historical periods

5. Risk analytics page
   - Rolling vol chart, VaR/CVaR over time, max drawdown chart
   - Correlation matrix heatmap (current)
   - Concentration metrics: HHI gauge, top-N weight chart
   - Factor exposure bar chart with t-stats

6. Recommendations page
   - Cards per recommendation: severity badge, plain-English rationale, supporting data, suggested action
   - Each card cites the scenario or metric that triggered it
   - Hedge suggestion section with instrument cards

7. Settings / data status page
   - Data provider configuration (API key entry, provider toggle)
   - Last fetch timestamps and data freshness indicator per source
   - Cache controls

---

## Explainability requirement

Every metric displayed in the UI must have a tooltip or expandable info section that explains:
- What it means in plain English
- How it is calculated (formula or method name)
- Why it matters for portfolio risk

This is non-negotiable. Examples:
- CVaR tooltip: "Conditional Value at Risk — the average loss on the worst 5% of days. More conservative than VaR because it measures the severity of tail losses, not just the threshold."
- Hedge ratio tooltip: "How many units of the hedge instrument to hold per unit of portfolio exposure. Calculated as: (portfolio DV01) / (hedge instrument DV01)."

---

## Engineering quality requirements

- Provider abstraction: DataProvider interface with concrete implementations for Polygon, Alpaca, yfinance — switchable via config
- Scenario engine abstraction: ScenarioRunner interface, separate implementations for historical replay and hypothetical shocks
- All analytics functions: docstrings, unit tests, deterministic behavior
- API: typed Pydantic models for all request/response shapes
- Error handling: missing ticker data → warn and skip; API timeout → retry with exponential backoff (max 3 attempts); stale cache → surface warning to frontend
- Logging: structured JSON logs with request_id, portfolio_id, scenario_id
- Health endpoint returns: service status, database connectivity, data source freshness
- No hardcoded credentials anywhere

---

## Documentation requirements

README must include:
- Project motivation (2–3 paragraphs)
- Architecture diagram (Mermaid)
- Setup instructions
- Feature list
- Data sources and licensing notes
- Design tradeoffs and limitations
- Future work section

Include a section titled exactly: "How to talk about this project in SWE, quant, and consulting interviews"
- SWE version: emphasize the provider abstraction, async task queue, data pipeline, API design
- Quant version: emphasize the factor decomposition, liquidity-adjusted risk, hedge ratio calculations, scenario framework
- Consulting version: emphasize the decision-support framing, the recommendation engine rationale, the explainability layer

---

## Deliverables

- Complete codebase
- .env.example
- Sample CSV portfolio upload file (5 holdings)
- SQL schema / Alembic migrations
- pytest test suite with >80% coverage of analytics module
- Seeded demo data: three preset portfolios with pre-run scenario results
- README with architecture diagram
- Demo script: 3–5 minute walkthrough narrative
- Resume bullet suggestions (3 bullets for each of SWE, quant, consulting)
- Repo tree at end

---

## Build sequence

1. Scaffold repo, docker-compose, .env.example, Alembic migrations, folder structure
2. Data provider interface + yfinance implementation + caching layer
3. Portfolio ingestion, normalization, preset portfolios
4. Fama-French factor decomposition
5. Historical scenario engine (2008 and 2020 first)
6. Risk analytics module + unit tests
7. Hypothetical shock engine
8. Liquidity-adjusted risk
9. Hedge suggestion engine
10. Similar periods finder
11. FastAPI endpoints + Pydantic models
12. Celery task queue for long-running runs
13. Next.js frontend — portfolio builder first, then scenario pages
14. Explainability tooltips throughout
15. Recommendations page
16. Polish: loading states, error states, data status page
17. Tests, README, demo script, resume bullets

Start by generating the complete repo scaffold and docker-compose. Then implement modules in sequence. Do not skip the unit tests for the analytics module — they will be shown in interviews.
