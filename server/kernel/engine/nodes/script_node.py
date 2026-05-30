import json
import logging

from engine.base_handler import BaseNodeHandler, NodeResult
from engine.flow_graph import FlowGraph
from engine.node_registry import NodeRegistry
from engine.runner import run_branch

logger = logging.getLogger(__name__)


@NodeRegistry.register("script")
class ScriptNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        script_id = self.ctx.node.data.get("script_id", "").strip()
        if not script_id:
            return NodeResult(success=False, error="Script node: no script_id configured")

        if script_id in self.ctx.script_call_stack:
            cycle = " → ".join(self.ctx.script_call_stack + [script_id])
            return NodeResult(success=False, error=f"Script node: circular reference detected: {cycle}")

        if len(self.ctx.script_call_stack) >= 10:
            return NodeResult(success=False, error="Script node: call depth limit (10) exceeded")

        async with self.ctx.session_factory() as db:
            from database import Script
            script = await db.get(Script, script_id)
            if not script:
                return NodeResult(success=False, error=f"Script node: script '{script_id}' not found")
            flow_json = json.loads(script.flow_json or "{}")
            script_name = script.name

        graph = FlowGraph.from_x6_json(flow_json)
        start = graph.get_start_node()
        if not start:
            return NodeResult(success=False, error="Script node: referenced script has no start node")

        from engine.context import ExecutionContext
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
            script_call_stack=self.ctx.script_call_stack + [script_id],
        )

        async def _log(message: str):
            self.ctx.log.append(message)
            await self.ctx.ui_manager.broadcast_event("execution_log", {
                "execution_id": self.ctx.execution_id,
                "client_id": self.ctx.client_id,
                "message": message,
            })

        await _log(f"  ▶ 子脚本开始：{script_name}")
        error = await run_branch(sub_ctx, start, {}, script_name)

        if error:
            await _log(f"  ◀ 子脚本失败：{script_name}  ERROR: {error}")
            return NodeResult(success=False, error=error)

        await _log(f"  ◀ 子脚本完成：{script_name}")

        if sub_ctx.completion_result:
            self.ctx.variables.update(sub_ctx.completion_result)

        return NodeResult(success=True, output=sub_ctx.completion_result)
