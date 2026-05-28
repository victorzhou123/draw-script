import asyncio
import logging
import os
import socket
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.toml")


def _write_config(server_ip: str, server_port: str, client_id: str, client_name: str) -> None:
    content = (
        f'[server]\n'
        f'url = "ws://{server_ip}:{server_port}/ws/client"\n'
        f'\n'
        f'[client]\n'
        f'id = "{client_id}"\n'
        f'name = "{client_name}"\n'
        f'platform = "windows"\n'
    )
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def setup_first_run() -> None:
    print("=" * 50)
    print("  Draw-Script 客户端 — 首次配置")
    print("=" * 50)
    print()

    server_ip = input("请输入服务端 IP 地址（例如 192.168.1.100）: ").strip()
    if not server_ip:
        print("[错误] 服务端 IP 不能为空")
        sys.exit(1)

    port_input = input("请输入服务端端口 [默认 9001]: ").strip()
    server_port = port_input if port_input else "9001"

    default_id = socket.gethostname().lower().replace(" ", "-")
    id_input = input(f"请输入本机唯一 ID [默认 {default_id}]: ").strip()
    client_id = id_input if id_input else default_id

    default_name = socket.gethostname()
    name_input = input(f"请输入本机显示名称 [默认 {default_name}]: ").strip()
    client_name = name_input if name_input else default_name

    _write_config(server_ip, server_port, client_id, client_name)

    print()
    print(f"  配置已保存到 config.toml")
    print(f"  服务端地址: ws://{server_ip}:{server_port}/ws/client")
    print(f"  客户端 ID:  {client_id}")
    print(f"  客户端名称: {client_name}")
    print()


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        setup_first_run()

    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            logger.warning("tomllib not available, using defaults")
            return {
                "server": {"url": "ws://127.0.0.1:9001/ws/client"},
                "client": {"id": "pc-001", "name": "PC-001", "platform": "windows"},
            }

    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


async def main() -> None:
    from connection import DrawScriptAgent

    config = load_config()
    server_url = config["server"]["url"]
    client_cfg = config["client"]

    agent = DrawScriptAgent(
        server_url=server_url,
        client_id=client_cfg.get("id", "pc-001"),
        name=client_cfg.get("name", "PC-001"),
        platform=client_cfg.get("platform", "windows"),
    )

    logger.info(f"Draw-Script client agent starting (ID: {client_cfg.get('id')})")
    await agent.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Agent stopped by user")
        sys.exit(0)
