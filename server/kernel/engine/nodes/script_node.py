import json
import logging

from engine.base_handler import BaseNodeHandler, NodeResult
from engine.context import ExecutionContext
from engine.flow_graph import FlowGraph
from engine.node_registry import NodeRegistry

logger = logging.getLogger(__name__)


@NodeRegistry.register("script")
class ScriptNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        script_id = self.ctx.node.data.get("script_id", "").strip()
        if not script_id:
            return NodeResult(success=False, error="Script node: no script_id configured")

        async with self.ctx.session_factory() as db:
            from database import Script
            script = await db.get(Script, script_id)
            if not script:
                return NodeResult(success=False, error=f"Script node: script '{script_id}' not found")
            flow_json = json.loads(script.flow_json or "{}")

        graph = FlowGraph.from_x6_json(flow_json)
        start = graph.get_start_node()
        if not start:
            return NodeResult(success=False, error="Script node: referenced script has no start node")

        sub_ctx = ExecutionContext(
            execution_id=self.ctx.execution_id,
            client_id=self.ctx.client_id,
            node=start,
            graph=graph,
            ws_manager=self.ctx.ws_manager,
            ui_manager=self.ctx.ui_manager,
            session_factory=self.ctx.session_factory,
            project_id=self.ctx.project_id,
            variables=dict(self.ctx.variables),
            stop_event=self.ctx.stop_event,
            loop_stack=[],
            log=self.ctx.log,
            completion_event=None,
        )

        current = start
        visited: dict[str, int] = {}
        while current and not self.ctx.stop_event.is_set():
            visited[current.id] = visited.get(current.id, 0) + 1
            if visited[current.id] > 1000:
                return NodeResult(success=False, error="Script node: infinite loop detected in sub-script")

            sub_ctx.node = current
            self.ctx.log.append(f"  [sub:{script_id[:8]}] [{current.node_type}] {current.id}")

            try:
                handler_cls = NodeRegistry.get_handler(current.node_type)
                result = await handler_cls(sub_ctx).execute()
            except Exception as e:
                logger.exception(f"Sub-script node {current.id} ({current.node_type}) failed: {e}")
                return NodeResult(success=False, error=str(e))

            if not result.success:
                return NodeResult(success=False, error=result.error)

            next_nodes = graph.get_next_nodes(current.id, result.branch)
            current = next_nodes[0] if next_nodes else None

        if sub_ctx.completion_result:
            self.ctx.variables.update(sub_ctx.completion_result)

        return NodeResult(success=True, output=sub_ctx.completion_result)
