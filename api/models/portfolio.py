from sqlalchemy import Column, Integer, String, Float, DateTime, Date, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from api.database import Base
from datetime import datetime


class HistoricalPrice(Base):
    """
    Persistent cache for historical stock prices.
    Stores daily close prices fetched from yfinance.
    """
    __tablename__ = "historical_prices"
    __table_args__ = (
        UniqueConstraint('ticker', 'date', name='uq_ticker_date'),
        Index('ix_historical_prices_ticker_date', 'ticker', 'date'),
    )

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(10), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    close_price = Column(Float, nullable=False)
    fetched_at = Column(DateTime, default=datetime.utcnow)


class Transaction(Base):
    """
    Individual transaction record from Robinhood CSV or manual entry.
    Used for time-weighted performance calculation via replay.
    """
    __tablename__ = "transactions"
    __table_args__ = (
        Index('ix_transactions_portfolio_date', 'portfolio_id', 'date'),
    )

    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    trans_type = Column(String(20), nullable=False)  # BUY, SELL, CDIV, DEPOSIT, WITHDRAWAL, etc.
    ticker = Column(String(10), nullable=True)  # Null for cash transactions
    quantity = Column(Float, nullable=True)  # Shares bought/sold
    price = Column(Float, nullable=True)  # Price per share
    amount = Column(Float, nullable=False)  # Total cash amount (negative for buys, positive for sells)
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    portfolio = relationship("Portfolio", back_populates="transactions")


class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    holdings = relationship("Holding", back_populates="portfolio", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="portfolio", cascade="all, delete-orphan")


class Holding(Base):
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"))
    ticker = Column(String)
    shares = Column(Float)
    cost_basis = Column(Float)

    portfolio = relationship("Portfolio", back_populates="holdings")


class Benchmark(Base):
    __tablename__ = "benchmarks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    ticker = Column(String)  # e.g., SPY for S&P 500
