import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal, Client
from ws_manager import client_ws_manager, ui_ws_manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


async def _upsert_client(client_id: str, name: str, platform: str) -> None:
    async with AsyncSessionLocal() as db:
        client = await db.get(Client, client_id)
        if client:
            client.name = name
            client.platform = platform
            client.status = "idle"
            client.last_seen = datetime.now(timezone.utc)
        else:
            client = Client(id=client_id, name=name, platform=platform, status="idle")
            db.add(client)
        await db.commit()


async def _update_client_status(client_id: str, status: str) -> None:
    async with AsyncSessionLocal() as db:
        client = await db.get(Client, client_id)
        if client:
            client.status = status
            client.last_seen = datetime.now(timezone.utc)
            await db.commit()


async def _handle_client_message(client_id: str, msg: dict) -> None:
    msg_type = msg.get("type")

    if msg_type == "register":
        name = msg.get("name", client_id)
        platform = msg.get("platform", "unknown")
        await _upsert_client(client_id, name, platform)
        await ui_ws_manager.broadcast_event("client_connected", {
            "client_id": client_id,
            "name": name,
            "platform": platform,
        })
        logger.info(f"Client registered: {client_id} ({name} / {platform})")

    elif msg_type == "heartbeat":
        client_ws_manager.update_heartbeat(client_id)
        await _update_client_status(client_id, msg.get("status", "idle"))
        await ui_ws_manager.broadcast_event("client_heartbeat", {
            "client_id": client_id,
            "status": msg.get("status", "idle"),
        })

    elif msg_type == "screenshot_response":
        request_id = msg.get("request_id")
        if request_id:
            client_ws_manager.resolve_pending(request_id, {
                "success": msg.get("success", True),
                "screenshot": msg.get("screenshot"),
                "error": msg.get("error"),
            })

    elif msg_type == "node_result":
        node_id = msg.get("node_id")
        request_id = msg.get("request_id", node_id)
        if request_id:
            client_ws_manager.resolve_pending(request_id, {
                "success": msg.get("success", True),
                "output": msg.get("output", {}),
                "error": msg.get("error"),
            })

    elif msg_type == "markers_captured":
        project_id = msg.get("project_id")
        markers = msg.get("markers", [])
        window = msg.get("window")  # {title, process, x, y, w, h} or None

        if project_id and markers:
            from database import Marker, MarkerCapture
            from sqlalchemy import select
            async with AsyncSessionLocal() as db:
                for m in markers:
                    name = m.get("name")
                    x, y = m.get("x"), m.get("y")
                    if not name or x is None or y is None:
                        continue
                    # Look up marker definition
                    result = await db.execute(
                        select(Marker).where(Marker.project_id == project_id, Marker.name == name)
                    )
                    marker_row = result.scalar_one_or_none()
                    if not marker_row:
                        continue
                    # Upsert: one capture row per (marker_id, client_id)
                    cap_result = await db.execute(
                        select(MarkerCapture).where(
                            MarkerCapture.marker_id == marker_row.id,
                            MarkerCapture.client_id == client_id,
                        )
                    )
                    capture = cap_result.scalar_one_or_none()
                    if capture:
                        capture.x = x
                        capture.y = y
                        capture.w = m.get("w")
                        capture.h = m.get("h")
                        capture.captured_at = datetime.now(timezone.utc)
                    else:
                        capture = MarkerCapture(
                            marker_id=marker_row.id, client_id=client_id,
                            x=x, y=y, w=m.get("w"), h=m.get("h"),
                        )
                        db.add(capture)
                    if window:
                        capture.window_title = window.get("title")
                        capture.window_process = window.get("process")
                        capture.window_x = window.get("x")
                        capture.window_y = window.get("y")
                        capture.window_w = window.get("w")
                        capture.window_h = window.get("h")
                await db.commit()
            logger.info(f"Saved {len(markers)} captures for client {client_id} / project {project_id}")

        count = len(markers)
        await ui_ws_manager.broadcast_event("markers_captured", {
            "client_id": client_id,
            "project_id": project_id,
            "count": count,
        })

    elif msg_type == "window_resized":
        project_id     = msg.get("project_id")
        window_title   = msg.get("window_title")
        new_w          = msg.get("new_w")
        new_h          = msg.get("new_h")
        new_x          = msg.get("new_x")
        new_y          = msg.get("new_y")

        if project_id and window_title and new_w and new_h:
            from database import Marker, MarkerCapture
            from sqlalchemy import select
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(MarkerCapture)
                    .join(Marker, MarkerCapture.marker_id == Marker.id)
                    .where(
                        Marker.project_id == project_id,
                        MarkerCapture.client_id == client_id,
                        MarkerCapture.x.isnot(None),
                    )
                )
                captures = result.scalars().all()
                scaled = 0
                for cap in captures:
                    old_w = cap.window_w
                    old_h = cap.window_h
                    if not old_w or not old_h or old_w <= 0 or old_h <= 0:
                        continue
                    if cap.x is not None:
                        cap.x = round(cap.x * new_w / old_w)
                    if cap.y is not None:
                        cap.y = round(cap.y * new_h / old_h)
                    if cap.w is not None:
                        cap.w = round(cap.w * new_w / old_w)
                    if cap.h is not None:
                        cap.h = round(cap.h * new_h / old_h)
                    cap.window_w = new_w
                    cap.window_h = new_h
                    if new_x is not None:
                        cap.window_x = new_x
                    if new_y is not None:
                        cap.window_y = new_y
                    scaled += 1
                await db.commit()
            logger.info(
                f"window_resized: scaled {scaled} captures for client {client_id} "
                f"/ project {project_id} to {new_w}×{new_h}"
            )
            await ui_ws_manager.broadcast_event("window_resize_applied", {
                "client_id":  client_id,
                "project_id": project_id,
                "new_w":      new_w,
                "new_h":      new_h,
                "scaled":     scaled,
            })

    elif msg_type == "window_list_response":
        request_id = msg.get("request_id")
        if request_id:
            client_ws_manager.resolve_pending(request_id, {
                "windows": msg.get("windows", []),
            })

    elif msg_type == "template_region_response":
        request_id = msg.get("request_id")
        if request_id:
            client_ws_manager.resolve_pending(request_id, {
                "success":   msg.get("success", False),
                "image_b64": msg.get("image_b64"),
                "window_w":  msg.get("window_w"),
                "window_h":  msg.get("window_h"),
                "error":     msg.get("error"),
            })

    elif msg_type == "error":
        logger.warning(f"Client {client_id} error: {msg.get('message')}")

    else:
        logger.debug(f"Unknown message type from {client_id}: {msg_type}")


