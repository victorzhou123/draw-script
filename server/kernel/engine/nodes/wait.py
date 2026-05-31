import asyncio

from engine.base_handler import BaseNodeHandler, NodeResult
from engine.node_registry import NodeRegistry


@NodeRegistry.register("wait")
class WaitNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        node_id = self.ctx.node.id
        expected = len(self.ctx.graph.get_in_edges(node_id))

        if expected <= 1:
            return NodeResult()

        if node_id not in self.ctx.wait_barriers:
            self.ctx.wait_barriers[node_id] = {"count": 0, "event": asyncio.Event()}

        barrier = self.ctx.wait_barriers[node_id]
        barrier["count"] += 1
        my_count = barrier["count"]

        if my_count >= expected:
            # Last branch to arrive — wake the others and continue downstream
            barrier["event"].set()
            return NodeResult()

        # Earlier branches wait; their variables are superseded by the last arrival
        await barrier["event"].wait()
        return NodeResult(stop_branch=True)
