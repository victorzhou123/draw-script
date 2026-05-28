from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NodeResult:
    success: bool = True
    output: dict[str, Any] = field(default_factory=dict)
    branch: str | None = None
    error: str | None = None


class BaseNodeHandler(ABC):
    def __init__(self, context: "ExecutionContext"):  # noqa: F821
        self.ctx = context

    @abstractmethod
    async def execute(self) -> NodeResult: ...
