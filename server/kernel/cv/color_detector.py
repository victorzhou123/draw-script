import asyncio
from concurrent.futures import ThreadPoolExecutor

from cv.vision_engine import VisionResult

_executor = ThreadPoolExecutor(max_workers=2)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _do_detect(screenshot_bytes: bytes, color: str, tolerance: int, mode: str) -> VisionResult:
    import cv2
    import numpy as np

    arr = np.frombuffer(screenshot_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    r, g, b = _hex_to_rgb(color) if color.startswith("#") else (0, 0, 0)
    bgr = np.array([b, g, r], dtype=np.uint8)
    low = np.clip(bgr.astype(int) - tolerance, 0, 255).astype(np.uint8)
    high = np.clip(bgr.astype(int) + tolerance, 0, 255).astype(np.uint8)

    mask = cv2.inRange(img, low, high)
    pixel_count = int(np.sum(mask > 0))
    found = pixel_count > 0

    location = None
    if found and mode == "largest_contour":
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest)
            location = {"x": x + w // 2, "y": y + h // 2, "w": w, "h": h}

    return VisionResult(
        found=found,
        confidence=1.0 if found else 0.0,
        location=location,
        raw={"pixel_count": pixel_count, "color": color},
    )


class ColorDetector:
    async def detect(self, screenshot: bytes, params: dict) -> VisionResult:
        color = params.get("color", "#FF0000")
        tolerance = int(params.get("tolerance", 20))
        mode = params.get("mode", "largest_contour")
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(_executor, _do_detect, screenshot, color, tolerance, mode)
        except Exception as e:
            return VisionResult(found=False, raw={"error": str(e)})
