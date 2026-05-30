import base64
import json
import re

import httpx

from config import settings
from cv.vision_engine import VisionResult


class AIVisionEngine:
    async def analyze(self, screenshot: bytes, params: dict, model_config: dict | None = None) -> VisionResult:
        if model_config:
            api_key = model_config.get("api_key") or settings.ai_api_key
            base_url = model_config.get("base_url") or settings.ai_base_url
            model_name = model_config.get("model_name") or settings.ai_model
        else:
            api_key = settings.ai_api_key
            base_url = settings.ai_base_url
            model_name = settings.ai_model

        if not api_key:
            return VisionResult(found=False, raw={"error": "AI API key not configured"})

        prompt = params.get("prompt", "Describe what you see in this screenshot.")
        mode = params.get("mode", "describe")
        b64_img = base64.b64encode(screenshot).decode()

        if mode == "find":
            target = params.get("target", "")
            prompt = (
                f"Find '{target}' in this screenshot. "
                "If found, respond with JSON: {\"found\": true, \"x\": <center_x>, \"y\": <center_y>, \"description\": \"...\"} "
                "If not found: {\"found\": false}"
            )

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": model_name, "messages": messages},
                    timeout=60,
                )
            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            if mode == "find":
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    found = result.get("found", False)
                    return VisionResult(
                        found=found,
                        location={"x": result.get("x", 0), "y": result.get("y", 0)} if found else None,
                        text=result.get("description"),
                        raw=result,
                    )

            return VisionResult(found=True, text=content, raw={"response": content})
        except Exception as e:
            return VisionResult(found=False, raw={"error": str(e)})
