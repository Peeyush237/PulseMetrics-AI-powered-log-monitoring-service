from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter(prefix="/ui", tags=["dashboard"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent.parent / "templates"))


@router.get("", response_class=HTMLResponse)
async def overview(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("overview.html", {"request": request})


@router.get("/search", response_class=HTMLResponse)
async def search(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("search.html", {"request": request})


@router.get("/rules", response_class=HTMLResponse)
async def rules(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("rules.html", {"request": request})


@router.get("/clusters", response_class=HTMLResponse)
async def clusters(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("clusters.html", {"request": request})


@router.get("/settings", response_class=HTMLResponse)
async def settings(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("settings.html", {"request": request})
