"""Backfill sector / asset-class metadata onto existing holdings.

Re-resolves any holding whose sector or asset class is missing or "Unknown" —
useful for portfolios created before ingestion-time tagging existed. Idempotent:
holdings already tagged are left untouched.

Usage (from the ``backend`` directory)::

    python -m app.db.backfill                 # against DATABASE_URL
    python -m app.db.backfill --sqlite demo.db
"""

from __future__ import annotations

import argparse

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import UserPortfolio  # noqa: F401  (registers tables on Base.metadata)
from app.db.session import SessionLocal
from app.services import portfolio_service


def _session_factory(sqlite_path: str | None) -> sessionmaker[Session]:
    if sqlite_path is None:
        return SessionLocal
    engine = create_engine(f"sqlite:///{sqlite_path}", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill holding sector/asset-class metadata.")
    parser.add_argument(
        "--sqlite",
        metavar="PATH",
        default=None,
        help="Backfill a standalone SQLite file at PATH instead of DATABASE_URL.",
    )
    args = parser.parse_args()

    db = _session_factory(args.sqlite)()
    try:
        count = portfolio_service.backfill_holding_metadata(db)
        print(f"Backfilled metadata on {count} holding(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
