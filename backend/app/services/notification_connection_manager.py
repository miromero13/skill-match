"""Single-worker WebSocket connection registry for HU-24."""
import asyncio
from collections import defaultdict
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from fastapi import WebSocket


class NotificationConnectionManager:
    """Own active sockets by authenticated user within one FastAPI process."""

    def __init__(self) -> None:
        self._connections: dict[UUID, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, user_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[user_id].add(websocket)

    async def disconnect(self, user_id: UUID, websocket: WebSocket) -> None:
        async with self._lock:
            sockets = self._connections.get(user_id)
            if sockets is None:
                return
            sockets.discard(websocket)
            if not sockets:
                self._connections.pop(user_id, None)

    def connection_count(self, user_id: UUID) -> int:
        return len(self._connections.get(user_id, ()))

    async def publish(self, user_id: UUID, payload: Mapping[str, Any]) -> int:
        async with self._lock:
            sockets = tuple(self._connections.get(user_id, ()))
        delivered = 0
        dead: list[WebSocket] = []
        message = dict(payload)
        for websocket in sockets:
            try:
                await websocket.send_json(message)
                delivered += 1
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            await self.disconnect(user_id, websocket)
        return delivered

    async def close_all(self, code: int = 1001) -> None:
        async with self._lock:
            sockets = [socket for group in self._connections.values() for socket in group]
            self._connections.clear()
        for websocket in sockets:
            try:
                await websocket.close(code=code)
            except Exception:
                pass


notification_connection_manager = NotificationConnectionManager()
