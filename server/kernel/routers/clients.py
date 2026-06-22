import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import Client, Execution, ProjectClient, get_session
from dependencies import get_engine
from schemas import ClientResponse
from ws_manager import client_ws_manager

router = APIRouter(prefix="/clients", tags=["clients"])


async def _build_client_response(clients, connected_ids: set, db: AsyncSession) -> list[dict]:
    pc_result = await db.execute(select(ProjectClient))
    pc_map: dict[str, list[str]] = {}
    for pc in pc_result.scalars().all():
        pc_map.setdefault(pc.client_id, []).append(pc.project_id)

    return [
        {
            "id": c.id,
            "name": c.name,
            "platform": c.platform,
            "last_seen": c.last_seen,
            "status": c.status if c.id in connected_ids else "disconnected",
            "project_ids": pc_map.get(c.id, []),
            "gpu_enabled": bool(c.gpu_enabled),
        }
        for c in clients
    ]


@router.get("", response_model=list[ClientResponse])
async def list_clients(db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Client).order_by(Client.last_seen.desc()))
    clients = result.scalars().all()
    connected_ids = set(client_ws_manager.get_connected_ids())
    return await _build_client_response(clients, connected_ids, db)


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(client_id: str, db: AsyncSession = Depends(get_session)):
    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(404, "Client not found")
    connected_ids = set(client_ws_manager.get_connected_ids())
    rows = await _build_client_response([client], connected_ids, db)
    return rows[0]


@router.post("/{client_id}/stop")
async def stop_client_execution(client_id: str, request: Request, db: AsyncSession = Depends(get_session)):
    """Stop the currently running execution on a client (by client_id, no execution_id needed)."""
    result = await db.execute(
        select(Execution)
        .where(Execution.client_id == client_id, Execution.status == "running")
        .order_by(Execution.started_at.desc())
        .limit(1)
    )
    execution = result.scalar_one_or_none()
    if not execution:
        return {"ok": True, "stopped": False, "reason": "no running execution"}
    engine = get_engine(request)
    if engine:
        await engine.stop_execution(execution.id)
    return {"ok": True, "stopped": True, "execution_id": execution.id}


@router.post("/{client_id}/screenshot")
async def capture_client_screenshot(client_id: str):
    """Request a screenshot from a connected client and return it as base64."""
    if not client_ws_manager.is_connected(client_id):
        raise HTTPException(400, f"Client {client_id} is not connected")

    request_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    future: asyncio.Future = loop.create_future()
    client_ws_manager.pending_requests[request_id] = future

    sent = await client_ws_manager.send_to_client(client_id, {
        "type": "capture_screenshot",
        "request_id": request_id,
    })
    if not sent:
        client_ws_manager.pending_requests.pop(request_id, None)
        raise HTTPException(500, "Failed to send screenshot request to client")

    try:
        result = await asyncio.wait_for(future, timeout=settings.node_timeout)
        if not result.get("success"):
            raise HTTPException(500, result.get("error") or "Screenshot failed")
        return {"data": result["screenshot"]}
    except asyncio.TimeoutError:
        client_ws_manager.pending_requests.pop(request_id, None)
        raise HTTPException(408, "Screenshot request timed out")


@router.get("/{client_id}/windows")
async def get_client_windows(client_id: str):
    """Request the list of open windows from a connected client."""
    if not client_ws_manager.is_connected(client_id):
        raise HTTPException(400, f"Client {client_id} is not connected")

    request_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    future: asyncio.Future = loop.create_future()
    client_ws_manager.pending_requests[request_id] = future

    sent = await client_ws_manager.send_to_client(client_id, {
        "type": "get_window_list",
        "request_id": request_id,
    })
    if not sent:
        client_ws_manager.pending_requests.pop(request_id, None)
        raise HTTPException(500, "Failed to send window list request to client")

    try:
        result = await asyncio.wait_for(future, timeout=10.0)
        return {"windows": result.get("windows", [])}
    except asyncio.TimeoutError:
        client_ws_manager.pending_requests.pop(request_id, None)
        raise HTTPException(408, "Window list request timed out")


class CaptureTemplateRegionRequest(BaseModel):
    window_title: str
    window_process: str
    window_w: int
    window_h: int


@router.post("/{client_id}/capture_template_region")
async def capture_template_region(client_id: str, body: CaptureTemplateRegionRequest):
    """Ask client to let user draw a region and return it as a base64 PNG."""
    if not client_ws_manager.is_connected(client_id):
        raise HTTPException(400, f"Client {client_id} is not connected")

    request_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    future: asyncio.Future = loop.create_future()
    client_ws_manager.pending_requests[request_id] = future

    sent = await client_ws_manager.send_to_client(client_id, {
        "type":           "capture_template_region",
        "request_id":     request_id,
        "window_title":   body.window_title,
        "window_process": body.window_process,
        "window_w":       body.window_w,
        "window_h":       body.window_h,
    })
    if not sent:
        client_ws_manager.pending_requests.pop(request_id, None)
        raise HTTPException(500, "Failed to send capture request to client")

    try:
        result = await asyncio.wait_for(future, timeout=120.0)
        if not result.get("success"):
            raise HTTPException(400, result.get("error") or "Capture failed")
        return {
            "image_b64": result["image_b64"],
            "window_w":  result["window_w"],
            "window_h":  result["window_h"],
        }
    except asyncio.TimeoutError:
        client_ws_manager.pending_requests.pop(request_id, None)
        raise HTTPException(408, "Template region capture timed out")


class GpuUpdateRequest(BaseModel):
    gpu_enabled: bool


@router.patch("/{client_id}/gpu")
async def update_client_gpu(client_id: str, body: GpuUpdateRequest, db: AsyncSession = Depends(get_session)):
    """Toggle GPU acceleration for a client's template matching."""
    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(404, "Client not found")
    client.gpu_enabled = body.gpu_enabled
    await db.commit()
    return {"ok": True, "gpu_enabled": client.gpu_enabled}
