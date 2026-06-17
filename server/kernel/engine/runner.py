import asyncio
import copy
import logging

from engine.base_handler import LoopCountError, resolve_loop_count
from engine.node_registry import NodeRegistry

logger = logging.getLogger(__name__)

MAX_VISITS = 1000


async def _broadcast_log(ctx, node_id: str, level: str, message: str) -> None:
    """Append to the execution log and broadcast it tagged with node_id + level
    ("action" for normal node-activity descriptions, "error" for failures), so
    the UI can split a node's status view into "节点动作" / "日志" tabs."""
    ctx.log.append(message)
    await ctx.ui_manager.broadcast_event("execution_log", {
        "execution_id": ctx.execution_id,
        "client_id": ctx.client_id,
        "node_id": node_id,
        "level": level,
        "message": message,
    })


async def _broadcast_progress(ctx, node_id: str, node_type: str | None, status: str) -> None:
    payload = {
        "execution_id": ctx.execution_id,
        "client_id": ctx.client_id,
        "node_id": node_id,
        "status": status,
    }
    if node_type is not None:
        payload["node_type"] = node_type
    await ctx.ui_manager.broadcast_event("execution_progress", payload)


async def run_branch(
    ctx,
    start_node,
    visited_count: dict[str, int],
    script_name: str,
    stop_node_ids: set[str] | None = None,
) -> str | None:
    """Run a flow branch starting from start_node. Returns error string or None.

    Shared by ExecutionEngine and ScriptNodeHandler so sub-script behaviour is
    identical to top-level execution.
    """
    current = start_node
    while current and not ctx.stop_event.is_set():
        if stop_node_ids and current.id in stop_node_ids:
            return None
        visited_count[current.id] = visited_count.get(current.id, 0) + 1
        if visited_count[current.id] > MAX_VISITS:
            return "Infinite loop detected"

        await _broadcast_progress(ctx, current.id, current.node_type, "running")

        ctx.node = current
        node_label = current.data.get("label", "").strip()
        script_prefix = f"[{script_name}] " if script_name else ""
        label_suffix = f' "{node_label}"' if node_label else ""
        log_entry = f"{script_prefix}[{current.node_type}] {current.id}{label_suffix}"
        await _broadcast_log(ctx, current.id, "action", log_entry)

        try:
            handler_cls = NodeRegistry.get_handler(current.node_type)
            result = await handler_cls(ctx).execute()
        except Exception as e:
            logger.exception(f"Node {current.id} ({current.node_type}) failed: {e}")
            await _broadcast_log(ctx, current.id, "error", f"  ERROR: {e}")
            await _broadcast_progress(ctx, current.id, None, "error")
            return str(e)

        await _broadcast_progress(ctx, current.id, None, "done" if result.success else "error")

        if not result.success and result.error:
            await _broadcast_log(ctx, current.id, "error", f"  ERROR: {result.error}")

        if result.stop_branch:
            return None

        next_nodes = ctx.graph.get_next_nodes(current.id, result.branch)

        # When fan-out includes a loop node, check the counter first.
        # - Count not yet reached: route only to the loop node (continue looping).
        # - Count satisfied + loop has an exit edge: route to the loop node so it
        #   returns branch="exit" and the runner follows the exit edge naturally.
        # - Count satisfied + no exit edge: clean up counter and route to the
        #   other downstream nodes instead.
        if len(next_nodes) > 1:
            loop_nodes = [n for n in next_nodes if n.node_type == "loop"]
            if loop_nodes:
                loop_node = loop_nodes[0]
                try:
                    max_count = resolve_loop_count(ctx.variables, loop_node.data.get("params", {}))
                except LoopCountError as e:
                    return f"Loop node {loop_node.id}: {e}"
                if ctx.loop_counters.get(loop_node.id, 1) >= max_count:
                    if ctx.graph.get_next_nodes(loop_node.id, "exit"):
                        next_nodes = [loop_node]
                    else:
                        ctx.loop_counters.pop(loop_node.id, None)
                        next_nodes = [n for n in next_nodes if n.node_type != "loop"]
                else:
                    next_nodes = [loop_node]

        if len(next_nodes) <= 1:
            current = next_nodes[0] if next_nodes else None
        else:
            # Fan-out: branches share the same variables dict so any branch's writes
            # are immediately visible to all others and to the End node, regardless of
            # which branch arrives at Wait last. log and script_call_stack remain
            # per-branch; visited_count is copied so loop counters stay independent.
            branch_ctxs = []
            for _ in next_nodes:
                bctx = copy.copy(ctx)
                bctx.log = list(ctx.log)
                bctx.script_call_stack = list(ctx.script_call_stack)
                branch_ctxs.append(bctx)

            branch_tasks = [
                asyncio.create_task(run_branch(bctx, node, dict(visited_count), script_name))
                for bctx, node in zip(branch_ctxs, next_nodes)
            ]
            error = await _wait_for_branches(ctx, branch_tasks)
            return error

    return None


async def _wait_for_branches(ctx, branch_tasks: list) -> str | None:
    """Wait for parallel branches; returns early when end_event fires."""
    end_waiter = asyncio.create_task(ctx.end_event.wait())
    pending = set(branch_tasks)

    while pending:
        done, _ = await asyncio.wait(pending | {end_waiter}, return_when=asyncio.FIRST_COMPLETED)

        if end_waiter in done:
            if ctx._result_box:
                ctx.completion_result = ctx._result_box[0]
            for task in pending - done:
                task.add_done_callback(_log_bg_branch_error)
            return None

        for task in done:
            result = task.result()
            if result:
                end_waiter.cancel()
                return result

        pending -= done

    end_waiter.cancel()
    return None


def _log_bg_branch_error(task: asyncio.Task) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.warning("Background branch error after end: %s", exc)
