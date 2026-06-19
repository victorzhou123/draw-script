import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from engine.context import ExecutionContext
from engine.flow_graph import FlowGraph, FlowNode
from engine.node_registry import NodeRegistry
from engine.runner import run_branch, _broadcast_log, _broadcast_progress, _broadcast_context

logger = logging.getLogger(__name__)


class ExecutionEngine:
    def __init__(self, ws_manager, ui_manager, session_factory):
        self.ws_manager = ws_manager
        self.ui_manager = ui_manager
        self.session_factory = session_factory
        self._tasks: dict[str, asyncio.Task] = {}
        self._stop_events: dict[str, asyncio.Event] = {}

    async def run_script(
        self,
        execution_id: str,
        script_id: str,
        client_id: str,
        flow_json: dict[str, Any],
        project_id: str | None = None,
        initial_variables: dict[str, Any] | None = None,
        completion_event: asyncio.Event | None = None,
        script_name: str = "",
    ) -> None:
        stop_event = asyncio.Event()
        self._stop_events[execution_id] = stop_event
        task = asyncio.create_task(
            self._execute(execution_id, script_id, client_id, flow_json, stop_event, project_id, initial_variables or {}, completion_event, script_name)
        )
        self._tasks[execution_id] = task
        try:
            await task
        except asyncio.CancelledError:
            await self._finish_execution(execution_id, client_id, "stopped",
                                         completion_event=completion_event)
        except Exception as e:
            logger.exception(f"Execution {execution_id} failed: {e}")
            await self._finish_execution(execution_id, client_id, "error", str(e),
                                         completion_event=completion_event)
        finally:
            self._tasks.pop(execution_id, None)
            self._stop_events.pop(execution_id, None)

    async def stop_execution(self, execution_id: str) -> None:
        stop_event = self._stop_events.get(execution_id)
        if stop_event:
            stop_event.set()
        task = self._tasks.get(execution_id)
        if task and not task.done():
            task.cancel()

    async def _execute(
        self,
        execution_id: str,
        script_id: str,
        client_id: str,
        flow_json: dict[str, Any],
        stop_event: asyncio.Event,
        project_id: str | None = None,
        initial_variables: dict[str, Any] | None = None,
        completion_event: asyncio.Event | None = None,
        script_name: str = "",
    ) -> None:
        graph = FlowGraph.from_x6_json(flow_json)
        current = graph.get_start_node()
        if not current:
            await self._finish_execution(execution_id, client_id, "error", "No start node found",
                                         completion_event=completion_event)
            return

        gpu_enabled = False
        async with self.session_factory() as db:
            from database import Client
            client_row = await db.get(Client, client_id)
            if client_row:
                gpu_enabled = bool(client_row.gpu_enabled)

        await self.ui_manager.broadcast_event("execution_started", {
            "execution_id": execution_id,
            "script_id": script_id,
            "client_id": client_id,
        })

        from log_handler import enqueue_execution_log
        log: list[str] = []
        separator = "-" * 40
        sep_entry = f"{separator}\n开始执行：{script_name or execution_id}"
        log.append(sep_entry)
        await self.ui_manager.broadcast_event("execution_log", {
            "execution_id": execution_id,
            "client_id": client_id,
            "message": sep_entry,
        })
        enqueue_execution_log(
            level="INFO",
            message=sep_entry,
            client_id=client_id,
            script_id=script_id,
            execution_id=execution_id,
        )
        ctx = ExecutionContext(
            execution_id=execution_id,
            client_id=client_id,
            node=current,
            graph=graph,
            ws_manager=self.ws_manager,
            ui_manager=self.ui_manager,
            session_factory=self.session_factory,
            project_id=project_id,
            script_id=script_id,
            gpu_enabled=gpu_enabled,
            variables=dict(initial_variables) if initial_variables else {},
            stop_event=stop_event,
            log=log,
            completion_event=completion_event,
        )

        visited_count: dict[str, int] = {}
        error = await self._run_branch(ctx, current, visited_count, script_name)

        import json as _json
        if error:
            await self._finish_execution(execution_id, client_id, "error", error, "\n".join(log),
                                         completion_event=completion_event)
        else:
            status = "stopped" if stop_event.is_set() else "completed"
            completion = ctx._result_box[0] if ctx._result_box else ctx.completion_result
            result_json = _json.dumps(completion, ensure_ascii=False) if completion else None
            await self._finish_execution(execution_id, client_id, status, None, "\n".join(log),
                                         result_json=result_json, completion_event=completion_event)

    async def _run_branch(
        self,
        ctx: ExecutionContext,
        start_node: FlowNode,
        visited_count: dict[str, int],
        script_name: str,
    ) -> str | None:
        return await run_branch(ctx, start_node, visited_count, script_name)

    async def _finish_execution(
        self,
        execution_id: str,
        client_id: str,
        status: str,
        error: str | None = None,
        log: str = "",
        result_json: str | None = None,
        completion_event: asyncio.Event | None = None,
    ) -> None:
        async with self.session_factory() as db:
            from database import Execution
            execution = await db.get(Execution, execution_id)
            if execution:
                execution.status = status
                execution.finished_at = datetime.now(timezone.utc)
                if log:
                    execution.log = log
                elif error:
                    execution.log = f"ERROR: {error}"
                if result_json is not None:
                    execution.result_json = result_json
                await db.commit()
        if completion_event and not completion_event.is_set():
            completion_event.set()

        await self.ui_manager.broadcast_event("execution_finished", {
            "execution_id": execution_id,
            "client_id": client_id,
            "status": status,
            "error": error,
        })
        logger.info(f"Execution {execution_id} finished: {status}")
        logger.debug(f"Execution {execution_id} result: {result_json}")

    async def debug_execute_node(
        self,
        script_id: str,
        client_id: str,
        flow_json: dict[str, Any],
        node_id: str,
        project_id: str | None = None,
        initial_variables: dict[str, Any] | None = None,
    ) -> None:
        execution_id = f"debug-{uuid.uuid4().hex[:8]}"
        graph = FlowGraph.from_x6_json(flow_json)
        target = graph.nodes.get(node_id)

        gpu_enabled = False
        async with self.session_factory() as db:
            from database import Client
            client_row = await db.get(Client, client_id)
            if client_row:
                gpu_enabled = bool(client_row.gpu_enabled)

        await self.ui_manager.broadcast_event("execution_started", {
            "execution_id": execution_id,
            "script_id": script_id,
            "client_id": client_id,
            "debug": True,
            "debug_node_id": node_id,
        })

        if not target:
            await self.ui_manager.broadcast_event("execution_finished", {
                "execution_id": execution_id,
                "client_id": client_id,
                "status": "error",
                "error": f"Node {node_id} not found",
            })
            return

        ctx = ExecutionContext(
            execution_id=execution_id,
            client_id=client_id,
            node=target,
            graph=graph,
            ws_manager=self.ws_manager,
            ui_manager=self.ui_manager,
            session_factory=self.session_factory,
            project_id=project_id,
            script_id=script_id,
            gpu_enabled=gpu_enabled,
            variables=dict(initial_variables or {}),
        )

        await _broadcast_progress(ctx, node_id, target.node_type, "running")
        await _broadcast_context(ctx, node_id, "before")
        try:
            handler_cls = NodeRegistry.get_handler(target.node_type)
            result = await handler_cls(ctx).execute()
            await _broadcast_progress(ctx, node_id, None, "done" if result.success else "error")
            await _broadcast_context(ctx, node_id, "after")
            if not result.success and result.error:
                await _broadcast_log(ctx, node_id, "error", f"  ERROR: {result.error}")
        except Exception as e:
            logger.exception(f"Debug execute node {node_id} failed: {e}")
            await _broadcast_log(ctx, node_id, "error", f"  ERROR: {e}")
            await _broadcast_progress(ctx, node_id, None, "error")
            await _broadcast_context(ctx, node_id, "after")

        await self.ui_manager.broadcast_event("execution_finished", {
            "execution_id": execution_id,
            "client_id": client_id,
            "status": "completed",
            "error": None,
        })

    async def debug_run_to_node(
        self,
        script_id: str,
        client_id: str,
        flow_json: dict[str, Any],
        node_id: str,
        project_id: str | None = None,
    ) -> None:
        execution_id = f"debug-{uuid.uuid4().hex[:8]}"
        graph = FlowGraph.from_x6_json(flow_json)
        start_node = graph.get_start_node()

        gpu_enabled = False
        async with self.session_factory() as db:
            from database import Client
            client_row = await db.get(Client, client_id)
            if client_row:
                gpu_enabled = bool(client_row.gpu_enabled)

        await self.ui_manager.broadcast_event("execution_started", {
            "execution_id": execution_id,
            "script_id": script_id,
            "client_id": client_id,
            "debug": True,
        })

        if not start_node:
            await self.ui_manager.broadcast_event("execution_finished", {
                "execution_id": execution_id,
                "client_id": client_id,
                "status": "error",
                "error": "No start node found",
            })
            return

        ctx = ExecutionContext(
            execution_id=execution_id,
            client_id=client_id,
            node=start_node,
            graph=graph,
            ws_manager=self.ws_manager,
            ui_manager=self.ui_manager,
            session_factory=self.session_factory,
            project_id=project_id,
            script_id=script_id,
            gpu_enabled=gpu_enabled,
            variables={},
        )

        error = await run_branch(ctx, start_node, {}, "", stop_after_node_id=node_id)

        status = "error" if error else "completed"
        await self.ui_manager.broadcast_event("execution_finished", {
            "execution_id": execution_id,
            "client_id": client_id,
            "status": status,
            "error": error,
        })
