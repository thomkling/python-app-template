from fastapi import APIRouter, HTTPException
import structlog
import uuid

router = APIRouter()

log = structlog.stdlib.get_logger(f"app_logs")

@router.get("/ping")
async def ping():
    return "PONG"

@router.get("/exception")
async def exception():
    raise HTTPException(status_code=500, detail="exception yo!")

@router.get("/widget/{widget_id}")
async def get_widget(widget_id: uuid.UUID):
    structlog.contextvars.bind_contextvars(widget_id=widget_id)
    log.info("Successfully retrieved widget")
    return {"widget_id": widget_id}