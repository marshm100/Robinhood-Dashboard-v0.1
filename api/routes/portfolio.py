from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from api.database import get_db
from api.models.portfolio import Portfolio, Holding

router = APIRouter(prefix="/api/portfolios", tags=["portfolios"])

@router.post("/")
def create_portfolio(name: str, db: Session = Depends(get_db)):
    portfolio = Portfolio(name=name)
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return {"id": portfolio.id, "name": portfolio.name}

@router.get("/")
def list_portfolios(db: Session = Depends(get_db)):
    return db.query(Portfolio).all()