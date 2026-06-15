from dataclasses import dataclass

from fastapi import Query


@dataclass
class PaginationParams:
    page: int = Query(default=1, ge=1)
    page_size: int = Query(default=5, ge=1, le=100)
