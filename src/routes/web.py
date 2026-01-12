"""
Web routes for serving HTML pages
"""

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path

from ..database import get_db_sync

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/dashboard")
def dashboard(request: Request, db: Session = Depends(get_db_sync)):
    """Main dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/upload")
def upload_page(request: Request):
    """CSV upload page"""
    return templates.TemplateResponse("upload.html", {"request": request})


@router.get("/analysis")
def analysis_page(request: Request):
    """Portfolio analysis page"""
    return templates.TemplateResponse("analysis.html", {"request": request})


@router.get("/comparison")
def comparison_page(request: Request):
    """Portfolio comparison page"""
    return templates.TemplateResponse("comparison.html", {"request": request})
