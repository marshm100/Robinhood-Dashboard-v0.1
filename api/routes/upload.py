from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import get_db
from api.models.portfolio import Holding
import pandas as pd
from io import StringIO

router = APIRouter(prefix="/api/upload", tags=["upload"])

@router.post("/{portfolio_id}")
async def upload_holdings_csv(portfolio_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    contents = await file.read()
    from api.services.blob_service import archive_upload
    archive_url = await archive_upload(file.filename, contents)
    try:
        df = pd.read_csv(StringIO(contents.decode("utf-8")))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV format: {str(e)}")

    # Flexible column detection
    ticker_cols = [c for c in df.columns if c.lower() in ["ticker", "symbol"]]
    shares_cols = [c for c in df.columns if c.lower() in ["shares", "quantity", "amount"]]
    if not ticker_cols or not shares_cols:
        raise HTTPException(status_code=400, detail="CSV must contain ticker/symbol and shares/quantity columns")

    ticker_col = ticker_cols[0]
    shares_col = shares_cols[0]
    cost_cols = [c for c in df.columns if "cost" in c.lower()]
    cost_col = cost_cols[0] if cost_cols else None

    # Clear existing holdings (replace mode)
    db.query(Holding).filter(Holding.portfolio_id == portfolio_id).delete()

    added = 0
    for _, row in df.iterrows():
        try:
            ticker = str(row[ticker_col]).upper().strip()
            if not ticker or ticker.startswith("--"):
                continue
            shares = float(row[shares_col])
            if shares <= 0:
                continue
            cost_basis = float(row[cost_col]) if cost_col and pd.notna(row[cost_col]) else None
            holding = Holding(portfolio_id=portfolio_id, ticker=ticker, shares=shares, cost_basis=cost_basis)
            db.add(holding)
            added += 1
        except:
            continue  # skip invalid rows

    await db.commit()
    return {"status": "success", "holdings_added": added, "note": "Previous holdings cleared and replaced", "archive_url": archive_url}