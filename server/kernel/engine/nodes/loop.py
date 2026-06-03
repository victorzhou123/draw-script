import asyncio
import copy
import logging

from engine.base_handler import BaseNodeHandler, NodeResult
from engine.node_registry import NodeRegistry

logger = logging.getLogger(__name__)


@NodeRegistry.register("loop")
class LoopNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        data = self.ctx.node.data
        params = data.get("params", {})
        max_count = int(params.get("count", 1))
        loop_node_id = self.ctx.node.id

        body_starts = self.ctx.graph.get_next_nodes(loop_node_id, "loop")

        for iteration in range(1, max_count + 1):
            if self.ctx.stop_event.is_set():
                break
            if not body_starts:
                break

            # Reset wait barriers so each iteration gets a fresh sync state.
            self.ctx.wait_barriers.clear()

            current = body_starts[0]
            visited: dict[str, int] = {}
            dead_end = False

            while current and current.id != loop_node_id and not self.ctx.stop_event.is_set():
                visited[current.id] = visited.get(current.id, 0) + 1
                if visited[current.id] > 200:
                    return NodeResult(success=False, error=f"Loop body: too many visits at node {current.id}")

                self.ctx.node = current
                node_label = current.data.get("label", "").strip()
                label_suffix = f' "{node_label}"' if node_label else ""

                await self.ctx.ui_manager.broadcast_event("execution_log", {
                    "execution_id": self.ctx.execution_id,
                    "client_id": self.ctx.client_id,
                    "message": f"  [loop {iteration}/{max_count}] [{current.node_type}] {current.id}{label_suffix}",
                })
                await self.ctx.ui_manager.broadcast_event("execution_progress", {
                    "execution_id": self.ctx.execution_id,
                    "client_id": self.ctx.client_id,
                    "node_id": current.id,
                    "node_type": current.node_type,
                    "status": "running",
                })

                try:
                    handler_cls = NodeRegistry.get_handler(current.node_type)
                    result = await handler_cls(self.ctx).execute()
                except Exception as e:
                    logger.exception(f"Loop body node {current.id} ({current.node_type}) failed: {e}")
                    return NodeResult(success=False, error=str(e))

                await self.ctx.ui_manager.broadcast_event("execution_progress", {
                    "execution_id": self.ctx.execution_id,
                    "client_id": self.ctx.client_id,
                    "node_id": current.id,
                    "status": "done" if result.success else "error",
                })

                if not result.success:
                    if result.error:
                        await self.ctx.ui_manager.broadcast_event("execution_log", {
                            "execution_id": self.ctx.execution_id,
                            "client_id": self.ctx.client_id,
                            "message": f"  ERROR: {result.error}",
                        })
                    return NodeResult(success=False, error=result.error)

                if result.stop_branch:
                    # This branch is done (e.g. non-last arrival at a wait node).
                    break

                next_nodes = self.ctx.graph.get_next_nodes(current.id, result.branch)
                # Exclude the back-edge to the loop node itself (marks end of body).
                body_next = [n for n in next_nodes if n.id != loop_node_id]

                if len(body_next) > 1:
                    # Fan-out: run all branches in parallel, stopping at the loop boundary.
                    from engine.runner import run_branch
                    branch_tasks = [
                        asyncio.create_task(
                            run_branch(
                                copy.copy(self.ctx), node, visited.copy(),
                                f"loop {iteration}/{max_count}",
                                stop_node_ids={loop_node_id},
                            )
                        )
                        for node in body_next
                    ]
                    branch_errors = await asyncio.gather(*branch_tasks, return_exceptions=True)
                    for err in branch_errors:
                        if isinstance(err, Exception):
                            return NodeResult(success=False, error=str(err))
                        if err:
                            return NodeResult(success=False, error=err)
                    current = None  # fan-out consumed the rest of this iteration
                elif body_next:
                    current = body_next[0]
                else:
                    # No continuation and we didn't reach the loop back-edge.
                    current = None
                    dead_end = True

            if dead_end:
                break

        return NodeResult(success=True, branch="exit")
