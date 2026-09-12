from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.config.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


@router.get("/health/db")
async def health_check_db(db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(text("SELECT 1"))
        row = result.scalar()
    
        return {"status": "ok", "db": row == 1}
    except Exception as e:
        raise HTTPException(status_code=503, 
                            detail={"status": "unhealthy", "db": False, "error": str(e)})