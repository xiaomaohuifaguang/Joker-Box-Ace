"""v1 示例接口：验证双凭证通路（登录 token 或 API-Key 均可调）"""
from fastapi import APIRouter, Request

from app.models.response import HttpResult

router = APIRouter()


@router.get("/ping")
async def ping(request: Request):
    """回显当前调用方身份：登录用户显示用户名，API-Key 调用显示 key 的 name"""
    return HttpResult.ok({"caller": getattr(request.state, "user", None)}, "pong")
