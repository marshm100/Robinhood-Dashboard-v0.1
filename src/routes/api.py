"""
API routes for portfolio analysis
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
from io import StringIO
import time
from functools import lru_cache
import hashlib
import json

from src.database import get_db_sync
from src.models import Transaction, CustomPortfolio
from src.services import csv_processor, portfolio_calculator
from src.services.custom_portfolio_service import CustomPortfolioService
from src.config import get_temp_file_path
from pydantic import BaseModel, Field

# Simple caching decorator
def simple_cache(expire_seconds: int = 300):
    """Simple time-based cache decorator"""
    cache = {}

    def decorator(func):
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            key_data = {
                'func': func.__name__,
                'args': str(args),
                'kwargs': str(sorted(kwargs.items()))
            }
            cache_key = hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()

            current_time = time.time()

            # Check if cached result exists and is not expired
            if cache_key in cache:
                cached_time, cached_result = cache[cache_key]
                if current_time - cached_time < expire_seconds:
                    return cached_result

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache[cache_key] = (current_time, result)
            return result

        return wrapper
    return decorator

# Create router
router = APIRouter()


@router.get("/health")
def api_health():
    """API health check"""
    return {
        "status": "healthy",
        "service": "api",
        "version": "1.0.0",
        "timestamp": int(time.time())
    }


@router.post("/validate-csv")
async def validate_csv(file: UploadFile = File(...)):
    """Validate CSV file structure without processing"""
    try:
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="File must be a CSV")

        content = await file.read()
        csv_content = content.decode('utf-8')

        validation_result = csv_processor.validate_csv_structure(csv_content)
        return validation_result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating CSV: {str(e)}")


@router.post("/test-upload")
async def test_upload():
    """Simple test endpoint"""
    print("DEBUG: Test upload function called")
    debug_log_path = get_temp_file_path("debug_upload.log")
    with open(debug_log_path, "w") as f:
        f.write("Test upload function called\n")
    return {"message": "Test upload endpoint works"}

@router.post("/upload-csv")
async def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db_sync)
):
    """Upload and process Robinhood CSV file with security measures"""
    # Debug logging
    debug_log_path = get_temp_file_path("debug_upload.log")
    print("DEBUG: Upload function called")
    with open(debug_log_path, "w") as f:
        f.write("Upload function called\n")

    # Rate limiting - temporarily disabled for debugging
    # if not check_rate_limit(request):
    #     raise HTTPException(status_code=429, detail="Rate limit exceeded")

    try:
        # Validate file type
        if not file.filename or not file.filename.lower().endswith('.csv'):
            raise HTTPException(status_code=400, detail="File must be a CSV file")

        # Check file size (limit to 10MB)
        file_size = 0
        content_chunks = []
        chunk_size = 8192

        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            content_chunks.append(chunk)
            file_size += len(chunk)

            # Security: Prevent extremely large files
            if file_size > 10 * 1024 * 1024:  # 10MB limit
                raise HTTPException(status_code=413, detail="File too large (max 10MB)")

        # Reconstruct content
        content = b''.join(content_chunks)

        # Debug logging
        with open(debug_log_path, "w") as f:
            f.write(f"File reconstructed, size: {len(content)}\n")

        # Validate content type
        if not content:
            raise HTTPException(status_code=400, detail="File is empty")

        # Try to decode as UTF-8
        try:
            csv_content = content.decode('utf-8')
            with open(debug_log_path, "a") as f:
                f.write(f"CSV content length: {len(csv_content)}\n")
                f.write(f"First 500 chars: {csv_content[:500]}\n")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")

        # Process CSV with validation
        try:
            transactions_df = csv_processor.process_robinhood_csv(csv_content)
        except Exception as csv_error:
            import traceback
            raise HTTPException(status_code=400, detail=f"CSV processing failed: {str(csv_error)}")

        # Validate reasonable data size
        if len(transactions_df) == 0:
            raise HTTPException(status_code=400, detail="No valid transactions found in CSV")

        if len(transactions_df) > 10000:  # Reasonable upper limit
            raise HTTPException(status_code=413, detail="Too many transactions (max 10,000)")

        # Get count before deleting
        deleted_count = db.query(Transaction).count()
        
        # Clear existing transactions
        db.execute(Transaction.__table__.delete())
        db.commit()

        # Save to database in batches for performance
        transactions_saved = 0
        batch_size = 100

        for i in range(0, len(transactions_df), batch_size):
            batch = transactions_df.iloc[i:i+batch_size]

            # Prepare batch data for bulk insert
            batch_data = []
            for _, row in batch.iterrows():
                batch_data.append({
                    'activity_date': row['activity_date'],
                    'ticker': row.get('ticker'),
                    'trans_code': row['trans_code'],
                    'quantity': row.get('quantity'),
                    'price': row.get('price'),
                    'amount': row['amount']
                })

            # Bulk insert
            db.execute(Transaction.__table__.insert(), batch_data)
            transactions_saved += len(batch_data)

            # Commit batch
            db.commit()

        return {
            "message": "CSV processed successfully",
            "file_name": file.filename,
            "file_size": file_size,
            "transactions_processed": len(transactions_df),
            "transactions_saved": transactions_saved,
            "previous_transactions_deleted": deleted_count
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        # Log the actual error for debugging
        import logging
        logging.error(f"CSV upload failed: {str(e)}", exc_info=True)
        with open(debug_log_path, "a") as f:
            f.write(f"CSV upload failed: {str(e)}\n")
            import traceback
            f.write(traceback.format_exc())
        # Secure error handling - don't reveal internal details
        raise HTTPException(
            status_code=500,
            detail="CSV processing failed. Please ensure the file is a valid Robinhood export."
        )


@simple_cache(expire_seconds=60)  # Cache for 1 minute
@router.get("/portfolio-overview")
def get_portfolio_overview(db: Session = Depends(get_db_sync)):
    """Get comprehensive portfolio overview with current values"""
    import logging
    logger = logging.getLogger(__name__)

    logger.info("[API] Portfolio overview request started")

    # Check for transaction data before initializing calculator
    try:
        transaction_count = db.query(func.count(Transaction.id)).scalar() or 0
        logger.info(f"[API] Transaction count: {transaction_count}")
        
        # Return early with empty structure if no transactions exist
        if transaction_count == 0:
            logger.info("[API] No transactions found, returning empty structure")
            return {
                "has_data": False,
                "transaction_count": 0,
                "unique_tickers": 0,
                "current_holdings_count": 0,
                "holdings": {},
                "performance": {
                    "total_return": 0,
                    "total_value": 0,
                    "start_value": 0,
                    "start_date": "",
                    "end_date": ""
                },
                "performance_metrics": {},
                "risk_assessment": {},
                "advanced_analytics": {},
                "stock_database": {"status": "unknown"}
            }
    except Exception as e:
        logger.error(f"[API] Error checking transaction count: {e}", exc_info=True)
        # Continue anyway - calculator initialization will handle it

    # Initialize empty structure for partial data return
    overview_data = {
        "has_data": False,
        "transaction_count": 0,
        "unique_tickers": 0,
        "current_holdings_count": 0,
        "holdings": {},
        "performance": {
            "total_return": 0,
            "total_value": 0,
            "start_value": 0,
            "start_date": "",
            "end_date": ""
        },
        "performance_metrics": {},
        "risk_assessment": {},
        "advanced_analytics": {},
        "sector_allocation": {},
        "stock_database": {"status": "unknown"}
    }

    # Initialize calculator with error handling
    calculator = None
    try:
        logger.info("[API] Initializing portfolio calculator")
        from src.services.portfolio_calculator import PortfolioCalculator
        calculator = PortfolioCalculator(db)
        logger.info("[API] Portfolio calculator initialized successfully")
    except Exception as e:
        logger.error(f"[API] Error initializing portfolio calculator: {e}", exc_info=True)
        # Return empty structure if initialization fails completely
        overview_data["error"] = "Failed to initialize portfolio calculator"
        return overview_data

    # Get portfolio summary
    try:
        logger.info("[API] Getting portfolio summary")
        summary_data = calculator.get_portfolio_summary()
        if summary_data:
            overview_data.update(summary_data)
            logger.info(f"[API] Portfolio summary retrieved: {overview_data.get('transaction_count', 0)} transactions")
    except Exception as e:
        logger.error(f"[API] Error getting portfolio summary: {e}", exc_info=True)
        # Keep default empty structure

    # Add performance metrics
    try:
        logger.info("[API] Calculating performance metrics")
        performance_metrics = calculator.calculate_performance_metrics()
        if performance_metrics:
            overview_data["performance_metrics"] = performance_metrics
            logger.info("[API] Performance metrics calculated successfully")
    except Exception as e:
        logger.error(f"[API] Error calculating performance metrics: {e}", exc_info=True)
        overview_data["performance_metrics"] = {}

    # Add risk assessment
    try:
        logger.info("[API] Getting risk assessment")
        risk_assessment = calculator.get_risk_assessment()
        if risk_assessment:
            overview_data["risk_assessment"] = risk_assessment
            logger.info("[API] Risk assessment retrieved successfully")
    except Exception as e:
        logger.error(f"[API] Error getting risk assessment: {e}", exc_info=True)
        overview_data["risk_assessment"] = {}

    # Add sector allocation
    try:
        logger.info("[API] Getting sector allocation")
        sector_data = calculator.get_sector_allocation()
        if sector_data and "sector_allocation" in sector_data:
            overview_data["sector_allocation"] = sector_data.get("sector_allocation", {})
            overview_data["sector_count"] = sector_data.get("sector_count", 0)
            overview_data["largest_sector"] = sector_data.get("largest_sector", ("None", 0))
            logger.info(f"[API] Sector allocation retrieved successfully ({len(overview_data['sector_allocation'])} sectors)")
    except Exception as e:
        logger.error(f"[API] Error getting sector allocation: {e}", exc_info=True)
        overview_data["sector_allocation"] = {}

    # Add advanced analytics
    try:
        logger.info("[API] Getting advanced analytics")
        advanced_analytics = calculator.get_advanced_analytics()
        if advanced_analytics:
            overview_data["advanced_analytics"] = advanced_analytics
            logger.info("[API] Advanced analytics retrieved successfully")
    except Exception as e:
        logger.error(f"[API] Error getting advanced analytics: {e}", exc_info=True)
        overview_data["advanced_analytics"] = {}

    # Validate stock database connection
    try:
        from src.services import stock_price_service
        stock_db_status = stock_price_service.validate_database()
        overview_data["stock_database"] = stock_db_status
        logger.info("[API] Stock database validation completed")
    except Exception as e:
        logger.error(f"[API] Error validating stock database: {e}", exc_info=True)
        overview_data["stock_database"] = {"status": "error", "message": str(e)}

    logger.info("[API] Portfolio overview request completed successfully")
    return overview_data


@router.get("/transactions")
def get_transactions(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return (max 1000)"),
    db: Session = Depends(get_db_sync)
):
    """Get paginated transaction list with enhanced validation"""
    try:
        # Get total count
        total_count = db.query(func.count(Transaction.id)).scalar()

        # Validate pagination parameters
        if skip >= total_count and total_count > 0:
            raise HTTPException(status_code=400, detail="Skip value exceeds available records")

        # Get paginated results
        transactions = db.query(Transaction).offset(skip).limit(limit).all()

        return {
            "transactions": [
                {
                    "id": tx.id,
                    "activity_date": tx.activity_date,
                    "ticker": tx.ticker,
                    "trans_code": tx.trans_code,
                    "quantity": tx.quantity,
                    "price": tx.price,
                    "amount": tx.amount
                }
                for tx in transactions
            ],
            "pagination": {
                "total": total_count,
                "skip": skip,
                "limit": limit,
                "has_more": skip + limit < total_count,
                "page": (skip // limit) + 1,
                "total_pages": (total_count + limit - 1) // limit
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Transaction retrieval temporarily unavailable."
        )


@router.get("/stock-price/{symbol}/{date}")
async def get_stock_price(symbol: str, date: str):
    """Get stock price for a specific symbol and date"""
    try:
        from src.services import stock_price_service

        price_data = stock_price_service.get_price_at_date(symbol.upper(), date)
        if price_data:
            return {
                "symbol": symbol.upper(),
                "date": date,
                "price": price_data['close'],
                "full_data": price_data
            }
        else:
            raise HTTPException(status_code=404, detail=f"No price data found for {symbol} on {date}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting stock price: {str(e)}")


@router.get("/validate-stock-database")
async def validate_stock_database():
    """Validate stockr database connection and data availability"""
    try:
        from src.services import stock_price_service

        validation_result = stock_price_service.validate_database()
        return validation_result

    except Exception as e:
        return {
            "valid": False,
            "error": str(e),
            "stock_count": 0,
            "price_records": 0
        }


@router.get("/available-stocks")
async def get_available_stocks():
    """Get list of available stocks in the database"""
    try:
        from src.services import stock_price_service

        stocks = stock_price_service.get_available_stocks()
        return {"stocks": stocks, "count": len(stocks)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting available stocks: {str(e)}")


@router.get("/performance-metrics")
def get_performance_metrics(db: Session = Depends(get_db_sync)):
    """Get comprehensive performance metrics"""
    try:
        from src.services import PortfolioCalculator

        calculator = PortfolioCalculator(db)
        metrics = calculator.calculate_performance_metrics()

        return metrics

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting performance metrics: {str(e)}")


@router.get("/monthly-performance")
def get_monthly_performance(db: Session = Depends(get_db_sync)):
    """Get monthly performance breakdown like Portfolio Visualizer"""
    try:
        from src.services.portfolio_calculator import PortfolioCalculator
        calculator = PortfolioCalculator(db)
        monthly_data = calculator.get_monthly_performance_table()

        return monthly_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting monthly performance: {str(e)}")


# Removed duplicate drawdown-analysis endpoint


# Temporarily disabled - causing JSON serialization issues
# @router.get("/asset-analysis")
# def get_asset_analysis(db: Session = Depends(get_db_sync)):
#     """Get asset-level analysis like Portfolio Visualizer"""


@router.get("/risk-assessment")
def get_risk_assessment(db: Session = Depends(get_db_sync)):
    """Get comprehensive risk assessment"""
    import logging
    logger = logging.getLogger(__name__)

    logger.info("[API] Risk assessment request started")

    # Check for transaction data before calculations
    try:
        transaction_count = db.query(func.count(Transaction.id)).scalar() or 0
        logger.info(f"[API] Transaction count: {transaction_count}")
        
        # Return default structure if no transactions exist
        if transaction_count == 0:
            logger.info("[API] No transactions found, returning default risk metrics")
            return {
                "volatility": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "value_at_risk": {
                    "var_95": 0.0,
                    "var_99": 0.0,
                    "expected_shortfall": 0.0
                },
                "beta_analysis": {
                    "beta": 0.0,
                    "alpha": 0.0,
                    "r_squared": 0.0
                },
                "correlation_matrix": {},
                "has_data": False
            }
    except Exception as e:
        logger.error(f"[API] Error checking transaction count: {e}", exc_info=True)

    # Initialize calculator with error handling
    calculator = None
    try:
        logger.info("[API] Initializing portfolio calculator for risk assessment")
        from src.services import PortfolioCalculator
        calculator = PortfolioCalculator(db)
        logger.info("[API] Portfolio calculator initialized successfully")
    except Exception as e:
        logger.error(f"[API] Error initializing portfolio calculator: {e}", exc_info=True)
        # Return default structure if initialization fails
        return {
            "volatility": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "value_at_risk": {
                "var_95": 0.0,
                "var_99": 0.0,
                "expected_shortfall": 0.0
            },
            "beta_analysis": {
                "beta": 0.0,
                "alpha": 0.0,
                "r_squared": 0.0
            },
            "correlation_matrix": {},
            "has_data": False,
            "error": "Failed to initialize portfolio calculator"
        }

    # Get risk assessment
    try:
        logger.info("[API] Calculating risk assessment")
        risk_data = calculator.get_risk_assessment()
        if risk_data:
            risk_data["has_data"] = True
            logger.info("[API] Risk assessment calculated successfully")
            return risk_data
        else:
            logger.warning("[API] Risk assessment returned empty data")
            return {
                "volatility": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "value_at_risk": {"var_95": 0.0, "var_99": 0.0, "expected_shortfall": 0.0},
                "beta_analysis": {"beta": 0.0, "alpha": 0.0, "r_squared": 0.0},
                "correlation_matrix": {},
                "has_data": False
            }
    except Exception as e:
        logger.error(f"[API] Error calculating risk assessment: {e}", exc_info=True)
        # Return default structure on calculation errors
        return {
            "volatility": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "value_at_risk": {
                "var_95": 0.0,
                "var_99": 0.0,
                "expected_shortfall": 0.0
            },
            "beta_analysis": {
                "beta": 0.0,
                "alpha": 0.0,
                "r_squared": 0.0
            },
            "correlation_matrix": {},
            "has_data": False,
            "error": "Error calculating risk metrics"
        }




@router.get("/portfolio-history")
def get_portfolio_history(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db_sync)
):
    """Get portfolio value history over time"""
    import logging
    logger = logging.getLogger(__name__)

    logger.info(f"[API] Portfolio history request started - dates: {start_date} to {end_date}")

    try:
        # Validate date format if provided
        if start_date:
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                logger.warning(f"[API] Invalid start_date format: {start_date}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid start_date format. Expected YYYY-MM-DD, got: {start_date}"
                )
        
        if end_date:
            try:
                datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                logger.warning(f"[API] Invalid end_date format: {end_date}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid end_date format. Expected YYYY-MM-DD, got: {end_date}"
                )

        logger.info("[API] Initializing portfolio calculator for history")
        try:
            from src.services import PortfolioCalculator
            calculator = PortfolioCalculator(db)
            logger.info("[API] Portfolio calculator initialized successfully")
        except Exception as init_error:
            logger.error(f"[API] Error initializing portfolio calculator: {init_error}", exc_info=True)
            # Return empty response instead of 500 error
            return {
                "history": [],
                "total_points": 0,
                "message": "Unable to initialize portfolio calculator. Please ensure database is available."
            }
        
        logger.info("[API] Calculating portfolio value history")
        
        try:
            history_df = calculator.get_portfolio_value_history(start_date, end_date)
        except Exception as calc_error:
            logger.error(f"[API] Error in portfolio calculator: {calc_error}", exc_info=True)
            # Return empty response instead of 500 error
            return {
                "history": [],
                "total_points": 0,
                "message": "Unable to calculate portfolio history. Please ensure transaction data is available."
            }

        # Check if history_df is a valid DataFrame and not empty
        import pandas as pd
        if not isinstance(history_df, pd.DataFrame) or history_df.empty:
            logger.info("[API] Portfolio history is empty - returning empty response")
            return {
                "history": [],
                "total_points": 0,
                "message": "No portfolio history available. This may occur if there are no transactions or price data is unavailable."
            }

        # Convert to list of dicts for JSON response
        history_data = []
        try:
            for _, row in history_df.iterrows():
                try:
                    # Handle different date formats
                    date_value = row["date"]
                    if hasattr(date_value, 'strftime'):
                        date_value = date_value.strftime('%Y-%m-%d')
                    elif isinstance(date_value, str):
                        date_value = date_value
                    else:
                        date_value = str(date_value)

                    # Safely extract portfolio value
                    portfolio_value = row.get("portfolio_value", 0.0)
                    try:
                        portfolio_value = float(portfolio_value)
                    except (ValueError, TypeError):
                        portfolio_value = 0.0

                    # Safely extract holdings
                    holdings = row.get("holdings", {})
                    if not isinstance(holdings, dict):
                        holdings = {}

                    history_data.append({
                        "date": date_value,
                        "portfolio_value": round(portfolio_value, 2),
                        "holdings": holdings
                    })
                except Exception as row_error:
                    logger.warning(f"[API] Error processing row in history data: {row_error}")
                    # Skip this row but continue processing others
                    continue
                    
        except Exception as e:
            logger.error(f"[API] Error converting history data to JSON: {e}", exc_info=True)
            # Return partial data if available, otherwise empty response
            if history_data:
                logger.info(f"[API] Returning partial data: {len(history_data)} points")
                return {
                    "history": history_data,
                    "total_points": len(history_data),
                    "message": "Partial data returned due to processing errors"
                }
            else:
                return {
                    "history": [],
                    "total_points": 0,
                    "message": "Error processing portfolio history data"
                }

        logger.info(f"[API] Returning {len(history_data)} history points")
        return {
            "history": history_data,
            "total_points": len(history_data)
        }

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"[API] Error getting portfolio history: {e}", exc_info=True)
        # Return empty response instead of 500 error to prevent breaking the UI
        return {
            "history": [],
            "total_points": 0,
            "message": "Unable to retrieve portfolio history. Please try again later or check if transaction data is available."
        }


@router.get("/advanced-analytics")
def get_advanced_analytics(db: Session = Depends(get_db_sync)):
    """Get comprehensive advanced analytics"""
    import logging
    logger = logging.getLogger(__name__)

    logger.info("[API] Advanced analytics request started")

    # Check for transaction data before calculations
    try:
        transaction_count = db.query(func.count(Transaction.id)).scalar() or 0
        logger.info(f"[API] Transaction count: {transaction_count}")
        
        # Return default structure if no transactions exist
        if transaction_count == 0:
            logger.info("[API] No transactions found, returning default analytics structure")
            return {
                "position_weights": {},
                "sector_allocation": {},
                "diversification_metrics": {},
                "optimization_recommendations": {},
                "has_data": False
            }
    except Exception as e:
        logger.error(f"[API] Error checking transaction count: {e}", exc_info=True)

    # Initialize calculator with error handling
    calculator = None
    try:
        logger.info("[API] Initializing portfolio calculator for analytics")
        from src.services import PortfolioCalculator
        calculator = PortfolioCalculator(db)
        logger.info("[API] Portfolio calculator initialized successfully")
    except Exception as e:
        logger.error(f"[API] Error initializing portfolio calculator: {e}", exc_info=True)
        # Return default structure if initialization fails
        return {
            "position_weights": {},
            "sector_allocation": {},
            "diversification_metrics": {},
            "optimization_recommendations": {},
            "has_data": False,
            "error": "Failed to initialize portfolio calculator"
        }

    # Get advanced analytics
    try:
        logger.info("[API] Calculating advanced analytics")
        analytics = calculator.get_advanced_analytics()
        if analytics:
            analytics["has_data"] = True
            logger.info(f"[API] Advanced analytics completed - position weights: {len(analytics.get('position_weights', {}))}")
            return analytics
        else:
            logger.warning("[API] Advanced analytics returned empty data")
            return {
                "position_weights": {},
                "sector_allocation": {},
                "diversification_metrics": {},
                "optimization_recommendations": {},
                "has_data": False
            }
    except Exception as e:
        logger.error(f"[API] Error getting advanced analytics: {e}", exc_info=True)
        # Return default structure on calculation errors
        return {
            "position_weights": {},
            "sector_allocation": {},
            "diversification_metrics": {},
            "optimization_recommendations": {},
            "has_data": False,
            "error": "Error calculating advanced analytics"
        }


# Pydantic models for custom portfolios
class CustomPortfolioCreate(BaseModel):
    name: str = Field(..., description="Portfolio name")
    description: Optional[str] = Field(None, description="Portfolio description")
    asset_allocation: Dict[str, float] = Field(..., description="Asset allocation as ticker -> weight dict")
    strategy: str = Field("lump_sum", description="Investment strategy: 'lump_sum' or 'dca'")
    monthly_investment: Optional[float] = Field(None, description="Monthly investment for DCA strategy")


class CustomPortfolioUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    asset_allocation: Optional[Dict[str, float]] = None
    strategy: Optional[str] = None
    monthly_investment: Optional[float] = None


class PortfolioComparisonRequest(BaseModel):
    portfolio_ids: List[int] = Field(..., description="List of custom portfolio IDs to compare")
    benchmark_tickers: Optional[List[str]] = Field(None, description="Benchmark tickers (e.g., ['SPY', 'QQQ'])")
    include_robinhood: bool = Field(True, description="Include Robinhood portfolio in comparison")
    start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")
    initial_investment: float = Field(10000.0, description="Initial investment amount for backtesting")


# Custom Portfolio Endpoints
@router.post("/custom-portfolios")
def create_custom_portfolio(
    portfolio_data: CustomPortfolioCreate,
    db: Session = Depends(get_db_sync)
):
    """Create a new custom portfolio"""
    try:
        service = CustomPortfolioService(db)
        portfolio = service.create_portfolio(
            name=portfolio_data.name,
            asset_allocation=portfolio_data.asset_allocation,
            description=portfolio_data.description,
            strategy=portfolio_data.strategy,
            monthly_investment=portfolio_data.monthly_investment
        )
        
        return {
            "id": portfolio.id,
            "name": portfolio.name,
            "description": portfolio.description,
            "asset_allocation": json.loads(portfolio.asset_allocation),
            "strategy": portfolio.strategy,
            "monthly_investment": portfolio.monthly_investment,
            "created_at": portfolio.created_at.isoformat() if portfolio.created_at else None
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating portfolio: {str(e)}")


@router.get("/custom-portfolios")
def list_custom_portfolios(db: Session = Depends(get_db_sync)):
    """List all custom portfolios"""
    try:
        service = CustomPortfolioService(db)
        portfolios = service.list_portfolios()
        
        return [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "asset_allocation": json.loads(p.asset_allocation),
                "strategy": p.strategy,
                "monthly_investment": p.monthly_investment,
                "created_at": p.created_at.isoformat() if p.created_at else None
            }
            for p in portfolios
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing portfolios: {str(e)}")


@router.get("/custom-portfolios/{portfolio_id}")
def get_custom_portfolio(portfolio_id: int, db: Session = Depends(get_db_sync)):
    """Get a specific custom portfolio"""
    try:
        service = CustomPortfolioService(db)
        portfolio = service.get_portfolio(portfolio_id)
        
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        return {
            "id": portfolio.id,
            "name": portfolio.name,
            "description": portfolio.description,
            "asset_allocation": json.loads(portfolio.asset_allocation),
            "strategy": portfolio.strategy,
            "monthly_investment": portfolio.monthly_investment,
            "created_at": portfolio.created_at.isoformat() if portfolio.created_at else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting portfolio: {str(e)}")


@router.put("/custom-portfolios/{portfolio_id}")
def update_custom_portfolio(
    portfolio_id: int,
    portfolio_data: CustomPortfolioUpdate,
    db: Session = Depends(get_db_sync)
):
    """Update a custom portfolio"""
    try:
        service = CustomPortfolioService(db)
        portfolio = service.get_portfolio(portfolio_id)
        
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        if portfolio_data.name is not None:
            portfolio.name = portfolio_data.name
        if portfolio_data.description is not None:
            portfolio.description = portfolio_data.description
        if portfolio_data.asset_allocation is not None:
            # Validate weights
            total_weight = sum(portfolio_data.asset_allocation.values())
            if abs(total_weight - 1.0) > 0.01:
                raise ValueError(f"Asset allocation weights must sum to 1.0, got {total_weight}")
            portfolio.asset_allocation = json.dumps(portfolio_data.asset_allocation)
        if portfolio_data.strategy is not None:
            portfolio.strategy = portfolio_data.strategy
        if portfolio_data.monthly_investment is not None:
            portfolio.monthly_investment = portfolio_data.monthly_investment
        
        db.commit()
        db.refresh(portfolio)
        
        return {
            "id": portfolio.id,
            "name": portfolio.name,
            "description": portfolio.description,
            "asset_allocation": json.loads(portfolio.asset_allocation),
            "strategy": portfolio.strategy,
            "monthly_investment": portfolio.monthly_investment,
            "updated_at": portfolio.updated_at.isoformat() if portfolio.updated_at else None
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating portfolio: {str(e)}")


@router.delete("/custom-portfolios/{portfolio_id}")
def delete_custom_portfolio(portfolio_id: int, db: Session = Depends(get_db_sync)):
    """Delete a custom portfolio"""
    try:
        service = CustomPortfolioService(db)
        success = service.delete_portfolio(portfolio_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        return {"message": "Portfolio deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting portfolio: {str(e)}")


@router.post("/custom-portfolios/{portfolio_id}/backtest")
def backtest_portfolio(
    portfolio_id: int,
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    initial_investment: float = Query(10000.0, description="Initial investment amount"),
    db: Session = Depends(get_db_sync)
):
    """Backtest a custom portfolio"""
    try:
        service = CustomPortfolioService(db)
        result = service.backtest_portfolio(portfolio_id, start_date, end_date, initial_investment)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error backtesting portfolio: {str(e)}")


@router.post("/portfolio-comparison")
def compare_portfolios(
    comparison_request: PortfolioComparisonRequest,
    db: Session = Depends(get_db_sync)
):
    """Compare multiple portfolios, benchmarks, and Robinhood portfolio"""
    try:
        service = CustomPortfolioService(db)
        result = service.compare_portfolios(
            portfolio_ids=comparison_request.portfolio_ids,
            benchmark_tickers=comparison_request.benchmark_tickers,
            include_robinhood=comparison_request.include_robinhood,
            start_date=comparison_request.start_date,
            end_date=comparison_request.end_date,
            initial_investment=comparison_request.initial_investment
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error comparing portfolios: {str(e)}")


@router.get("/benchmarks/{ticker}")
def get_benchmark(
    ticker: str,
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    initial_investment: float = Query(10000.0, description="Initial investment amount"),
    db: Session = Depends(get_db_sync)
):
    """Get benchmark data (e.g., SPY) for comparison"""
    try:
        service = CustomPortfolioService(db)
        result = service.get_benchmark_history(ticker, start_date, end_date, initial_investment)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting benchmark: {str(e)}")


@router.get("/performance-attribution")
def get_performance_attribution(db: Session = Depends(get_db_sync)):
    """Get performance attribution analysis"""
    try:
        from src.services import PortfolioCalculator
        calculator = PortfolioCalculator(db)
        return calculator.get_performance_attribution()
    except Exception as e:
        return {"by_asset": {}, "by_period": {}, "total_return": 0, "error": str(e)}


@router.get("/drawdown-analysis")
def get_drawdown_analysis(db: Session = Depends(get_db_sync)):
    """Get drawdown analysis with historical data"""
    try:
        from src.services import PortfolioCalculator
        calculator = PortfolioCalculator(db)
        return calculator.get_drawdown_analysis()
    except Exception as e:
        return {
            "drawdown_series": [],
            "max_drawdown": 0,
            "max_drawdown_date": None,
            "recovery_time_days": None,
            "drawdown_periods": [],
            "error": str(e)
        }


class ScenarioRequest(BaseModel):
    portfolio_id: Optional[int] = Field(None, description="Portfolio ID (use 'robinhood' for Robinhood portfolio)")
    scenario_type: str = Field(..., description="Type: rebalance, add_asset, reduce_position, market_change")
    params: Dict[str, Any] = Field(default_factory=dict, description="Scenario parameters")


@router.post("/scenarios")
def run_scenario(
    request: ScenarioRequest,
    db: Session = Depends(get_db_sync)
):
    """Run what-if scenario analysis on a portfolio"""
    try:
        service = CustomPortfolioService(db)
        result = service.run_scenario(
            portfolio_id=request.portfolio_id,
            scenario_type=request.scenario_type,
            params=request.params
        )
        return result
    except Exception as e:
        return {
            "original": {"return": 0, "risk": 0, "sharpe": 0},
            "scenario": {"return": 0, "risk": 0, "sharpe": 0},
            "difference": {"return": 0, "risk": 0, "sharpe": 0},
            "error": str(e)
        }
