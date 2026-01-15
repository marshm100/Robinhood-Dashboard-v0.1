"""
SQLAlchemy database models
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, UniqueConstraint, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from typing import Optional
import sqlite3
from .config import settings

Base = declarative_base()


class Transaction(Base):
    """Transaction model for storing Robinhood transaction data"""
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    activity_date = Column(String, nullable=False, index=True)
    ticker = Column(String, index=True)
    trans_code = Column(String, nullable=False)  # Buy, Sell, Dividend, etc.
    quantity = Column(Float)
    price = Column(Float)
    amount = Column(Float)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index('ix_transactions_date', 'activity_date'),
        Index('ix_transactions_ticker', 'ticker'),
        Index('ix_transactions_date_ticker', 'activity_date', 'ticker'),
    )


class StockPrice(Base):
    """Stock price model for caching historical prices"""
    __tablename__ = "stock_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=False, index=True)
    date = Column(String, nullable=False, index=True)
    close_price = Column(Float, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('ticker', 'date', name='uix_ticker_date'),
        Index('ix_stockprice_ticker', 'ticker'),
        Index('ix_stockprice_date', 'date'),
    )


class CustomPortfolio(Base):
    """Custom portfolio model for hypothetical portfolios"""
    __tablename__ = "custom_portfolios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    asset_allocation = Column(Text, nullable=False)  # JSON string: {"TICKER": weight, ...}
    strategy = Column(String)  # "lump_sum", "dca", etc.
    monthly_investment = Column(Float)  # For DCA strategy
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('ix_custom_portfolio_name', 'name'),
    )


class PortfolioSnapshot(Base):
    """Portfolio snapshot for storing historical portfolio values"""
    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, nullable=False, index=True)  # CustomPortfolio.id or -1 for Robinhood
    portfolio_type = Column(String, nullable=False)  # "custom", "robinhood", "benchmark"
    date = Column(String, nullable=False, index=True)
    total_value = Column(Float, nullable=False)
    holdings = Column(Text)  # JSON string of holdings at this date
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index('ix_snapshot_portfolio_date', 'portfolio_id', 'date'),
        Index('ix_snapshot_date', 'date'),
    )


def get_close_price(symbol: str, date: str) -> Optional[float]:
    """Pure function for price lookup; error-handled."""
    try:
        conn = sqlite3.connect(settings.stockr_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT close FROM prices WHERE symbol = ? AND date = ?", (symbol, date))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        print(f"DB error: {e}")
        return None  # Fallback
