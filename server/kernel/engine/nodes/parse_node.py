import re

from engine.base_handler import BaseNodeHandler, NodeResult, interpolate_value
from engine.node_registry import NodeRegistry

_HTML_RE = re.compile(r"<[a-zA-Z]")


def _is_html(value: str) -> bool:
    return isinstance(value, str) and bool(_HTML_RE.search(value))


def _extract(html: str, params: dict) -> dict | str:
    from lxml import html as lhtml

    root = lhtml.fromstring(html)
    if root is None:
        raise ValueError("Parse node: HTML 解析失败，内容为空或无法识别")

    selector_mode = params.get("selector_mode", "single")

    if selector_mode == "multi_field":
        fields: list = params.get("fields", [])
        result: dict = {}
        for f in fields:
            name = (f.get("name") or "").strip()
            sel_type = f.get("selector_type", "css")
            selector = (f.get("selector") or "").strip()
            if not name or not selector:
                continue
            matches = root.xpath(selector) if sel_type == "xpath" else root.cssselect(selector)
            texts = []
            for el in matches:
                if isinstance(el, str):
                    texts.append(el)
                elif hasattr(el, "text_content"):
                    texts.append(el.text_content().strip())
            result[name] = texts[0] if len(texts) == 1 else texts
        if params.get("output_format") == "str":
            return "\n".join(f"{k}: {v}" for k, v in result.items())
        return result

    # single selector mode
    sel_type = params.get("selector_type", "css")
    selector = (params.get("selector") or "").strip()
    matches = root.xpath(selector) if sel_type == "xpath" else root.cssselect(selector)
    texts = []
    for el in matches:
        if isinstance(el, str):
            texts.append(el)
        elif hasattr(el, "text_content"):
            texts.append(el.text_content().strip())
    return "\n".join(texts)


@NodeRegistry.register("parse")
class ParseNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        data = self.ctx.node.data
        params = data.get("params", {})
        input_var = (data.get("input_var") or "").strip()
        input_format = (data.get("input_format") or "html").strip()
        output_var = (data.get("output_var") or "").strip()

        if not input_var:
            return NodeResult(success=False, error="Parse node: 请指定输入变量")

        raw_value = self.ctx.variables.get(input_var)
        if raw_value is None:
            return NodeResult(success=False, error=f"Parse node: context 中不存在变量 '{input_var}'")

        if input_format == "html":
            if not _is_html(raw_value):
                return NodeResult(
                    success=False,
                    error=f"Parse node: 变量 '{input_var}' 的内容不是有效的 HTML（未检测到 HTML 标签）",
                )

        try:
            extracted = _extract(raw_value, params)
        except Exception as e:
            return NodeResult(success=False, error=f"Parse node: {e}")

        if output_var:
            self.ctx.variables[output_var] = extracted

        return NodeResult(success=True, output={output_var: extracted} if output_var else {"result": extracted})
