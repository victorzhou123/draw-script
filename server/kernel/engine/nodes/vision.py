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
from engine.runner import _broadcast_log
from engine.type_coerce import coerce_typed, TypeConversionError

logger = logging.getLogger(__name__)


@NodeRegistry.register("vision")
class VisionNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        data = self.ctx.node.data
        vision_type = data.get("vision_type", "template_match")
        params = dict(data.get("params", {}))
        result_var = data.get("result_var", "").strip()
        range_marker = data.get("range_marker", "").strip()

        if not result_var:
            return NodeResult(success=False, error="Vision node: 结果存入字段未配置")

        if vision_type == "template_match":
            if not params.get("template_id", "") and not params.get("template_context_var", ""):
                return NodeResult(success=False, error="Vision node (模板匹配): 请选择模板图片或指定图片来源字段")
        elif vision_type == "ai_vision":
            if not params.get("model_id", "").strip():
                return NodeResult(success=False, error="Vision node (AI视觉): 未选择 AI 模型")
            if not params.get("prompt", "").strip():
                return NodeResult(success=False, error="Vision node (AI视觉): 提示词未填写")
        elif vision_type == "color_detect":
            if not params.get("color", "").strip():
                return NodeResult(success=False, error="Vision node (颜色检测): 颜色值未填写")

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
                    await _broadcast_log(self.ctx, self.ctx.node.id, "action", f"[Vision] OCR完成(context图): text={truncate_for_log(vision_result.text)!r}")
                    if result_var:
                        if vision_result.text:
                            value_type = data.get("value_type") or "str"
                            raw_value = vision_result.text
                        else:
                            value_type = data.get("ocr_not_found_value_type") or "str"
                            raw_value = data.get("ocr_not_found_value") or ""
                        try:
                            self.ctx.variables[result_var] = coerce_typed(raw_value, value_type)
                        except TypeConversionError as e:
                            return NodeResult(success=False, error=f"OCR 结果类型转换失败（变量 '{result_var}'，声明类型 {value_type}）: {e}")
                    return NodeResult(success=True, output=vision_result.__dict__)
                except Exception as e:
                    await _broadcast_log(self.ctx, self.ctx.node.id, "error", f"[Vision] OCR异常: {e}")
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
                    await _broadcast_log(self.ctx, self.ctx.node.id, "action", f"[Vision] AI分析完成(context图): found={vision_result.found}, text={truncate_for_log(vision_result.text)!r}")
                    if result_var:
                        value_type = data.get("value_type") or "str"
                        if vision_result.found and vision_result.location:
                            x, y = int(vision_result.location.get("x", 0)), int(vision_result.location.get("y", 0))
                            raw_value = f"{x},{y}"
                        elif vision_result.text:
                            post_process: list = data.get("post_process") or []
                            raw_value = vision_result.text
                            if "parse_markdown_json" in post_process:
                                raw_value = _parse_markdown_json(raw_value)
                                await _broadcast_log(self.ctx, self.ctx.node.id, "action", f"[Vision] post_process parse_markdown_json → {type(raw_value).__name__}")
                        else:
                            raw_value = None
                        try:
                            self.ctx.variables[result_var] = coerce_typed(raw_value, value_type)
                        except TypeConversionError as e:
                            return NodeResult(success=False, error=f"AI视觉结果类型转换失败（变量 '{result_var}'，声明类型 {value_type}）: {e}")

                    return NodeResult(success=True, output=vision_result.__dict__)
                except Exception as e:
                    await _broadcast_log(self.ctx, self.ctx.node.id, "error", f"[Vision] 异常: {e}")
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
                result_type = params.get("result_type", "coordinate")
                found_value_type = data.get("found_value_type") or "str"
                not_found_value_type = data.get("not_found_value_type") or "str"

                if locations is not None:
                    if locations:
                        raw_value, type_name = locations, found_value_type
                    else:
                        raw_value, type_name = data.get("not_found_value", "") or "", not_found_value_type
                elif found:
                    if result_type == "custom":
                        raw_value, type_name = data.get("found_value", "") or "", found_value_type
                    elif location:
                        x, y = int(location.get("x", 0)), int(location.get("y", 0))
                        raw_value, type_name = f"{x},{y}", found_value_type
                    else:
                        raw_value, type_name = None, found_value_type
                else:
                    raw_value, type_name = data.get("not_found_value", "") or "", not_found_value_type

                try:
                    self.ctx.variables[result_var] = coerce_typed(raw_value, type_name)
                except TypeConversionError as e:
                    return NodeResult(success=False, error=f"模板匹配结果类型转换失败（变量 '{result_var}'，声明类型 {type_name}）: {e}")

            cuda_error = output.pop("cuda_error", None)
            if cuda_error:
                await _broadcast_log(self.ctx, self.ctx.node.id, "error", f"[Vision] ⚠ GPU加速失败，已回退CPU: {cuda_error}")
            return NodeResult(success=True, output=output)

        # OCR / AI vision / color detect: client returns cropped screenshot
        screenshot_b64 = output.get("screenshot")
        await _broadcast_log(self.ctx, self.ctx.node.id, "action", f"[Vision] client result keys={list(result.keys())}, has_screenshot={bool(screenshot_b64)}")
        if not screenshot_b64:
            await _broadcast_log(self.ctx, self.ctx.node.id, "error", f"[Vision] 未收到 screenshot, output={truncate_for_log(output)}")
            return NodeResult(success=False, error="Vision node: client did not return screenshot")

        screenshot_bytes = base64.b64decode(screenshot_b64)
        await _broadcast_log(self.ctx, self.ctx.node.id, "action", f"[Vision] screenshot 大小={len(screenshot_bytes)} bytes, 开始分析 vision_type={vision_type}")

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
            await _broadcast_log(self.ctx, self.ctx.node.id, "action", f"[Vision] 分析完成: found={vision_result.found}, text={truncate_for_log(vision_result.text)!r}, location={vision_result.location}")
            if result_var:
                if vision_type == "color_detect":
                    result_type = params.get("result_type", "coordinate")
                    found_value_type = data.get("found_value_type") or "str"
                    not_found_value_type = data.get("not_found_value_type") or "str"

                    if result_type == "custom":
                        if vision_result.found:
                            raw_value, type_name = data.get("found_value", "") or "", found_value_type
                        else:
                            raw_value, type_name = data.get("not_found_value", "") or "", not_found_value_type
                    else:
                        locations = vision_result.raw.get("locations")
                        if locations:
                            raw_value, type_name = locations, found_value_type
                        elif vision_result.found and vision_result.location:
                            x, y = int(vision_result.location.get("x", 0)), int(vision_result.location.get("y", 0))
                            raw_value, type_name = f"{x},{y}", found_value_type
                        else:
                            raw_value, type_name = data.get("not_found_value", "") or "", not_found_value_type

                    try:
                        self.ctx.variables[result_var] = coerce_typed(raw_value, type_name)
                    except TypeConversionError as e:
                        return NodeResult(success=False, error=f"颜色检测结果类型转换失败（变量 '{result_var}'，声明类型 {type_name}）: {e}")
                else:
                    value_type = data.get("value_type") or "str"
                    locations = vision_result.raw.get("locations")
                    if locations is not None:
                        raw_value = locations
                    elif vision_result.found and vision_result.location:
                        x, y = int(vision_result.location.get("x", 0)), int(vision_result.location.get("y", 0))
                        raw_value = f"{x},{y}"
                    elif vision_result.text:
                        post_process: list = data.get("post_process") or []
                        raw_value = vision_result.text
                        if "parse_markdown_json" in post_process:
                            raw_value = _parse_markdown_json(raw_value)
                            await _broadcast_log(self.ctx, self.ctx.node.id, "action", f"[Vision] post_process parse_markdown_json → {type(raw_value).__name__}")
                    else:
                        if vision_type == "ocr":
                            value_type = data.get("ocr_not_found_value_type") or value_type
                            raw_value = data.get("ocr_not_found_value") or ""
                        else:
                            raw_value = None
                    try:
                        self.ctx.variables[result_var] = coerce_typed(raw_value, value_type)
                    except TypeConversionError as e:
                        return NodeResult(success=False, error=f"识别结果类型转换失败（变量 '{result_var}'，声明类型 {value_type}）: {e}")

            return NodeResult(success=True, output=vision_result.__dict__)
        except Exception as e:
            await _broadcast_log(self.ctx, self.ctx.node.id, "error", f"[Vision] 异常: {e}")
            return NodeResult(success=False, error=str(e))


def _parse_markdown_json(text: str):
    """Strip markdown code fences and parse as JSON. Returns parsed object on success, raw string on failure."""
    cleaned = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return text
