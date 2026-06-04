from engine.base_handler import BaseNodeHandler, NodeResult
from engine.node_registry import NodeRegistry


@NodeRegistry.register("loop")
class LoopNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        data = self.ctx.node.data
        params = data.get("params", {})
        raw_count = self._interpolate(params.get("count", 1))
        try:
            max_count = int(raw_count)
        except (TypeError, ValueError):
            max_count = 1

        node_id = self.ctx.node.id
        self.ctx.loop_counters[node_id] = self.ctx.loop_counters.get(node_id, 0) + 1
        iteration = self.ctx.loop_counters[node_id]

        # TODO: if a condition node inside the loop body exits without passing
        # through this node's exit branch, loop_counters[node_id] will be stale
        # the next time this loop is entered (e.g. in a nested-loop scenario).

        if iteration > max_count:
            del self.ctx.loop_counters[node_id]
            return NodeResult(branch="exit")

        return NodeResult(branch="loop")
