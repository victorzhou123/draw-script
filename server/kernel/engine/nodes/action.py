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
        params = {k: self._interpolate(v) for k, v in data.get("params", {}).items()}

        # Resolve 'coords' param: "$varname" → "x,y" string → split into x/y integers.
        # This is how vision results (template_match, ai_vision find, etc.) are consumed.
        coords_val = params.get("coords")
        if isinstance(coords_val, str) and "," in coords_val:
            try:
                cx, cy = coords_val.split(",", 1)
                params["x"] = int(float(cx.strip()))
                params["y"] = int(float(cy.strip()))
            except (ValueError, AttributeError):
                pass
        params.pop("coords", None)

        request_id = str(uuid.uuid4())
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self.ctx.ws_manager.pending_requests[request_id] = future

        sent = await self.ctx.ws_manager.send_to_client(self.ctx.client_id, {
            "type": "execute_node",
            "node_id": self.ctx.node.id,
            "request_id": request_id,
            "node_type": action_type,
            "project_id": self.ctx.project_id,
            "params": params,
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

    _MISSING = object()

    def _resolve_var(self, ref: str) -> any:
        key = ref.lstrip("$")
        parts = key.split(".")
        val = self.ctx.variables
        for part in parts:
            if isinstance(val, dict):
                if part not in val:
                    return self._MISSING
                val = val[part]
            else:
                return self._MISSING
        return val

    def _interpolate(self, value: any) -> any:
        """Resolve {{var}} and legacy $var references in string param values."""
        if not isinstance(value, str):
            return value
        # Whole-value {{var}} or legacy $var: return the raw Python value so
        # callers get the correct type (e.g. int coords, not the string "123").
        import re
        tpl_whole = re.match(r'^\{\{([^}]+)\}\}$', value)
        if tpl_whole:
            resolved = self._resolve_var(tpl_whole.group(1).strip())
            return value if resolved is self._MISSING else resolved
        if value.startswith("$"):
            resolved = self._resolve_var(value)
            return value if resolved is self._MISSING else resolved
        # Partial template: substitute each {{var}} with its string representation.
        def _replace(m):
            resolved = self._resolve_var(m.group(1).strip())
            if resolved is self._MISSING:
                return m.group(0)
            return str(resolved) if resolved is not None else ""
        return re.sub(r"\{\{([^}]+)\}\}", _replace, value)
