import json
import re

import httpx

from engine.base_handler import BaseNodeHandler, NodeResult
from engine.node_registry import NodeRegistry


def _interpolate(text: str, variables: dict) -> str:
    """Replace {{key}} placeholders with plain string values (for headers/URL)."""
    def replacer(match: re.Match) -> str:
        key = match.group(1).strip()
        val = variables.get(key)
        if val is None:
            return match.group(0)
        return str(val)
    return re.sub(r'\{\{([^}]+)\}\}', replacer, text)


def _json_interpolate(text: str, variables: dict) -> str:
    """Replace {{key}} placeholders with JSON-encoded values (strings get quoted automatically).
    Missing variables become JSON null rather than leaving invalid placeholder text."""
    def replacer(match: re.Match) -> str:
        key = match.group(1).strip()
        if key not in variables:
            return 'null'
        return json.dumps(variables[key], ensure_ascii=False)
    return re.sub(r'\{\{([^}]+)\}\}', replacer, text)


@NodeRegistry.register("http")
class HttpNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        data = self.ctx.node.data
        params = data.get("params", {})
        method = params.get("method", "GET").upper()
        timeout = params.get("timeout", 30)

        url = _interpolate(params.get("url", ""), self.ctx.variables)
        if not url:
            return NodeResult(success=False, error="HTTP node: URL is required")

        # Interpolate header values
        raw_headers = params.get("headers", {})
        headers = {k: _interpolate(str(v), self.ctx.variables) for k, v in raw_headers.items()}

        # bodyText is a JSON string (may contain {{}} placeholders)
        body_text = params.get("bodyText", "").strip()
        content: bytes | None = None
        if body_text:
            body_text = _json_interpolate(body_text, self.ctx.variables)
            try:
                json.loads(body_text)  # validate JSON after interpolation
            except json.JSONDecodeError as e:
                return NodeResult(success=False, error=f"HTTP node: invalid JSON body after interpolation: {e}")
            if "Content-Type" not in headers and "content-type" not in headers:
                headers["Content-Type"] = "application/json"
            content = body_text.encode()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    content=content,
                    timeout=timeout,
                )
            result = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "text": response.text[:4096],
            }
            try:
                result["json"] = response.json()
            except Exception:
                pass

            return NodeResult(success=response.is_success, output=result)
        except Exception as e:
            return NodeResult(success=False, error=str(e))
