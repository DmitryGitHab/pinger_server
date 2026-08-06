"""WebSocket, транслирующий актуальный статус всех IP каждые N секунд."""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder

from config import WS_PUSH_INTERVAL
from database import fetch_all_ips

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket client connected")
    try:
        while True:
            ips = await fetch_all_ips()
            await websocket.send_json(jsonable_encoder(ips))
            await asyncio.sleep(WS_PUSH_INTERVAL)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
