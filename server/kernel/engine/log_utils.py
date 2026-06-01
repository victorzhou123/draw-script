import re

_B64_RE = re.compile(r'^[A-Za-z0-9+/\-_]+=*$')
_TRUNCATE_THRESHOLD = 100


def truncate_for_log(v):
    """Recursively shorten base64/long strings so they don't flood execution logs."""
    if isinstance(v, str) and len(v) > _TRUNCATE_THRESHOLD:
        if _B64_RE.match(v):
            return f"<base64 {len(v)}chars>"
        return f"{v[:60]}...[{len(v)}chars]"
    if isinstance(v, dict):
        return {k: truncate_for_log(vv) for k, vv in v.items()}
    if isinstance(v, list):
        return [truncate_for_log(item) for item in v]
    return v
