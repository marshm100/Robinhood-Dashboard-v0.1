import csv
import logging
from decimal import Decimal, InvalidOperation
from io import StringIO
from typing import List, Dict, Tuple

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
import pandas as pd

from api.database import get_db
from api.models.portfolio import Holding
from api.services.blob_service import archive_upload

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/upload", tags=["upload"])


def detect_csv_type(df: pd.DataFrame) -> str:
    """
    Detect whether CSV is a Robinhood transaction history or a simple holdings snapshot.

    Returns: "transactions" or "holdings"
    """
    columns_lower = [c.lower().strip() for c in df.columns]

    # Robinhood transaction history has these columns
    robinhood_markers = ["trans code", "activity date", "instrument", "description"]
    if any(marker in columns_lower for marker in robinhood_markers):
        return "transactions"

    # Simple holdings file has ticker/symbol and shares/quantity
    has_ticker = any(c in columns_lower for c in ["ticker", "symbol"])
    has_shares = any(c in columns_lower for c in ["shares", "quantity", "amount"])
    if has_ticker and has_shares:
        return "holdings"

    # Default to trying transaction parser for unknown formats
    return "unknown"


def parse_robinhood_transactions(csv_content: str, portfolio_id: int) -> Tuple[List[Holding], Dict]:
    """
    Parse Robinhood transaction history CSV and compute current holdings.

    Handles:
    - Buy transactions (including fractional shares)
    - Sell transactions (reduces holdings with average cost basis)
    - CDIV (dividend reinvestment)
    - Stock splits (via quantity adjustments)

    Returns:
    - List of Holding objects with computed shares and cost basis
    - Stats dict with transaction counts
    """
    try:
        df = pd.read_csv(
            StringIO(csv_content),
            engine="python",
            on_bad_lines="skip",
            quoting=csv.QUOTE_ALL,
            dtype=str,
            encoding="utf-8"
        )
    except Exception as e:
        logger.error(f"Failed to parse CSV: {e}")
        raise ValueError(f"Failed to parse CSV: {e}")

    # Clean column names
    df.columns = df.columns.str.strip()
    df = df.fillna("")

    logger.info(f"Transaction CSV columns: {list(df.columns)}")

    # Track holdings: ticker -> {shares, total_cost}
    holdings: Dict[str, Dict[str, Decimal]] = {}
    stats = {
        "total_rows": len(df),
        "buys": 0,
        "sells": 0,
        "dividends": 0,
        "skipped": 0,
        "tickers_found": set()
    }

    for idx, row in df.iterrows():
        try:
            # Get ticker - try multiple column names
            ticker = ""
            for col in ["Instrument", "Symbol", "Ticker", "instrument", "symbol", "ticker"]:
                if col in row and row[col]:
                    ticker = str(row[col]).strip().upper()
                    break

            if not ticker or ticker in ["", "NAN", "NONE"]:
                stats["skipped"] += 1
                continue

            # Get transaction code
            trans_code = ""
            for col in ["Trans Code", "Trans. Code", "Transaction", "trans code", "Type", "type"]:
                if col in row and row[col]:
                    trans_code = str(row[col]).strip()
                    break

            # Parse quantity
            quantity = Decimal("0")
            for col in ["Quantity", "Qty", "Shares", "quantity", "qty", "shares"]:
                if col in row and row[col]:
                    try:
                        qty_str = str(row[col]).replace(",", "").strip()
                        if qty_str and qty_str.lower() not in ["", "nan", "none"]:
                            quantity = Decimal(qty_str)
                            break
                    except (InvalidOperation, ValueError):
                        pass

            # Parse price
            price = Decimal("0")
            for col in ["Price", "price", "Unit Price", "Share Price"]:
                if col in row and row[col]:
                    try:
                        price_str = str(row[col]).replace("$", "").replace(",", "").strip()
                        if price_str and price_str.lower() not in ["", "nan", "none"]:
                            price = Decimal(price_str)
                            break
                    except (InvalidOperation, ValueError):
                        pass

            # Parse amount (total transaction value)
            amount = Decimal("0")
            for col in ["Amount", "amount", "Total", "Value"]:
                if col in row and row[col]:
                    try:
                        amt_str = str(row[col]).replace("$", "").replace(",", "")
                        amt_str = amt_str.replace("(", "-").replace(")", "").strip()
                        if amt_str and amt_str.lower() not in ["", "nan", "none"]:
                            amount = Decimal(amt_str)
                            break
                    except (InvalidOperation, ValueError):
                        pass

            # Initialize ticker if new
            if ticker not in holdings:
                holdings[ticker] = {"shares": Decimal("0"), "total_cost": Decimal("0")}

            # Process based on transaction type
            trans_upper = trans_code.upper()

            if trans_upper in ["BUY", "CDIV", "DRIP", "ACH", "REINVEST"]:
                # Buy or dividend reinvestment
                if quantity > 0:
                    cost = abs(amount) if amount != 0 else quantity * price
                    holdings[ticker]["shares"] += quantity
                    holdings[ticker]["total_cost"] += cost
                    stats["buys"] += 1
                    if trans_upper in ["CDIV", "DRIP", "REINVEST"]:
                        stats["dividends"] += 1
                    stats["tickers_found"].add(ticker)

            elif trans_upper in ["SELL", "SLD"]:
                # Sell - reduce holdings using average cost basis
                if quantity > 0 and holdings[ticker]["shares"] > 0:
                    avg_cost = holdings[ticker]["total_cost"] / holdings[ticker]["shares"]
                    sold_cost = avg_cost * quantity
                    holdings[ticker]["shares"] -= quantity
                    holdings[ticker]["total_cost"] -= sold_cost
                    stats["sells"] += 1
                    stats["tickers_found"].add(ticker)

            elif trans_upper in ["SPLIT", "STKSPLT"]:
                # Stock split - just adjust quantity, cost basis stays same
                if quantity != 0:
                    holdings[ticker]["shares"] = quantity
                    stats["tickers_found"].add(ticker)

            else:
                # Unknown transaction type - log but skip
                if trans_code:
                    logger.debug(f"Skipping unknown trans code '{trans_code}' for {ticker}")
                stats["skipped"] += 1

        except Exception as e:
            logger.warning(f"Error processing row {idx}: {e}")
            stats["skipped"] += 1
            continue

    # Build Holding objects from aggregated data
    result = []
    for ticker, data in holdings.items():
        # Clean up near-zero positions
        if data["shares"] < Decimal("0.0001"):
            continue

        # Calculate average cost basis
        if data["shares"] > 0:
            avg_cost_per_share = data["total_cost"] / data["shares"]
            total_cost_basis = float(data["total_cost"])
        else:
            total_cost_basis = None

        result.append(Holding(
            portfolio_id=portfolio_id,
            ticker=ticker,
            shares=float(data["shares"]),
            cost_basis=total_cost_basis
        ))

    stats["tickers_found"] = len(stats["tickers_found"])
    stats["holdings_created"] = len(result)

    logger.info(f"Transaction parsing complete: {stats}")
    return result, stats


