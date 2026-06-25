from engine.base_handler import BaseNodeHandler, LoopCountError, NodeResult, resolve_loop_count
from engine.node_registry import NodeRegistry
from engine.type_coerce import coerce_typed, TypeConversionError


@NodeRegistry.register("loop")
class LoopNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        data = self.ctx.node.data
        params = data.get("params", {})

        if params.get("mode") == "iterate":
            return self._execute_iterate(params)
        return self._execute_count(params)

    def _execute_count(self, params: dict) -> NodeResult:
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

    def _execute_iterate(self, params: dict) -> NodeResult:
        node_id = self.ctx.node.id
        iter_var = params.get("iter_var", "")
        item_var = params.get("item_var", "")
        item_type = params.get("item_type", "str")

        if not iter_var:
            return NodeResult(success=False, error="迭代模式未指定迭代变量 (iter_var)")

        raw = self.ctx.variables.get(iter_var)
        if raw is None:
            return NodeResult(success=False, error=f"Context 中不存在变量 {iter_var!r}")

        if isinstance(raw, dict):
            items = [{"key": k, "value": v} for k, v in raw.items()]
        elif isinstance(raw, list):
            items = raw
        else:
            return NodeResult(
                success=False,
                error=f"迭代变量 {iter_var!r} 不是 list 或 dict，实际类型: {type(raw).__name__}",
            )

        idx = self.ctx.loop_counters.get(node_id, 0)

        if idx >= len(items):
            self.ctx.loop_counters.pop(node_id, None)
            return NodeResult(branch="exit")

        item = items[idx]

        if item_type and item_type != "None":
            try:
                item = coerce_typed(item, item_type)
            except TypeConversionError as e:
                return NodeResult(success=False, error=str(e))

        if item_var:
            self.ctx.variables[item_var] = item

        self.ctx.loop_counters[node_id] = idx + 1

        return NodeResult(branch="loop")
