import asyncio
import uuid

from config import settings
from engine.base_handler import BaseNodeHandler, NodeResult
from engine.node_registry import NodeRegistry
from engine.type_coerce import coerce_typed, TypeConversionError


@NodeRegistry.register("context-edit")
class ContextEditNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        params = self.ctx.node.data.get("params", {})
        operations = params.get("operations", [])

        if not operations:
            return NodeResult(success=False, error="context-edit: 未配置任何操作")

        output: dict = {}
        for i, op in enumerate(operations):
            op_type = op.get("op")

            if op_type == "set":
                key = (op.get("key") or "").strip()
                if not key:
                    return NodeResult(success=False, error=f"context-edit: 第 {i + 1} 个操作（set）的 key 为空")
                value = self._interpolate(op.get("value", ""))
                value_type = (op.get("value_type") or "").strip()
                if value_type:
                    try:
                        value = coerce_typed(value, value_type)
                    except TypeConversionError as e:
                        return NodeResult(success=False, error=f"context-edit: set '{key}' 类型转换失败: {e}")
                self.ctx.variables[key] = value
                output[key] = value

            elif op_type == "delete":
                key = (op.get("key") or "").strip()
                if not key:
                    return NodeResult(success=False, error=f"context-edit: 第 {i + 1} 个操作（delete）的 key 为空")
                self.ctx.variables.pop(key, None)

            elif op_type == "rename":
                from_key = (op.get("from") or "").strip()
                to_key = (op.get("to") or "").strip()
                if not from_key or not to_key:
                    return NodeResult(success=False, error=f"context-edit: 第 {i + 1} 个操作（rename）的 from/to 不能为空")
                value = self.ctx.variables.get(from_key)
                self.ctx.variables[to_key] = value
                self.ctx.variables.pop(from_key, None)
                output[to_key] = value

            elif op_type == "clipboard-read":
                key = (op.get("key") or "").strip()
                if not key:
                    return NodeResult(success=False, error=f"context-edit: 第 {i + 1} 个操作（clipboard-read）的 key 为空")

                request_id = str(uuid.uuid4())
                future: asyncio.Future = asyncio.get_running_loop().create_future()
                self.ctx.ws_manager.pending_requests[request_id] = future

                sent = await self.ctx.ws_manager.send_to_client(self.ctx.client_id, {
                    "type": "read_clipboard",
                    "node_id": self.ctx.node.id,
                    "request_id": request_id,
                })
                if not sent:
                    return NodeResult(success=False, error=f"context-edit: Client {self.ctx.client_id} not reachable")

                try:
                    result = await asyncio.wait_for(future, timeout=settings.node_timeout)
                except asyncio.TimeoutError:
                    self.ctx.ws_manager.pending_requests.pop(request_id, None)
                    return NodeResult(success=False, error="context-edit: clipboard-read 超时")

                if not result.get("success", True):
                    return NodeResult(success=False, error=result.get("error") or "clipboard-read 失败")

                value = result.get("output", {}).get("text", "")
                value_type = (op.get("value_type") or "").strip()
                if value_type:
                    try:
                        value = coerce_typed(value, value_type)
                    except TypeConversionError as e:
                        return NodeResult(success=False, error=f"context-edit: clipboard-read '{key}' 类型转换失败: {e}")

                self.ctx.variables[key] = value
                output[key] = value

            else:
                return NodeResult(success=False, error=f"context-edit: 未知操作类型 '{op_type}'")

        return NodeResult(success=True, output=output)
