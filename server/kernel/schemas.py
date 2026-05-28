from datetime import datetime
from typing import Any

from pydantic import BaseModel


# ── Project ──────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Marker ───────────────────────────────────────────────────────────────────

class MarkerCreate(BaseModel):
    name: str
    type: str  # 'point' | 'box'


class MarkerResponse(BaseModel):
    id: str
    project_id: str
    name: str
    type: str
    created_at: datetime

    class Config:
        from_attributes = True


class SendMarkersRequest(BaseModel):
    client_id: str


# ── Script ───────────────────────────────────────────────────────────────────

class ScriptCreate(BaseModel):
    name: str
    description: str = ""
    flow_json: str = "{}"


class ScriptUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    flow_json: str | None = None
    project_id: str | None = None


class ScriptResponse(BaseModel):
    id: str
    name: str
    description: str
    flow_json: str
    project_id: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Client ───────────────────────────────────────────────────────────────────

class ClientResponse(BaseModel):
    id: str
    name: str
    platform: str
    last_seen: datetime
    status: str
    project_ids: list[str] = []

    class Config:
        from_attributes = True


# ── Execution ─────────────────────────────────────────────────────────────────

class ExecutionResponse(BaseModel):
    id: str
    script_id: str
    client_id: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    log: str

    class Config:
        from_attributes = True


# ── Webhook ───────────────────────────────────────────────────────────────────

class WebhookCreate(BaseModel):
    name: str
    url: str
    events: list[str] = []
    secret: str = ""
    enabled: bool = True


class WebhookUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    events: list[str] | None = None
    secret: str | None = None
    enabled: bool | None = None


class WebhookResponse(BaseModel):
    id: str
    name: str
    url: str
    events: str
    secret: str
    enabled: bool

    class Config:
        from_attributes = True


class RunScriptRequest(BaseModel):
    client_id: str


# ── WebSocket ─────────────────────────────────────────────────────────────────

class WSMessage(BaseModel):
    type: str
    data: dict[str, Any] = {}
