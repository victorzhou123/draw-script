import asyncio
import base64
import logging
import uuid

from config import settings
from engine.base_handler import BaseNodeHandler, NodeResult
from engine.node_registry import NodeRegistry

logger = logging.getLogger(__name__)


@NodeRegistry.register("vision")
class VisionNodeHandler(BaseNodeHandler):
    async def _log(self, message: str) -> None:
        self.ctx.log.append(message)
        await self.ctx.ui_manager.broadcast_event("execution_log", {
            "execution_id": self.ctx.execution_id,
            "client_id": self.ctx.client_id,
            "message": message,
        })

    async def execute(self) -> NodeResult:
        data = self.ctx.node.data
        vision_type = data.get("vision_type", "template_match")
        params = dict(data.get("params", {}))
        result_var = data.get("result_var", "").strip()
        range_marker = data.get("range_marker", "").strip()

        if not range_marker:
            return NodeResult(success=False, error="Vision 节点需要选择检测范围（Box 标记）")

        params["range_marker"] = range_marker

        if vision_type == "template_match":
            template_context_var = params.pop("template_context_var", "")
            template_id = params.pop("template_id", "")
            if template_context_var:
                raw = self.ctx.variables.get(template_context_var, "")
                if raw and isinstance(raw, str):
                    if "," in raw and raw.startswith("data:"):
                        raw = raw.split(",", 1)[1]
                    params["template_b64"] = raw
            elif template_id:
                import os
                from database import Template
                async with self.ctx.session_factory() as session:
                    tpl = await session.get(Template, template_id)
                    if tpl:
                        tpl_path = os.path.join(settings.templates_dir, tpl.filename)
                        if os.path.isfile(tpl_path):
                            with open(tpl_path, "rb") as fh:
                                params["template_b64"] = base64.b64encode(fh.read()).decode()

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
            "node_type": vision_type,
            "project_id": self.ctx.project_id,
            "params": params,
            "_markers": marker_data,
        })

        if not sent:
            return NodeResult(success=False, error=f"Client {self.ctx.client_id} not reachable")

        try:
            result = await asyncio.wait_for(future, timeout=settings.node_timeout)
        except asyncio.TimeoutError:
            self.ctx.ws_manager.pending_requests.pop(request_id, None)
            return NodeResult(success=False, error="Vision node timed out")

        if not result.get("success", True):
            return NodeResult(success=False, error=result.get("error", "Unknown error"))

        output = result.get("output", {})

        if vision_type == "template_match":
            found = output.get("found", False)
            location = output.get("location")
            confidence = output.get("confidence", 0.0)

            if result_var:
                found_value = data.get("found_value", "") or ""
                not_found_value = data.get("not_found_value", "None") or "None"
                if found_value or not_found_value not in ("", "None"):
                    self.ctx.variables[result_var] = found_value if found else (None if not_found_value == "None" else not_found_value)
                else:
                    if found and location:
                        x, y = int(location.get("x", 0)), int(location.get("y", 0))
                        self.ctx.variables[result_var] = f"{x},{y}"
                    else:
                        self.ctx.variables[result_var] = None

            self.ctx.variables["last_vision_result"] = output
            return NodeResult(success=True, output=output)

        # OCR / AI vision / color detect: client returns cropped screenshot
        screenshot_b64 = output.get("screenshot")
        await self._log(f"[Vision] client result keys={list(result.keys())}, has_screenshot={bool(screenshot_b64)}")
        if not screenshot_b64:
            await self._log(f"[Vision] 未收到 screenshot, output={output}")
            return NodeResult(success=False, error="Vision node: client did not return screenshot")

        screenshot_bytes = base64.b64decode(screenshot_b64)
        await self._log(f"[Vision] screenshot 大小={len(screenshot_bytes)} bytes, 开始分析 vision_type={vision_type}")

        try:
            model_config = None
            if vision_type == "ai_vision":
                model_id = params.get("model_id", "").strip()
                if model_id:
                    from database import AIModelConfig
                    async with self.ctx.session_factory() as session:
                        mc = await session.get(AIModelConfig, model_id)
                        if mc:
                            model_config = {
                                "api_key": mc.api_key,
                                "base_url": mc.base_url,
                                "model_name": mc.model_name,
                            }

            from cv.vision_engine import VisionEngine
            vision_result = await VisionEngine().analyze(vision_type, screenshot_bytes, params, model_config)
            await self._log(f"[Vision] 分析完成: found={vision_result.found}, text={vision_result.text!r}, location={vision_result.location}, raw={vision_result.raw}")
            self.ctx.variables["last_vision_result"] = vision_result.__dict__

            if result_var:
                if vision_result.found and vision_result.location:
                    x, y = int(vision_result.location.get("x", 0)), int(vision_result.location.get("y", 0))
                    self.ctx.variables[result_var] = f"{x},{y}"
                elif vision_result.text:
                    self.ctx.variables[result_var] = vision_result.text
                else:
                    self.ctx.variables[result_var] = None

            return NodeResult(success=True, output=vision_result.__dict__)
        except Exception as e:
            await self._log(f"[Vision] 异常: {e}")
            return NodeResult(success=False, error=str(e))
