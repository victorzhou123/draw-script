import asyncio
import logging
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor

from cv.vision_engine import VisionResult

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=1)
_ocr_instance = None
_ocr_loading = False
_ocr_error: str | None = None

_AUTOSTART_FLAG = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".ocr_autostart")

# Upscale factor applied before recognition — small game UI text benefits greatly from 3x
_UPSCALE = 3


def _get_ocr():
    global _ocr_instance, _ocr_error
    if _ocr_instance is None:
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        from paddleocr import PaddleOCR
        try:
            # PaddleOCR 3.x: use PP-OCRv4 with higher detection limit for small text
            _ocr_instance = PaddleOCR(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                text_det_limit_side_len=2048,
                text_det_limit_type="max",
                text_recognition_model_name="en_PP-OCRv4_mobile_rec",
            )
        except TypeError:
            # PaddleOCR 2.x fallback
            _ocr_instance = PaddleOCR(use_angle_cls=True, lang="ch")
        _ocr_error = None
    return _ocr_instance


def _do_init():
    global _ocr_loading, _ocr_error
    try:
        _get_ocr()
        open(_AUTOSTART_FLAG, "w").close()
    except Exception as e:
        _ocr_error = str(e)
    finally:
        _ocr_loading = False


def should_autostart() -> bool:
    return os.path.exists(_AUTOSTART_FLAG)


def get_ocr_status() -> dict:
    try:
        import paddleocr  # noqa: F401
        installed = True
    except ImportError:
        installed = False
    return {
        "installed": installed,
        "loaded": _ocr_instance is not None,
        "loading": _ocr_loading,
        "error": _ocr_error,
    }


async def init_ocr_async() -> None:
    global _ocr_loading
    if _ocr_instance is not None or _ocr_loading:
        return
    _ocr_loading = True
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_executor, _do_init)


async def reinit_ocr_async() -> None:
    global _ocr_instance, _ocr_loading
    if _ocr_loading:
        return
    _ocr_instance = None
    _ocr_loading = True
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_executor, _do_init)


def _preprocess(img):
    """3x upscale + white border — dramatically improves small-text recognition."""
    import cv2
    h, w = img.shape[:2]
    upscaled = cv2.resize(img, (w * _UPSCALE, h * _UPSCALE), interpolation=cv2.INTER_CUBIC)
    return cv2.copyMakeBorder(upscaled, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=(255, 255, 255))


def _run_ocr(ocr, img):
    """Try PaddleOCR 3.x predict() first, fall back to 2.x ocr()."""
    tmp_path = None
    try:
        import cv2
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            tmp_path = tf.name
        cv2.imwrite(tmp_path, img)
        result = ocr.predict(tmp_path)
        return result, "3x"
    except AttributeError:
        # predict() not available → PaddleOCR 2.x
        try:
            result = ocr.ocr(img, cls=True)
        except TypeError:
            result = ocr.ocr(img)
        return result, "2x"
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def _parse_results(results, api_ver: str) -> tuple[str, list]:
    """Parse PaddleOCR output into (all_text, boxes) regardless of API version."""
    all_text = ""
    boxes = []

    if not results or not results[0]:
        return all_text, boxes

    r = results[0]

    if api_ver == "3x" or isinstance(r, dict):
        rec_texts = r.get("rec_texts", [])
        rec_scores = r.get("rec_scores", [])
        dt_polys = r.get("dt_polys", [])
        for i, text in enumerate(rec_texts):
            conf = rec_scores[i] if i < len(rec_scores) else 1.0
            box = dt_polys[i].tolist() if i < len(dt_polys) else []
            all_text += text + " "
            boxes.append({"text": text, "confidence": float(conf), "box": box})
    else:
        # PaddleOCR 2.x: [[box, [text, conf]], ...]
        for line in r:
            box, text_info = line[0], line[1]
            text = text_info[0] if isinstance(text_info, (list, tuple)) else str(text_info)
            conf = text_info[1] if isinstance(text_info, (list, tuple)) else 1.0
            all_text += text + " "
            boxes.append({"text": text, "confidence": float(conf), "box": box})

    return all_text.strip(), boxes


def _do_ocr(screenshot_bytes: bytes, find_text: str | None) -> VisionResult:
    logger.info("[OCR] 开始识别, bytes=%d, find_text=%r", len(screenshot_bytes), find_text)
    import numpy as np
    import cv2

    arr = np.frombuffer(screenshot_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    img = _preprocess(img)

    ocr = _get_ocr()
    results, api_ver = _run_ocr(ocr, img)
    all_text, boxes = _parse_results(results, api_ver)

    logger.info("[OCR] 识别完成: api=%s text=%r boxes=%d", api_ver, all_text, len(boxes))

    if find_text:
        for item in boxes:
            if find_text.lower() in item["text"].lower():
                box = item["box"]
                xs = [p[0] for p in box]
                ys = [p[1] for p in box]
                # Map coordinates back to original image space
                cx = int(sum(xs) / len(xs) / _UPSCALE)
                cy = int(sum(ys) / len(ys) / _UPSCALE)
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
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(_executor, _do_ocr, screenshot, find_text)
        except ImportError:
            return VisionResult(found=False, raw={"error": "PaddleOCR not installed. Run: pip install paddleocr paddlepaddle"})
        except Exception as e:
            return VisionResult(found=False, raw={"error": str(e)})
