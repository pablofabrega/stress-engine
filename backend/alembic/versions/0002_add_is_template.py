"""Add is_template flag to user_portfolios."""

from alembic import op
import sqlalchemy as sa


revision = "0002_add_is_template"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_portfolios",
        sa.Column("is_template", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("user_portfolios", "is_template")
