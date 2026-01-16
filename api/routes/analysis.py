from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from api.database import get_db
from api.models.portfolio import Portfolio
from api.services.analysis_service import calculate_portfolio_returns

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

@router.get("/compare/{portfolio_id}")
async def compare_portfolio(
    portfolio_id: int,
    benchmark: str = "SPY",
    period: str = "1y",
    db: AsyncSession = Depends(get_db)
):
    portfolio = await db.query(Portfolio).options(selectinload(Portfolio.holdings)).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    result = calculate_portfolio_returns(portfolio.holdings, benchmark, period)
    return result