"""Live WebSocket event bus powering the real-time Red Alarm dashboard stream.

Every connected state_inspector browser receives instant `red_alarm`,
`attendance_submitted`, `exam_published` and `audit_completed` events.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging

from fastapi import WebSocket

logger = logging.getLogger("ws.bus")


class ConnectionManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # socket -> {"user_id", "role", "school_id"}
        self.active: dict[WebSocket, dict] = {}
        # The main event loop, bound at startup so worker threads (sync
        # endpoints, cron jobs) can marshal broadcasts onto the loop.
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, websocket: WebSocket, user: dict) -> None:
        await websocket.accept()
        async with self._lock:
            self.active[websocket] = user

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.active.pop(websocket, None)

    async def broadcast(self, event_type: str, payload: dict) -> None:
        """Fan an event out to every connected client."""
        message = json.dumps(
            {"type": event_type, "payload": payload, "ts": dt.datetime.now(dt.timezone.utc).isoformat()}
        )
        dead: list[WebSocket] = []
        async with self._lock:
            targets = list(self.active.items())
        for socket, meta in targets:
            try:
                await socket.send_text(message)
            except Exception:
                dead.append(socket)
        for socket in dead:
            await self.disconnect(socket)

    def broadcast_sync(self, event_type: str, payload: dict) -> None:
        """Schedule a broadcast from synchronous code — either an endpoint
        running on the loop or a worker thread (threads are marshalled onto
        the loop bound at startup via run_coroutine_threadsafe)."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.broadcast(event_type, payload))
        except RuntimeError:
            loop = self._loop
            if loop is not None and loop.is_running():
                asyncio.run_coroutine_threadsafe(self.broadcast(event_type, payload), loop)
            else:
                logger.warning("No event loop available; event %s dropped", event_type)


manager = ConnectionManager()


def emit_live_websocket_alarm_event(school_id: int, message: str, school_name: str | None = None) -> None:
    """AI Agent Note implementation: stream the alarm instantly to all active
    state_inspector client browser connections."""
    manager.broadcast_sync(
        "red_alarm",
        {
            "school_id": school_id,
            "school_name": school_name,
            "message": message,
            "alarm": True,
        },
    )
