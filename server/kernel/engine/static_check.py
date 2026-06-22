"""
Static checks run before saving a script.

Each check function receives a single node's data dict, the script's project_id
and default_client_id, and an open DB session.  It returns a NodeCheckResult if
there is something to report, or None when everything is fine.

Add new check functions and register them in `check_node` to extend coverage.
"""
from __future__ import annotations

import json
from dataclasses import dataclass


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class NodeCheckResult:
    node_id: str
    status: str          # "ok" | "warning" | "error"
    message: str = ""


# ── Dispatcher ────────────────────────────────────────────────────────────────

async def check_node(
    cell: dict,
    project_id: str | None,
    client_id: str | None,
    session,
) -> NodeCheckResult | None:
    """Run all applicable static checks for a single graph cell."""
    data = cell.get("data") or {}
    node_type = data.get("type", "")
    node_id = cell.get("id", "")

    if node_type == "vision":
        return await _check_vision_node(node_id, data, project_id, client_id, session)

    return None


# ── Per-node checks ───────────────────────────────────────────────────────────

async def _check_vision_node(
    node_id: str,
    data: dict,
    project_id: str | None,
    client_id: str | None,
    session,
) -> NodeCheckResult | None:
    """Warn when range_marker and template are bound to different windows."""
    if data.get("vision_type", "template_match") != "template_match":
        return None

    range_marker_name = (data.get("range_marker") or "").strip()
    template_id = (data.get("params", {}).get("template_id") or "").strip()

    if not range_marker_name or not template_id:
        return None

    from database import Template, ProjectClientWindow

    tpl = await session.get(Template, template_id)
    if not tpl or not tpl.window_title:
        return None  # template has no window info → cannot compare

    if not project_id or not client_id:
        return None

    pcw = await session.get(ProjectClientWindow, (project_id, client_id))
    if not pcw or not pcw.window_title:
        return NodeCheckResult(
            node_id=node_id,
            status="warning",
            message="客户端无窗口绑定，无法验证检测范围与模板是否来自同一窗口",
        )

    if pcw.window_title != tpl.window_title:
        return NodeCheckResult(
            node_id=node_id,
            status="warning",
            message=(
                f"检测范围绑定窗口「{pcw.window_title}」"
                f"与模板来源窗口「{tpl.window_title}」不一致"
            ),
        )

    return None


# ── Batch helper ──────────────────────────────────────────────────────────────

async def run_flow_checks(
    flow_json: str | dict,
    project_id: str | None,
    client_id: str | None,
    session,
) -> list[NodeCheckResult]:
    """Check every node in a flow and return all non-None results."""
    if isinstance(flow_json, str):
        try:
            flow = json.loads(flow_json)
        except Exception:
            return []
    else:
        flow = flow_json

    results: list[NodeCheckResult] = []
    for cell in flow.get("cells", []):
        result = await check_node(cell, project_id, client_id, session)
        if result is not None:
            results.append(result)
    return results
