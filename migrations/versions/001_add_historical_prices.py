"""Add historical_prices table for persistent price caching

Revision ID: 001_historical_prices
Revises:
Create Date: 2025-01-29

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001_historical_prices'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'historical_prices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ticker', sa.String(length=10), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('close_price', sa.Float(), nullable=False),
        sa.Column('fetched_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ticker', 'date', name='uq_ticker_date')
    )
    op.create_index('ix_historical_prices_id', 'historical_prices', ['id'], unique=False)
    op.create_index('ix_historical_prices_ticker', 'historical_prices', ['ticker'], unique=False)
    op.create_index('ix_historical_prices_date', 'historical_prices', ['date'], unique=False)
    op.create_index('ix_historical_prices_ticker_date', 'historical_prices', ['ticker', 'date'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_historical_prices_ticker_date', table_name='historical_prices')
    op.drop_index('ix_historical_prices_date', table_name='historical_prices')
    op.drop_index('ix_historical_prices_ticker', table_name='historical_prices')
    op.drop_index('ix_historical_prices_id', table_name='historical_prices')
    op.drop_table('historical_prices')
