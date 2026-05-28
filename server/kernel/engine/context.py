import asyncio
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from engine.flow_graph import FlowGraph, FlowNode
    from ws_manager import ClientWSManager, UIWSManager
    from sqlalchemy.ext.asyncio import async_sessionmaker


@dataclass
class ExecutionContext:
    execution_id: str
    client_id: str
    node: "FlowNode"
    graph: "FlowGraph"
    ws_manager: "ClientWSManager"
    ui_manager: "UIWSManager"
    session_factory: "async_sessionmaker"
    variables: dict[str, Any] = field(default_factory=dict)
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    loop_stack: list[dict] = field(default_factory=list)
    log: list[str] = field(default_factory=list)
