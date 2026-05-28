import json

import httpx

from engine.base_handler import BaseNodeHandler, NodeResult
from engine.node_registry import NodeRegistry


@NodeRegistry.register("http")
class HttpNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        data = self.ctx.node.data
        params = data.get("params", {})
        method = params.get("method", "GET").upper()
        url = params.get("url", "")
        headers = params.get("headers", {})
        body = params.get("body")
        timeout = params.get("timeout", 30)

        if not url:
            return NodeResult(success=False, error="HTTP node: URL is required")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    content=json.dumps(body).encode() if body else None,
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

            self.ctx.variables["last_http_response"] = result
            return NodeResult(success=response.is_success, output=result)
        except Exception as e:
            return NodeResult(success=False, error=str(e))
