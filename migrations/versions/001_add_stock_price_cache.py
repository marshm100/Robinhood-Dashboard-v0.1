"""add stock price cache tables

Revision ID: 001
Revises:
Create Date: 2026-01-30
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stocks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stocks_id"), "stocks", ["id"])
    op.create_index(op.f("ix_stocks_symbol"), "stocks", ["symbol"], unique=True)

    op.create_table(
        "historical_prices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("open", sa.Float(), nullable=True),
        sa.Column("high", sa.Float(), nullable=True),
        sa.Column("low", sa.Float(), nullable=True),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["stock_id"], ["stocks.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stock_id", "date", name="uq_stock_date"),
    )
    op.create_index(op.f("ix_historical_prices_id"), "historical_prices", ["id"])
    op.create_index(
        op.f("ix_historical_prices_date"), "historical_prices", ["date"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_historical_prices_date"), table_name="historical_prices")
    op.drop_index(op.f("ix_historical_prices_id"), table_name="historical_prices")
    op.drop_table("historical_prices")
    op.drop_index(op.f("ix_stocks_symbol"), table_name="stocks")
    op.drop_index(op.f("ix_stocks_id"), table_name="stocks")
    op.drop_table("stocks")
