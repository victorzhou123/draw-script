import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NodeResult:
    success: bool = True
    output: dict[str, Any] = field(default_factory=dict)
    branch: str | None = None
    error: str | None = None
    stop_branch: bool = False


class BaseNodeHandler(ABC):
    def __init__(self, context: "ExecutionContext"):  # noqa: F821
        self.ctx = context

    @abstractmethod
    async def execute(self) -> NodeResult: ...

    _MISSING = object()

    def _resolve_var(self, ref: str) -> Any:
        key = ref.lstrip("$")
        parts = key.split(".")
        val = self.ctx.variables
        for part in parts:
            if isinstance(val, dict):
                if part not in val:
                    return self._MISSING
                val = val[part]
            else:
                return self._MISSING
        return val

    def _interpolate(self, value: Any) -> Any:
        """Resolve {{var}} and legacy $var references in string param values."""
        if not isinstance(value, str):
            return value
        tpl_whole = re.match(r'^\{\{([^}]+)\}\}$', value)
        if tpl_whole:
            resolved = self._resolve_var(tpl_whole.group(1).strip())
            return value if resolved is self._MISSING else resolved
        if value.startswith("$"):
            resolved = self._resolve_var(value)
            return value if resolved is self._MISSING else resolved
        def _replace(m):
            resolved = self._resolve_var(m.group(1).strip())
            if resolved is self._MISSING:
                return m.group(0)
            return str(resolved) if resolved is not None else ""
        return re.sub(r"\{\{([^}]+)\}\}", _replace, value)
