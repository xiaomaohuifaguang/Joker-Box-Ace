"""页面路由：返回 Jinja 模板（HTML）。

约定：本模块只出页面，JSON 接口一律放 app/api/ 下并返回 HttpResult。
"""
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(include_in_schema=False)   # 页面不进 OpenAPI 文档


@router.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")


@router.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"message": "Hello from FastAPI + Jinja2"},
    )
