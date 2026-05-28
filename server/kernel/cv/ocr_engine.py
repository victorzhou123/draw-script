import asyncio
import io
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from cv.vision_engine import VisionResult

_executor = ThreadPoolExecutor(max_workers=1)
_ocr_instance = None


def _get_ocr():
    global _ocr_instance
    if _ocr_instance is None:
        from paddleocr import PaddleOCR
        _ocr_instance = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
    return _ocr_instance


def _do_ocr(screenshot_bytes: bytes, find_text: str | None) -> VisionResult:
    import numpy as np
    import cv2

    arr = np.frombuffer(screenshot_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    ocr = _get_ocr()
    results = ocr.ocr(img, cls=True)

    all_text = ""
    boxes = []
    if results and results[0]:
        for line in results[0]:
            box, (text, conf) = line
            all_text += text + " "
            boxes.append({"text": text, "confidence": conf, "box": box})

    all_text = all_text.strip()

    if find_text:
        for item in boxes:
            if find_text.lower() in item["text"].lower():
                box = item["box"]
                xs = [p[0] for p in box]
                ys = [p[1] for p in box]
                cx = int(sum(xs) / len(xs))
                cy = int(sum(ys) / len(ys))
                return VisionResult(
                    found=True,
                    confidence=item["confidence"],
                    location={"x": cx, "y": cy},
                    text=item["text"],
                    raw={"all_text": all_text, "boxes": boxes},
                )
        return VisionResult(found=False, text=all_text, raw={"all_text": all_text, "boxes": boxes})

    return VisionResult(
        found=bool(all_text),
        text=all_text,
        raw={"all_text": all_text, "boxes": boxes},
    )


class OCREngine:
    async def recognize(self, screenshot: bytes, params: dict) -> VisionResult:
        find_text = params.get("find_text")
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(_executor, _do_ocr, screenshot, find_text)
        except ImportError:
            return VisionResult(found=False, raw={"error": "PaddleOCR not installed. Run: pip install paddleocr paddlepaddle"})
        except Exception as e:
            return VisionResult(found=False, raw={"error": str(e)})
