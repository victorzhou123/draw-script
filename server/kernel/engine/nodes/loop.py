from engine.base_handler import BaseNodeHandler, NodeResult
from engine.node_registry import NodeRegistry


@NodeRegistry.register("loop")
class LoopNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        data = self.ctx.node.data
        params = data.get("params", {})
        max_count = int(params.get("count", 1))
        node_id = self.ctx.node.id

        # Find or initialize loop frame on the stack
        frame = None
        for f in self.ctx.loop_stack:
            if f["node_id"] == node_id:
                frame = f
                break

        if frame is None:
            frame = {"node_id": node_id, "iteration": 0}
            self.ctx.loop_stack.append(frame)

        frame["iteration"] += 1

        if frame["iteration"] <= max_count and not self.ctx.stop_event.is_set():
            return NodeResult(success=True, branch="loop", output={"iteration": frame["iteration"]})
        else:
            self.ctx.loop_stack.remove(frame)
            return NodeResult(success=True, branch="exit", output={"iterations_done": frame["iteration"] - 1})
