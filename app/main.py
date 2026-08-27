import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
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

APP_DIR = Path(__file__).parent
TEMPLATES_DIR = APP_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# 静态资源（tailwind/daisyui 等全部本地化，内网无外网也能跑）
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")


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


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    # 浏览器不管页面怎么声明都会默认请求 /favicon.ico，重定向到真实位置
    return RedirectResponse("/static/favicon.ico")


@app.get("/alive")
async def alive():
    return HttpResult.ok(None, "alive")
