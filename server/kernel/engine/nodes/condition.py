from engine.base_handler import BaseNodeHandler, NodeResult
from engine.node_registry import NodeRegistry


@NodeRegistry.register("condition")
class ConditionNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        data = self.ctx.node.data
        condition_type = data.get("condition_type", "vision_found")
        params = data.get("params", {})

        result = self._evaluate(condition_type, params)
        return NodeResult(success=True, branch="true" if result else "false", output={"result": result})

    def _evaluate(self, condition_type: str, params: dict) -> bool:
        variables = self.ctx.variables

        if condition_type == "vision_found":
            vision_result = variables.get("last_vision_result", {})
            return bool(vision_result.get("found", False))

        if condition_type == "vision_text_contains":
            vision_result = variables.get("last_vision_result", {})
            text = vision_result.get("text", "") or ""
            return params.get("value", "").lower() in text.lower()

        if condition_type == "variable_compare":
            var_path = params.get("variable", "")
            operator = params.get("operator", "==")
            expected = self._resolve_value(params.get("value"))
            actual = self._get_var(var_path)
            return self._compare(actual, operator, expected)

        if condition_type == "http_status":
            response = variables.get("last_http_response", {})
            status = response.get("status_code", 0)
            return self._compare(status, params.get("operator", "=="), int(params.get("value", 200)))

        if condition_type == "boolean_check":
            var_path = params.get("variable", "")
            val = self._get_var(var_path) if var_path else None
            return bool(val)

        return False

    def _resolve_value(self, value):
        if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
            return self._get_var(value[2:-2].strip())
        return value

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
