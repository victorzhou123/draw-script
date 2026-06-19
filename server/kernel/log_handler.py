import asyncio
import logging
import queue
import re
import sys
from collections import deque
from datetime import datetime

_WS_FRAME_RE = re.compile(r'^[<>%] ')
_NOISE_ACCESS_RE = re.compile(r'(GET|POST|DELETE|PUT|PATCH) /api/logs')

_db_queue: queue.Queue = queue.Queue()


def _is_noise(record: logging.LogRecord, msg: str) -> bool:
    if record.name == 'uvicorn.error' and _WS_FRAME_RE.match(record.getMessage()):
        return True
    if record.name == 'uvicorn.access' and _NOISE_ACCESS_RE.search(msg):
        return True
    return False


class MemoryLogHandler(logging.Handler):
    def __init__(self, maxlen: int = 500):
        super().__init__()
        self._records: deque = deque(maxlen=maxlen)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            if _is_noise(record, msg):
                return
            self._records.append({
                "time": datetime.fromtimestamp(record.created).strftime("%H:%M:%S.") + f"{record.msecs:03.0f}",
                "level": record.levelname,
                "name": record.name,
                "msg": msg,
            })
            _db_queue.put_nowait({
                "timestamp": datetime.fromtimestamp(record.created),
                "level": record.levelname,
                "source": "system",
                "logger_name": record.name,
                "message": msg,
                "client_id": None,
                "script_id": None,
                "execution_id": None,
                "node_id": None,
            })
        except Exception:
            pass

    def get_records(self, limit: int = 300) -> list[dict]:
        records = list(self._records)
        return records[-limit:]

    def clear(self) -> None:
        self._records.clear()


memory_handler = MemoryLogHandler()


def enqueue_execution_log(
    *,
    level: str,
    message: str,
    client_id: str | None = None,
    script_id: str | None = None,
    execution_id: str | None = None,
    node_id: str | None = None,
    node_label: str | None = None,
    node_type: str | None = None,
) -> None:
    _db_queue.put_nowait({
        "timestamp": datetime.now(),
        "level": level,
        "source": "execution",
        "logger_name": None,
        "message": message,
        "client_id": client_id,
        "script_id": script_id,
        "execution_id": execution_id,
        "node_id": node_id,
        "node_label": node_label or None,
        "node_type": node_type or None,
    })


async def db_log_writer(session_factory) -> None:
    """Background task: drain _db_queue every second and batch-write to AppLog."""
    from database import AppLog
    while True:
        await asyncio.sleep(1.0)
        if _db_queue.empty():
            continue
        batch: list[dict] = []
        try:
            while True:
                batch.append(_db_queue.get_nowait())
        except queue.Empty:
            pass
        if not batch:
            continue
        try:
            async with session_factory() as db:
                db.add_all([AppLog(**entry) for entry in batch])
                await db.commit()
        except Exception as e:
            print(f"[log_handler] DB write error: {e}", file=sys.stderr)
