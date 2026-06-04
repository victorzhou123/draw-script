import json
import logging

from sqlalchemy import select

from database import GlobalVariable
from engine.base_handler import BaseNodeHandler, NodeResult
from engine.node_registry import NodeRegistry

logger = logging.getLogger(__name__)


@NodeRegistry.register("global-var")
class GlobalVarNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        data = self.ctx.node.data
        params = data.get("params", {})
        mode = params.get("mode", "read")

        if not self.ctx.project_id:
            return NodeResult(success=False, error="global_var: node must be used inside a project")

        if mode == "write":
            return await self._write_all(params)
        else:
            return await self._read_all(params)

    async def _write_all(self, params: dict) -> NodeResult:
        items = params.get("write_items", [])
        if not items:
            return NodeResult(success=False, error="global_var write: no items configured")

        async with self.ctx.session_factory() as session:
            for item in items:
                var_name = (item.get("var_name") or "").strip()
                if not var_name:
                    return NodeResult(success=False, error="global_var write: var_name is required for every item")

                source_type = item.get("source_type", "literal")
                if source_type == "context":
                    source_key = (item.get("source_key") or "").strip()
                    if not source_key:
                        return NodeResult(success=False, error=f"global_var write: source_key is required for item '{var_name}'")
                    if source_key not in self.ctx.variables:
                        return NodeResult(success=False, error=f"global_var write: context key '{source_key}' not found")
                    value = self.ctx.variables[source_key]
                else:
                    # literal: try to parse as JSON so numbers/bools/lists stay typed;
                    # fall back to plain string if the input is not valid JSON.
                    raw = item.get("literal_value", "")
                    try:
                        value = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        value = raw

                encoded = json.dumps(value, ensure_ascii=False)
                result = await session.execute(
                    select(GlobalVariable).where(
                        GlobalVariable.project_id == self.ctx.project_id,
                        GlobalVariable.name == var_name,
                    )
                )
                row = result.scalar_one_or_none()
                if row:
                    row.value = encoded
                else:
                    session.add(GlobalVariable(
                        project_id=self.ctx.project_id,
                        name=var_name,
                        value=encoded,
                    ))
                logger.debug(f"global_var write: project={self.ctx.project_id} name={var_name!r} value={encoded!r}")

            await session.commit()

        return NodeResult(success=True)

    async def _read_all(self, params: dict) -> NodeResult:
        items = params.get("read_items", [])
        if not items:
            return NodeResult(success=False, error="global_var read: no items configured")

        output: dict = {}
        async with self.ctx.session_factory() as session:
            for item in items:
                var_name = (item.get("var_name") or "").strip()
                if not var_name:
                    return NodeResult(success=False, error="global_var read: var_name is required for every item")

                target_key = (item.get("target_key") or "").strip() or var_name
                result = await session.execute(
                    select(GlobalVariable).where(
                        GlobalVariable.project_id == self.ctx.project_id,
                        GlobalVariable.name == var_name,
                    )
                )
                row = result.scalar_one_or_none()
                value = json.loads(row.value) if row else None
                self.ctx.variables[target_key] = value
                output[target_key] = value
                logger.debug(f"global_var read: project={self.ctx.project_id} name={var_name!r} -> ctx[{target_key!r}]={value!r}")

        return NodeResult(success=True, output=output)
