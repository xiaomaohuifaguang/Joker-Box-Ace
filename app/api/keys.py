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
    description: str | None = Field(default=None, max_length=255)
    expires_in_days: int | None = None     # 留空/0 = 永不过期


def _to_dict(k) -> dict:
    return {
        "id": k.id,
        "name": k.name,
        "description": k.description,
        "key": k.key_value,
        "enabled": k.enabled,
        "expires_at": k.expires_at.isoformat() if k.expires_at else None,
        "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        "created_at": k.created_at.isoformat() if k.created_at else None,
    }


@router.post("")
async def create(body: CreateKeyIn):
    """创建 key"""
    expires_at = None
    if body.expires_in_days:
        from datetime import timedelta
        expires_at = datetime.now() + timedelta(days=body.expires_in_days)
    record = await svc.create_key(body.name, body.description, expires_at)
    return HttpResult.ok(_to_dict(record), "创建成功")


@router.get("")
async def list_all():
    return HttpResult.ok([_to_dict(k) for k in await svc.list_keys()])


@router.post("/{key_id}/revoke")
async def revoke(key_id: int):
    """吊销：保留记录但立即失效"""
    if await svc.revoke_key(key_id):
        return HttpResult.ok(None, "已吊销")
    return HttpResult.fail(code=404, msg="key 不存在")


@router.delete("/{key_id}")
async def delete(key_id: int):
    """删除：彻底移除记录"""
    if await svc.delete_key(key_id):
        return HttpResult.ok(None, "已删除")
    return HttpResult.fail(code=404, msg="key 不存在")
