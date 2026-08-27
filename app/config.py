"""
全局配置中心 —— 整个项目读取配置的唯一入口

用法：
    from app.config import settings
    settings.APP_PORT、settings.NACOS_SERVER_ADDR ...

优先级：真实系统环境变量 > .env 文件 > 代码默认值
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（config.py 在 app/ 里，向上两级）
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # ─── dotenv 来源与行为配置 ───────────────────────────────
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",     # 钉死路径，不依赖启动目录
        env_file_encoding="utf-8-sig",
        extra="ignore",                 # .env 里多出来的键不报错（重要！见下文说明）
    )

    # ─── 应用 ───
    APP_NAME: str = "joker-box-ace"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000               # 类型直接声明，转换和校验全自动
    APP_DEBUG: bool = False            # "true"/"True"/"1" 都能正确解析

    # ─── Nacos ───
    NACOS_ENABLED: bool = True
    NACOS_SERVER_ADDR: str = "127.0.0.1:8848"
    NACOS_NAMESPACE_ID: str = ""       # 公共命名空间留空即可
    NACOS_GROUP_NAME: str = "DEFAULT_GROUP"
    NACOS_USERNAME: str = "nacos"
    NACOS_PASSWORD: str = "nacos"
    NACOS_SERVICE_NAME: str = ""       # 留空时在业务侧回退到 APP_NAME


# 全局单例 —— 所有模块 import 这一个对象
settings = Settings()
