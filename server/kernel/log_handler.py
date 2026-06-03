import logging
import re
from collections import deque
from datetime import datetime

_WS_FRAME_RE = re.compile(r'^[<>%] ')


class MemoryLogHandler(logging.Handler):
    def __init__(self, maxlen: int = 500):
        super().__init__()
        self._records: deque = deque(maxlen=maxlen)

    def emit(self, record: logging.LogRecord) -> None:
        if record.name == 'uvicorn.error' and _WS_FRAME_RE.match(record.getMessage()):
            return
        try:
            self._records.append({
                "time": datetime.fromtimestamp(record.created).strftime("%H:%M:%S.") + f"{record.msecs:03.0f}",
                "level": record.levelname,
                "name": record.name,
                "msg": self.format(record),
            })
        except Exception:
            pass

    def get_records(self, limit: int = 300) -> list[dict]:
        records = list(self._records)
        return records[-limit:]

    def clear(self) -> None:
        self._records.clear()


memory_handler = MemoryLogHandler()
