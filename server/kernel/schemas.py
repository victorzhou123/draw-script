from datetime import datetime
from typing import Any

import json

from pydantic import BaseModel, Field, field_validator


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
    marker_names: list[str] | None = None  # None = send all markers


# ── Template ─────────────────────────────────────────────────────────────────

class TemplateResponse(BaseModel):
    id: str
    project_id: str
    name: str
    filename: str
    source_w: int | None = None
    source_h: int | None = None
    window_title: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── GlobalVariable ───────────────────────────────────────────────────────────

class GlobalVariableResponse(BaseModel):
    id: str
    project_id: str
    name: str
    # value is decoded from JSON so the API returns the real Python type
    value: Any
    updated_at: datetime

    @field_validator("value", mode="before")
    @classmethod
    def parse_value(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return v
        return v


class GlobalVariableUpsert(BaseModel):
    value: Any

    class Config:
        from_attributes = True


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
    default_client_id: str | None = None


class NodeCheckResult(BaseModel):
    node_id: str
    status: str  # "ok" | "warning" | "error"
    message: str = ""


class ScriptResponse(BaseModel):
    id: str
    name: str
    description: str
    flow_json: str
    project_id: str | None
    default_client_id: str | None
    created_at: datetime
    updated_at: datetime
    checks: list[NodeCheckResult] = []

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
    gpu_enabled: bool = False

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
    result_json: Any | None = None

    @field_validator("result_json", mode="before")
    @classmethod
    def parse_result_json(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    class Config:
        from_attributes = True



class RunScriptRequest(BaseModel):
    client_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    wait: bool = False


class DebugNodeRequest(BaseModel):
    client_id: str
    node_id: str
    flow_json: dict[str, Any] = Field(default_factory=dict)
    initial_variables: dict[str, Any] = Field(default_factory=dict)


# ── WebSocket ─────────────────────────────────────────────────────────────────

class WSMessage(BaseModel):
    type: str
    data: dict[str, Any] = {}