def parse_simple_holdings(csv_content: str, portfolio_id: int) -> Tuple[List[Holding], Dict]:
    """
    Parse simple holdings CSV (ticker, shares, optional cost_basis columns).

    Returns:
    - List of Holding objects
    - Stats dict
    """
    try:
        df = pd.read_csv(StringIO(csv_content))
    except Exception as e:
        raise ValueError(f"Failed to parse CSV: {e}")

    df.columns = df.columns.str.strip()
    columns_lower = {c.lower(): c for c in df.columns}

    # Find ticker column
    ticker_col = None
    for name in ["ticker", "symbol"]:
        if name in columns_lower:
            ticker_col = columns_lower[name]
            break

    # Find shares column
    shares_col = None
    for name in ["shares", "quantity", "amount"]:
        if name in columns_lower:
            shares_col = columns_lower[name]
            break

    if not ticker_col or not shares_col:
        raise ValueError("CSV must contain ticker/symbol and shares/quantity columns")

    # Find optional cost basis column
    cost_col = None
    for name in ["cost_basis", "cost basis", "costbasis", "cost"]:
        if name in columns_lower:
            cost_col = columns_lower[name]
            break

    result = []
    stats = {"total_rows": len(df), "holdings_created": 0, "skipped": 0}

    for _, row in df.iterrows():
        try:
            ticker = str(row[ticker_col]).upper().strip()
            if not ticker or ticker in ["", "NAN", "NONE"] or ticker.startswith("--"):
                stats["skipped"] += 1
                continue

            shares = float(row[shares_col])
            if shares <= 0:
                stats["skipped"] += 1
                continue

            cost_basis = None
            if cost_col and pd.notna(row[cost_col]):
                try:
                    cost_basis = float(str(row[cost_col]).replace("$", "").replace(",", ""))
                except ValueError:
                    pass

            result.append(Holding(
                portfolio_id=portfolio_id,
                ticker=ticker,
                shares=shares,
                cost_basis=cost_basis
            ))
            stats["holdings_created"] += 1

        except Exception as e:
            logger.warning(f"Error parsing row: {e}")
            stats["skipped"] += 1
            continue

    return result, stats


@router.post("/{portfolio_id}")
async def upload_csv(
    portfolio_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a CSV file to populate portfolio holdings.

    Supports two formats:
    1. Robinhood transaction history (with Trans Code, Instrument, etc.)
    2. Simple holdings snapshot (with ticker/symbol, shares/quantity columns)

    The parser auto-detects the format and processes accordingly.
    For transaction history, it computes current holdings from buy/sell activity.
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    contents = await file.read()
    csv_content = contents.decode("utf-8")

    # Archive the upload
    archive_url = await archive_upload(file.filename, contents)

    # Detect CSV type
    try:
        df = pd.read_csv(
            StringIO(csv_content),
            engine="python",
            on_bad_lines="skip",
            nrows=5  # Just peek at first few rows
        )
        csv_type = detect_csv_type(df)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read CSV: {e}")

    logger.info(f"Detected CSV type: {csv_type}")

    # Parse based on type
    try:
        if csv_type == "transactions":
            holdings, stats = parse_robinhood_transactions(csv_content, portfolio_id)
            parse_method = "Robinhood transaction history"
        else:
            holdings, stats = parse_simple_holdings(csv_content, portfolio_id)
            parse_method = "Simple holdings"
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not holdings:
        raise HTTPException(
            status_code=400,
            detail="No valid holdings found in CSV. Check the file format."
        )

    # Clear existing holdings (replace mode)
    db.query(Holding).filter(Holding.portfolio_id == portfolio_id).delete()

    # Add new holdings
    for holding in holdings:
        db.add(holding)

    db.commit()

    return {
        "status": "success",
        "parse_method": parse_method,
        "holdings_added": len(holdings),
        "stats": stats,
        "archive_url": archive_url,
        "note": "Previous holdings cleared and replaced"
    }
