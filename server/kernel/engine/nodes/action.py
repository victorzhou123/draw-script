import asyncio
import uuid

from config import settings
from engine.base_handler import BaseNodeHandler, NodeResult
from engine.node_registry import NodeRegistry


@NodeRegistry.register("action")
class ActionNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        data = self.ctx.node.data
        action_type = data.get("action_type", "mouse_click")
        params = data.get("params", {})

        # Resolve variable references for coordinates
        if "x" in params and isinstance(params["x"], str) and params["x"].startswith("$"):
            params["x"] = self._resolve_var(params["x"])
        if "y" in params and isinstance(params["y"], str) and params["y"].startswith("$"):
            params["y"] = self._resolve_var(params["y"])

        request_id = str(uuid.uuid4())
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self.ctx.ws_manager.pending_requests[request_id] = future

        sent = await self.ctx.ws_manager.send_to_client(self.ctx.client_id, {
            "type": "execute_node",
            "node_id": self.ctx.node.id,
            "request_id": request_id,
            "node_type": action_type,
            "params": params,
        })

        if not sent:
            return NodeResult(success=False, error=f"Client {self.ctx.client_id} not reachable")

        try:
            result = await asyncio.wait_for(future, timeout=settings.node_timeout)
            return NodeResult(
                success=result.get("success", True),
                output=result.get("output", {}),
                error=result.get("error"),
            )
        except asyncio.TimeoutError:
            self.ctx.ws_manager.pending_requests.pop(request_id, None)
            return NodeResult(success=False, error="Action node timed out")

    def _resolve_var(self, ref: str) -> any:
        key = ref.lstrip("$")
        parts = key.split(".")
        val = self.ctx.variables
        for part in parts:
            if isinstance(val, dict):
                val = val.get(part)
            else:
                return None
        return val
