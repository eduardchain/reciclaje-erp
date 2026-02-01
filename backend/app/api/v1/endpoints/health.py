from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db

router = APIRouter()


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    description="Verify API and database are running",
)
def health_check(db: Session = Depends(get_db)) -> dict:
    """
    Health check endpoint that verifies the API and database connectivity.

    Returns:
        dict: Status information including API and database status
    """
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "healthy",
        "database": db_status,
    }
