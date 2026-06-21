import asyncio

import httpx

from engine.base_handler import BaseNodeHandler, NodeResult, interpolate_value
from engine.node_registry import NodeRegistry

_FIRECRAWL_DEFAULT_BASE = "https://api.firecrawl.dev"
_POLL_INTERVAL = 3
_POLL_TIMEOUT = 120


async def _get_service_key(session_factory, key_id: str) -> dict | None:
    async with session_factory() as db:
        from database import ServiceApiKey
        k = await db.get(ServiceApiKey, key_id)
        if not k:
            return None
        return {"api_key": k.api_key, "base_url": k.base_url}


def _extract_native(html: bytes | str, params: dict) -> dict | str:
    from lxml import html as lhtml

    if isinstance(html, bytes):
        root = lhtml.document_fromstring(html)
    else:
        root = lhtml.fromstring(html)
    if root is None:
        raise ValueError("HTML 解析失败：响应内容为空或无法识别")

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
            if sel_type == "xpath":
                matches = root.xpath(selector)
            else:
                matches = root.cssselect(selector)
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

    # single selector mode — always returns str
    sel_type = params.get("selector_type", "css")
    selector = (params.get("selector") or "").strip()

    if sel_type == "xpath":
        matches = root.xpath(selector)
    else:
        matches = root.cssselect(selector)

    texts = []
    for el in matches:
        if isinstance(el, str):
            texts.append(el)
        elif hasattr(el, "text_content"):
            texts.append(el.text_content().strip())

    return "\n".join(texts)


async def _scrape_native(url: str, params: dict) -> dict:
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; DrawScript-Crawler/1.0)"})
    resp.raise_for_status()

    selector_mode = params.get("selector_mode", "single")
    has_selector = (
        selector_mode == "multi_field" and params.get("fields")
    ) or (
        selector_mode == "single" and (params.get("selector") or "").strip()
    )

    if has_selector:
        extracted = _extract_native(resp.content, params)
        return {"url": url, "content": extracted}

    return {"url": url, "content": resp.text}


async def _scrape_firecrawl_single(url: str, params: dict, api_key: str, base_url: str) -> dict:
    output_format = params.get("output_format", "markdown")
    formats = [output_format] if output_format in ("markdown", "html", "rawHtml", "links", "screenshot") else ["markdown"]

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{base_url.rstrip('/')}/v1/scrape",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"url": url, "formats": formats},
        )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(data.get("error", "Firecrawl scrape failed"))
    return data.get("data", {})


async def _crawl_firecrawl_recursive(url: str, params: dict, api_key: str, base_url: str) -> list:
    output_format = params.get("output_format", "markdown")
    formats = [output_format] if output_format in ("markdown", "html", "rawHtml", "links") else ["markdown"]
    max_depth = int(params.get("max_depth", 2))
    limit = int(params.get("limit", 10))
    url_filter = (params.get("url_filter") or "").strip()

    crawl_body: dict = {"url": url, "maxDepth": max_depth, "limit": limit, "scrapeOptions": {"formats": formats}}
    if url_filter:
        crawl_body["includePaths"] = [url_filter]

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    burl = base_url.rstrip("/")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{burl}/v1/crawl", headers=headers, json=crawl_body)
    resp.raise_for_status()
    job = resp.json()

    if not job.get("success"):
        raise RuntimeError(job.get("error", "Firecrawl crawl job failed to start"))

    job_id = job.get("id")
    if not job_id:
        raise RuntimeError("Firecrawl did not return a job ID")

    # Poll until done
    elapsed = 0
    async with httpx.AsyncClient(timeout=30) as client:
        while elapsed < _POLL_TIMEOUT:
            await asyncio.sleep(_POLL_INTERVAL)
            elapsed += _POLL_INTERVAL
            status_resp = await client.get(f"{burl}/v1/crawl/{job_id}", headers=headers)
            status_resp.raise_for_status()
            status_data = status_resp.json()
            if status_data.get("status") == "completed":
                return status_data.get("data", [])
            if status_data.get("status") == "failed":
                raise RuntimeError(f"Firecrawl crawl failed: {status_data.get('error', '')}")

    raise RuntimeError(f"Firecrawl crawl timed out after {_POLL_TIMEOUT}s")


@NodeRegistry.register("crawl")
class CrawlNodeHandler(BaseNodeHandler):
    async def execute(self) -> NodeResult:
        data = self.ctx.node.data
        params = data.get("params", {})
        crawl_engine = data.get("crawl_engine", "native")
        output_var = (data.get("output_var") or "").strip()

        raw_url = params.get("url", "")
        url = interpolate_value(self.ctx.variables, raw_url)
        if not url:
            return NodeResult(success=False, error="Crawl node: URL is required")

        try:
            if crawl_engine == "firecrawl":
                service_key_id = (params.get("service_key_id") or "").strip()
                if not service_key_id:
                    return NodeResult(success=False, error="Crawl node: Firecrawl 模式需要选择 API Key 配置")

                svc = await _get_service_key(self.ctx.session_factory, service_key_id)
                if not svc:
                    return NodeResult(success=False, error=f"Crawl node: 找不到服务 Key（id={service_key_id}）")

                api_key = svc["api_key"]
                base_url = svc["base_url"].strip() or _FIRECRAWL_DEFAULT_BASE

                crawl_type = params.get("crawl_type", "single")
                if crawl_type == "recursive":
                    result = await _crawl_firecrawl_recursive(url, params, api_key, base_url)
                else:
                    result = await _scrape_firecrawl_single(url, params, api_key, base_url)
            else:
                result = await _scrape_native(url, params)

        except httpx.HTTPStatusError as e:
            return NodeResult(success=False, error=f"Crawl node: HTTP {e.response.status_code} — {e.response.text[:300]}")
        except Exception as e:
            return NodeResult(success=False, error=f"Crawl node: {e}")

        stored = result.get("content", result) if isinstance(result, dict) else result
        if output_var:
            self.ctx.variables[output_var] = stored

        return NodeResult(success=True, output={output_var: stored} if output_var else {"result": result})
