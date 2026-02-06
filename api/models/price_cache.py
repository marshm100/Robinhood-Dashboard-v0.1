from sqlalchemy import Column, Integer, String, Float, BigInteger, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from api.database import Base


class Stock(Base):
    __tablename__ = "stocks"

    ticker = Column(String, primary_key=True)
    name = Column(String, nullable=True)
    sector = Column(String, nullable=True)
    last_fetched = Column(DateTime, nullable=True)

    prices = relationship("DailyPrice", back_populates="stock", cascade="all, delete-orphan")


class DailyPrice(Base):
    __tablename__ = "daily_prices"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, ForeignKey("stocks.ticker", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    close = Column(Float, nullable=False)
    volume = Column(BigInteger, nullable=True)

    stock = relationship("Stock", back_populates="prices")

    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_ticker_date"),
    )
