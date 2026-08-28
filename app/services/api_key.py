"""API-Key 的生成与校验

verify_key() 就是未来塞进鉴权中间件 _CREDENTIAL_CHECKERS 的函数，
签名已按"通过返回身份标识、失败返回 None"设计好，到时一行接入。
"""
import hashlib
import secrets
from datetime import datetime

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.api_key import ApiKey, localnow

KEY_PREFIX = "jba-"       # 一眼认出是本系统的 key


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


async def create_key(name: str, description: str | None = None,
                     expires_at: datetime | None = None) -> ApiKey:
    """生成新 key（明文入库可回显，内网工具的取舍）"""
    plain = KEY_PREFIX + secrets.token_urlsafe(32)
    record = ApiKey(name=name, description=description, key_value=plain,
                    key_hash=_hash(plain), expires_at=expires_at)
    async with SessionLocal() as session:
        session.add(record)
        await session.commit()
        await session.refresh(record)
    return record


async def verify_key(key: str) -> str | None:
    """校验 key：通过返回 name（身份标识），失败返回 None。命中时刷新 last_used_at"""
    if not key.startswith(KEY_PREFIX):
        return None
    async with SessionLocal() as session:
        row = (await session.execute(
            select(ApiKey).where(ApiKey.key_hash == _hash(key), ApiKey.enabled.is_(True))
        )).scalar_one_or_none()
        if row is None:
            return None
        if row.expires_at is not None and row.expires_at < localnow():
            return None
        row.last_used_at = localnow()
        await session.commit()
        return row.name


async def list_keys() -> list[ApiKey]:
    """全量列表（管理界面用；key 只有哈希和 prefix，天然脱敏）"""
    async with SessionLocal() as session:
        return list((await session.execute(
            select(ApiKey).order_by(ApiKey.id.desc())
        )).scalars())


async def revoke_key(key_id: int) -> bool:
    """吊销（软删除：置 enabled=False，保留审计痕迹）"""
    return await _set_enabled(key_id, False)


async def enable_key(key_id: int) -> bool:
    """重新启用已吊销的 key"""
    return await _set_enabled(key_id, True)


async def _set_enabled(key_id: int, enabled: bool) -> bool:
    async with SessionLocal() as session:
        row = await session.get(ApiKey, key_id)
        if row is None:
            return False
        row.enabled = enabled
        await session.commit()
        return True


async def delete_key(key_id: int) -> bool:
    """删除（硬删除：彻底移除记录）"""
    async with SessionLocal() as session:
        row = await session.get(ApiKey, key_id)
        if row is None:
            return False
        await session.delete(row)
        await session.commit()
        return True
