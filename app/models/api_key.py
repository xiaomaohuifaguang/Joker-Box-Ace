"""API-Key 表模型（API-Key 鉴权的存储）

设计要点：
- key_value 存明文支持界面回显（内网单账号工具的取舍）；key_hash 用于校验时快速索引
- 只用通用类型，保证未来切 MySQL/PG 零改动（见 CLAUDE.md 可移植性约束）
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TABLE_PREFIX


class ApiKey(Base):
    __tablename__ = f"{TABLE_PREFIX}api_keys"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), comment="名称，标识这个 key 给谁用")
    description: Mapped[str | None] = mapped_column(String(255), nullable=True,
                                                    comment="详细描述")
    key_value: Mapped[str] = mapped_column(String(64), comment="key 明文（界面回显用）")
    # 唯一约束内联在建表语句里（unique=True），不要 index=True——
    # 独立 CREATE INDEX 的 IF NOT EXISTS 是 MySQL 不支持的语法
    key_hash: Mapped[str] = mapped_column(String(64), unique=True,
                                          comment="sha256(key)，校验索引；唯一约束自带索引")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True,
                                                        comment="留空 = 永不过期")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