@router.websocket("/ws/client")
async def client_websocket(ws: WebSocket):
    await ws.accept()
    client_id = None
    try:
        raw = await ws.receive_text()
        first_msg = json.loads(raw)
        client_id = first_msg.get("client_id") or first_msg.get("data", {}).get("client_id")
        if not client_id:
            await ws.close(code=4000, reason="Missing client_id in first message")
            return

        await client_ws_manager.connect(client_id, ws)
        await _handle_client_message(client_id, first_msg)

        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            await _handle_client_message(client_id, msg)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception(f"Client WS error ({client_id}): {e}")
    finally:
        if client_id:
            await client_ws_manager.disconnect(client_id)
            await _update_client_status(client_id, "disconnected")
            await ui_ws_manager.broadcast_event("client_disconnected", {"client_id": client_id})
            logger.info(f"Client disconnected: {client_id}")


@router.websocket("/ws/ui")
async def ui_websocket(ws: WebSocket):
    await ws.accept()
    await ui_ws_manager.connect(ws)
    try:
        connected_ids = client_ws_manager.get_connected_ids()
        await ws.send_text(json.dumps({
            "type": "init",
            "connected_clients": connected_ids,
        }))
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"UI WS closed: {e}")
    finally:
        await ui_ws_manager.disconnect(ws)
