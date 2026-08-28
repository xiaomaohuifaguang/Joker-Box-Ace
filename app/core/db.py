"""数据库引擎与会话（SQLAlchemy 2.x async）

内置/远程切换：只换连接 URL，业务代码不动。
  DB_URL 显式配置  → 直接使用（任何 SQLAlchemy 支持的库，切库逃生门）
  DB_TYPE=sqlite   → 内置库，文件位置取 SQLITE_PATH
  DB_TYPE=其他     → 必须显式配置 DB_URL，否则启动报错

可移植性约束（SQLite → 远程库切换不炸的前提）：
  - 模型只用通用类型（String/Integer/DateTime/Boolean/Text/JSON），禁方言特有类型
  - 禁裸 SQL 字符串，统一走 ORM/Core 表达式
  - SQLite 启动时开外键 PRAGMA，行为与远程库对齐
"""
import logging
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """所有表模型的基类"""


# 表名统一前缀：所有模型的 __tablename__ 必须用它拼接，例: f"{TABLE_PREFIX}api_keys"
TABLE_PREFIX = "cat_ace_"


def build_db_url() -> str:
    """DB_URL 显式配置优先；否则按 DB_TYPE 走预设"""
    if settings.DB_URL:
        return settings.DB_URL
    if settings.DB_TYPE == "sqlite":
        path = Path(settings.SQLITE_PATH)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent.parent.parent / path  # 相对项目根
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{path}"
    raise ValueError(
        f"DB_TYPE={settings.DB_TYPE!r} 需要显式配置 DB_URL，"
        f"例如 mysql+aiomysql://user:pass@host:3306/dbname"
    )


DB_URL = build_db_url()
logger.info("数据库: %s", DB_URL.split("///")[-1] if "sqlite" in DB_URL else DB_URL.split("@")[-1])

engine = create_async_engine(DB_URL, echo=settings.APP_DEBUG)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# SQLite 默认关外键，开启以与 MySQL/PG 行为对齐
if DB_URL.startswith("sqlite"):
    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_fk_on(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


async def init_db():
    """启动时调用：建表（仅 sqlite 模式自动建，远程库请用迁移工具）"""
    if DB_URL.startswith("sqlite"):
        import app.models  # noqa: F401  确保所有表模型注册到 Base.metadata
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("内置库就绪: %s", settings.SQLITE_PATH)


async def close_db():
    """关闭时调用：释放连接池"""
    await engine.dispose()
    logger.info("数据库连接已释放")
