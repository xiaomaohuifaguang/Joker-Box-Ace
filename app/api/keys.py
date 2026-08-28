"""API-Key 管理接口

安全边界：本模块在 /api/keys 下，不属于 /api/v数字/** 版本化路径，
因此中间件只认登录 token，API-Key 无法调用管理口（设计如此，勿改路径）。
"""
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.models.response import HttpResult
from app.services import api_key as svc

router = APIRouter(prefix="/api/keys", tags=["api-keys"])


class CreateKeyIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    expires_at: datetime | None = None     # 留空 = 永不过期


def _to_dict(k) -> dict:
    """出参只给 prefix，永不出明文/哈希"""
    return {
        "id": k.id,
        "name": k.name,
        "key_prefix": k.key_prefix,
        "enabled": k.enabled,
        "expires_at": k.expires_at.isoformat() if k.expires_at else None,
        "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        "created_at": k.created_at.isoformat() if k.created_at else None,
    }


@router.post("")
async def create(body: CreateKeyIn):
    """创建 key：明文仅本次响应返回一次，之后无法找回"""
    record, plain = await svc.create_key(body.name, body.expires_at)
    return HttpResult.ok({"key": plain, "info": _to_dict(record)},
                         "创建成功，明文 key 只显示这一次，请立即保存")


@router.get("")
async def list_all():
    return HttpResult.ok([_to_dict(k) for k in await svc.list_keys()])


@router.post("/{key_id}/revoke")
async def revoke(key_id: int):
    if await svc.revoke_key(key_id):
        return HttpResult.ok(None, "已吊销")
    return HttpResult.fail(code=404, msg="key 不存在")
