import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import Webhook, get_session
from schemas import WebhookCreate, WebhookResponse, WebhookUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("", response_model=list[WebhookResponse])
async def list_webhooks(db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Webhook))
    return result.scalars().all()


@router.post("", response_model=WebhookResponse)
async def create_webhook(body: WebhookCreate, db: AsyncSession = Depends(get_session)):
    existing = await db.execute(select(Webhook).where(Webhook.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(400, f"Webhook with name '{body.name}' already exists")
    wh = Webhook(
        name=body.name,
        url=body.url,
        events=json.dumps(body.events),
        secret=body.secret,
        enabled=body.enabled,
    )
    db.add(wh)
    await db.commit()
    await db.refresh(wh)
    return wh


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(webhook_id: str, db: AsyncSession = Depends(get_session)):
    wh = await db.get(Webhook, webhook_id)
    if not wh:
        raise HTTPException(404, "Webhook not found")
    return wh


@router.put("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(webhook_id: str, body: WebhookUpdate, db: AsyncSession = Depends(get_session)):
    wh = await db.get(Webhook, webhook_id)
    if not wh:
        raise HTTPException(404, "Webhook not found")
    data = body.model_dump(exclude_none=True)
    if "events" in data:
        data["events"] = json.dumps(data["events"])
    for field, value in data.items():
        setattr(wh, field, value)
    await db.commit()
    await db.refresh(wh)
    return wh


@router.delete("/{webhook_id}")
async def delete_webhook(webhook_id: str, db: AsyncSession = Depends(get_session)):
    wh = await db.get(Webhook, webhook_id)
    if not wh:
        raise HTTPException(404, "Webhook not found")
    await db.delete(wh)
    await db.commit()
    return {"ok": True}


@router.post("/receive/{name}")
async def receive_webhook(name: str, request: Request, db: AsyncSession = Depends(get_session)):
    """Inbound webhook endpoint — triggers a script execution when called."""
    result = await db.execute(select(Webhook).where(Webhook.name == name, Webhook.enabled == True))
    wh = result.scalar_one_or_none()
    if not wh:
        raise HTTPException(404, f"No active webhook named '{name}'")

    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    logger.info(f"Received inbound webhook '{name}': {body}")
    return {"received": True, "name": name}
