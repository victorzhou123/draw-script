import asyncio
import time
import uuid
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import AIModelConfig, get_session

router = APIRouter(prefix="/models", tags=["models"])


class ModelConfigCreate(BaseModel):
    type: str
    provider: str
    name: str
    api_key: Optional[str] = ""
    base_url: Optional[str] = ""
    model_name: Optional[str] = ""
    enabled: bool = True


class ModelConfigUpdate(BaseModel):
    name: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    enabled: Optional[bool] = None


class ModelConfigTestBody(BaseModel):
    api_key: str
    base_url: str
    model_name: str


def _serialize(m: AIModelConfig) -> dict:
    return {
        "id": m.id,
        "type": m.type,
        "provider": m.provider,
        "name": m.name,
        "api_key": m.api_key,
        "base_url": m.base_url,
        "model_name": m.model_name,
        "enabled": m.enabled,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


async def _run_connection_test(api_key: str, base_url: str, model_name: str) -> dict:
    """
    Connectivity test using a text-only chat request with max_tokens=1.
    Avoids image size restrictions entirely while still verifying key, URL, and model name.
    Qwen/GLM are both OpenAI-compatible and accept text-only messages on VL models.
    """
    start = time.time()
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 1,
                },
                timeout=15,
            )
        latency_ms = int((time.time() - start) * 1000)

        if resp.status_code == 200:
            return {"success": True, "message": "连接成功", "latency_ms": latency_ms}

        try:
            err_body = resp.json()
            err_msg = (
                err_body.get("error", {}).get("message")
                or err_body.get("message")
                or str(err_body)
            )
        except Exception:
            err_msg = resp.text[:300]

        if resp.status_code in (401, 403):
            return {"success": False, "message": f"API Key 无效 ({err_msg})", "latency_ms": latency_ms}
        return {"success": False, "message": f"HTTP {resp.status_code}: {err_msg}", "latency_ms": latency_ms}

    except httpx.ConnectError:
        return {"success": False, "message": "无法连接到服务器，请检查 Base URL", "latency_ms": None}
    except httpx.TimeoutException:
        return {"success": False, "message": "连接超时（15s），请检查网络或 Base URL", "latency_ms": None}
    except Exception as e:
        return {"success": False, "message": str(e), "latency_ms": None}


# ── literal sub-paths must be declared before /{model_id} ──────────

@router.get("/local/status")
async def local_model_status():
    from cv.ocr_engine import get_ocr_status
    return {"paddleocr": get_ocr_status()}


@router.post("/local/init")
async def init_local_model():
    from cv.ocr_engine import init_ocr_async
    asyncio.create_task(init_ocr_async())
    return {"status": "initializing"}


@router.post("/local/reinit")
async def reinit_local_model():
    from cv.ocr_engine import reinit_ocr_async
    asyncio.create_task(reinit_ocr_async())
    return {"status": "reinitializing"}


@router.post("/test")
async def test_model_credentials(body: ModelConfigTestBody):
    """Test arbitrary credentials without saving them (used by the add/edit modal)."""
    return await _run_connection_test(body.api_key, body.base_url, body.model_name)


# ── CRUD ────────────────────────────────────────────────────────────

@router.get("")
async def list_models(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(AIModelConfig).order_by(AIModelConfig.created_at))
    return [_serialize(m) for m in result.scalars().all()]


@router.post("", status_code=201)
async def create_model(body: ModelConfigCreate, session: AsyncSession = Depends(get_session)):
    m = AIModelConfig(
        id=str(uuid.uuid4()),
        type=body.type,
        provider=body.provider,
        name=body.name,
        api_key=body.api_key or "",
        base_url=body.base_url or "",
        model_name=body.model_name or "",
        enabled=body.enabled,
    )
    session.add(m)
    await session.commit()
    await session.refresh(m)
    return _serialize(m)


@router.post("/{model_id}/test")
async def test_saved_model(model_id: str, session: AsyncSession = Depends(get_session)):
    """Test a saved model config by ID."""
    m = await session.get(AIModelConfig, model_id)
    if not m:
        raise HTTPException(status_code=404, detail="Model not found")
    return await _run_connection_test(m.api_key, m.base_url, m.model_name)


@router.put("/{model_id}")
async def update_model(model_id: str, body: ModelConfigUpdate, session: AsyncSession = Depends(get_session)):
    m = await session.get(AIModelConfig, model_id)
    if not m:
        raise HTTPException(status_code=404, detail="Model not found")
    if body.name is not None:
        m.name = body.name
    if body.api_key is not None:
        m.api_key = body.api_key
    if body.base_url is not None:
        m.base_url = body.base_url
    if body.model_name is not None:
        m.model_name = body.model_name
    if body.enabled is not None:
        m.enabled = body.enabled
    await session.commit()
    await session.refresh(m)
    return _serialize(m)


@router.delete("/{model_id}", status_code=204)
async def delete_model(model_id: str, session: AsyncSession = Depends(get_session)):
    m = await session.get(AIModelConfig, model_id)
    if m:
        await session.delete(m)
        await session.commit()
