import glob
import logging
import os
import socket
import sys

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.toml")

# Keep references alive so RemoveDllDirectory is never called by GC.
_dll_dir_handles: list = []


def _write_config(
    server_ip: str, server_port: str, client_id: str, client_name: str,
    dll_dirs: list[str],
) -> None:
    dll_lines = "\n".join('  "{}",'.format(d.replace("\\", "/")) for d in dll_dirs)
    content = (
        f'[server]\n'
        f'url = "ws://{server_ip}:{server_port}/ws/client"\n'
        f'\n'
        f'[client]\n'
        f'id = "{client_id}"\n'
        f'name = "{client_name}"\n'
        f'platform = "windows"\n'
        f'\n'
        f'[cuda]\n'
        f'# DLL 目录列表，Python 3.8+ 需要显式注册才能加载 CUDA/cuDNN\n'
        f'dll_dirs = [\n{dll_lines}\n]\n'
    )
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def _detect_dll_dirs() -> list[str]:
    """Auto-detect CUDA Toolkit and cuDNN DLL directories on this machine."""
    dirs: list[str] = []

    cuda_bins = sorted(
        glob.glob(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v*\bin"),
        reverse=True,
    )
    dirs.extend(cuda_bins)

    cudnn_pip = os.path.join(os.path.dirname(sys.executable), r"Lib\site-packages\nvidia\cudnn\bin")
    if os.path.isdir(cudnn_pip):
        dirs.append(cudnn_pip)

    return dirs


def register_dll_dirs(dll_dirs: list[str]) -> None:
    """Register CUDA/cuDNN DLL directories so cv2.pyd can load its dependencies.

    Only os.add_dll_directory is used — no sys.path injection. sys.path injection
    loads cv2.pyd as a bare top-level module, which prevents OpenCV from running
    PyImport_AddModule("cv2.cuda") correctly. Letting cv2 load via its own
    namespace package (__init__.py → from .cv2 import *) keeps the package
    structure intact and makes cv2.cuda accessible.
    """
    if sys.platform != "win32":
        return
    for d in dll_dirs:
        if os.path.isdir(d):
            _dll_dir_handles.append(os.add_dll_directory(d))
            logger.info(f"[CUDA] DLL 目录已注册: {d}")
        else:
            logger.warning(f"[CUDA] DLL 目录不存在，跳过: {d}")

    # The cudawarped rolling wheel has no __init__.py, so cv2/ is treated as a
    # namespace package and cv2.pyd is never loaded automatically. Insert the
    # cv2 package directory into sys.path[0] so "import cv2" finds cv2.pyd
    # directly instead of the namespace package.
    import site
    for sp in site.getsitepackages():
        cv2_dir = os.path.join(sp, "cv2")
        if os.path.isfile(os.path.join(cv2_dir, "cv2.pyd")):
            cv2_keys = [k for k in sys.modules if k == "cv2" or k.startswith("cv2.")]
            for k in cv2_keys:
                sys.modules.pop(k, None)
            if cv2_dir not in sys.path:
                sys.path.insert(0, cv2_dir)
            logger.info(f"[CUDA] cv2.pyd sys.path 已注入: {cv2_dir}")
            break


def check_cuda() -> None:
    """Probe CUDA availability at startup and print a clear status line."""
    try:
        import cv2
        count = cv2.cuda.getCudaEnabledDeviceCount()
        if count > 0:
            logger.info(f"[CUDA] 可用 — 检测到 {count} 个 CUDA GPU (OpenCV {cv2.__version__})")
        else:
            logger.warning("[CUDA] 不可用 — 未检测到 CUDA 设备，GPU加速开关将自动回退CPU")
    except AttributeError:
        logger.warning("[CUDA] 不可用 — 当前 OpenCV 未编译 CUDA 支持（缺少 cv2.cuda 模块），GPU加速开关将自动回退CPU")
    except Exception as e:
        logger.warning(f"[CUDA] 检测失败: {type(e).__name__}: {e}，GPU加速开关将自动回退CPU")


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

    detected = _detect_dll_dirs()
    if detected:
        print()
        print("  检测到以下 CUDA/cuDNN 目录，将自动写入配置：")
        for d in detected:
            print(f"    {d}")
    else:
        print()
        print("  未检测到 CUDA/cuDNN 目录，GPU 加速将不可用")
        print("  如需启用，请安装后手动编辑 config.toml 的 [cuda] dll_dirs")

    _write_config(server_ip, server_port, client_id, client_name, detected)

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
                "cuda": {"dll_dirs": []},
            }

    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)
