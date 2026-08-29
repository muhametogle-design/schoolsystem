"""Live WebSocket stream — /ws?token=<jwt>

Fans red alarms, publication events and audit completions out to connected
state dashboards (and school dashboards) in real time.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import decode_access_token
from app.core.ws import manager

logger = logging.getLogger("ws.router")
router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = ""):
    try:
        payload = decode_access_token(token)
    except Exception:
        await websocket.close(code=4401)
        return

    user = {"user_id": int(payload["sub"]), "role": payload["role"], "school_id": payload.get("school_id")}
    await manager.connect(websocket, user)
    try:
        await websocket.send_json({"type": "connected", "payload": user})
        while True:
            # Clients may ping; anything received is ignored (server-push bus).
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)
