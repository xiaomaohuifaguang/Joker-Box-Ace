"""API-Key 的生成与校验

verify_key() 就是未来塞进鉴权中间件 _CREDENTIAL_CHECKERS 的函数，
签名已按"通过返回身份标识、失败返回 None"设计好，到时一行接入。
"""
import hashlib
import secrets
from datetime import datetime

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.api_key import ApiKey

KEY_PREFIX = "jba-"       # 一眼认出是本系统的 key


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


async def create_key(name: str, expires_at: datetime | None = None) -> tuple[ApiKey, str]:
    """生成新 key。返回 (记录, 明文 key)——明文只在此刻返回一次，之后无法找回！"""
    plain = KEY_PREFIX + secrets.token_urlsafe(32)
    record = ApiKey(name=name, key_hash=_hash(plain), key_prefix=plain[:12],
                    expires_at=expires_at)
    async with SessionLocal() as session:
        session.add(record)
        await session.commit()
        await session.refresh(record)
    return record, plain


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
        if row.expires_at is not None and row.expires_at < datetime.now():
            return None
        row.last_used_at = datetime.now()
        await session.commit()
        return row.name


async def revoke_key(key_id: int) -> bool:
    """吊销（软删除：置 enabled=False，保留审计痕迹）"""
    async with SessionLocal() as session:
        row = await session.get(ApiKey, key_id)
        if row is None:
            return False
        row.enabled = False
        await session.commit()
        return True
