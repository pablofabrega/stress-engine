"""Portable SQLAlchemy column types.

Production runs on PostgreSQL (native ``UUID`` and ``JSONB``), but the test
suite runs against in-memory SQLite. These helpers render the PostgreSQL types
on PostgreSQL and fall back to dialect-agnostic equivalents elsewhere, so the
same ORM models work in both environments without changing production behavior.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


def uuid_column_type() -> sa.types.TypeEngine:
    """UUID type: native ``UUID`` on PostgreSQL, ``CHAR(32)`` elsewhere."""

    return sa.Uuid(as_uuid=True)


def json_column_type() -> sa.types.TypeEngine:
    """JSON type: ``JSONB`` on PostgreSQL, generic ``JSON`` elsewhere."""

    return sa.JSON().with_variant(JSONB(), "postgresql")
