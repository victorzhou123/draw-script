import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from database import init_db
from routers import clients, projects, scripts, webhooks, ws

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Database initialized")

    from engine.executor import ExecutionEngine
    from ws_manager import client_ws_manager, ui_ws_manager
    from database import AsyncSessionLocal

    engine = ExecutionEngine(client_ws_manager, ui_ws_manager, AsyncSessionLocal)
    scripts.set_engine(engine)
    webhooks.set_engine(engine)

    from heartbeat import HeartbeatMonitor
    monitor = HeartbeatMonitor(client_ws_manager, ui_ws_manager)
    import asyncio
    heartbeat_task = asyncio.create_task(monitor.run())

    logger.info(f"Draw-Script server started on {settings.host}:{settings.port}")
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
app.include_router(webhooks.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(ws.router)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, log_level=settings.log_level, reload=True)
