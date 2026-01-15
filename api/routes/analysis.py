from fastapi import APIRouter

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

@router.get("/compare")
def compare_portfolios():
    return {"status": "placeholder", "message": "Portfolio vs benchmark comparison (stockr_backbone integration coming)"}