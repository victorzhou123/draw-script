import json

from engine.base_handler import BaseNodeHandler, NodeResult
from engine.node_registry import NodeRegistry


@NodeRegistry.register("watch")
class WatchNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        data = self.ctx.node.data
        fields: list[str] = data.get("params", {}).get("fields", [])

        if fields:
            snapshot = {k: self.ctx.variables.get(k) for k in fields}
        else:
            snapshot = dict(self.ctx.variables)

        label = data.get("label", "").strip()
        prefix = f'[watch] {label}: ' if label else '[watch] '
        message = prefix + json.dumps(snapshot, ensure_ascii=False, default=str)

        await self.ctx.ui_manager.broadcast_event("execution_log", {
            "execution_id": self.ctx.execution_id,
            "client_id": self.ctx.client_id,
            "message": message,
        })
        self.ctx.log.append(message)

        return NodeResult(success=True, output={"snapshot": snapshot})
