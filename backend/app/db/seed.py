"""Seed the database with demo data.

Creates the four preset portfolios (with deterministic, offline holdings derived
from each preset's target weights) and a set of ``pending`` scenario runs so the
application has data to display in a demo.

The script is idempotent: re-running it will not create duplicate portfolios or
duplicate runs for the same (portfolio, scenario) pair.

Usage (from the ``backend`` directory)::

    python -m app.db.seed

By default it seeds against the configured ``DATABASE_URL``. Pass ``--sqlite
PATH`` to seed a standalone SQLite file instead (handy for a local, no-Postgres
demo); the schema is created automatically in that case.

Note on scenario *results*: by default the seeded runs are executed immediately
against the configured market-data provider so the demo opens with real results
(pass ``--no-execute`` to leave them ``pending``). We never fabricate result
numbers; if data is unavailable a run is recorded as ``failed`` with the error,
rather than filled with synthetic values.
"""

from __future__ import annotations

import argparse

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import UserPortfolio  # noqa: F401  (ensures metadata is populated)
from app.db.models.scenario import ScenarioDefinition, ScenarioRun
from app.db.session import SessionLocal
from app.domain.portfolio.loader import PortfolioLoader
from app.domain.portfolio.metadata import STATIC_SECURITY_METADATA
from app.domain.portfolio.presets import get_preset_portfolios
from app.domain.scenarios.historical import HistoricalScenarioRunner
from app.domain.scenarios.hypothetical import HypotheticalScenarioRunner
from app.schemas.portfolio import HoldingInput
from app.services import portfolio_service, scenario_executor, scenario_service

# Total notional each preset portfolio is scaled to, and an assumed flat share
# price used only to turn target weights into share quantities. Because notional
# per holding = quantity * cost_basis = target_weight * TOTAL_NOTIONAL, the
# resulting nominal weights reproduce each preset's target weights exactly.
TOTAL_NOTIONAL = 1_000_000.0
ASSUMED_PRICE = 100.0

# Historical scenarios to attach to every seeded portfolio as pending runs.
DEFAULT_SCENARIO_KEYS = ("2008-gfc", "2020-covid-crash", "2022-rate-tightening")


def build_seed_holdings(target_weights: dict[str, float]) -> list[HoldingInput]:
    """Convert preset target weights into concrete, offline-taggable holdings."""

    holdings: list[HoldingInput] = []
    for ticker, weight in target_weights.items():
        metadata = STATIC_SECURITY_METADATA.get(ticker)
        quantity = round(weight * TOTAL_NOTIONAL / ASSUMED_PRICE, 6)
        holdings.append(
            HoldingInput(
                ticker=ticker,
                quantity=quantity,
                cost_basis=ASSUMED_PRICE,
                asset_class=metadata.asset_class if metadata else None,
                sector=metadata.sector if metadata else None,
            )
        )
    return holdings


def seed_portfolios(db: Session) -> list[UserPortfolio]:
    """Create the preset portfolios if they do not already exist (by name)."""

    portfolios: list[UserPortfolio] = []
    for preset in get_preset_portfolios():
        existing = db.execute(
            select(UserPortfolio).where(UserPortfolio.name == preset.name)
        ).scalars().first()
        if existing is not None:
            print(f"  portfolio exists, skipping: {preset.name}")
            portfolios.append(existing)
            continue

        portfolio = portfolio_service.create_portfolio(
            db,
            name=preset.name,
            holdings=build_seed_holdings(preset.target_weights),
        )
        print(f"  created portfolio: {preset.name} ({len(preset.target_weights)} holdings)")
        portfolios.append(portfolio)
    return portfolios


def seed_scenario_runs(
    db: Session,
    portfolios: list[UserPortfolio],
    scenario_keys: tuple[str, ...] = DEFAULT_SCENARIO_KEYS,
) -> list[ScenarioRun]:
    """Create one pending run per (portfolio, scenario), skipping duplicates."""

    runs: list[ScenarioRun] = []
    for portfolio in portfolios:
        for key in scenario_keys:
            scenario = scenario_service.resolve_scenario(db, key)
            if scenario is None:
                print(f"  unknown scenario key, skipping: {key}")
                continue

            already = db.execute(
                select(ScenarioRun).where(
                    ScenarioRun.portfolio_id == portfolio.id,
                    ScenarioRun.scenario_id == scenario.id,
                )
            ).scalars().first()
            if already is not None:
                continue

            run = scenario_service.create_run(db, portfolio_id=portfolio.id, scenario=scenario)
            runs.append(run)
            print(f"  queued run: {portfolio.name} -> {scenario.name} [pending]")
    return runs


def execute_pending_runs(db: Session) -> int:
    """Execute every ``pending`` scenario run against the real engines.

    Errors are captured onto the run record (status ``failed``) by the executor,
    so a missing data provider degrades gracefully instead of aborting the seed.
    """

    loader = PortfolioLoader()
    historical_runner = HistoricalScenarioRunner()
    hypothetical_runner = HypotheticalScenarioRunner()

    pending = db.execute(select(ScenarioRun).where(ScenarioRun.status == "pending")).scalars().all()
    for run in pending:
        scenario = db.get(ScenarioDefinition, run.scenario_id)
        if scenario is None:
            continue
        scenario_executor.execute_run(
            db,
            run,
            scenario,
            loader=loader,
            historical_runner=historical_runner,
            hypothetical_runner=hypothetical_runner,
        )
        print(f"  executed run {run.id}: {run.status}")
    return len(pending)


def seed(db: Session, execute: bool = True) -> None:
    """Run the full seed routine."""

    print("Seeding preset portfolios...")
    portfolios = seed_portfolios(db)
    print("Seeding scenario runs...")
    runs = seed_scenario_runs(db, portfolios)
    executed = 0
    if execute:
        print("Executing pending scenario runs (real market data)...")
        executed = execute_pending_runs(db)
    state = f"{executed} runs executed" if execute else f"{len(runs)} new pending runs created"
    print(f"Done: {len(portfolios)} portfolios present, {state}.")


def _session_factory(sqlite_path: str | None) -> sessionmaker[Session]:
    if sqlite_path is None:
        return SessionLocal
    engine = create_engine(f"sqlite:///{sqlite_path}", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo data for the stress workbench.")
    parser.add_argument(
        "--sqlite",
        metavar="PATH",
        default=None,
        help="Seed a standalone SQLite file at PATH (schema auto-created) instead of DATABASE_URL.",
    )
    parser.add_argument(
        "--no-execute",
        dest="execute",
        action="store_false",
        help="Leave scenario runs in the 'pending' state instead of executing them.",
    )
    parser.set_defaults(execute=True)
    args = parser.parse_args()

    factory = _session_factory(args.sqlite)
    db = factory()
    try:
        seed(db, execute=args.execute)
    finally:
        db.close()


if __name__ == "__main__":
    main()
