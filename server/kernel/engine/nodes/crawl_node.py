import httpx

from engine.base_handler import BaseNodeHandler, NodeResult, interpolate_value
from engine.node_registry import NodeRegistry

# ──────────────────────────────────────────────────────────────────────────────
# [FIRECRAWL_DISABLED] Firecrawl 集成代码已暂时屏蔽。
# 后端实现保留在此文件中供参考，但执行路径已在 execute() 中注释掉。
# 重新启用时需同步开放前端入口（CrawlForm.vue 中的 radio-button）。
# ──────────────────────────────────────────────────────────────────────────────

_FIRECRAWL_DEFAULT_BASE = "https://api.firecrawl.dev"


async def _get_service_key(session_factory, key_id: str) -> dict | None:
    async with session_factory() as db:
        from database import ServiceApiKey
        k = await db.get(ServiceApiKey, key_id)
        if not k:
            return None
        return {"api_key": k.api_key, "base_url": k.base_url}


async def _fetch_native(url: str) -> str:
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; DrawScript-Crawler/1.0)"})
    resp.raise_for_status()
    return resp.text


# [FIRECRAWL_DISABLED] 以下两个函数为 Firecrawl 实现，暂不启用。
# async def _scrape_firecrawl_single(url, params, api_key, base_url): ...
# async def _crawl_firecrawl_recursive(url, params, api_key, base_url): ...


@NodeRegistry.register("crawl")
class CrawlNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        data = self.ctx.node.data
        params = data.get("params", {})
        output_var = (data.get("output_var") or "").strip()

        raw_url = params.get("url", "")
        url = interpolate_value(self.ctx.variables, raw_url)
        if not url:
            return NodeResult(success=False, error="Crawl node: URL is required")

        try:
            # [FIRECRAWL_DISABLED] Firecrawl 路径暂时屏蔽，仅使用原生 HTTP 爬取。
            # crawl_engine = data.get("crawl_engine", "native")
            # if crawl_engine == "firecrawl":
            #     ... Firecrawl 逻辑 ...
            html = await _fetch_native(url)
        except httpx.HTTPStatusError as e:
            return NodeResult(success=False, error=f"Crawl node: HTTP {e.response.status_code} — {e.response.text[:300]}")
        except Exception as e:
            return NodeResult(success=False, error=f"Crawl node: {e}")

        if output_var:
            self.ctx.variables[output_var] = html

        return NodeResult(success=True, output={output_var: html} if output_var else {"result": html})
