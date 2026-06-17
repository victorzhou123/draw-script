import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

_MISSING = object()


def _resolve_var(variables: dict, ref: str) -> Any:
    key = ref.lstrip("$")
    val = variables
    for part in key.split("."):
        if isinstance(val, dict):
            if part not in val:
                return _MISSING
            val = val[part]
        else:
            return _MISSING
    return val


def interpolate_value(variables: dict, value: Any) -> Any:
    """Resolve {{var}} and legacy $var references against variables dict."""
    if not isinstance(value, str):
        return value
    tpl_whole = re.match(r'^\{\{([^}]+)\}\}$', value)
    if tpl_whole:
        resolved = _resolve_var(variables, tpl_whole.group(1).strip())
        return value if resolved is _MISSING else resolved
    if value.startswith("$"):
        resolved = _resolve_var(variables, value)
        return value if resolved is _MISSING else resolved
    def _replace(m):
        resolved = _resolve_var(variables, m.group(1).strip())
        if resolved is _MISSING:
            return m.group(0)
        return str(resolved) if resolved is not None else ""
    return re.sub(r"\{\{([^}]+)\}\}", _replace, value)


class LoopCountError(ValueError):
    pass


def resolve_loop_count(variables: dict, params: dict) -> int:
    """Resolve a loop node's 'count' param (may be a {{var}} reference) to an int.

    Raises LoopCountError instead of silently defaulting, since a wrong count
    (e.g. "run once" instead of "run 10 times") fails the script in a way that's
    easy to miss otherwise.
    """
    raw_count = interpolate_value(variables, params.get("count", 1))
    try:
        return int(raw_count)
    except (TypeError, ValueError):
        raise LoopCountError(f"循环次数配置无效: {raw_count!r}")


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

    def _interpolate(self, value: Any) -> Any:
        return interpolate_value(self.ctx.variables, value)
