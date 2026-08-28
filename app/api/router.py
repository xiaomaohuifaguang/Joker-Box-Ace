"""API 路由汇总：以后新增业务模块（user.py、order.py …）只改这一个文件。

示例：
    from app.api import user
    router.include_router(user.router, prefix="/api/v1", tags=["user"])
"""
from fastapi import APIRouter

from app.api import auth, keys, system
from app.api.v1 import router as v1_router

router = APIRouter()
router.include_router(system.router)
router.include_router(auth.router)
router.include_router(keys.router)
router.include_router(v1_router)
