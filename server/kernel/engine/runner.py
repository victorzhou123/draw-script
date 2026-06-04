import asyncio
import copy
import logging

from engine.base_handler import interpolate_value
from engine.node_registry import NodeRegistry

logger = logging.getLogger(__name__)

MAX_VISITS = 1000
MIN_HIGHLIGHT_SECS = 0.5


def _schedule_done(ctx, node_id: str, status: str, node_start: float) -> None:
    """Fire-and-forget: broadcast execution_progress after the node has been
    visually highlighted for at least MIN_HIGHLIGHT_SECS."""
    loop = asyncio.get_running_loop()
    delay = max(0.0, MIN_HIGHLIGHT_SECS - (loop.time() - node_start))

    async def _emit() -> None:
        if delay > 0:
            await asyncio.sleep(delay)
        await ctx.ui_manager.broadcast_event("execution_progress", {
            "execution_id": ctx.execution_id,
            "client_id": ctx.client_id,
            "node_id": node_id,
            "status": status,
        })

    asyncio.create_task(_emit())


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

        node_start = asyncio.get_running_loop().time()
        await ctx.ui_manager.broadcast_event("execution_progress", {
            "execution_id": ctx.execution_id,
            "client_id": ctx.client_id,
            "node_id": current.id,
            "node_type": current.node_type,
            "status": "running",
        })

        ctx.node = current
        node_label = current.data.get("label", "").strip()
        script_prefix = f"[{script_name}] " if script_name else ""
        label_suffix = f' "{node_label}"' if node_label else ""
        log_entry = f"{script_prefix}[{current.node_type}] {current.id}{label_suffix}"
        ctx.log.append(log_entry)
        await ctx.ui_manager.broadcast_event("execution_log", {
            "execution_id": ctx.execution_id,
            "client_id": ctx.client_id,
            "message": log_entry,
        })

        try:
            handler_cls = NodeRegistry.get_handler(current.node_type)
            result = await handler_cls(ctx).execute()
        except Exception as e:
            logger.exception(f"Node {current.id} ({current.node_type}) failed: {e}")
            _schedule_done(ctx, current.id, "error", node_start)
            return str(e)

        _schedule_done(ctx, current.id, "done" if result.success else "error", node_start)

        if not result.success and result.error:
            err_entry = f"  ERROR: {result.error}"
            ctx.log.append(err_entry)
            await ctx.ui_manager.broadcast_event("execution_log", {
                "execution_id": ctx.execution_id,
                "client_id": ctx.client_id,
                "message": err_entry,
            })

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
                raw_count = interpolate_value(ctx.variables, loop_node.data.get("params", {}).get("count", 1))
                try:
                    max_count = int(raw_count)
                except (TypeError, ValueError):
                    max_count = 1
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
