import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from cv.vision_engine import VisionResult

_executor = ThreadPoolExecutor(max_workers=2)


def _do_match(screenshot_bytes: bytes, template_b64: str, threshold: float) -> VisionResult:
    import cv2
    import numpy as np

    screenshot_arr = np.frombuffer(screenshot_bytes, np.uint8)
    screenshot = cv2.imdecode(screenshot_arr, cv2.IMREAD_COLOR)

    template_bytes = base64.b64decode(template_b64)
    template_arr = np.frombuffer(template_bytes, np.uint8)
    template = cv2.imdecode(template_arr, cv2.IMREAD_COLOR)

    if screenshot is None or template is None:
        return VisionResult(found=False, raw={"error": "Failed to decode images"})

    result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    found = float(max_val) >= threshold
    h, w = template.shape[:2]
    center_x = max_loc[0] + w // 2
    center_y = max_loc[1] + h // 2

    return VisionResult(
        found=found,
        confidence=float(max_val),
        location={"x": center_x, "y": center_y, "top": max_loc[1], "left": max_loc[0], "w": w, "h": h} if found else None,
        raw={"max_val": float(max_val), "max_loc": list(max_loc)},
    )


class TemplateMatchCV:
    async def match(self, screenshot: bytes, params: dict) -> VisionResult:
        template_b64 = params.get("template")
        if not template_b64:
            return VisionResult(found=False, raw={"error": "No template provided"})
        threshold = float(params.get("threshold", 0.8))
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_executor, _do_match, screenshot, template_b64, threshold)
