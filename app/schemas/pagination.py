from math import ceil
from typing import Generic, Sequence, TypeVar

from pydantic import BaseModel, computed_field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: Sequence[T]
    total: int
    page: int
    page_size: int

    @computed_field
    @property
    def total_pages(self) -> int:
        if self.total == 0:
            return 0
        return ceil(self.total / self.page_size)
