from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload
from api.database import get_db
from api.models.portfolio import Portfolio
from api.services.analysis_service import (
    calculate_portfolio_returns,
    calculate_portfolio_returns_from_transactions,
)

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("/compare/{portfolio_id}")
def compare_portfolio(
    portfolio_id: int,
    benchmark: str = "SPY",
    period: str = "1y",
    track_to_present: bool = True,
    db: Session = Depends(get_db),
):
    portfolio = (
        db.query(Portfolio)
        .options(
            selectinload(Portfolio.holdings),
            selectinload(Portfolio.transactions),
        )
        .filter(Portfolio.id == portfolio_id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    # Prefer transaction-based DCA series when transactions are available
    if portfolio.transactions:
        result = calculate_portfolio_returns_from_transactions(
            portfolio.transactions, benchmark, track_to_present,
        )
    else:
        result = calculate_portfolio_returns(
            portfolio.holdings, benchmark, period,
        )

    return result
