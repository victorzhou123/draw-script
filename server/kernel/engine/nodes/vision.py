import base64

from engine.base_handler import BaseNodeHandler, NodeResult
from engine.node_registry import NodeRegistry


@NodeRegistry.register("vision")
class VisionNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        data = self.ctx.node.data
        vision_type = data.get("vision_type", "template_match")
        params = data.get("params", {})

        screenshot_b64 = self.ctx.variables.get("last_screenshot")
        if not screenshot_b64:
            return NodeResult(success=False, error="No screenshot in context. Add a Screenshot node before Vision.")

        try:
            screenshot_bytes = base64.b64decode(screenshot_b64)
        except Exception:
            return NodeResult(success=False, error="Invalid screenshot data")

        try:
            from cv.vision_engine import VisionEngine
            result = await VisionEngine().analyze(vision_type, screenshot_bytes, params)
            self.ctx.variables["last_vision_result"] = result.__dict__
            return NodeResult(success=True, output=result.__dict__)
        except Exception as e:
            return NodeResult(success=False, error=str(e))
