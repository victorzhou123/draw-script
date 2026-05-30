import ast
import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import Execution, Script, get_session
from dependencies import get_engine
from schemas import ExecutionResponse, RunScriptRequest, ScriptCreate, ScriptResponse, ScriptUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scripts", tags=["scripts"])


class SyntaxCheckRequest(BaseModel):
    code: str


@router.post("/syntax-check")
async def syntax_check(body: SyntaxCheckRequest):
    try:
        ast.parse(body.code)
        return {"ok": True}
    except SyntaxError as e:
        return {"ok": False, "line": e.lineno, "col": e.offset, "msg": e.msg}


@router.get("", response_model=list[ScriptResponse])
async def list_scripts(db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Script).order_by(Script.updated_at.desc()))
    return result.scalars().all()


@router.post("", response_model=ScriptResponse)
async def create_script(body: ScriptCreate, db: AsyncSession = Depends(get_session)):
    script = Script(**body.model_dump())
    db.add(script)
    await db.commit()
    await db.refresh(script)
    return script


@router.get("/{script_id}", response_model=ScriptResponse)
async def get_script(script_id: str, db: AsyncSession = Depends(get_session)):
    script = await db.get(Script, script_id)
    if not script:
        raise HTTPException(404, "Script not found")
    return script


@router.put("/{script_id}", response_model=ScriptResponse)
async def update_script(script_id: str, body: ScriptUpdate, db: AsyncSession = Depends(get_session)):
    script = await db.get(Script, script_id)
    if not script:
        raise HTTPException(404, "Script not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(script, field, value)
    script.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(script)
    return script


@router.delete("/{script_id}")
async def delete_script(script_id: str, db: AsyncSession = Depends(get_session)):
    script = await db.get(Script, script_id)
    if not script:
        raise HTTPException(404, "Script not found")
    await db.delete(script)
    await db.commit()
    return {"ok": True}


@router.post("/{script_id}/run", response_model=ExecutionResponse)
async def run_script(
    script_id: str,
    body: RunScriptRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    script = await db.get(Script, script_id)
    if not script:
        raise HTTPException(404, "Script not found")

    from ws_manager import client_ws_manager
    if not client_ws_manager.is_connected(body.client_id):
        raise HTTPException(400, f"Client {body.client_id} is not connected")

    execution = Execution(
        script_id=script_id,
        client_id=body.client_id,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    flow = json.loads(script.flow_json) if script.flow_json else {}
    engine = get_engine(request)

    if body.wait and engine:
        from config import settings
        completion_event = asyncio.Event()
        asyncio.create_task(
            engine.run_script(execution.id, script_id, body.client_id,
                              flow, script.project_id, body.params, completion_event,
                              script_name=script.name)
        )
        try:
            await asyncio.wait_for(completion_event.wait(), timeout=settings.run_timeout)
        except asyncio.TimeoutError:
            pass
        await db.refresh(execution)
    elif engine:
        background_tasks.add_task(
            engine.run_script,
            execution.id, script_id, body.client_id,
            flow, script.project_id, body.params, None, script.name,
        )

    return execution


@router.post("/{script_id}/stop")
async def stop_script(script_id: str, execution_id: str, request: Request, db: AsyncSession = Depends(get_session)):
    engine = get_engine(request)
    if engine:
        await engine.stop_execution(execution_id)
    return {"ok": True}


@router.get("/{script_id}/executions", response_model=list[ExecutionResponse])
async def list_executions(script_id: str, db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(Execution)
        .where(Execution.script_id == script_id)
        .order_by(Execution.started_at.desc())
        .limit(50)
    )
    return result.scalars().all()
