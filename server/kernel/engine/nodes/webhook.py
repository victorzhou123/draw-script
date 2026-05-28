import json

import httpx

from engine.base_handler import BaseNodeHandler, NodeResult
from engine.node_registry import NodeRegistry


@NodeRegistry.register("webhook")
class WebhookNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        data = self.ctx.node.data
        params = data.get("params", {})
        webhook_name = params.get("name")
        extra_payload = params.get("payload", {})

        if not webhook_name:
            return NodeResult(success=False, error="Webhook node: name is required")

        async with self.ctx.session_factory() as db:
            from database import Webhook
            from sqlalchemy import select
            result = await db.execute(
                select(Webhook).where(Webhook.name == webhook_name, Webhook.enabled == True)
            )
            wh = result.scalar_one_or_none()

        if not wh:
            return NodeResult(success=False, error=f"Webhook '{webhook_name}' not found or disabled")

        payload = {
            "execution_id": self.ctx.execution_id,
            "node_id": self.ctx.node.id,
            **extra_payload,
        }

        try:
            headers = {"Content-Type": "application/json"}
            if wh.secret:
                import hashlib
                import hmac
                sig = hmac.new(wh.secret.encode(), json.dumps(payload).encode(), hashlib.sha256).hexdigest()
                headers["X-Signature"] = f"sha256={sig}"

            async with httpx.AsyncClient() as client:
                resp = await client.post(wh.url, json=payload, headers=headers, timeout=10)
            return NodeResult(success=resp.is_success, output={"status_code": resp.status_code})
        except Exception as e:
            return NodeResult(success=False, error=str(e))
