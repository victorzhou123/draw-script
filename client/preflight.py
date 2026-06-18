"""
Pre-flight check: initialises config (prompts on first run) then queries the
server for this client's gpu_enabled flag to select the right requirements.

Exit codes
  0  →  CPU mode / server unreachable / unknown  →  requirements.txt
  1  →  gpu_enabled = true                       →  requirements-cuda.txt
"""
import json
import logging
import sys
import urllib.error
import urllib.request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _ws_to_http_base(ws_url: str) -> str:
    """ws://host:port/ws/client  →  http://host:port"""
    if ws_url.startswith("wss://"):
        http = "https://" + ws_url[6:]
    else:
        http = "http://" + ws_url[5:]
    return http.rsplit("/ws/", 1)[0]


def main() -> None:
    from config_utils import load_config

    try:
        config = load_config()
    except SystemExit:
        sys.exit(0)

    client_id = config["client"].get("id", "")
    if not client_id:
        logger.warning("[preflight] 未找到 client_id，跳过 GPU 检查")
        sys.exit(0)

    http_base = _ws_to_http_base(config["server"]["url"])
    api_url = f"{http_base}/api/clients/{client_id}"

    try:
        with urllib.request.urlopen(api_url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        if data.get("gpu_enabled"):
            logger.info("[preflight] gpu模式，安装 CUDA 依赖...")
            sys.exit(1)
        else:
            logger.info("[preflight] cpu模式，安装基础依赖...")
            sys.exit(0)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            logger.info("[preflight] cpu模式，安装基础依赖...")
        else:
            logger.warning(f"[preflight] 服务端返回错误 HTTP {e.code}，使用基础模式")
        sys.exit(0)
    except Exception as e:
        logger.warning(f"[preflight] 无法连接服务端，使用基础模式: {e}")
        sys.exit(0)


if __name__ == "__main__":
    main()
