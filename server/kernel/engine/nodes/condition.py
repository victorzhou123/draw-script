from engine.base_handler import BaseNodeHandler, NodeResult
from engine.node_registry import NodeRegistry
from engine.type_coerce import coerce_typed, TypeConversionError


@NodeRegistry.register("condition")
class ConditionNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        data = self.ctx.node.data

        try:
            if "conditions" in data:
                operator = data.get("operator", "and")
                conditions = data.get("conditions", [])
                if not conditions:
                    result = False
                elif operator == "and":
                    result = all(self._evaluate(c.get("condition_type", ""), c.get("params", {})) for c in conditions)
                else:
                    result = any(self._evaluate(c.get("condition_type", ""), c.get("params", {})) for c in conditions)
            else:
                # Backward compat: old single-condition format
                result = self._evaluate(data.get("condition_type", ""), data.get("params", {}))
        except ValueError as e:
            return NodeResult(success=False, error=f"条件节点配置错误: {e}")
        except TypeConversionError as e:
            return NodeResult(success=False, error=f"条件判断类型转换失败: {e}")

        return NodeResult(success=True, branch="true" if result else "false", output={"result": result})

    def _evaluate(self, condition_type: str, params: dict) -> bool:
        variables = self.ctx.variables

        if condition_type == "variable_compare":
            var_path = params.get("variable", "")
            if not var_path:
                raise ValueError("变量路径未填写")
            operator = params.get("operator", "==")
            value_type = params.get("value_type") or "str"
            expected = self._resolve_value(params.get("value"), value_type)
            actual = self._get_var(var_path)
            return self._compare(actual, operator, expected)

        if condition_type == "boolean_check":
            var_path = params.get("variable", "")
            if not var_path:
                raise ValueError("变量路径未填写")
            val = self._get_var(var_path)
            if val is not True and val is not False:
                raise ValueError(f"布尔值判断要求变量为严格 True/False，实际值: {repr(val)}")
            expect_true = params.get("expect_true", True)
            return val is True if expect_true else val is False

        if condition_type == "none_check":
            var_path = params.get("variable", "")
            if not var_path:
                raise ValueError("变量路径未填写")
            val = self._get_var(var_path)
            is_none = val is None
            return is_none if params.get("expect_none", True) else not is_none

        return False

    def _resolve_value(self, value, value_type: str):
        if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
            return self._get_var(value[2:-2].strip())
        return coerce_typed(value, value_type)

    def _get_var(self, path: str):
        parts = path.split(".")
        val = self.ctx.variables
        for part in parts:
            if isinstance(val, dict):
                val = val.get(part)
            else:
                return None
        return val

    def _compare(self, actual, operator: str, expected) -> bool:
        try:
            if operator == "==":
                return actual == expected
            if operator == "!=":
                return actual != expected
            if operator == ">":
                return actual > expected
            if operator == ">=":
                return actual >= expected
            if operator == "<":
                return actual < expected
            if operator == "<=":
                return actual <= expected
            if operator == "contains":
                return str(expected).lower() in str(actual).lower()
        except Exception:
            pass
        return False
