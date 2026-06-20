from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter(prefix="/ui", tags=["dashboard"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent.parent / "templates"))


@router.get("", response_class=HTMLResponse)
async def overview(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "overview.html")


@router.get("/search", response_class=HTMLResponse)
async def search(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "search.html")


@router.get("/rules", response_class=HTMLResponse)
async def rules(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "rules.html")


@router.get("/clusters", response_class=HTMLResponse)
async def clusters(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "clusters.html")


@router.get("/settings", response_class=HTMLResponse)
async def settings(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "settings.html")
