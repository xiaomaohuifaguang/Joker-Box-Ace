"""系统类接口：健康检查、站点图标等基础设施路由。

注意：这些路径要保持稳定，外部监控、Nacos、容器探针都依赖它们，
不要因为业务路由重构而改路径或加前缀。
"""
from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from app.models.response import HttpResult

router = APIRouter()


@router.get("/alive", tags=["system"])
async def alive():
    """健康检查：负载均衡、容器探针、监控告警都指它"""
    return HttpResult.ok(None, "alive")


@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    # 浏览器不管页面怎么声明都会默认请求 /favicon.ico，重定向到真实位置
    return RedirectResponse("/static/favicon.ico")
