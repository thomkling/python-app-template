from fastapi import APIRouter
import structlog
import uuid

router = APIRouter()

log = structlog.stdlib.get_logger(f"app_logs")

@router.get("/ping")
async def ping():
    return "PONG"
