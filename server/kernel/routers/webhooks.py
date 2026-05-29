import json
import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import Execution, Script, Webhook, get_session
from schemas import WebhookCreate, WebhookResponse, WebhookUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_engine_ref = None


def set_engine(engine):
    global _engine_ref
    _engine_ref = engine


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
async def receive_webhook(
    name: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
):
    """Inbound webhook endpoint — triggers a script execution when called."""
    result = await db.execute(select(Webhook).where(Webhook.name == name, Webhook.enabled == True))
    wh = result.scalar_one_or_none()
    if not wh:
        raise HTTPException(404, f"No active webhook named '{name}'")

    params = {}
    if request.headers.get("content-type", "").startswith("application/json"):
        try:
            params = await request.json()
        except Exception:
            params = {}

    logger.info(f"Received inbound webhook '{name}': {params}")

    if not wh.script_id or not wh.client_id:
        return {"received": True, "name": name, "triggered": False, "reason": "no script_id/client_id configured"}

    from ws_manager import client_ws_manager
    if not client_ws_manager.is_connected(wh.client_id):
        raise HTTPException(400, f"Client {wh.client_id} is not connected")

    script = await db.get(Script, wh.script_id)
    if not script:
        raise HTTPException(404, f"Script {wh.script_id} not found")

    execution = Execution(
        script_id=wh.script_id,
        client_id=wh.client_id,
        status="running",
        started_at=datetime.utcnow(),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    if _engine_ref:
        background_tasks.add_task(
            _engine_ref.run_script,
            execution.id,
            wh.script_id,
            wh.client_id,
            json.loads(script.flow_json) if script.flow_json else {},
            script.project_id,
            params,
        )

    return {"received": True, "name": name, "triggered": True, "execution_id": execution.id}
