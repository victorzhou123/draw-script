import asyncio
import logging
from datetime import datetime, timedelta

from config import settings

logger = logging.getLogger(__name__)


class HeartbeatMonitor:
    def __init__(self, client_ws_manager, ui_ws_manager):
        self.client_ws = client_ws_manager
        self.ui_ws = ui_ws_manager

    async def run(self) -> None:
        while True:
            await asyncio.sleep(settings.heartbeat_interval)
            await self._check()

    async def _check(self) -> None:
        threshold = timedelta(seconds=settings.heartbeat_timeout)
        now = datetime.utcnow()

        for client_id in self.client_ws.get_connected_ids():
            last = self.client_ws.get_last_heartbeat(client_id)
            if last and (now - last) > threshold:
                logger.warning(f"Client {client_id} heartbeat timeout ({(now - last).seconds}s)")
                await self.ui_ws.broadcast_event("client_status", {
                    "client_id": client_id,
                    "status": "timeout",
                    "last_seen": last.isoformat(),
                })
