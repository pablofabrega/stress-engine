# Demo Script — Market Scenario and Stress Testing Workbench

**Target length:** 3–5 minutes. **Audience:** a recruiter or interviewer (SWE / quant / consulting).

**Before you start:** `docker compose up --build`, run `alembic upgrade head`, and seed with
`python -m app.db.seed` (executes scenario runs against the data provider). Open
`http://localhost:3000`. Have the **Concentrated Tech** preset selected in the header dropdown.

---

## 0:00 — Framing (20s)

> "This is a portfolio stress-testing workbench. It answers three questions a real portfolio
> manager asks: how much would I lose if a past crisis repeated, what drives that loss, and what
> hedges would reduce my downside. Everything is computed from real market data and every number is
> explainable — there's a tooltip on every metric explaining what it is and how it's calculated."

Hover one tooltip (e.g. CVaR) to show the explainability layer.

## 0:20 — Build / pick a portfolio (40s)

Go to **Portfolio Builder**.

> "You can enter holdings by hand, paste a CSV, or instantiate a preset. Weights normalize live."

Click the **Concentrated Tech** preset to create it. Point out the live weight preview.

> "Under the hood this hits a typed FastAPI endpoint; the holdings are tagged with sector and asset
> class, and the portfolio becomes the active one across every page."

## 1:00 — Overview & headline risk (40s)

Go to **Overview**.

> "Here's composition plus headline risk — VaR, CVaR, max drawdown, and market beta from a
> Fama-French regression. Note the beta above 1: this concentrated-tech book amplifies the market."

Click **Run replay** on the **2008** quick card.

> "That just executed a full historical replay synchronously and returned the portfolio's return,
> versus SPY and a 60/40 benchmark."

## 1:40 — Historical stress (60s)

Go to **Historical Scenarios**, click **March 2020 COVID Crash**.

> "We replay current holdings through actual daily returns. This is the cumulative path vs SPY and
> 60/40, and the underwater drawdown curve."

Scroll to contributors and the correlation heatmaps.

> "PnL is attributed to the worst and best names and to sectors. And this is the key quant point —
> the correlation heatmaps show 'before' vs 'during'. Ringed cells rose by more than 0.2:
> diversification breaks down in a crisis, exactly when you need it."

## 2:40 — Hypothetical shock (50s)

Go to **Hypothetical Scenarios**. Click the **Rates +100 bps** preset, then try a **Custom** equity
shock of -20%.

> "Shocks are applied through factor sensitivities — beta for equities, duration for bonds, sector
> correlations for spillovers. We get instantaneous PnL, a liquidity-adjusted loss after a
> days-to-liquidate haircut, a simulated 30-day path, and the factor-exposure shift."

Point to **Most similar historical periods**.

> "And we surface the three historical windows whose macro signature is closest by cosine
> similarity, with what actually happened."

## 3:30 — Recommendations (40s)

Go to **Recommendations**.

> "Each hedge cites the specific weakness it addresses — here, high tech concentration and high
> beta. It shows the instrument, the hedge ratio with the calculation expanded step by step, the
> estimated annual cost in basis points, and how much of the stress loss it would have offset."

Expand one "Show hedge-ratio calculation".

## 4:10 — Close on engineering (30s)

Go to **Settings** to show data-source health, then close:

> "Architecturally: a swappable data-provider abstraction, clean domain/service/API layering with
> typed Pydantic contracts, scenario execution that runs inline or on a Celery worker through one
> shared executor, and 235 passing tests. The emphasis throughout is interpretability — every method
> is defensible from first principles, and nothing uses synthetic data."

---

## One-liner per role

- **SWE:** provider abstraction, typed API, dual sync/async execution, test coverage.
- **Quant:** Fama-French decomposition, historical VaR/CVaR, correlation breakdown, hedge-ratio math.
- **Consulting:** the three user questions, cited recommendations, explainability layer.
