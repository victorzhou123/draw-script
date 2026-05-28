import asyncio

from engine.base_handler import BaseNodeHandler, NodeResult
from engine.node_registry import NodeRegistry


@NodeRegistry.register("delay")
class DelayNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        data = self.ctx.node.data
        params = data.get("params", {})
        seconds = float(params.get("seconds", 1.0))
        ms = float(params.get("ms", 0))
        total = seconds + ms / 1000.0

        # Check stop_event periodically instead of one big sleep
        elapsed = 0.0
        chunk = 0.1
        while elapsed < total:
            if self.ctx.stop_event.is_set():
                return NodeResult(success=True, output={"interrupted": True})
            await asyncio.sleep(min(chunk, total - elapsed))
            elapsed += chunk

        return NodeResult(success=True, output={"slept_seconds": total})
