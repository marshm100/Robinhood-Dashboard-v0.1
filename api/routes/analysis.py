from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload
from api.database import get_db
from api.models.portfolio import Portfolio
from api.services.analysis_service import calculate_portfolio_returns

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

@router.get("/compare/{portfolio_id}")
def compare_portfolio(
    portfolio_id: int,
    benchmark: str = "SPY",
    period: str = "1y",
    track_present: Optional[str] = None,
    db: Session = Depends(get_db),
):
    portfolio = db.query(Portfolio).options(selectinload(Portfolio.holdings)).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    if track_present is not None:
        track_to_present = track_present not in ("0", "false", "off")
    else:
        track_to_present = bool(portfolio.track_to_present) if portfolio.track_to_present is not None else True

    result = calculate_portfolio_returns(
        portfolio.holdings, benchmark, period, db=db,
        inception_date=portfolio.inception_date,
        track_to_present=track_to_present,
        snapshot_date=portfolio.snapshot_date,
    )
    return result