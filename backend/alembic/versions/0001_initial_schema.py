"""Initial schema for portfolios, scenarios, risk, and recommendations."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')

    op.create_table(
        "user_portfolios",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "scenario_definitions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "holdings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("portfolio_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("cost_basis", sa.Numeric(18, 6), nullable=True),
        sa.Column("asset_class", sa.String(length=64), nullable=True),
        sa.Column("sector", sa.String(length=128), nullable=True),
    )

    op.create_table(
        "scenario_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("portfolio_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scenario_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "risk_snapshots",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("portfolio_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("var_95", sa.Numeric(18, 6), nullable=True),
        sa.Column("var_99", sa.Numeric(18, 6), nullable=True),
        sa.Column("cvar_95", sa.Numeric(18, 6), nullable=True),
        sa.Column("max_drawdown", sa.Numeric(18, 6), nullable=True),
        sa.Column("rolling_vol", sa.Numeric(18, 6), nullable=True),
        sa.Column("concentration_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )

    op.create_table(
        "recommendations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("portfolio_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scenario_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scenario_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "data_source_statuses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("source_name", sa.String(length=64), nullable=False, unique=True),
        sa.Column("last_fetched", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("error_message", sa.Text(), nullable=True),
    )

    op.create_index("ix_holdings_portfolio_id", "holdings", ["portfolio_id"])
    op.create_index("ix_scenario_runs_portfolio_id", "scenario_runs", ["portfolio_id"])
    op.create_index("ix_scenario_runs_scenario_id", "scenario_runs", ["scenario_id"])
    op.create_index("ix_risk_snapshots_portfolio_id", "risk_snapshots", ["portfolio_id"])
    op.create_index("ix_recommendations_portfolio_id", "recommendations", ["portfolio_id"])
    op.create_index("ix_recommendations_scenario_run_id", "recommendations", ["scenario_run_id"])


def downgrade() -> None:
    op.drop_index("ix_recommendations_scenario_run_id", table_name="recommendations")
    op.drop_index("ix_recommendations_portfolio_id", table_name="recommendations")
    op.drop_index("ix_risk_snapshots_portfolio_id", table_name="risk_snapshots")
    op.drop_index("ix_scenario_runs_scenario_id", table_name="scenario_runs")
    op.drop_index("ix_scenario_runs_portfolio_id", table_name="scenario_runs")
    op.drop_index("ix_holdings_portfolio_id", table_name="holdings")
    op.drop_table("data_source_statuses")
    op.drop_table("recommendations")
    op.drop_table("risk_snapshots")
    op.drop_table("scenario_runs")
    op.drop_table("holdings")
    op.drop_table("scenario_definitions")
    op.drop_table("user_portfolios")

