import json

TYPE_NAMES = ("str", "int", "float", "bool", "list", "dict", "None")

_BOOL_TRUE = {"true", "1", "yes"}
_BOOL_FALSE = {"false", "0", "no"}


class TypeConversionError(ValueError):
    pass


def coerce_typed(value, type_name: str):
    """Convert value to the declared type. Raises TypeConversionError on failure.

    type_name == "None" forces the result to Python None regardless of value,
    replacing the old magic-string ("None" as text) sentinel.
    """
    if type_name == "None":
        return None

    if type_name == "str":
        return str(value) if value is not None else ""

    if type_name == "int":
        try:
            return int(value)
        except (TypeError, ValueError):
            raise TypeConversionError(f"无法转换为 int: {value!r}")

    if type_name == "float":
        try:
            return float(value)
        except (TypeError, ValueError):
            raise TypeConversionError(f"无法转换为 float: {value!r}")

    if type_name == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            v = value.strip().lower()
            if v in _BOOL_TRUE:
                return True
            if v in _BOOL_FALSE:
                return False
        raise TypeConversionError(f"无法转换为 bool: {value!r}")

    if type_name == "list":
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except (TypeError, ValueError):
                raise TypeConversionError(f"无法解析为 list（不是合法 JSON）: {value!r}")
            if isinstance(parsed, list):
                return parsed
            raise TypeConversionError(f"解析结果不是 list，而是 {type(parsed).__name__}: {value!r}")
        raise TypeConversionError(f"无法转换为 list: {value!r}")

    if type_name == "dict":
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except (TypeError, ValueError):
                raise TypeConversionError(f"无法解析为 dict（不是合法 JSON）: {value!r}")
            if isinstance(parsed, dict):
                return parsed
            raise TypeConversionError(f"解析结果不是 dict，而是 {type(parsed).__name__}: {value!r}")
        raise TypeConversionError(f"无法转换为 dict: {value!r}")

    raise TypeConversionError(f"未知类型声明: {type_name!r}")
