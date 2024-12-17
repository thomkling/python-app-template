from fastapi import APIRouter
import structlog

router = APIRouter()

log = structlog.stdlib.get_logger("app_logs")

@router.get("/ping")
async def ping():
    return "PONG"
