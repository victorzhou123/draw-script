import asyncio
import uuid

from config import settings
from engine.base_handler import BaseNodeHandler, NodeResult
from engine.node_registry import NodeRegistry


@NodeRegistry.register("screenshot")
class ScreenshotNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        data = self.ctx.node.data
        result_var = data.get("result_var", "").strip()
        range_marker = data.get("range_marker", "").strip()

        if not result_var:
            return NodeResult(success=False, error="Screenshot node: result_var is required")

        params: dict = {}
        if range_marker:
            params["range_marker"] = range_marker

        marker_data: dict = {}
        if self.ctx.project_id:
            from engine.marker_loader import load_project_markers
            marker_data = await load_project_markers(
                self.ctx.project_id, self.ctx.client_id, self.ctx.session_factory
            )

        request_id = str(uuid.uuid4())
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self.ctx.ws_manager.pending_requests[request_id] = future

        sent = await self.ctx.ws_manager.send_to_client(self.ctx.client_id, {
            "type": "capture_screenshot",
            "request_id": request_id,
            "params": params,
            "_markers": marker_data,
        })

        if not sent:
            return NodeResult(success=False, error=f"Client {self.ctx.client_id} not reachable")

        try:
            result = await asyncio.wait_for(future, timeout=settings.node_timeout)
        except asyncio.TimeoutError:
            self.ctx.ws_manager.pending_requests.pop(request_id, None)
            return NodeResult(success=False, error="Screenshot capture timed out")

        if not result.get("success", True):
            return NodeResult(success=False, error=result.get("error", "Unknown error"))

        b64_data = result.get("screenshot", "")
        self.ctx.variables[result_var] = b64_data
        return NodeResult(success=True, output={"stored_in": result_var})
