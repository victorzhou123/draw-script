import asyncio
import json
import logging
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

from commands import CommandHandler

logger = logging.getLogger(__name__)


class DrawScriptAgent:
    def __init__(self, server_url: str, client_id: str, name: str, platform: str):
        self.server_url = server_url
        self.client_id = client_id
        self.name = name
        self.platform = platform
        self._ws = None
        self._handler = None
        self._reconnect_delay = 2.0
        self._max_delay = 60.0

    async def run(self) -> None:
        while True:
            try:
                await self._connect_and_run()
                self._reconnect_delay = 2.0
            except Exception as e:
                logger.warning(f"Connection failed: {e}. Reconnecting in {self._reconnect_delay:.0f}s...")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, self._max_delay)

    async def _connect_and_run(self) -> None:
        logger.info(f"Connecting to {self.server_url} as {self.client_id}...")
        async with websockets.connect(self.server_url) as ws:
            self._ws = ws
            self._handler = CommandHandler(self._send)
            logger.info("Connected.")

            await self._send({
                "type": "register",
                "client_id": self.client_id,
                "name": self.name,
                "platform": self.platform,
            })

            heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            try:
                await self._receive_loop()
            finally:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

    async def _receive_loop(self) -> None:
        _tasks: set[asyncio.Task] = set()
        async for raw in self._ws:
            try:
                msg = json.loads(raw)
                task = asyncio.create_task(self._handler.dispatch(msg))
                _tasks.add(task)
                task.add_done_callback(_tasks.discard)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received: {raw[:200]}")

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(5)
            await self._send({
                "type": "heartbeat",
                "client_id": self.client_id,
                "status": "idle",
            })

    async def _send(self, msg: dict[str, Any]) -> None:
        if self._ws:
            try:
                await self._ws.send(json.dumps(msg))
            except Exception as e:
                logger.warning(f"Send failed: {e}")
