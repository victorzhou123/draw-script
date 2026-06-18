import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

from config_utils import load_config, register_dll_dirs, check_cuda


async def main() -> None:
    from connection import DrawScriptAgent

    config = load_config()
    server_url = config["server"]["url"]
    client_cfg = config["client"]

    # Only initialize CUDA if the user has explicitly configured dll_dirs.
    # Clients without gpu_enabled never need CUDA setup.
    dll_dirs = config.get("cuda", {}).get("dll_dirs", [])
    if dll_dirs:
        register_dll_dirs(dll_dirs)
        check_cuda()

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
