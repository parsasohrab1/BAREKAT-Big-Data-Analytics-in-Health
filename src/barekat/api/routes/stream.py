"""WebSocket and REST endpoints for real-time alerts."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from barekat.api.websocket_manager import alert_manager
from barekat.streaming.redis_bridge import get_recent_live_alerts

router = APIRouter()


@router.websocket("/alerts")
async def websocket_alerts(websocket: WebSocket):
    await alert_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await alert_manager.disconnect(websocket)


@router.get("/alerts/recent")
def recent_live_alerts(limit: int = 50):
    return {"alerts": get_recent_live_alerts(limit=limit)}
