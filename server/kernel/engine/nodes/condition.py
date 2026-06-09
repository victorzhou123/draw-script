from engine.base_handler import BaseNodeHandler, NodeResult
from engine.node_registry import NodeRegistry


@NodeRegistry.register("condition")
class ConditionNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        data = self.ctx.node.data

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

        return NodeResult(success=True, branch="true" if result else "false", output={"result": result})

    def _evaluate(self, condition_type: str, params: dict) -> bool:
        variables = self.ctx.variables

        if condition_type == "variable_compare":
            var_path = params.get("variable", "")
            operator = params.get("operator", "==")
            expected = self._resolve_value(params.get("value"))
            actual = self._get_var(var_path)
            return self._compare(actual, operator, expected)

        if condition_type == "boolean_check":
            var_path = params.get("variable", "")
            val = self._get_var(var_path) if var_path else None
            return bool(val)

        # Legacy types kept for backward compat with saved scripts
        if condition_type == "vision_found":
            return bool(variables.get("last_vision_result", {}).get("found", False))

        if condition_type == "vision_text_contains":
            text = (variables.get("last_vision_result", {}).get("text", "") or "")
            return params.get("value", "").lower() in text.lower()

        if condition_type == "http_status":
            status = variables.get("last_http_response", {}).get("status_code", 0)
            return self._compare(status, params.get("operator", "=="), int(params.get("value", 200)))

        return False

    def _resolve_value(self, value):
        if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
            return self._get_var(value[2:-2].strip())
        if isinstance(value, str):
            import json
            try:
                return json.loads(value)
            except (ValueError, TypeError):
                pass
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
