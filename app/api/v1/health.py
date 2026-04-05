from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import check_db_connection


router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    db_connection: str


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Verifies that the API is running and the database connection is active.",
)
def health_check() -> HealthResponse:
    """
    Runs a SELECT 1 query against PostgreSQL.
    Returns {"status": "ok", "db_connection": "success"} on healthy state.
    Returns HTTP 503 if the database is unreachable.
    """
    try:
        check_db_connection()
        db_status = "success"
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "error",
                "db_connection": "failed",
                "detail": str(exc),
            },
        )

    return HealthResponse(status="ok", db_connection=db_status)
