"""鉴权中间件：凭证解析管道 + 页面 302 / API 401 分流

凭证管道设计（未来 API-Key 在此扩展）：
    现在: Cookie / Authorization: Bearer 携带的登录 token
    未来: 加 X-API-Key 头的校验函数，append 进 _CREDENTIAL_CHECKERS 即可，
          下游路由和本中间件零改动。

放行边界（勿随意收紧）：
    /alive、/static/*、/favicon.ico —— 探针和登录页自身的静态资源必须可用
    /login、/api/auth/login        —— 登录入口本身
"""
import logging
import re
from typing import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config import settings
from app.core.security import verify_token
from app.models.response import HttpResult

logger = logging.getLogger(__name__)

COOKIE_NAME = "token"

# 精确匹配放行的路径
OPEN_PATHS = {"/alive", "/favicon.ico", "/login", "/api/auth/login"}
# 前缀匹配放行的路径
OPEN_PREFIXES = ("/static",)

# API-Key 仅对版本化业务接口生效（/api/v1/**、/api/v2/** …），管理口和页面不认
_API_VERSIONED_PATH = re.compile(r"^/api/v\d+/")


async def _check_token(request: Request) -> str | None:
    """凭证类型 1：登录 token（Cookie 或 Bearer 头），所有受保护路径都认"""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    return verify_token(token) if token else None


async def _check_api_key(request: Request) -> str | None:
    """凭证类型 2：API-Key（X-API-Key 头），仅版本化业务接口生效"""
    if not _API_VERSIONED_PATH.match(request.url.path):
        return None
    key = request.headers.get("X-API-Key")
    if not key:
        return None
    from app.services.api_key import verify_key   # 延迟导入避免循环依赖
    return await verify_key(key)


# 凭证校验函数列表：每个返回身份标识 或 None。新凭证类型追加在这里。
_CREDENTIAL_CHECKERS: list[Callable[[Request], Awaitable[str | None]]] = [
    _check_token,
    _check_api_key,
]


async def _resolve_identity(request: Request) -> str | None:
    for checker in _CREDENTIAL_CHECKERS:
        identity = await checker(request)
        if identity:
            return identity
    return None


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.AUTH_ENABLED:
            return await call_next(request)

        path = request.url.path
        if path in OPEN_PATHS or any(path.startswith(p) for p in OPEN_PREFIXES):
            return await call_next(request)

        identity = await _resolve_identity(request)
        if identity:
            request.state.user = identity
            return await call_next(request)

        # 未通过：API 返回 401 JSON，页面重定向登录页
        if path.startswith("/api"):
            return JSONResponse(
                status_code=401,
                content=HttpResult.fail(code=401, msg="未登录或登录已过期").model_dump(),
            )
        return RedirectResponse(f"/login?next={path}", status_code=302)
