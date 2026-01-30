import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/health")
def api_health(db: Session = Depends(get_db)):
    db_ok = False
    try:
        db.execute(text("SELECT 1")).scalar()
        db_ok = True
    except Exception as exc:
        logger.error("Health check DB probe failed: %s", exc)

    return {
        "status": "ok" if db_ok else "degraded",
        "api": "running",
        "database": "connected" if db_ok else "unreachable",
    }
