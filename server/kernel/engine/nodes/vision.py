import asyncio
import base64
import json
import logging
import re
import uuid

from engine.log_utils import truncate_for_log

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

        if range_marker:
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

        # ocr shortcut: use context image directly, skip client screenshot
        if vision_type == "ocr":
            ocr_context_image_var = params.pop("ocr_context_image_var", "").strip()
            if ocr_context_image_var:
                raw = self.ctx.variables.get(ocr_context_image_var, "")
                if not raw or not isinstance(raw, str):
                    return NodeResult(success=False, error=f"OCR: context 字段 '{ocr_context_image_var}' 为空或类型无效")
                if raw.startswith("data:") and "," in raw:
                    raw = raw.split(",", 1)[1]
                try:
                    img_bytes = base64.b64decode(raw)
                except Exception as e:
                    return NodeResult(success=False, error=f"OCR: context 字段 base64 解码失败: {e}")
                try:
                    from cv.vision_engine import VisionEngine
                    vision_result = await VisionEngine().analyze("ocr", img_bytes, params, None)
                    await self._log(f"[Vision] OCR完成(context图): text={truncate_for_log(vision_result.text)!r}")
                    self.ctx.variables["last_vision_result"] = vision_result.__dict__
                    if result_var:
                        self.ctx.variables[result_var] = vision_result.text
                    return NodeResult(success=True, output=vision_result.__dict__)
                except Exception as e:
                    await self._log(f"[Vision] OCR异常: {e}")
                    return NodeResult(success=False, error=str(e))

        # ai_vision shortcut: use context image directly, skip client screenshot
        if vision_type == "ai_vision":
            context_image_var = params.pop("context_image_var", "").strip()
            if context_image_var:
                raw = self.ctx.variables.get(context_image_var, "")
                if not raw or not isinstance(raw, str):
                    return NodeResult(success=False, error=f"AI视觉: context 字段 '{context_image_var}' 为空或类型无效")
                if raw.startswith("data:") and "," in raw:
                    raw = raw.split(",", 1)[1]
                try:
                    img_bytes = base64.b64decode(raw)
                except Exception as e:
                    return NodeResult(success=False, error=f"AI视觉: context 字段 base64 解码失败: {e}")

                model_config = None
                model_id = params.get("model_id", "").strip()
                if model_id:
                    from database import AIModelConfig
                    async with self.ctx.session_factory() as session:
                        mc = await session.get(AIModelConfig, model_id)
                        if mc:
                            model_config = {"api_key": mc.api_key, "base_url": mc.base_url, "model_name": mc.model_name}

                try:
                    from cv.vision_engine import VisionEngine
                    vision_result = await VisionEngine().analyze(vision_type, img_bytes, params, model_config)
                    await self._log(f"[Vision] AI分析完成(context图): found={vision_result.found}, text={truncate_for_log(vision_result.text)!r}")
                    self.ctx.variables["last_vision_result"] = vision_result.__dict__

                    if result_var:
                        if vision_result.found and vision_result.location:
                            x, y = int(vision_result.location.get("x", 0)), int(vision_result.location.get("y", 0))
                            self.ctx.variables[result_var] = f"{x},{y}"
                        elif vision_result.text:
                            post_process: list = data.get("post_process") or []
                            value = vision_result.text
                            if "parse_markdown_json" in post_process:
                                value = _parse_markdown_json(value)
                                await self._log(f"[Vision] post_process parse_markdown_json → {type(value).__name__}")
                            self.ctx.variables[result_var] = value
                        else:
                            self.ctx.variables[result_var] = None

                    return NodeResult(success=True, output=vision_result.__dict__)
                except Exception as e:
                    await self._log(f"[Vision] 异常: {e}")
                    return NodeResult(success=False, error=str(e))

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
            "params": {**params, "use_gpu": self.ctx.gpu_enabled},
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
            locations = output.get("locations")
            confidence = output.get("confidence", 0.0)

            if result_var:
                if locations is not None:
                    self.ctx.variables[result_var] = locations
                else:
                    found_value = data.get("found_value", "") or ""
                    not_found_value = data.get("not_found_value", "None") or "None"
                    # found 和 not_found 分支独立处理，避免旧逻辑的耦合问题：
                    # 旧逻辑用 `if found_value or not_found_value not in ("", "None")` 统一判断，
                    # 导致只要 not_found_value 有自定义值（如 "0"），found=True 时就会写入
                    # found_value（空字符串），而不是实际坐标，坐标被静默覆盖。
                    if found:
                        if found_value:
                            # 用户显式配置了找到时的静态值，优先使用
                            self.ctx.variables[result_var] = found_value
                        elif location:
                            x, y = int(location.get("x", 0)), int(location.get("y", 0))
                            self.ctx.variables[result_var] = f"{x},{y}"
                        else:
                            self.ctx.variables[result_var] = None
                    else:
                        # not_found_value 仅在未找到时生效，与 found 分支完全独立
                        self.ctx.variables[result_var] = None if not_found_value == "None" else not_found_value

            cuda_error = output.pop("cuda_error", None)
            if cuda_error:
                await self._log(f"[Vision] ⚠ GPU加速失败，已回退CPU: {cuda_error}")
            self.ctx.variables["last_vision_result"] = output
            return NodeResult(success=True, output=output)

        # OCR / AI vision / color detect: client returns cropped screenshot
        screenshot_b64 = output.get("screenshot")
        await self._log(f"[Vision] client result keys={list(result.keys())}, has_screenshot={bool(screenshot_b64)}")
        if not screenshot_b64:
            await self._log(f"[Vision] 未收到 screenshot, output={truncate_for_log(output)}")
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
            await self._log(f"[Vision] 分析完成: found={vision_result.found}, text={truncate_for_log(vision_result.text)!r}, location={vision_result.location}")
            self.ctx.variables["last_vision_result"] = vision_result.__dict__

            if result_var:
                locations = vision_result.raw.get("locations")
                if locations is not None:
                    self.ctx.variables[result_var] = locations
                elif vision_result.found and vision_result.location:
                    x, y = int(vision_result.location.get("x", 0)), int(vision_result.location.get("y", 0))
                    self.ctx.variables[result_var] = f"{x},{y}"
                elif vision_result.text:
                    post_process: list = data.get("post_process") or []
                    value = vision_result.text
                    if "parse_markdown_json" in post_process:
                        value = _parse_markdown_json(value)
                        await self._log(f"[Vision] post_process parse_markdown_json → {type(value).__name__}")
                    self.ctx.variables[result_var] = value
                else:
                    self.ctx.variables[result_var] = None

            return NodeResult(success=True, output=vision_result.__dict__)
        except Exception as e:
            await self._log(f"[Vision] 异常: {e}")
            return NodeResult(success=False, error=str(e))


def _parse_markdown_json(text: str):
    """Strip markdown code fences and parse as JSON. Returns parsed object on success, raw string on failure."""
    cleaned = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return text
