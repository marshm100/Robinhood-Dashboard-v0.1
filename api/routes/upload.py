from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from api.database import get_db
from api.models.portfolio import Holding, Transaction
from api.services.blob_service import archive_upload
import pandas as pd
from io import StringIO
from collections import defaultdict
from datetime import datetime

router = APIRouter(prefix="/api/upload", tags=["upload"])


def _find_col(df_columns, candidates):
    """Return the first column whose lowered name matches any candidate."""
    for c in df_columns:
        if c.strip().lower() in candidates:
            return c
    return None


def _parse_float(val):
    """Best-effort float parse: strip $, commas, parens for negatives."""
    if pd.isna(val):
        return None
    s = str(val).strip().replace("$", "").replace(",", "")
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _is_transaction_csv(df):
    """Detect whether the CSV has Robinhood transaction-history columns."""
    cols_lower = {c.strip().lower() for c in df.columns}
    has_date = any("activity" in c and "date" in c for c in cols_lower) or "date" in cols_lower
    has_instrument = bool(cols_lower & {"instrument", "ticker", "symbol"})
    has_trans = any("trans" in c for c in cols_lower)
    return has_date and has_instrument and has_trans


def _parse_transactions(df, portfolio_id):
    """Parse a Robinhood transaction-history CSV into Transaction objects.

    Returns (transactions, net_holdings_dict) where net_holdings_dict maps
    ticker -> {shares, total_cost} computed from buy legs.
    """
    # Flexible column resolution
    date_col = _find_col(df.columns, {"activity date", "date"})
    instr_col = _find_col(df.columns, {"instrument", "ticker", "symbol"})
    trans_col = _find_col(df.columns, {"trans code", "trans_code", "transaction code", "type"})
    qty_col = _find_col(df.columns, {"quantity", "shares", "qty"})
    price_col = _find_col(df.columns, {"price"})
    amount_col = _find_col(df.columns, {"amount"})

    if not (date_col and instr_col and trans_col):
        return [], {}

    valid_codes = {"buy", "sell", "cdiv"}
    transactions = []
    # For computing net holdings and weighted avg cost
    holdings_acc = defaultdict(lambda: {"shares": 0.0, "total_cost": 0.0})

    for _, row in df.iterrows():
        try:
            instrument = str(row[instr_col]).strip().upper()
            if not instrument or instrument in ("NAN", "NONE", ""):
                continue

            code_raw = str(row[trans_col]).strip().lower()
            if code_raw not in valid_codes:
                continue

            # Parse date
            activity_date = pd.to_datetime(row[date_col]).date()

            # Parse quantity (always stored positive in CSV; we add sign)
            raw_qty = _parse_float(row[qty_col]) if qty_col else None
            if raw_qty is None or raw_qty == 0:
                continue
            qty = abs(raw_qty)

            price = _parse_float(row[price_col]) if price_col else None
            amount = _parse_float(row[amount_col]) if amount_col else None

            # Sign convention: Buy/CDIV positive, Sell negative
            if code_raw == "sell":
                signed_qty = -qty
            else:
                signed_qty = qty  # buy or cdiv (reinvest)

            transactions.append(Transaction(
                portfolio_id=portfolio_id,
                activity_date=activity_date,
                ticker=instrument,
                quantity=signed_qty,
                price=price,
                amount=amount,
            ))

            # Accumulate for net holdings
            acc = holdings_acc[instrument]
            acc["shares"] += signed_qty
            if signed_qty > 0 and price is not None:
                acc["total_cost"] += qty * price

        except Exception:
            continue

    return transactions, dict(holdings_acc)


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

    try:
        df = pd.read_csv(StringIO(contents.decode("utf-8")))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV format: {str(e)}")

    # --- Transaction-history CSV path -----------------------------------
    if _is_transaction_csv(df):
        transactions, holdings_acc = _parse_transactions(df, portfolio_id)
        if not transactions:
            raise HTTPException(
                status_code=400,
                detail="No valid Buy/Sell/CDIV rows found in transaction CSV",
            )

        # Clear old transactions & holdings for this portfolio
        db.query(Transaction).filter(Transaction.portfolio_id == portfolio_id).delete()
        db.query(Holding).filter(Holding.portfolio_id == portfolio_id).delete()

        # Persist transactions
        for txn in transactions:
            db.add(txn)

        # Derive net holdings from transactions
        holdings_added = 0
        for ticker, acc in holdings_acc.items():
            net_shares = acc["shares"]
            if net_shares <= 0:
                continue  # fully sold or short — skip from holdings
            total_cost = acc["total_cost"]
            # Weighted avg cost = total dollars spent on buys / total shares bought
            # total_cost already accumulated only buy legs
            cost_basis = total_cost  # total dollars spent
            holding = Holding(
                portfolio_id=portfolio_id,
                ticker=ticker,
                shares=round(net_shares, 6),
                cost_basis=round(cost_basis, 2) if cost_basis else None,
            )
            db.add(holding)
            holdings_added += 1

        db.commit()
        return {
            "status": "success",
            "transactions_stored": len(transactions),
            "holdings_added": holdings_added,
            "archive_url": archive_url,
            "note": "Transaction history stored; net holdings derived from transactions",
        }

    # --- Simple holdings CSV path (legacy) ------------------------------
    ticker_cols = [c for c in df.columns if c.lower() in ["ticker", "symbol"]]
    shares_cols = [c for c in df.columns if c.lower() in ["shares", "quantity", "amount"]]
    if not ticker_cols or not shares_cols:
        raise HTTPException(
            status_code=400,
            detail="CSV must contain ticker/symbol and shares/quantity columns, "
                   "or be a Robinhood transaction-history CSV",
        )

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
            holding = Holding(
                portfolio_id=portfolio_id,
                ticker=ticker,
                shares=shares,
                cost_basis=cost_basis,
            )
            db.add(holding)
            added += 1
        except Exception:
            continue

    db.commit()
    return {
        "status": "success",
        "holdings_added": added,
        "archive_url": archive_url,
        "note": "Previous holdings cleared and replaced",
    }
