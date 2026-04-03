from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    total: int
    skip: int
    limit: int
    has_more: bool
    items: list[T]
