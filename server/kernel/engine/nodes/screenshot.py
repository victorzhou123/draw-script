import asyncio
import uuid

from config import settings
from engine.base_handler import BaseNodeHandler, NodeResult
from engine.node_registry import NodeRegistry


@NodeRegistry.register("screenshot")
class ScreenshotNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        request_id = str(uuid.uuid4())
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self.ctx.ws_manager.pending_requests[request_id] = future

        sent = await self.ctx.ws_manager.send_to_client(self.ctx.client_id, {
            "type": "capture_screenshot",
            "request_id": request_id,
        })

        if not sent:
            return NodeResult(success=False, error=f"Client {self.ctx.client_id} not reachable")

        try:
            b64_data = await asyncio.wait_for(future, timeout=settings.node_timeout)
            self.ctx.variables["last_screenshot"] = b64_data
            return NodeResult(success=True, output={"screenshot": "stored"})
        except asyncio.TimeoutError:
            self.ctx.ws_manager.pending_requests.pop(request_id, None)
            return NodeResult(success=False, error="Screenshot capture timed out")
