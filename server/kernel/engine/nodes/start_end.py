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
        return_fields: list[str] = self.ctx.node.data.get("return_fields", [])
        if return_fields:
            self.ctx.completion_result = {
                k: self.ctx.variables[k]
                for k in return_fields
                if k in self.ctx.variables
            }
        else:
            self.ctx.completion_result = dict(self.ctx.variables)

        if self.ctx.completion_event and not self.ctx.completion_event.is_set():
            self.ctx.completion_event.set()

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
    return value
