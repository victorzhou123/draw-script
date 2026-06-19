import json
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import AppLog, AppSetting, get_session
from log_handler import memory_handler

router = APIRouter()

_DEFAULT_SETTINGS = {
    "log_retention_days": 7,
    "log_auto_refresh_interval": 5,
}


async def _get_setting(db: AsyncSession, key: str):
    row = await db.get(AppSetting, key)
    return json.loads(row.value) if row else _DEFAULT_SETTINGS.get(key)


# ── In-memory log endpoints (keep for backward compatibility) ─────────────────

@router.get("/logs")
def get_memory_logs(limit: int = 300):
    return memory_handler.get_records(limit)


@router.delete("/logs")
def clear_memory_logs():
    memory_handler.clear()
    return {"ok": True}


# Preset → offset in hours
_PRESET_HOURS: dict[str, float] = {
    "1h": 1, "6h": 6, "12h": 12, "24h": 24, "48h": 48,
    "7d": 168, "14d": 336, "30d": 720,
}


def _parse_dt(s: str) -> datetime:
    """Parse ISO datetime string (local time, no timezone suffix)."""
    s = s.replace("Z", "").replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse datetime: {s!r}")


# ── Persistent log query ──────────────────────────────────────────────────────

@router.get("/logs/entries")
async def query_logs(
    level: Optional[str] = None,
    source: Optional[str] = None,
    script_id: Optional[str] = None,
    client_id: Optional[str] = None,
    keyword: Optional[str] = None,
    time_range: Optional[str] = None,   # preset key or omit for custom
    start_time: Optional[str] = None,   # ISO local datetime for custom range
    end_time: Optional[str] = None,
    page: int = 1,
    page_size: int = 100,
    db: AsyncSession = Depends(get_session),
):
    filters = []
    if level and level != "ALL":
        filters.append(AppLog.level == level)
    if source and source != "ALL":
        filters.append(AppLog.source == source)
    if script_id:
        filters.append(AppLog.script_id == script_id)
    if client_id:
        filters.append(AppLog.client_id == client_id)
    if keyword:
        filters.append(AppLog.message.contains(keyword))

    if time_range and time_range in _PRESET_HOURS:
        cutoff = datetime.now() - timedelta(hours=_PRESET_HOURS[time_range])
        filters.append(AppLog.timestamp >= cutoff)
    else:
        if start_time:
            try:
                filters.append(AppLog.timestamp >= _parse_dt(start_time))
            except ValueError:
                pass
        if end_time:
            try:
                filters.append(AppLog.timestamp <= _parse_dt(end_time))
            except ValueError:
                pass

    from sqlalchemy import and_
    where = and_(*filters) if filters else True

    total = (await db.execute(select(func.count()).select_from(AppLog).where(where))).scalar()
    offset = (page - 1) * page_size
    rows = (
        await db.execute(
            select(AppLog)
            .where(where)
            .order_by(AppLog.timestamp.desc(), AppLog.id.desc())
            .offset(offset)
            .limit(page_size)
        )
    ).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat(),
                "level": r.level,
                "source": r.source,
                "logger_name": r.logger_name,
                "message": r.message,
                "client_id": r.client_id,
                "script_id": r.script_id,
                "execution_id": r.execution_id,
                "node_id": r.node_id,
                "node_label": r.node_label,
                "node_type": r.node_type,
            }
            for r in rows
        ],
    }


@router.delete("/logs/entries")
async def clear_persistent_logs(db: AsyncSession = Depends(get_session)):
    await db.execute(delete(AppLog))
    await db.commit()
    return {"ok": True}


# ── App settings ──────────────────────────────────────────────────────────────

@router.get("/app-settings")
async def get_app_settings(db: AsyncSession = Depends(get_session)):
    result = {}
    for key in _DEFAULT_SETTINGS:
        result[key] = await _get_setting(db, key)
    return result


class SettingsUpdate(BaseModel):
    log_retention_days: Optional[int] = None
    log_auto_refresh_interval: Optional[int] = None


@router.put("/app-settings")
async def update_app_settings(data: SettingsUpdate, db: AsyncSession = Depends(get_session)):
    for key, val in data.model_dump(exclude_none=True).items():
        row = await db.get(AppSetting, key)
        if row is None:
            db.add(AppSetting(key=key, value=json.dumps(val)))
        else:
            row.value = json.dumps(val)
    await db.commit()
    return {"ok": True}


# ── Cleanup helper (called from main.py lifespan) ─────────────────────────────

async def cleanup_old_logs(session_factory, retention_days: int) -> None:
    cutoff = datetime.now() - timedelta(days=retention_days)
    async with session_factory() as db:
        await db.execute(delete(AppLog).where(AppLog.timestamp < cutoff))
        await db.commit()
