import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from app.models.response import HttpResult
from app.nacos_registry import lifespan

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

# 统一走 lifespan 包装器，NACOS_ENABLED 开关在这里生效
app = FastAPI(title="Joker Box Ace", lifespan=lifespan)

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """兜底异常处理：未捕获的异常统一包成 HttpResult 返回"""
    logger.exception("未处理异常: %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=HttpResult.fail(code=500, msg="服务器内部错误").model_dump(),
    )


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"message": "Hello from FastAPI + Jinja2"},
    )


@app.get("/alive")
async def alive():
    return HttpResult.ok(None, "alive")
