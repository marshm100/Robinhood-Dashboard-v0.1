from fastapi import APIRouter

router = APIRouter()

@router.get("/api/health")
def api_health():
    return {"status": "API routes working"}