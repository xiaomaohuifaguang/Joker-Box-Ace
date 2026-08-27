import time
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class HttpResult(BaseModel, Generic[T]):
    """统一返回结果"""
    code: int = 200
    data: Optional[T] = None
    msg: str = "success"
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))

    @classmethod
    def ok(cls, data: T = None, msg: str = "success") -> "HttpResult[T]":
        return cls(code=200, data=data, msg=msg)

    @classmethod
    def fail(cls, code: int = 500, msg: str = "error") -> "HttpResult":
        return cls(code=code, data=None, msg=msg)
