"""鉴权接口：登录、登出、查询当前身份"""
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.middleware import COOKIE_NAME
from app.core.security import check_password, issue_token
from app.models.response import HttpResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(request: Request):
    """登录：支持 JSON 和表单两种提交方式，成功则签发 token 并写 HttpOnly Cookie"""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        username, password = body.get("username", ""), body.get("password", "")
    else:
        form = await request.form()
        username, password = str(form.get("username", "")), str(form.get("password", ""))

    if not check_password(username, password):
        logger.warning("登录失败: username=%s", username)
        return HttpResult.fail(code=401, msg="账号或密码错误")

    token = issue_token(username)
    logger.info("登录成功: %s", username)
    resp = JSONResponse(content=HttpResult.ok({"token": token}, "登录成功").model_dump())
    # HttpOnly 防 XSS 偷 token；SameSite=Lax 防 CSRF；内网 http 不设 Secure
    resp.set_cookie(COOKIE_NAME, token, max_age=settings.AUTH_TOKEN_TTL,
                    httponly=True, samesite="lax")
    return resp


@router.post("/logout")
async def logout():
    """登出：删 Cookie。无状态 token 无法吊销，服务端过期靠 TTL"""
    resp = JSONResponse(content=HttpResult.ok(None, "已登出").model_dump())
    resp.delete_cookie(COOKIE_NAME)
    return resp


@router.get("/me")
async def me(request: Request):
    """查询当前登录身份（中间件已保证到这里一定已登录）"""
    return HttpResult.ok({"username": getattr(request.state, "user", None)})
