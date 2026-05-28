import asyncio
import hashlib
import hmac
import json
import logging

import httpx

logger = logging.getLogger(__name__)


class WebhookDispatcher:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    async def dispatch(self, event: str, payload: dict) -> None:
        asyncio.create_task(self._send_all(event, payload))

    async def _send_all(self, event: str, payload: dict) -> None:
        from database import Webhook
        from sqlalchemy import select

        async with self.session_factory() as db:
            result = await db.execute(select(Webhook).where(Webhook.enabled == True))
            webhooks = result.scalars().all()

        for wh in webhooks:
            events = json.loads(wh.events or "[]")
            if event in events or "*" in events:
                asyncio.create_task(self._post(wh.url, wh.secret, event, payload))

    async def _post(self, url: str, secret: str, event: str, payload: dict) -> None:
        body = {"event": event, **payload}
        headers = {"Content-Type": "application/json", "X-Event": event}
        if secret:
            sig = hmac.new(secret.encode(), json.dumps(body).encode(), hashlib.sha256).hexdigest()
            headers["X-Signature"] = f"sha256={sig}"
        try:
            async with httpx.AsyncClient() as client:
                await client.post(url, json=body, headers=headers, timeout=10)
        except Exception as e:
            logger.warning(f"Webhook POST to {url} failed: {e}")
