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

        data = self.ctx.node.data
        params = data.get("params", {})
        timeout_enabled = params.get("timeout_enabled", False)

        if node_id not in self.ctx.wait_barriers:
            self.ctx.wait_barriers[node_id] = {
                "count": 0,
                "event": asyncio.Event(),
                "timed_out": False,
            }

        barrier = self.ctx.wait_barriers[node_id]

        # Late arrival after timeout already fired — pass through immediately
        if barrier.get("timed_out"):
            barrier["count"] += 1
            if barrier["count"] >= expected:
                del self.ctx.wait_barriers[node_id]
            return NodeResult()

        barrier["count"] += 1
        my_count = barrier["count"]

        if my_count >= expected:
            # Last branch to arrive naturally — cancel timeout task and proceed
            task = barrier.get("timeout_task")
            if task and not task.done():
                task.cancel()
            del self.ctx.wait_barriers[node_id]
            barrier["event"].set()
            return NodeResult()

        # Start one shared timeout task when the first waiter arrives
        if timeout_enabled and "timeout_task" not in barrier:
            seconds = float(params.get("timeout_seconds", 0))
            ms = float(params.get("timeout_ms", 0))
            total = seconds + ms / 1000.0

            async def _fire_timeout(bid: str, b: dict):
                try:
                    await asyncio.sleep(total)
                    b2 = self.ctx.wait_barriers.get(bid)
                    if b2 is b and not b2.get("timed_out"):
                        b2["timed_out"] = True
                        b2["event"].set()
                except asyncio.CancelledError:
                    pass

            barrier["timeout_task"] = asyncio.create_task(_fire_timeout(node_id, barrier))

        await barrier["event"].wait()

        if barrier.get("timed_out"):
            return NodeResult()  # Timeout fired — continue execution
        return NodeResult(stop_branch=True)  # Normal: last arrival woke us
