import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ClientWSManager:
    """Manages WebSocket connections from Windows client agents."""

    def __init__(self):
        self._connections: dict[str, WebSocket] = {}
        self._heartbeats: dict[str, datetime] = {}
        self._lock = asyncio.Lock()
        self.pending_requests: dict[str, asyncio.Future] = {}

    async def connect(self, client_id: str, ws: WebSocket) -> None:
        async with self._lock:
            self._connections[client_id] = ws
            self._heartbeats[client_id] = datetime.utcnow()

    async def disconnect(self, client_id: str) -> None:
        async with self._lock:
            self._connections.pop(client_id, None)
            self._heartbeats.pop(client_id, None)

    def update_heartbeat(self, client_id: str) -> None:
        self._heartbeats[client_id] = datetime.utcnow()

    def get_last_heartbeat(self, client_id: str) -> datetime | None:
        return self._heartbeats.get(client_id)

    def get_connected_ids(self) -> list[str]:
        return list(self._connections.keys())

    def is_connected(self, client_id: str) -> bool:
        return client_id in self._connections

    async def send_to_client(self, client_id: str, message: dict[str, Any]) -> bool:
        ws = self._connections.get(client_id)
        if not ws:
            return False
        try:
            await ws.send_text(json.dumps(message))
            return True
        except Exception as e:
            logger.warning(f"Failed to send to client {client_id}: {e}")
            return False

    async def broadcast(self, message: dict[str, Any]) -> None:
        for client_id in list(self._connections.keys()):
            await self.send_to_client(client_id, message)

    def resolve_pending(self, request_id: str, result: Any) -> None:
        future = self.pending_requests.pop(request_id, None)
        if future and not future.done():
            future.set_result(result)

    def reject_pending(self, request_id: str, error: Exception) -> None:
        future = self.pending_requests.pop(request_id, None)
        if future and not future.done():
            future.set_exception(error)


class UIWSManager:
    """Manages WebSocket connections from browser UI sessions."""

    def __init__(self):
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(ws)

    async def broadcast_event(self, event_type: str, data: dict[str, Any]) -> None:
        message = json.dumps({"type": event_type, **data})
        dead = set()
        for ws in list(self._connections):
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            await self.disconnect(ws)


client_ws_manager = ClientWSManager()
ui_ws_manager = UIWSManager()
