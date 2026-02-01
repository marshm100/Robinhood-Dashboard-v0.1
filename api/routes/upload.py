import csv
from io import StringIO

import pandas as pd
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session

from api.database import get_db
from api.models.portfolio import Holding
from api.services.blob_service import archive_upload

router = APIRouter(prefix="/api/upload", tags=["upload"])


def _parse_transaction_history(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse a Robinhood-style transaction history CSV.

    Expected columns (case-insensitive): instrument, trans code, quantity.
    Buys add shares; sells subtract.  Net per instrument, drop dust.
    """
    df.columns = df.columns.str.lower().str.strip()

    required = ["instrument", "trans code", "quantity"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        return None  # not transaction-history format

    # Keep rows that reference an actual instrument
    df = df[df["instrument"].notna() & (df["instrument"].str.strip() != "")]
    df["instrument"] = df["instrument"].str.strip().str.upper()

    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df = df.dropna(subset=["quantity"])

    # Sells become negative quantities
    is_sell = df["trans code"].str.strip().str.upper() == "SELL"
    df.loc[is_sell, "quantity"] = -df.loc[is_sell, "quantity"].abs()

    # Net per instrument
    net = df.groupby("instrument")["quantity"].sum().reset_index()
    net = net[net["quantity"] > 0.01]  # ignore dust / fully-sold positions
    net.rename(columns={"instrument": "symbol", "quantity": "shares"}, inplace=True)
    return net


def _parse_simple_holdings(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fallback parser for simple CSVs with ticker/symbol + shares/quantity
    columns (and optional cost_basis).
    """
    df.columns = df.columns.str.lower().str.strip()

    ticker_cols = [c for c in df.columns if c in ("ticker", "symbol")]
    shares_cols = [c for c in df.columns if c in ("shares", "quantity")]
    if not ticker_cols or not shares_cols:
        return None

    out = df[[ticker_cols[0], shares_cols[0]]].copy()
    out.columns = ["symbol", "shares"]
    out["symbol"] = out["symbol"].astype(str).str.strip().str.upper()
    out["shares"] = pd.to_numeric(out["shares"], errors="coerce")
    out = out.dropna(subset=["shares"])
    out = out[out["shares"] > 0]
    out = out[~out["symbol"].str.startswith("--")]
    out = out[out["symbol"] != ""]

    # Aggregate in case there are duplicates
    out = out.groupby("symbol", as_index=False)["shares"].sum()
    return out


@router.post("/{portfolio_id}")
async def upload_holdings_csv(
    portfolio_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    contents = await file.read()
    archive_url = await archive_upload(file.filename, contents)

    # ── Read CSV robustly (handles multi-line quoted fields) ──────────
    try:
        df = pd.read_csv(
            StringIO(contents.decode("utf-8")),
            dtype=str,
            engine="python",
            on_bad_lines="skip",
            quoting=csv.QUOTE_ALL,
            skipinitialspace=True,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV read error: {e}")

    if df.empty:
        raise HTTPException(status_code=400, detail="CSV file is empty")

    # ── Try transaction-history format first, fall back to simple ─────
    holdings_df = _parse_transaction_history(df)
    fmt = "transaction_history"

    if holdings_df is None:
        holdings_df = _parse_simple_holdings(df)
        fmt = "simple"

    if holdings_df is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unrecognised CSV format. Upload either a Robinhood transaction "
                "history (columns: Instrument, Trans Code, Quantity) or a simple "
                "holdings file (columns: ticker/symbol, shares/quantity)."
            ),
        )

    if holdings_df.empty:
        raise HTTPException(
            status_code=400,
            detail="No net stock holdings found in the CSV.",
        )

    # ── Replace holdings in the portfolio ────────────────────────────
    db.query(Holding).filter(Holding.portfolio_id == portfolio_id).delete()

    added = 0
    for _, row in holdings_df.iterrows():
        db.add(
            Holding(
                portfolio_id=portfolio_id,
                ticker=row["symbol"],
                shares=float(row["shares"]),
                cost_basis=None,
            )
        )
        added += 1

    db.commit()

    return {
        "status": "success",
        "holdings_added": added,
        "archive_url": archive_url,
        "format_detected": fmt,
        "note": "Previous holdings cleared and replaced",
    }
