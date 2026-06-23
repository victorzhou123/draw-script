# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包规格 — Draw-Script 服务端（Linux x86_64）
# 用法: 由 server/build.sh 自动调用，也可手动执行:
#   cd server && pyinstaller draw-script-server.spec --noconfirm
#
# 注意: 需要先构建前端（npm run build），使 kernel/static/ 存在。

from PyInstaller.utils.hooks import collect_all, collect_submodules

# 用 collect_all 收集有动态子模块的大包，避免遗漏
def _collect(*pkg_names):
    datas, binaries, hiddenimports = [], [], []
    for pkg in pkg_names:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    return datas, binaries, hiddenimports

_datas, _binaries, _hiddenimports = _collect(
    'uvicorn',
    'fastapi',
    'starlette',
    'sqlalchemy',
    'aiosqlite',
    'pydantic',
    'pydantic_core',
    'anyio',
    'httpx',
    'multipart',    # python-multipart
    'cv2',
    'numpy',
    'PIL',
    'bs4',
    'lxml',
    'cssselect',
    'websockets',
)

# 应用自身各模块（pathex 已加 kernel/，这里显式列出防止遗漏）
_app_modules = collect_submodules('routers') + collect_submodules('engine') + collect_submodules('cv')
_hiddenimports += _app_modules + [
    'config', 'database', 'dependencies', 'heartbeat',
    'log_handler', 'schemas', 'ws_manager', 'webhook_dispatcher',
]

a = Analysis(
    ['kernel/main.py'],
    pathex=['kernel'],          # 让 "from config import ..." 等内部导入正常工作
    binaries=_binaries,
    datas=_datas + [
        ('kernel/static', 'static'),   # 预构建的前端，打包进 _MEIPASS/static/
    ],
    hiddenimports=_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # OCR 可选，体积巨大，发行版不捆绑
        'paddle', 'paddlepaddle', 'paddleocr',
        # 开发工具
        'pytest', 'IPython', 'jupyter',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='draw-script-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='draw-script-server',
)
