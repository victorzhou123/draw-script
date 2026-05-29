import asyncio
import logging
from datetime import datetime
from typing import Any

from engine.context import ExecutionContext
from engine.flow_graph import FlowGraph
from engine.node_registry import NodeRegistry

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
    ) -> None:
        stop_event = asyncio.Event()
        self._stop_events[execution_id] = stop_event
        task = asyncio.create_task(
            self._execute(execution_id, client_id, flow_json, stop_event, project_id, initial_variables or {}, completion_event)
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
        client_id: str,
        flow_json: dict[str, Any],
        stop_event: asyncio.Event,
        project_id: str | None = None,
        initial_variables: dict[str, Any] | None = None,
        completion_event: asyncio.Event | None = None,
    ) -> None:
        graph = FlowGraph.from_x6_json(flow_json)
        current = graph.get_start_node()
        if not current:
            await self._finish_execution(execution_id, client_id, "error", "No start node found",
                                         completion_event=completion_event)
            return

        await self.ui_manager.broadcast_event("execution_started", {
            "execution_id": execution_id,
            "client_id": client_id,
        })

        log: list[str] = []
        ctx = ExecutionContext(
            execution_id=execution_id,
            client_id=client_id,
            node=current,
            graph=graph,
            ws_manager=self.ws_manager,
            ui_manager=self.ui_manager,
            session_factory=self.session_factory,
            project_id=project_id,
            variables=dict(initial_variables) if initial_variables else {},
            stop_event=stop_event,
            log=log,
            completion_event=completion_event,
        )

        visited_count: dict[str, int] = {}
        MAX_VISITS = 1000

        while current and not stop_event.is_set():
            visited_count[current.id] = visited_count.get(current.id, 0) + 1
            if visited_count[current.id] > MAX_VISITS:
                await self._finish_execution(execution_id, client_id, "error", "Infinite loop detected",
                                             completion_event=completion_event)
                return

            await self.ui_manager.broadcast_event("execution_progress", {
                "execution_id": execution_id,
                "client_id": client_id,
                "node_id": current.id,
                "node_type": current.node_type,
                "status": "running",
            })

            ctx.node = current
            log_entry = f"[{current.node_type}] node {current.id}"
            log.append(log_entry)
            await self.ui_manager.broadcast_event("execution_log", {
                "execution_id": execution_id,
                "client_id": client_id,
                "message": log_entry,
            })

            try:
                handler_cls = NodeRegistry.get_handler(current.node_type)
                handler = handler_cls(ctx)
                result = await handler.execute()
            except Exception as e:
                logger.exception(f"Node {current.id} ({current.node_type}) failed: {e}")
                await self._finish_execution(execution_id, client_id, "error", str(e),
                                             completion_event=completion_event)
                return

            await self.ui_manager.broadcast_event("execution_progress", {
                "execution_id": execution_id,
                "client_id": client_id,
                "node_id": current.id,
                "status": "done" if result.success else "error",
            })

            next_nodes = graph.get_next_nodes(current.id, result.branch)
            current = next_nodes[0] if next_nodes else None

        import json as _json
        status = "stopped" if stop_event.is_set() else "completed"
        result_json = _json.dumps(ctx.completion_result) if ctx.completion_result else None
        await self._finish_execution(execution_id, client_id, status, None, "\n".join(log),
                                     result_json=result_json, completion_event=completion_event)

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
                execution.finished_at = datetime.utcnow()
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
