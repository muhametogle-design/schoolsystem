"""Live WebSocket stream — /ws?token=<jwt>

Fans red alarms, publication events and audit completions out to connected
state dashboards (and school dashboards) in real time.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.deps import AUTH_COOKIE, get_user_from_token
from app.core.db import SessionLocal, set_rls_context
from app.core.ws import manager

logger = logging.getLogger("ws.router")
router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = ""):
    # Same-origin mobile clients can use the HttpOnly login cookie when
    # localStorage is unavailable; a bearer query token remains supported for
    # existing clients and diagnostics.
    token = token or websocket.cookies.get(AUTH_COOKIE, "")
    try:
        # WebSocket connections do not use FastAPI's normal request dependency
        # chain, so explicitly apply the same active-account / stale-token
        # verification used by protected HTTP routes.
        with SessionLocal() as db:
            set_rls_context(db, school_id=None, role="none")
            account = get_user_from_token(token, db)
            user = {
                "user_id": account.id,
                "role": account.role,
                "school_id": account.school_id,
            }
    except Exception:
        await websocket.close(code=4401)
        return

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
