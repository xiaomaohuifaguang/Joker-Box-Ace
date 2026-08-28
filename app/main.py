"""应用装配入口：只负责组装，不写任何路由和业务逻辑。

- 生命周期:  app/nacos_registry.py 的 lifespan（NACOS_ENABLED 开关在里面）
- 页面路由:  app/pages.py（返回 HTML）
- JSON 接口: app/api/router.py 汇总（返回 HttpResult）
"""
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import router as api_router
from app.models.response import HttpResult
from app.nacos_registry import lifespan
from app.pages import router as pages_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Joker Box Ace", lifespan=lifespan)

# 静态资源（tailwind/daisyui 等全部本地化，内网无外网也能跑）
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """兜底异常处理：未捕获的异常统一包成 HttpResult 返回"""
    logger.exception("未处理异常: %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=HttpResult.fail(code=500, msg="服务器内部错误").model_dump(),
    )


app.include_router(pages_router)
app.include_router(api_router)
