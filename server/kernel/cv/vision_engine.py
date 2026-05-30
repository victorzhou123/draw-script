from dataclasses import dataclass, field
from typing import Any


@dataclass
class VisionResult:
    found: bool = False
    confidence: float = 0.0
    location: dict[str, float] | None = None
    text: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class VisionEngine:
    async def analyze(
        self,
        vision_type: str,
        screenshot: bytes,
        params: dict,
        model_config: dict | None = None,
    ) -> VisionResult:
        match vision_type:
            case "template_match":
                from cv.template_matcher import TemplateMatchCV
                return await TemplateMatchCV().match(screenshot, params)
            case "ocr":
                from cv.ocr_engine import OCREngine
                return await OCREngine().recognize(screenshot, params)
            case "ai_vision":
                from cv.ai_vision import AIVisionEngine
                return await AIVisionEngine().analyze(screenshot, params, model_config)
            case "color_detect":
                from cv.color_detector import ColorDetector
                return await ColorDetector().detect(screenshot, params)
            case _:
                raise ValueError(f"Unknown vision_type: {vision_type}")
