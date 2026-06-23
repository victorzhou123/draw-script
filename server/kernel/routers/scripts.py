import ast
import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import Execution, Marker, MarkerCapture, ProjectClientWindow, Script, get_session
from dependencies import get_engine
from schemas import DebugNodeRequest, ExecutionResponse, RunScriptRequest, ScriptCreate, ScriptResponse, ScriptUpdate
from ws_manager import client_ws_manager

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


@router.put("/{script_id}")
async def update_script(script_id: str, body: ScriptUpdate, db: AsyncSession = Depends(get_session)):
    script = await db.get(Script, script_id)
    if not script:
        raise HTTPException(404, "Script not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(script, field, value)
    script.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(script)

    checks: list[dict] = []
    if body.flow_json is not None:
        from engine.static_check import run_flow_checks
        results = await run_flow_checks(
            body.flow_json,
            script.project_id,
            script.default_client_id,
            db,
        )
        checks = [{"node_id": r.node_id, "status": r.status, "message": r.message} for r in results]

    from schemas import ScriptResponse, NodeCheckResult
    resp = ScriptResponse.model_validate(script)
    resp.checks = [NodeCheckResult(**c) for c in checks]
    return resp


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

    # restore all bound windows once before execution starts
    if script.project_id:
        from sqlalchemy import select as _select
        _pcw_result = await db.execute(
            _select(ProjectClientWindow).where(
                ProjectClientWindow.project_id == script.project_id,
                ProjectClientWindow.client_id == body.client_id,
            )
        )
        for _pcw in _pcw_result.scalars().all():
            await client_ws_manager.send_to_client(body.client_id, {
                "type": "restore_window",
                "title": _pcw.window_title,
                "process": _pcw.window_process or "",
                "x": _pcw.window_x or 0,
                "y": _pcw.window_y or 0,
                "w": _pcw.window_w,
                "h": _pcw.window_h,
            })

    logger.debug(
        f"run_script request: script_id={script_id} client_id={body.client_id} "
        f"wait={body.wait} params={body.params}"
    )

    flow = json.loads(script.flow_json) if script.flow_json else {}
    engine = get_engine(request)

    if body.wait and engine:
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

    logger.debug(
        f"run_script response: execution_id={execution.id} status={execution.status} "
        f"result={execution.result_json}"
    )
    return execution


@router.post("/{script_id}/stop")
async def stop_script(script_id: str, execution_id: str, request: Request, db: AsyncSession = Depends(get_session)):
    engine = get_engine(request)
    if engine:
        await engine.stop_execution(execution_id)
    return {"ok": True}


@router.post("/{script_id}/debug/execute-node")
async def debug_execute_node(
    script_id: str,
    body: DebugNodeRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    script = await db.get(Script, script_id)
    if not script:
        raise HTTPException(404, "Script not found")

    if not client_ws_manager.is_connected(body.client_id):
        raise HTTPException(400, f"Client {body.client_id} is not connected")

    engine = get_engine(request)
    if engine:
        background_tasks.add_task(
            engine.debug_execute_node,
            script_id, body.client_id, body.flow_json, body.node_id, script.project_id,
            body.initial_variables,
        )
    return {"ok": True}


@router.post("/{script_id}/debug/run-to-node")
async def debug_run_to_node(
    script_id: str,
    body: DebugNodeRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    script = await db.get(Script, script_id)
    if not script:
        raise HTTPException(404, "Script not found")

    if not client_ws_manager.is_connected(body.client_id):
        raise HTTPException(400, f"Client {body.client_id} is not connected")

    engine = get_engine(request)
    if engine:
        background_tasks.add_task(
            engine.debug_run_to_node,
            script_id, body.client_id, body.flow_json, body.node_id, script.project_id,
        )
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
