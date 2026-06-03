import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from database import init_db
from log_handler import memory_handler
from routers import clients, models, projects, scripts, ws

logger = logging.getLogger(__name__)

# basicConfig is a no-op if uvicorn's dictConfig already ran (which attaches a
# NullHandler to root before importing this module).  Set root level and attach
# the in-memory handler explicitly so it always works regardless of startup order.
_level = getattr(logging, settings.log_level.upper(), logging.INFO)
logging.getLogger().setLevel(_level)

# 应用层 logger：直接设置 level，避免第三方库（如 PaddleOCR）重置 root level 后失效
for _lg_name in ("routers", "engine", "cv", "main"):
    _lg = logging.getLogger(_lg_name)
    _lg.setLevel(_level)
    _lg.propagate = False
    if memory_handler not in _lg.handlers:
        _lg.addHandler(memory_handler)

# uvicorn logger：直接挂 handler，不依赖传播链
for _lg_name in ("uvicorn.error", "uvicorn.access"):
    _lg = logging.getLogger(_lg_name)
    _lg.propagate = False
    if memory_handler not in _lg.handlers:
        _lg.addHandler(memory_handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Database initialized")

    from engine.executor import ExecutionEngine
    from ws_manager import client_ws_manager, ui_ws_manager

    from cv.ocr_engine import should_autostart, init_ocr_async, get_ocr_status
    if should_autostart():
        logger.info("Auto-initializing PaddleOCR (previously initialized by user)")
        async def _init_ocr_and_notify():
            await init_ocr_async()
            await ui_ws_manager.broadcast_event("ocr_status_changed", {"paddleocr": get_ocr_status()})
        asyncio.create_task(_init_ocr_and_notify())
    from database import AsyncSessionLocal

    engine = ExecutionEngine(client_ws_manager, ui_ws_manager, AsyncSessionLocal)
    app.state.engine = engine

    from heartbeat import HeartbeatMonitor
    monitor = HeartbeatMonitor(client_ws_manager, ui_ws_manager)
    heartbeat_task = asyncio.create_task(monitor.run())

    root_handlers = [type(h).__name__ for h in logging.getLogger().handlers]
    logger.info(f"Draw-Script server started on {settings.host}:{settings.port}  log_level={settings.log_level}  root_handlers={root_handlers}")
    yield

    heartbeat_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Draw-Script", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scripts.router, prefix="/api")
app.include_router(clients.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(models.router, prefix="/api")
app.include_router(ws.router)


@app.get("/api/logs")
def get_logs(limit: int = 300):
    return memory_handler.get_records(limit)


@app.delete("/api/logs")
def clear_logs():
    memory_handler.clear()
    return {"ok": True}

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=settings.reload,
        reload_includes=["*.py"] if settings.reload else None,
    )
