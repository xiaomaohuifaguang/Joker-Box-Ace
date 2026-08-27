import asyncio
import logging
import socket
import time

from contextlib import asynccontextmanager

from fastapi import FastAPI
from v2.nacos import (
    NacosNamingService,
    ClientConfigBuilder,
    RegisterInstanceParam,
    DeregisterInstanceParam,
)

from app.config import settings

logger = logging.getLogger(__name__)

REGISTER_MAX_RETRIES = 3        # 注册失败重试次数
REGISTER_RETRY_INTERVAL = 5     # 重试间隔（秒）


def _local_ip() -> str:
    """获取本机局域网 IP（避免注册成 127.0.0.1 导致其他机器调不通）"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))       # 不会真的发包，只为选出口网卡
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def _service_name() -> str:
    """NACOS_SERVICE_NAME 留空时回退到 APP_NAME"""
    return settings.NACOS_SERVICE_NAME or settings.APP_NAME


def _register_ip() -> str:
    """注册的 IP：优先用显式配置（容器/多网卡环境必须配），留空才自动探测"""
    return settings.NACOS_REGISTER_IP or _local_ip()


@asynccontextmanager
async def register_to_nacos(app: FastAPI):
    """注册放到后台任务：不阻塞服务启动；失败只记日志不影响服务；关闭时确保注销"""

    async def _do_register():
        t0 = time.perf_counter()
        for attempt in range(1, REGISTER_MAX_RETRIES + 1):
            try:
                client_config = (
                    ClientConfigBuilder()
                    .server_address(settings.NACOS_SERVER_ADDR)
                    .namespace_id(settings.NACOS_NAMESPACE_ID)
                    .username(settings.NACOS_USERNAME)
                    .password(settings.NACOS_PASSWORD)
                    .log_level("INFO")
                    .build()
                )
                naming_client = await NacosNamingService.create_naming_service(client_config)
                app.state.nacos_client = naming_client      # ← 存到 state，关闭时要用来注销

                app_ip = _register_ip()
                app.state.nacos_ip = app_ip                 # ← 注销时用同一个 IP，防止网络变化注销错实例
                await naming_client.register_instance(request=RegisterInstanceParam(
                    service_name=_service_name(),
                    group_name=settings.NACOS_GROUP_NAME,
                    ip=app_ip,
                    port=settings.APP_PORT,
                    weight=1.0,
                    cluster_name="DEFAULT",
                    metadata={"app": settings.APP_NAME, "framework": "fastapi"},
                    enabled=True,
                    healthy=True,
                    ephemeral=True,
                ))
                logger.info("✅ 已注册到 Nacos: %s → %s:%s (耗时 %.2fs)",
                            _service_name(), app_ip, settings.APP_PORT,
                            time.perf_counter() - t0)
                return
            except Exception:
                logger.exception("注册 Nacos 失败（第 %d/%d 次）", attempt, REGISTER_MAX_RETRIES)
                if attempt < REGISTER_MAX_RETRIES:
                    await asyncio.sleep(REGISTER_RETRY_INTERVAL)
        logger.error("❌ Nacos 注册最终失败，服务继续运行但不参与服务发现")

    reg_task = asyncio.create_task(_do_register())   # ← 不 await，放后台跑

    yield                        # 服务立刻开始对外提供页面/API

    # ─── 关闭阶段 ───
    await reg_task               # _do_register 内部已吞掉异常，这里不会抛出
    client = getattr(app.state, "nacos_client", None)
    if client is not None:
        try:
            await client.deregister_instance(request=DeregisterInstanceParam(
                service_name=_service_name(),
                group_name=settings.NACOS_GROUP_NAME,
                ip=app.state.nacos_ip,
                port=settings.APP_PORT,
                cluster_name="DEFAULT",
                ephemeral=True,
            ))
            logger.info("👋 已从 Nacos 注销")
        except Exception:
            logger.exception("从 Nacos 注销失败")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """总入口：按开关组合多个生命周期任务（以后加数据库等就在这里嵌套）"""
    if settings.NACOS_ENABLED:
        async with register_to_nacos(app):
            yield
    else:
        yield
