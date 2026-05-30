import uuid
from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from config import settings

engine = create_async_engine(
    f"sqlite+aiosqlite:///{settings.db_path}",
    echo=False,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Marker(Base):
    __tablename__ = "markers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)  # 'point' | 'box'
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # Captured coordinates (relative to bound window, None until annotated)
    x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    y: Mapped[int | None] = mapped_column(Integer, nullable=True)
    w: Mapped[int | None] = mapped_column(Integer, nullable=True)
    h: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Window binding (client-side window the coords are relative to)
    window_title: Mapped[str | None] = mapped_column(String, nullable=True)
    window_process: Mapped[str | None] = mapped_column(String, nullable=True)
    window_x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    window_y: Mapped[int | None] = mapped_column(Integer, nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Script(Base):
    __tablename__ = "scripts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    flow_json: Mapped[str] = mapped_column(Text, default="{}")
    project_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ProjectClient(Base):
    """Many-to-many: projects ↔ clients."""
    __tablename__ = "project_clients"

    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    client_id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    platform: Mapped[str] = mapped_column(String, default="unknown")
    last_seen: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    status: Mapped[str] = mapped_column(String, default="idle")


class Execution(Base):
    __tablename__ = "executions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    script_id: Mapped[str] = mapped_column(String, ForeignKey("scripts.id"), nullable=False)
    client_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    log: Mapped[str] = mapped_column(Text, default="")
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    url: Mapped[str] = mapped_column(String, default="")
    events: Mapped[str] = mapped_column(Text, default="[]")
    secret: Mapped[str] = mapped_column(String, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # inbound trigger fields
    script_id: Mapped[str | None] = mapped_column(String, nullable=True)
    client_id: Mapped[str | None] = mapped_column(String, nullable=True)


class AIModelConfig(Base):
    __tablename__ = "ai_model_configs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    type: Mapped[str] = mapped_column(String, nullable=False)       # "local" | "third_party"
    provider: Mapped[str] = mapped_column(String, nullable=False)   # "paddleocr" | "qwen" | "glm"
    name: Mapped[str] = mapped_column(String, nullable=False)
    api_key: Mapped[str] = mapped_column(String, default="")
    base_url: Mapped[str] = mapped_column(String, default="")
    model_name: Mapped[str] = mapped_column(String, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migrate: add project_id to scripts if column not yet present
        try:
            await conn.execute(text("ALTER TABLE scripts ADD COLUMN project_id TEXT"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE webhooks ADD COLUMN script_id TEXT"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE webhooks ADD COLUMN client_id TEXT"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE executions ADD COLUMN result_json TEXT"))
        except Exception:
            pass
        # Marker coordinate columns
        for col, coltype in [
            ("x", "INTEGER"), ("y", "INTEGER"), ("w", "INTEGER"), ("h", "INTEGER"),
            ("window_title", "TEXT"), ("window_process", "TEXT"),
            ("window_x", "INTEGER"), ("window_y", "INTEGER"), ("captured_at", "TEXT"),
        ]:
            try:
                await conn.execute(text(f"ALTER TABLE markers ADD COLUMN {col} {coltype}"))
            except Exception:
                pass


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
