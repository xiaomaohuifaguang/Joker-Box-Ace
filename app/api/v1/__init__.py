"""v1 版本业务接口汇总。新业务模块在 v1/ 下建文件，在这里 include。"""
from fastapi import APIRouter

from app.api.v1 import demo

router = APIRouter(prefix="/api/v1", tags=["v1"])
router.include_router(demo.router)
