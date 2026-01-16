from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from api.database import get_db
from api.models.portfolio import Portfolio, Holding
from typing import List

router = APIRouter(prefix="/api/portfolios", tags=["portfolios"])

@router.post("/")
async def create_portfolio(name: str, db: AsyncSession = Depends(get_db)):
    portfolio = Portfolio(name=name)
    db.add(portfolio)
    await db.commit()
    await db.refresh(portfolio)
    return {"id": portfolio.id, "name": portfolio.name}

@router.get("/")
async def list_portfolios(db: AsyncSession = Depends(get_db)):
    return db.query(Portfolio).all()

@router.get("/{portfolio_id}")
def get_portfolio(portfolio_id: int, db: Session = Depends(get_db)):
    portfolio = await db.query(Portfolio).options(selectinload(Portfolio.holdings)).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolio

@router.post("/{portfolio_id}/holdings")
async def add_holding(
    portfolio_id: int,
    ticker: str,
    shares: float,
    cost_basis: float | None = None,
    db: Session = Depends(get_db)
):
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    holding = Holding(
        portfolio_id=portfolio_id,
        ticker=ticker.upper(),
        shares=shares,
        cost_basis=cost_basis
    )
    db.add(holding)
    db.commit()
    db.refresh(holding)
    return holding