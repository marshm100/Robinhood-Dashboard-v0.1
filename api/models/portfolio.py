from sqlalchemy import Column, Integer, String, Float, DateTime, Date, ForeignKey
from sqlalchemy.orm import relationship
from api.database import Base
from datetime import datetime


class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    holdings = relationship("Holding", back_populates="portfolio")
    transactions = relationship(
        "Transaction", back_populates="portfolio",
        order_by="Transaction.activity_date",
    )


class Holding(Base):
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"))
    ticker = Column(String)
    shares = Column(Float)
    cost_basis = Column(Float)

    portfolio = relationship("Portfolio", back_populates="holdings")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"))
    activity_date = Column(Date)
    ticker = Column(String)
    quantity = Column(Float)          # signed: +Buy/CDIV, −Sell
    price = Column(Float, nullable=True)
    amount = Column(Float, nullable=True)

    portfolio = relationship("Portfolio", back_populates="transactions")


class Benchmark(Base):
    __tablename__ = "benchmarks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    ticker = Column(String)  # e.g., SPY for S&P 500