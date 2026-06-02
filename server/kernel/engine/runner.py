import asyncio
import copy
import logging

from engine.node_registry import NodeRegistry

logger = logging.getLogger(__name__)

MAX_VISITS = 1000


async def run_branch(
    ctx,
    start_node,
    visited_count: dict[str, int],
    script_name: str,
) -> str | None:
    """Run a flow branch starting from start_node. Returns error string or None.

    Shared by ExecutionEngine and ScriptNodeHandler so sub-script behaviour is
    identical to top-level execution.
    """
    current = start_node
    while current and not ctx.stop_event.is_set():
        visited_count[current.id] = visited_count.get(current.id, 0) + 1
        if visited_count[current.id] > MAX_VISITS:
            return "Infinite loop detected"

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
            await ctx.ui_manager.broadcast_event("execution_progress", {
                "execution_id": ctx.execution_id,
                "client_id": ctx.client_id,
                "node_id": current.id,
                "status": "error",
            })
            return str(e)

        await ctx.ui_manager.broadcast_event("execution_progress", {
            "execution_id": ctx.execution_id,
            "client_id": ctx.client_id,
            "node_id": current.id,
            "status": "done" if result.success else "error",
        })

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

        # When fan-out includes a loop node, route by iteration count instead of parallelizing
        if len(next_nodes) > 1:
            loop_nodes = [n for n in next_nodes if n.node_type == "loop"]
            if loop_nodes:
                loop_node = loop_nodes[0]
                max_count = int(loop_node.data.get("params", {}).get("count", 1))
                if visited_count.get(loop_node.id, 0) < max_count:
                    next_nodes = [loop_node]
                else:
                    next_nodes = [n for n in next_nodes if n.node_type != "loop"]

        if len(next_nodes) <= 1:
            current = next_nodes[0] if next_nodes else None
        else:
            # Fan-out: run branches in parallel; return early if any branch hits end
            branch_tasks = [
                asyncio.create_task(run_branch(copy.copy(ctx), node, visited_count, script_name))
                for node in next_nodes
            ]
            return await _wait_for_branches(ctx, branch_tasks)

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
