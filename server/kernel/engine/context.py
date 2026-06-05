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
    project_id: str | None = None
    gpu_enabled: bool = False
    variables: dict[str, Any] = field(default_factory=dict)
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    script_call_stack: list[str] = field(default_factory=list)
    log: list[str] = field(default_factory=list)
    completion_event: asyncio.Event | None = None
    completion_result: dict[str, Any] = field(default_factory=dict)
    wait_barriers: dict[str, Any] = field(default_factory=dict)
    loop_counters: dict[str, int] = field(default_factory=dict)
    # Shared across shallow-copied branch contexts so any branch can signal end.
    end_event: asyncio.Event = field(default_factory=asyncio.Event)
    _result_box: list = field(default_factory=list)  # holds at most one dict
