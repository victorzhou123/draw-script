from engine.base_handler import BaseNodeHandler, NodeResult
from engine.node_registry import NodeRegistry


@NodeRegistry.register("start")
class StartNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        return NodeResult()


@NodeRegistry.register("end")
class EndNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        return NodeResult()
