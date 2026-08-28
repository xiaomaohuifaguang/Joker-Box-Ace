"""登录 token 的签发与校验（HMAC 签名，无状态，多机实例可独立验签）

token 格式: base64url("<username>.<expiry>") + "." + hex(hmac_sha256)

- 无状态：不需要 Redis/共享存储，多实例间天然互通（前提是 AUTH_SECRET_KEY 一致）
- 代价：无法主动吊销，靠 TTL 控制最长存活；需要"立即踢人"时再加黑名单机制
"""
import base64
import hashlib
import hmac
import logging
import secrets
import time

from app.config import settings

logger = logging.getLogger(__name__)


def _secret() -> bytes:
    """签名密钥：配置优先；留空则本次进程随机生成（多机会互踢，启动时已告警）"""
    key = settings.AUTH_SECRET_KEY
    if not key:
        key = _runtime_secret()
    return key.encode()


_runtime_key: str | None = None


def _runtime_secret() -> str:
    global _runtime_key
    if _runtime_key is None:
        _runtime_key = secrets.token_hex(32)
        logger.warning("⚠️ AUTH_SECRET_KEY 未配置，已随机生成；"
                       "重启后所有登录态失效，多机部署会互相踢下线！")
    return _runtime_key


def _sign(payload_b64: str) -> str:
    return hmac.new(_secret(), payload_b64.encode(), hashlib.sha256).hexdigest()


def issue_token(username: str) -> str:
    """签发 token"""
    expiry = int(time.time()) + settings.AUTH_TOKEN_TTL
    payload_b64 = base64.urlsafe_b64encode(f"{username}.{expiry}".encode()).decode()
    return f"{payload_b64}.{_sign(payload_b64)}"


def verify_token(token: str) -> str | None:
    """校验 token，通过返回用户名，失败返回 None"""
    try:
        payload_b64, sig = token.rsplit(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(sig, _sign(payload_b64)):
        return None
    try:
        username, expiry = base64.urlsafe_b64decode(payload_b64.encode()).decode().rsplit(".", 1)
        if int(expiry) < int(time.time()):
            return None
        return username
    except (ValueError, UnicodeDecodeError):
        return None


def check_password(username: str, password: str) -> bool:
    """比对账号密码（hmac.compare_digest 防时序攻击）。密码未配置时拒绝一切登录。"""
    if not settings.AUTH_PASSWORD:
        return False
    return (hmac.compare_digest(username, settings.AUTH_USERNAME)
            and hmac.compare_digest(password, settings.AUTH_PASSWORD))
