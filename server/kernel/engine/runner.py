import asyncio
import copy
import logging

from engine.base_handler import LoopCountError, resolve_loop_count
from engine.node_registry import NodeRegistry

logger = logging.getLogger(__name__)

MAX_VISITS = 1000


def _safe_vars(v, depth: int = 0):
    if depth > 4:
        return "…"
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, dict):
        return {str(k): _safe_vars(vv, depth + 1) for k, vv in list(v.items())[:100]}
    if isinstance(v, (list, tuple)):
        return [_safe_vars(i, depth + 1) for i in list(v)[:100]]
    return repr(v)


async def _broadcast_context(ctx, node_id: str, phase: str) -> None:
    """Broadcast a snapshot of ctx.variables before/after a node executes."""
    await ctx.ui_manager.broadcast_event("execution_context", {
        "execution_id": ctx.execution_id,
        "client_id": ctx.client_id,
        "node_id": node_id,
        "phase": phase,
        "variables": _safe_vars(ctx.variables),
    })


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
    from log_handler import enqueue_execution_log
    _node = ctx.graph.nodes.get(node_id) if ctx.graph else None
    enqueue_execution_log(
        level="ERROR" if level == "error" else "INFO",
        message=message,
        client_id=ctx.client_id,
        script_id=ctx.script_id,
        execution_id=ctx.execution_id,
        node_id=node_id,
        node_label=_node.data.get("label", "").strip() if _node else None,
        node_type=_node.node_type if _node else None,
    )


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
    stop_after_node_id: str | None = None,
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
        await _broadcast_context(ctx, current.id, "before")

        try:
            handler_cls = NodeRegistry.get_handler(current.node_type)
            result = await handler_cls(ctx).execute()
        except Exception as e:
            logger.exception(f"Node {current.id} ({current.node_type}) failed: {e}")
            await _broadcast_log(ctx, current.id, "error", f"  ERROR: {e}")
            await _broadcast_progress(ctx, current.id, None, "error")
            await _broadcast_context(ctx, current.id, "after")
            return str(e)

        await _broadcast_progress(ctx, current.id, None, "done" if result.success else "error")
        await _broadcast_context(ctx, current.id, "after")

        if not result.success and result.error:
            await _broadcast_log(ctx, current.id, "error", f"  ERROR: {result.error}")

        if result.stop_branch:
            return None

        if stop_after_node_id and current.id == stop_after_node_id:
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
                params = loop_node.data.get("params", {})
                if params.get("mode") == "iterate":
                    is_exhausted = _is_iterate_exhausted(ctx, loop_node.id, params)
                else:
                    try:
                        max_count = resolve_loop_count(ctx.variables, params)
                    except LoopCountError as e:
                        return f"Loop node {loop_node.id}: {e}"
                    is_exhausted = ctx.loop_counters.get(loop_node.id, 1) >= max_count
                if is_exhausted:
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
                asyncio.create_task(run_branch(bctx, node, dict(visited_count), script_name,
                                               stop_after_node_id=stop_after_node_id))
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


def _is_iterate_exhausted(ctx, loop_node_id: str, params: dict) -> bool:
    """Return True when the iterate-mode loop has consumed all items.

    If the source variable is missing or not iterable we return False so the
    loop node itself runs and produces a proper error message.
    """
    iter_var = params.get("iter_var", "")
    raw = ctx.variables.get(iter_var) if iter_var else None
    if isinstance(raw, (list, dict)):
        iterable_len = len(raw)
    else:
        return False  # let the loop node handle the error
    current_idx = ctx.loop_counters.get(loop_node_id, 0)
    return current_idx >= iterable_len
