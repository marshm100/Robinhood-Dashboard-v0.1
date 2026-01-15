from fastapi import APIRouter
from api.services.price_service import get_single_ticker_prices

router = APIRouter(prefix="/api/stockr", tags=["stockr"])

@router.get("/prices/{ticker}")
def get_historical_prices(ticker: str, period: str = "1y"):
    prices = get_single_ticker_prices(ticker.upper(), period)
    if not prices:
        return {"ticker": ticker.upper(), "error": "No data found"}
    return {
        "ticker": ticker.upper(),
        "period": period,
        "prices": prices
    }