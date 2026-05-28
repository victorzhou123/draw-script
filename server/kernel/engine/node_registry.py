from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.base_handler import BaseNodeHandler


class NodeRegistry:
    _handlers: dict[str, type] = {}

    @classmethod
    def register(cls, node_type: str):
        def decorator(handler_cls):
            cls._handlers[node_type] = handler_cls
            return handler_cls
        return decorator

    @classmethod
    def get_handler(cls, node_type: str) -> type:
        handler = cls._handlers.get(node_type)
        if not handler:
            raise ValueError(f"Unknown node type: '{node_type}'. Registered: {list(cls._handlers)}")
        return handler

    @classmethod
    def registered_types(cls) -> list[str]:
        return list(cls._handlers.keys())
