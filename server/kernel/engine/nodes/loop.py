from engine.base_handler import BaseNodeHandler, LoopCountError, NodeResult, resolve_loop_count
from engine.node_registry import NodeRegistry


@NodeRegistry.register("loop")
class LoopNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        data = self.ctx.node.data
        params = data.get("params", {})
        try:
            max_count = resolve_loop_count(self.ctx.variables, params)
        except LoopCountError as e:
            return NodeResult(success=False, error=str(e))

        node_id = self.ctx.node.id
        self.ctx.loop_counters[node_id] = self.ctx.loop_counters.get(node_id, 1) + 1
        iteration = self.ctx.loop_counters[node_id]

        if iteration > max_count:
            del self.ctx.loop_counters[node_id]
            return NodeResult(branch="exit")

        return NodeResult(branch="loop")
