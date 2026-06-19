import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import ServiceApiKey, get_session

router = APIRouter(prefix="/service-keys", tags=["service-keys"])


class ServiceKeyCreate(BaseModel):
    service_name: str
    api_key: Optional[str] = ""
    base_url: Optional[str] = ""


class ServiceKeyUpdate(BaseModel):
    service_name: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None


def _serialize(k: ServiceApiKey) -> dict:
    return {
        "id": k.id,
        "service_name": k.service_name,
        "api_key": k.api_key,
        "base_url": k.base_url,
        "created_at": k.created_at.isoformat() if k.created_at else None,
        "updated_at": k.updated_at.isoformat() if k.updated_at else None,
    }


@router.get("")
async def list_service_keys(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ServiceApiKey).order_by(ServiceApiKey.created_at))
    return [_serialize(k) for k in result.scalars().all()]


@router.post("", status_code=201)
async def create_service_key(body: ServiceKeyCreate, session: AsyncSession = Depends(get_session)):
    if not body.service_name.strip():
        raise HTTPException(status_code=422, detail="service_name is required")
    k = ServiceApiKey(
        id=str(uuid.uuid4()),
        service_name=body.service_name.strip(),
        api_key=body.api_key or "",
        base_url=body.base_url or "",
    )
    session.add(k)
    await session.commit()
    await session.refresh(k)
    return _serialize(k)


@router.put("/{key_id}")
async def update_service_key(key_id: str, body: ServiceKeyUpdate, session: AsyncSession = Depends(get_session)):
    k = await session.get(ServiceApiKey, key_id)
    if not k:
        raise HTTPException(status_code=404, detail="Service key not found")
    if body.service_name is not None:
        k.service_name = body.service_name.strip()
    if body.api_key is not None:
        k.api_key = body.api_key
    if body.base_url is not None:
        k.base_url = body.base_url
    await session.commit()
    await session.refresh(k)
    return _serialize(k)


@router.delete("/{key_id}", status_code=204)
async def delete_service_key(key_id: str, session: AsyncSession = Depends(get_session)):
    k = await session.get(ServiceApiKey, key_id)
    if k:
        await session.delete(k)
        await session.commit()
