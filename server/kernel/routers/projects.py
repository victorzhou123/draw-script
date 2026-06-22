import logging
import os
import uuid
from datetime import datetime, timezone

import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import GlobalVariable, Marker, MarkerCapture, Project, ProjectClient, ProjectClientWindow, Script, Template, get_session
from schemas import (
    GlobalVariableResponse, GlobalVariableUpsert,
    MarkerCreate, MarkerResponse,
    ProjectCreate, ProjectResponse, ProjectUpdate,
    SendMarkersRequest, TemplateResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["projects"])


# ── Projects ──────────────────────────────────────────────────────────────────

@router.get("", response_model=list[ProjectResponse])
async def list_projects(db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Project).order_by(Project.updated_at.desc()))
    return result.scalars().all()


@router.post("", response_model=ProjectResponse)
async def create_project(body: ProjectCreate, db: AsyncSession = Depends(get_session)):
    project = Project(**body.model_dump())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, body: ProjectUpdate, db: AsyncSession = Depends(get_session)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(project, field, value)
    project.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}")
async def delete_project(project_id: str, db: AsyncSession = Depends(get_session)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    # Unlink scripts from this project
    result = await db.execute(select(Script).where(Script.project_id == project_id))
    for script in result.scalars().all():
        script.project_id = None
    await db.delete(project)
    await db.commit()
    return {"ok": True}


# ── Markers ───────────────────────────────────────────────────────────────────

@router.get("/{project_id}/markers", response_model=list[MarkerResponse])
async def list_markers(project_id: str, db: AsyncSession = Depends(get_session)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    result = await db.execute(
        select(Marker).where(Marker.project_id == project_id).order_by(Marker.created_at)
    )
    return result.scalars().all()


@router.post("/{project_id}/markers", response_model=MarkerResponse)
async def create_marker(project_id: str, body: MarkerCreate, db: AsyncSession = Depends(get_session)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if body.type not in ("point", "box"):
        raise HTTPException(400, "type must be 'point' or 'box'")
    marker = Marker(project_id=project_id, **body.model_dump())
    db.add(marker)
    await db.commit()
    await db.refresh(marker)
    return marker


@router.delete("/{project_id}/markers/{marker_id}")
async def delete_marker(project_id: str, marker_id: str, db: AsyncSession = Depends(get_session)):
    marker = await db.get(Marker, marker_id)
    if not marker or marker.project_id != project_id:
        raise HTTPException(404, "Marker not found")
    await db.delete(marker)
    await db.commit()
    return {"ok": True}


# ── Send markers to client ────────────────────────────────────────────────────

@router.post("/{project_id}/markers/send")
async def send_markers_to_client(
    project_id: str,
    body: SendMarkersRequest,
    db: AsyncSession = Depends(get_session),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    from ws_manager import client_ws_manager
    if not client_ws_manager.is_connected(body.client_id):
        logger.warning(f"send_markers: client {body.client_id} is not connected")
        raise HTTPException(400, f"Client {body.client_id} is not connected")

    result = await db.execute(
        select(Marker).where(Marker.project_id == project_id).order_by(Marker.created_at)
    )
    markers = result.scalars().all()

    if body.marker_names is not None:
        name_set = set(body.marker_names)
        markers = [m for m in markers if m.name in name_set]

    # Fetch existing captures for this client so the client can pre-fill them
    cap_result = await db.execute(
        select(MarkerCapture).where(
            MarkerCapture.marker_id.in_([m.id for m in markers]),
            MarkerCapture.client_id == body.client_id,
        )
    )
    captures: dict[str, MarkerCapture] = {c.marker_id: c for c in cap_result.scalars().all()}

    marker_list = []
    for m in markers:
        item: dict = {"name": m.name, "type": m.type}
        cap = captures.get(m.id)
        if cap and cap.x is not None:
            item["existing"] = {"x": cap.x, "y": cap.y, "w": cap.w, "h": cap.h}
        marker_list.append(item)

    logger.info(f"send_markers: sending {len(marker_list)} markers to client {body.client_id} for project {project_id}")
    sent = await client_ws_manager.send_to_client(body.client_id, {
        "type": "set_markers",
        "project_id": project_id,
        "project_name": project.name,
        "markers": marker_list,
    })
    if not sent:
        logger.warning(f"send_markers: WS send failed for client {body.client_id}")
        raise HTTPException(500, "Failed to send to client")

    logger.info(f"send_markers: OK — {len(markers)} markers sent to client {body.client_id}")
    return {"ok": True, "count": len(markers)}


# ── Marker captures ────────────────────────────────────────────────────────────

async def _query_marker_captures(project_id: str, client_id: str, db: AsyncSession):
    result = await db.execute(
        select(Marker, MarkerCapture)
        .outerjoin(
            MarkerCapture,
            (MarkerCapture.marker_id == Marker.id) & (MarkerCapture.client_id == client_id),
        )
        .where(Marker.project_id == project_id)
        .order_by(Marker.created_at)
    )
    return result.all()


@router.get("/{project_id}/markers/captures")
async def get_marker_captures(
    project_id: str,
    client_id: str,
    db: AsyncSession = Depends(get_session),
):
    """Return per-marker capture status for one client (for frontend status display)."""
    rows = await _query_marker_captures(project_id, client_id, db)
    return [
        {
            "id": marker.id,
            "name": marker.name,
            "type": marker.type,
            "captured": capture is not None and capture.x is not None,
        }
        for marker, capture in rows
    ]


@router.get("/{project_id}/markers/captures/data")
async def get_marker_capture_data(
    project_id: str,
    client_id: str,
    db: AsyncSession = Depends(get_session),
):
    """Return per-marker coordinates for one client (for annotation preview)."""
    rows = await _query_marker_captures(project_id, client_id, db)
    return [
        {
            "id": marker.id,
            "name": marker.name,
            "type": marker.type,
            "captured": capture is not None and capture.x is not None,
            "x": capture.x if capture else None,
            "y": capture.y if capture else None,
            "w": capture.w if capture else None,
            "h": capture.h if capture else None,
            "window_x": capture.window_x if capture else None,
            "window_y": capture.window_y if capture else None,
            "window_w": capture.window_w if capture else None,
            "window_h": capture.window_h if capture else None,
        }
        for marker, capture in rows
    ]


# ── Restore window ────────────────────────────────────────────────────────────

class RestoreWindowRequest(BaseModel):
    client_id: str


@router.post("/{project_id}/markers/restore-window")
async def restore_window(
    project_id: str,
    body: RestoreWindowRequest,
    db: AsyncSession = Depends(get_session),
):
    pcw = await db.get(ProjectClientWindow, (project_id, body.client_id))
    if not pcw:
        logger.warning(f"restore_window: no window info for client {body.client_id} in project {project_id}")
        raise HTTPException(400, "No window info recorded for this client")

    from ws_manager import client_ws_manager
    sent = await client_ws_manager.send_to_client(body.client_id, {
        "type": "restore_window",
        "title": pcw.window_title,
        "process": pcw.window_process or "",
        "x": pcw.window_x or 0,
        "y": pcw.window_y or 0,
        "w": pcw.window_w,
        "h": pcw.window_h,
    })
    if not sent:
        logger.warning(f"restore_window: client {body.client_id} is not connected")
        raise HTTPException(400, f"Client {body.client_id} is not connected")
    return {"ok": True}


# ── Marker windows (distinct windows with captures across project clients) ────

@router.get("/{project_id}/marker-windows")
async def list_marker_windows(project_id: str, db: AsyncSession = Depends(get_session)):
    """Return distinct window bindings (with capture counts) across all project clients."""
    pc_result = await db.execute(
        select(ProjectClient.client_id).where(ProjectClient.project_id == project_id)
    )
    project_client_ids = {row[0] for row in pc_result.all()}
    if not project_client_ids:
        return []

    pcw_result = await db.execute(
        select(ProjectClientWindow).where(
            ProjectClientWindow.project_id == project_id,
            ProjectClientWindow.client_id.in_(project_client_ids),
        )
    )
    pcws = pcw_result.scalars().all()

    # Group by (window_title, window_w, window_h)
    window_map: dict[tuple, list[str]] = {}
    for pcw in pcws:
        key = (pcw.window_title, pcw.window_w, pcw.window_h)
        window_map.setdefault(key, []).append(pcw.client_id)

    marker_result = await db.execute(select(Marker).where(Marker.project_id == project_id))
    marker_ids = [m.id for m in marker_result.scalars().all()]

    result = []
    for (title, w, h), client_ids in window_map.items():
        if not marker_ids:
            break
        cap_count_result = await db.execute(
            select(func.count()).select_from(MarkerCapture).where(
                MarkerCapture.marker_id.in_(marker_ids),
                MarkerCapture.client_id.in_(client_ids),
                MarkerCapture.x.isnot(None),
            )
        )
        if (cap_count_result.scalar() or 0) > 0:
            result.append({
                "window_title": title,
                "window_w": w,
                "window_h": h,
                "client_count": len(client_ids),
                "client_ids": client_ids,
            })

    return result


# ── Copy captures between clients ────────────────────────────────────────────

class CopyCapturesRequest(BaseModel):
    # Window-based source (preferred): identify source by window binding
    source_window_title: str | None = None
    source_window_w: int | None = None
    source_window_h: int | None = None
    # Legacy fallback: explicit source client
    source_client_id: str | None = None
    target_client_ids: list[str]
    mode: str = "overwrite"  # "overwrite" | "fill_missing"
    auto_scale: bool = True


@router.post("/{project_id}/markers/copy-captures")
async def copy_captures(
    project_id: str,
    body: CopyCapturesRequest,
    db: AsyncSession = Depends(get_session),
):
    if not body.target_client_ids:
        raise HTTPException(400, "No target clients specified")

    marker_result = await db.execute(
        select(Marker).where(Marker.project_id == project_id)
    )
    markers = marker_result.scalars().all()
    if not markers:
        raise HTTPException(400, "Project has no markers")
    marker_ids = [m.id for m in markers]

    # ── Resolve source client ──────────────────────────────────────────────
    if body.source_window_title and body.source_window_w and body.source_window_h:
        # Find all project clients bound to this window
        pcw_result = await db.execute(
            select(ProjectClientWindow).where(
                ProjectClientWindow.project_id == project_id,
                ProjectClientWindow.window_title == body.source_window_title,
                ProjectClientWindow.window_w == body.source_window_w,
                ProjectClientWindow.window_h == body.source_window_h,
            )
        )
        window_client_ids = [pcw.client_id for pcw in pcw_result.scalars().all()]
        if not window_client_ids:
            raise HTTPException(400, "No clients found for the specified window")

        # Pick the client with most captures
        best_client_id, best_count = None, -1
        for cid in window_client_ids:
            cnt_result = await db.execute(
                select(func.count()).select_from(MarkerCapture).where(
                    MarkerCapture.marker_id.in_(marker_ids),
                    MarkerCapture.client_id == cid,
                    MarkerCapture.x.isnot(None),
                )
            )
            cnt = cnt_result.scalar() or 0
            if cnt > best_count:
                best_count, best_client_id = cnt, cid

        if not best_client_id or best_count == 0:
            raise HTTPException(400, "No captures found for the specified window")

        source_client_id = best_client_id
        source_w: int | None = body.source_window_w
        source_h: int | None = body.source_window_h
    elif body.source_client_id:
        source_client_id = body.source_client_id
        # Look up source window for auto-scaling
        if body.auto_scale:
            src_pcw = await db.get(ProjectClientWindow, (project_id, source_client_id))
            source_w = src_pcw.window_w if src_pcw else None
            source_h = src_pcw.window_h if src_pcw else None
        else:
            source_w = source_h = None
    else:
        raise HTTPException(400, "Provide source_window_title/w/h or source_client_id")

    # ── Load source captures ───────────────────────────────────────────────
    src_result = await db.execute(
        select(MarkerCapture).where(
            MarkerCapture.marker_id.in_(marker_ids),
            MarkerCapture.client_id == source_client_id,
            MarkerCapture.x.isnot(None),
        )
    )
    source_captures = src_result.scalars().all()
    if not source_captures:
        raise HTTPException(400, "Source has no captures for this project")

    # ── Copy (with optional proportional scaling) ──────────────────────────
    copied = 0
    for target_id in body.target_client_ids:
        if target_id == source_client_id:
            continue

        # Compute scale factors for this target
        sw, sh = 1.0, 1.0
        if body.auto_scale and source_w and source_h:
            target_pcw = await db.get(ProjectClientWindow, (project_id, target_id))
            if target_pcw and target_pcw.window_w and target_pcw.window_h:
                sw = target_pcw.window_w / source_w
                sh = target_pcw.window_h / source_h

        for src in source_captures:
            existing_result = await db.execute(
                select(MarkerCapture).where(
                    MarkerCapture.marker_id == src.marker_id,
                    MarkerCapture.client_id == target_id,
                )
            )
            existing = existing_result.scalar_one_or_none()

            if body.mode == "fill_missing" and existing and existing.x is not None:
                continue

            scaled_x = round(src.x * sw) if src.x is not None else None
            scaled_y = round(src.y * sh) if src.y is not None else None
            scaled_w = round(src.w * sw) if src.w is not None else None
            scaled_h = round(src.h * sh) if src.h is not None else None

            if existing:
                existing.x = scaled_x
                existing.y = scaled_y
                existing.w = scaled_w
                existing.h = scaled_h
                existing.captured_at = datetime.now(timezone.utc)
            else:
                db.add(MarkerCapture(
                    marker_id=src.marker_id,
                    client_id=target_id,
                    x=scaled_x, y=scaled_y, w=scaled_w, h=scaled_h,
                ))
            copied += 1

    await db.commit()
    logger.info(
        f"copy_captures: {copied} captures from client {source_client_id} "
        f"to {body.target_client_ids} in project {project_id} (mode={body.mode})"
    )
    return {"ok": True, "copied": copied}


# ── Resize window interactive ─────────────────────────────────────────────────

class ResizeWindowInteractiveRequest(BaseModel):
    client_id: str


@router.post("/{project_id}/markers/resize-window-interactive")
async def resize_window_interactive(
    project_id: str,
    body: ResizeWindowInteractiveRequest,
    db: AsyncSession = Depends(get_session),
):
    pcw = await db.get(ProjectClientWindow, (project_id, body.client_id))
    if not pcw:
        raise HTTPException(400, "No window info recorded for this client — please annotate markers first")

    from ws_manager import client_ws_manager
    sent = await client_ws_manager.send_to_client(body.client_id, {
        "type":           "resize_window_interactive",
        "project_id":     project_id,
        "window_title":   pcw.window_title,
        "window_process": pcw.window_process or "",
        "window_w":       pcw.window_w,
        "window_h":       pcw.window_h,
    })
    if not sent:
        raise HTTPException(400, f"Client {body.client_id} is not connected")
    return {"ok": True}


@router.get("/{project_id}/window-binding")
async def get_window_binding(
    project_id: str,
    client_id: str,
    db: AsyncSession = Depends(get_session),
):
    pcw = await db.get(ProjectClientWindow, (project_id, client_id))
    if not pcw:
        raise HTTPException(404, "No window binding found")
    return {
        "window_title": pcw.window_title,
        "window_process": pcw.window_process,
        "window_x": pcw.window_x,
        "window_y": pcw.window_y,
        "window_w": pcw.window_w,
        "window_h": pcw.window_h,
        "updated_at": pcw.updated_at.isoformat() if pcw.updated_at else None,
    }


# ── Templates ─────────────────────────────────────────────────────────────────

@router.get("/{project_id}/templates", response_model=list[TemplateResponse])
async def list_templates(project_id: str, db: AsyncSession = Depends(get_session)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    result = await db.execute(
        select(Template).where(Template.project_id == project_id).order_by(Template.created_at)
    )
    return result.scalars().all()


@router.post("/{project_id}/templates", response_model=TemplateResponse)
async def upload_template(
    project_id: str,
    name: str = Form(...),
    file: UploadFile = File(...),
    source_w: int | None = Form(None),
    source_h: int | None = Form(None),
    db: AsyncSession = Depends(get_session),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".bmp", ".webp"):
        raise HTTPException(400, "Only image files are accepted (png/jpg/jpeg/bmp/webp)")

    template_id = str(uuid.uuid4())
    filename = f"{template_id}{ext}"
    dest = os.path.join(settings.templates_dir, filename)
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)

    template = Template(id=template_id, project_id=project_id, name=name, filename=filename,
                        source_w=source_w, source_h=source_h)
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


class TemplateFromCaptureRequest(BaseModel):
    name: str
    image_b64: str
    source_w: int | None = None
    source_h: int | None = None


@router.post("/{project_id}/templates/from_capture", response_model=TemplateResponse)
async def create_template_from_capture(
    project_id: str,
    body: TemplateFromCaptureRequest,
    db: AsyncSession = Depends(get_session),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    import base64 as _b64
    try:
        image_bytes = _b64.b64decode(body.image_b64)
    except Exception:
        raise HTTPException(400, "Invalid base64 image data")

    template_id = str(uuid.uuid4())
    filename = f"{template_id}.png"
    dest = os.path.join(settings.templates_dir, filename)
    with open(dest, "wb") as f:
        f.write(image_bytes)

    template = Template(id=template_id, project_id=project_id, name=body.name,
                        filename=filename, source_w=body.source_w, source_h=body.source_h)
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


class CaptureTemplateAsyncRequest(BaseModel):
    client_id: str
    name: str


async def _await_and_save_template(
    future: asyncio.Future,
    project_id: str,
    name: str,
    request_id: str,
) -> None:
    from database import AsyncSessionLocal, Template
    from ws_manager import client_ws_manager, ui_ws_manager
    try:
        result = await asyncio.wait_for(future, timeout=300.0)
        if not result.get("success"):
            await ui_ws_manager.broadcast_event("template_capture_done", {
                "project_id": project_id,
                "success": False,
                "error": result.get("error") or "截图失败",
            })
            return

        import base64 as _b64
        image_bytes = _b64.b64decode(result["image_b64"])
        window_w = result.get("window_w")
        window_h = result.get("window_h")

        template_id = str(uuid.uuid4())
        filename = f"{template_id}.png"
        dest = os.path.join(settings.templates_dir, filename)
        with open(dest, "wb") as f:
            f.write(image_bytes)

        async with AsyncSessionLocal() as db:
            tpl = Template(
                id=template_id, project_id=project_id, name=name,
                filename=filename, source_w=window_w, source_h=window_h,
            )
            db.add(tpl)
            await db.commit()

        await ui_ws_manager.broadcast_event("template_capture_done", {
            "project_id": project_id,
            "success": True,
            "template_id": template_id,
            "name": name,
        })
    except asyncio.TimeoutError:
        client_ws_manager.pending_requests.pop(request_id, None)
        await ui_ws_manager.broadcast_event("template_capture_done", {
            "project_id": project_id,
            "success": False,
            "error": "截图超时",
        })
    except Exception as e:
        await ui_ws_manager.broadcast_event("template_capture_done", {
            "project_id": project_id,
            "success": False,
            "error": str(e),
        })


@router.post("/{project_id}/templates/capture_async", status_code=202)
async def capture_template_async(
    project_id: str,
    body: CaptureTemplateAsyncRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
):
    from ws_manager import client_ws_manager
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if not client_ws_manager.is_connected(body.client_id):
        raise HTTPException(400, "Client is not connected")

    request_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    future: asyncio.Future = loop.create_future()
    client_ws_manager.pending_requests[request_id] = future

    sent = await client_ws_manager.send_to_client(body.client_id, {
        "type": "capture_template_region",
        "request_id": request_id,
    })
    if not sent:
        client_ws_manager.pending_requests.pop(request_id, None)
        raise HTTPException(500, "Failed to send capture request to client")

    background_tasks.add_task(_await_and_save_template, future, project_id, body.name, request_id)
    return {"ok": True}


async def _await_and_update_template(
    future: asyncio.Future,
    project_id: str,
    template_id: str,
    name: str,
    request_id: str,
) -> None:
    from database import AsyncSessionLocal, Template
    from ws_manager import client_ws_manager, ui_ws_manager
    try:
        result = await asyncio.wait_for(future, timeout=300.0)
        if not result.get("success"):
            await ui_ws_manager.broadcast_event("template_capture_done", {
                "project_id": project_id,
                "success": False,
                "error": result.get("error") or "截图失败",
            })
            return

        import base64 as _b64
        image_bytes = _b64.b64decode(result["image_b64"])
        window_w = result.get("window_w")
        window_h = result.get("window_h")

        async with AsyncSessionLocal() as db:
            tpl = await db.get(Template, template_id)
            if not tpl:
                await ui_ws_manager.broadcast_event("template_capture_done", {
                    "project_id": project_id,
                    "success": False,
                    "error": "Template not found",
                })
                return
            old_path = os.path.join(settings.templates_dir, tpl.filename)
            if os.path.isfile(old_path):
                os.remove(old_path)
            filename = f"{template_id}.png"
            dest = os.path.join(settings.templates_dir, filename)
            with open(dest, "wb") as f:
                f.write(image_bytes)
            tpl.filename = filename
            tpl.name = name
            tpl.source_w = window_w
            tpl.source_h = window_h
            await db.commit()

        await ui_ws_manager.broadcast_event("template_capture_done", {
            "project_id": project_id,
            "success": True,
            "template_id": template_id,
            "name": name,
            "updated": True,
        })
    except asyncio.TimeoutError:
        client_ws_manager.pending_requests.pop(request_id, None)
        await ui_ws_manager.broadcast_event("template_capture_done", {
            "project_id": project_id,
            "success": False,
            "error": "截图超时",
        })
    except Exception as e:
        await ui_ws_manager.broadcast_event("template_capture_done", {
            "project_id": project_id,
            "success": False,
            "error": str(e),
        })


class RecaptureTemplateAsyncRequest(BaseModel):
    client_id: str
    name: str


@router.post("/{project_id}/templates/{template_id}/recapture_async", status_code=202)
async def recapture_template_async(
    project_id: str,
    template_id: str,
    body: RecaptureTemplateAsyncRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
):
    from ws_manager import client_ws_manager
    template = await db.get(Template, template_id)
    if not template or template.project_id != project_id:
        raise HTTPException(404, "Template not found")
    if not client_ws_manager.is_connected(body.client_id):
        raise HTTPException(400, "Client is not connected")

    request_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    future: asyncio.Future = loop.create_future()
    client_ws_manager.pending_requests[request_id] = future

    sent = await client_ws_manager.send_to_client(body.client_id, {
        "type": "capture_template_region",
        "request_id": request_id,
    })
    if not sent:
        client_ws_manager.pending_requests.pop(request_id, None)
        raise HTTPException(500, "Failed to send capture request to client")

    background_tasks.add_task(
        _await_and_update_template, future, project_id, template_id, body.name, request_id
    )
    return {"ok": True}


@router.patch("/{project_id}/templates/{template_id}", response_model=TemplateResponse)
async def rename_template(
    project_id: str,
    template_id: str,
    name: str = Form(...),
    db: AsyncSession = Depends(get_session),
):
    template = await db.get(Template, template_id)
    if not template or template.project_id != project_id:
        raise HTTPException(404, "Template not found")
    template.name = name
    await db.commit()
    await db.refresh(template)
    return template


@router.delete("/{project_id}/templates/{template_id}")
async def delete_template(project_id: str, template_id: str, db: AsyncSession = Depends(get_session)):
    template = await db.get(Template, template_id)
    if not template or template.project_id != project_id:
        raise HTTPException(404, "Template not found")
    path = os.path.join(settings.templates_dir, template.filename)
    if os.path.isfile(path):
        os.remove(path)
    await db.delete(template)
    await db.commit()
    return {"ok": True}


@router.put("/{project_id}/templates/{template_id}/image", response_model=TemplateResponse)
async def update_template_image(
    project_id: str,
    template_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
):
    template = await db.get(Template, template_id)
    if not template or template.project_id != project_id:
        raise HTTPException(404, "Template not found")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".bmp", ".webp"):
        raise HTTPException(400, "Only image files are accepted (png/jpg/jpeg/bmp/webp)")

    old_path = os.path.join(settings.templates_dir, template.filename)
    if os.path.isfile(old_path):
        os.remove(old_path)

    filename = f"{template_id}{ext}"
    dest = os.path.join(settings.templates_dir, filename)
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)

    template.filename = filename
    await db.commit()
    await db.refresh(template)
    return template


@router.get("/{project_id}/templates/{template_id}/image")
async def get_template_image(project_id: str, template_id: str, db: AsyncSession = Depends(get_session)):
    template = await db.get(Template, template_id)
    if not template or template.project_id != project_id:
        raise HTTPException(404, "Template not found")
    path = os.path.join(settings.templates_dir, template.filename)
    if not os.path.isfile(path):
        raise HTTPException(404, "Template file missing")
    return FileResponse(path)


# ── Project ↔ Client (many-to-many) ──────────────────────────────────────────

@router.get("/{project_id}/clients")
async def list_project_clients(project_id: str, db: AsyncSession = Depends(get_session)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    result = await db.execute(
        select(ProjectClient).where(ProjectClient.project_id == project_id)
    )
    return [pc.client_id for pc in result.scalars().all()]


@router.post("/{project_id}/clients/{client_id}")
async def add_client_to_project(project_id: str, client_id: str, db: AsyncSession = Depends(get_session)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    existing = await db.get(ProjectClient, (project_id, client_id))
    if not existing:
        db.add(ProjectClient(project_id=project_id, client_id=client_id))
        await db.commit()
    return {"ok": True}


@router.delete("/{project_id}/clients/{client_id}")
async def remove_client_from_project(project_id: str, client_id: str, db: AsyncSession = Depends(get_session)):
    pc = await db.get(ProjectClient, (project_id, client_id))
    if pc:
        await db.delete(pc)
        await db.commit()
    return {"ok": True}


# ── Global Variables ──────────────────────────────────────────────────────────

@router.get("/{project_id}/global-vars", response_model=list[GlobalVariableResponse])
async def list_global_vars(project_id: str, db: AsyncSession = Depends(get_session)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    result = await db.execute(
        select(GlobalVariable)
        .where(GlobalVariable.project_id == project_id)
        .order_by(GlobalVariable.name)
    )
    return result.scalars().all()


@router.put("/{project_id}/global-vars/{var_name}", response_model=GlobalVariableResponse)
async def upsert_global_var(project_id: str, var_name: str, body: GlobalVariableUpsert, db: AsyncSession = Depends(get_session)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    result = await db.execute(
        select(GlobalVariable).where(
            GlobalVariable.project_id == project_id,
            GlobalVariable.name == var_name,
        )
    )
    import json as _json
    row = result.scalar_one_or_none()
    encoded = _json.dumps(body.value, ensure_ascii=False)
    if row:
        row.value = encoded
    else:
        row = GlobalVariable(project_id=project_id, name=var_name, value=encoded)
        db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/{project_id}/global-vars/{var_name}")
async def delete_global_var(project_id: str, var_name: str, db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(GlobalVariable).where(
            GlobalVariable.project_id == project_id,
            GlobalVariable.name == var_name,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Global variable not found")
    await db.delete(row)
    await db.commit()
    return {"ok": True}
