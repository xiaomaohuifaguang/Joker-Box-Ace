"""API-Key 表模型（未来 API-Key 鉴权的存储）

设计要点：
- key 不明文入库，只存 sha256 哈希（key_hash）；明文只在创建时返回一次
- key_prefix 存前几位明文，用于管理界面上识别"是哪个 key"
- 只用通用类型，保证未来切 MySQL/PG 零改动（见 CLAUDE.md 可移植性约束）
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TABLE_PREFIX


class ApiKey(Base):
    __tablename__ = f"{TABLE_PREFIX}api_keys"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), comment="用途备注，标识这个 key 给谁用")
    # 唯一约束内联在建表语句里（unique=True），不要 index=True——
    # 独立 CREATE INDEX 的 IF NOT EXISTS 是 MySQL 不支持的语法
    key_hash: Mapped[str] = mapped_column(String(64), unique=True,
                                          comment="sha256(key)，不存明文；唯一约束自带索引")
    key_prefix: Mapped[str] = mapped_column(String(12), comment="key 开头几位，界面上识别用")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True,
                                                        comment="留空 = 永不过期")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
