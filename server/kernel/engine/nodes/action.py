import asyncio
import uuid

from config import settings
from engine.base_handler import BaseNodeHandler, NodeResult
from engine.node_registry import NodeRegistry


@NodeRegistry.register("action")
class ActionNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        data = self.ctx.node.data
        action_type = data.get("action_type", "mouse_click")
        raw_params = data.get("params", {})

        if action_type in ("mouse_click", "mouse_double_click", "mouse_move"):
            if not raw_params.get("coords") and raw_params.get("x") is None:
                return NodeResult(success=False, error=f"Action ({action_type}): 坐标未配置")
        elif action_type == "keyboard_type":
            if not str(raw_params.get("text") or "").strip():
                return NodeResult(success=False, error="Action (keyboard_type): 输入文本未配置")
        elif action_type == "keyboard_hotkey":
            if not str(raw_params.get("keys") or "").strip():
                return NodeResult(success=False, error="Action (keyboard_hotkey): 按键未配置")

        params = {k: self._interpolate(v) for k, v in raw_params.items()}

        # Resolve 'coords' param: "$varname" → "x,y" string → split into x/y integers.
        # This is how vision results (template_match, ai_vision find, etc.) are consumed.
        coords_val = params.get("coords")
        if isinstance(coords_val, str) and "," in coords_val:
            try:
                cx, cy = coords_val.split(",", 1)
                params["x"] = int(float(cx.strip()))
                params["y"] = int(float(cy.strip()))
            except (ValueError, AttributeError) as e:
                return NodeResult(success=False, error=f"Action node: 坐标解析失败 coords={coords_val!r}: {e}")
        params.pop("coords", None)

        request_id = str(uuid.uuid4())
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self.ctx.ws_manager.pending_requests[request_id] = future

        marker_data: dict = {}
        if self.ctx.project_id:
            from engine.marker_loader import load_project_markers
            marker_data = await load_project_markers(
                self.ctx.project_id, self.ctx.client_id, self.ctx.session_factory
            )

        sent = await self.ctx.ws_manager.send_to_client(self.ctx.client_id, {
            "type": "execute_node",
            "node_id": self.ctx.node.id,
            "request_id": request_id,
            "node_type": action_type,
            "project_id": self.ctx.project_id,
            "params": params,
            "_markers": marker_data,
        })

        if not sent:
            return NodeResult(success=False, error=f"Client {self.ctx.client_id} not reachable")

        try:
            result = await asyncio.wait_for(future, timeout=settings.node_timeout)
            return NodeResult(
                success=result.get("success", True),
                output=result.get("output", {}),
                error=result.get("error"),
            )
        except asyncio.TimeoutError:
            self.ctx.ws_manager.pending_requests.pop(request_id, None)
            return NodeResult(success=False, error="Action node timed out")

