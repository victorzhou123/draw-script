from engine.base_handler import BaseNodeHandler, NodeResult
from engine.node_registry import NodeRegistry


@NodeRegistry.register("start")
class StartNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        fields = self.ctx.node.data.get("fields", [])
        for f in fields:
            name = f.get("name", "").strip()
            if not name:
                continue
            if name not in self.ctx.variables:
                default = f.get("default", "")
                self.ctx.variables[name] = _coerce(default, f.get("type", "any"))
            else:
                self.ctx.variables[name] = _coerce(self.ctx.variables[name], f.get("type", "any"))
        return NodeResult()


@NodeRegistry.register("end")
class EndNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        if self.ctx._result_box:
            # Another branch already hit end; first wins.
            return NodeResult()

        return_fields: list[str] = self.ctx.node.data.get("return_fields", [])
        result = (
            {k: self.ctx.variables[k] for k in return_fields if k in self.ctx.variables}
            if return_fields
            else dict(self.ctx.variables)
        )
        self.ctx._result_box.append(result)
        self.ctx.completion_result = result
        self.ctx.end_event.set()
        return NodeResult()


def _coerce(value, type_hint: str):
    if type_hint == "int":
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0
    if type_hint == "float":
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0
    if type_hint == "bool":
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes")
    if type_hint == "str":
        return str(value) if value is not None else ""
    if type_hint == "list":
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            import json
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else []
            except (ValueError, TypeError):
                return []
        return []
    if type_hint == "dict":
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            import json
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, dict) else {}
            except (ValueError, TypeError):
                return {}
        return {}
    return value
