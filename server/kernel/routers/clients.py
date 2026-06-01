import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import Client, ProjectClient, get_session
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
