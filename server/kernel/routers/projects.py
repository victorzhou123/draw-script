import logging
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import Marker, Project, ProjectClient, Script, Template, get_session
from schemas import (
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
    project.updated_at = datetime.utcnow()
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
        raise HTTPException(400, f"Client {body.client_id} is not connected")

    result = await db.execute(
        select(Marker).where(Marker.project_id == project_id).order_by(Marker.created_at)
    )
    markers = result.scalars().all()

    sent = await client_ws_manager.send_to_client(body.client_id, {
        "type": "set_markers",
        "project_id": project_id,
        "project_name": project.name,
        "markers": [{"name": m.name, "type": m.type} for m in markers],
    })
    if not sent:
        raise HTTPException(500, "Failed to send to client")

    logger.info(f"Sent {len(markers)} markers to client {body.client_id} for project {project_id}")
    return {"ok": True, "count": len(markers)}


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

    template = Template(id=template_id, project_id=project_id, name=name, filename=filename)
    db.add(template)
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
