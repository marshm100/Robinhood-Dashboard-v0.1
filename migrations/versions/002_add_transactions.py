"""Add transactions table for time-weighted performance replay

Revision ID: 002_transactions
Revises: 001_historical_prices
Create Date: 2025-01-29

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002_transactions'
down_revision = '001_historical_prices'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('portfolio_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('trans_type', sa.String(length=20), nullable=False),
        sa.Column('ticker', sa.String(length=10), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=True),
        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['portfolio_id'], ['portfolios.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_transactions_id', 'transactions', ['id'], unique=False)
    op.create_index('ix_transactions_portfolio_id', 'transactions', ['portfolio_id'], unique=False)
    op.create_index('ix_transactions_date', 'transactions', ['date'], unique=False)
    op.create_index('ix_transactions_portfolio_date', 'transactions', ['portfolio_id', 'date'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_transactions_portfolio_date', table_name='transactions')
    op.drop_index('ix_transactions_date', table_name='transactions')
    op.drop_index('ix_transactions_portfolio_id', table_name='transactions')
    op.drop_index('ix_transactions_id', table_name='transactions')
    op.drop_table('transactions')
