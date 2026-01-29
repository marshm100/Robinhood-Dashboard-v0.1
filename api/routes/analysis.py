from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload
from api.database import get_db
from api.models.portfolio import Portfolio, Transaction
from api.services.analysis_service import (
    calculate_portfolio_returns,
    calculate_time_weighted_performance,
    calculate_portfolio_metrics,
)

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("/compare/{portfolio_id}")
def compare_portfolio(
    portfolio_id: int,
    benchmark: str = "SPY",
    period: str = "1y",
    force_snapshot: bool = Query(False, description="Force snapshot mode even if transactions available"),
    db: Session = Depends(get_db)
):
    """
    Compare portfolio performance against a benchmark.

    Automatically uses time-weighted calculation if transaction history is available,
    otherwise falls back to snapshot-based calculation.

    Args:
        portfolio_id: Portfolio ID
        benchmark: Benchmark ticker (SPY, QQQ, IWM, DIA)
        period: Time period (1mo, 3mo, 6mo, 1y, 2y) - only used for snapshot mode
        force_snapshot: Force snapshot mode even if transactions available
    """
    portfolio = db.query(Portfolio).options(
        selectinload(Portfolio.holdings)
    ).filter(Portfolio.id == portfolio_id).first()

    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    # Check if we have transaction history
    has_transactions = db.query(Transaction).filter(
        Transaction.portfolio_id == portfolio_id
    ).count() > 0

    if has_transactions and not force_snapshot:
        # Use time-weighted calculation with transaction replay
        result = calculate_time_weighted_performance(portfolio_id, benchmark, db)
    else:
        # Use snapshot-based calculation
        result = calculate_portfolio_returns(portfolio.holdings, benchmark, period)

    return result


@router.get("/time-weighted/{portfolio_id}")
def time_weighted_performance(
    portfolio_id: int,
    benchmark: str = "SPY",
    db: Session = Depends(get_db)
):
    """
    Get accurate time-weighted portfolio performance using transaction replay.

    This endpoint requires transaction history to be uploaded via Robinhood CSV.
    It replays all transactions chronologically to compute daily portfolio value.

    Returns:
        - Daily portfolio values and returns
        - Benchmark comparison
        - CAGR, max drawdown, alpha, cash drag metrics
    """
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()

    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    result = calculate_time_weighted_performance(portfolio_id, benchmark, db)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/snapshot/{portfolio_id}")
def snapshot_performance(
    portfolio_id: int,
    benchmark: str = "SPY",
    period: str = "1y",
    db: Session = Depends(get_db)
):
    """
    Get snapshot-based portfolio performance (assumes constant holdings).

    This calculation assumes current holdings were held for the entire period.
    For accurate time-weighted returns, use the /time-weighted endpoint.
    """
    portfolio = db.query(Portfolio).options(
        selectinload(Portfolio.holdings)
    ).filter(Portfolio.id == portfolio_id).first()

    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    result = calculate_portfolio_returns(portfolio.holdings, benchmark, period)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/metrics/{portfolio_id}")
def portfolio_metrics(
    portfolio_id: int,
    db: Session = Depends(get_db)
):
    """
    Get current portfolio metrics including position values and allocation.
    """
    portfolio = db.query(Portfolio).options(
        selectinload(Portfolio.holdings)
    ).filter(Portfolio.id == portfolio_id).first()

    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    result = calculate_portfolio_metrics(portfolio.holdings)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/transactions/{portfolio_id}")
def get_transactions(
    portfolio_id: int,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Get transaction history for a portfolio.
    """
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()

    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    total = db.query(Transaction).filter(
        Transaction.portfolio_id == portfolio_id
    ).count()

    transactions = db.query(Transaction).filter(
        Transaction.portfolio_id == portfolio_id
    ).order_by(Transaction.date.desc()).offset(offset).limit(limit).all()

    return {
        "portfolio_id": portfolio_id,
        "total": total,
        "limit": limit,
        "offset": offset,
        "transactions": [
            {
                "id": t.id,
                "date": t.date.isoformat(),
                "trans_type": t.trans_type,
                "ticker": t.ticker,
                "quantity": t.quantity,
                "price": t.price,
                "amount": t.amount,
                "description": t.description,
            }
            for t in transactions
        ]
    }
