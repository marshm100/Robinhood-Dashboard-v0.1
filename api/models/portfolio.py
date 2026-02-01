from sqlalchemy import Column, Integer, String, Float, DateTime, Date, ForeignKey
from sqlalchemy.orm import relationship
from api.database import Base
from datetime import datetime

class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    inception_date = Column(Date, nullable=True)

    holdings = relationship("Holding", back_populates="portfolio")

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

class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, unique=True, index=True, nullable=False)
    sector = Column(String, index=True, nullable=True)