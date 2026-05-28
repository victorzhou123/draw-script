import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def load_config() -> dict:
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

    import os
    config_path = os.path.join(os.path.dirname(__file__), "config.toml")
    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        logger.warning(f"config.toml not found at {config_path}, using defaults")
        return {
            "server": {"url": "ws://127.0.0.1:9001/ws/client"},
            "client": {"id": "pc-001", "name": "PC-001", "platform": "windows"},
        }


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
