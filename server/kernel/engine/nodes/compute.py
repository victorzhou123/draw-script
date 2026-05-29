import asyncio
import uuid

from config import settings
from engine.base_handler import BaseNodeHandler, NodeResult
from engine.node_registry import NodeRegistry


@NodeRegistry.register("compute")
class ComputeNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        data = self.ctx.node.data
        code: str = data.get("code", "").strip()
        if not code:
            return NodeResult()

        request_id = str(uuid.uuid4())
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self.ctx.ws_manager.pending_requests[request_id] = future

        sent = await self.ctx.ws_manager.send_to_client(self.ctx.client_id, {
            "type": "compute_node",
            "request_id": request_id,
            "node_id": self.ctx.node.id,
            "code": code,
            "context": dict(self.ctx.variables),
        })

        if not sent:
            return NodeResult(success=False, error=f"Client {self.ctx.client_id} not reachable")

        try:
            result = await asyncio.wait_for(future, timeout=settings.compute_timeout)
            if result.get("success"):
                updated = result.get("output", {}).get("updated_context", {})
                self.ctx.variables.update(updated)
            return NodeResult(
                success=result.get("success", True),
                output=result.get("output", {}),
                error=result.get("error"),
            )
        except asyncio.TimeoutError:
            self.ctx.ws_manager.pending_requests.pop(request_id, None)
            return NodeResult(success=False, error="Compute node timed out")
