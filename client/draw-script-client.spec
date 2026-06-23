# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包规格文件 - Draw-Script 客户端（CPU 模式）
# 用法: pyinstaller draw-script-client.spec --noconfirm
# 输出: dist/draw-script-client/ 文件夹，发给用户时整个文件夹一起打包即可。

a = Analysis(
    ['agent.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[
        # pyautogui 及其依赖
        'pyautogui',
        'pyscreeze',
        'pygetwindow',
        'pymsgbox',
        'mouseinfo',
        # Pillow
        'PIL',
        'PIL.Image',
        'PIL.ImageGrab',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        # cv2 (CPU only)
        'cv2',
        # websockets
        'websockets',
        'websockets.legacy',
        'websockets.legacy.client',
        'websockets.legacy.protocol',
        # psutil, pyperclip
        'psutil',
        'pyperclip',
        # TOML 解析：tomllib 是 Python 3.11+ 内置，3.10 用 tomli 作为 fallback
        # 两者都写进来，PyInstaller 打包哪个取决于构建时的 Python 版本
        'tomllib',
        'tomli',
        # Windows 键鼠控制依赖（pyautogui 用到）
        'pynput',
        'pynput.keyboard',
        'pynput.keyboard._win32',
        'pynput.mouse',
        'pynput.mouse._win32',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除 CUDA / GPU 相关，保持体积小
        'torch',
        'tensorflow',
        'paddlepaddle',
        'paddle',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='draw-script-client',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,        # 保留控制台窗口，方便查看日志
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
    name='draw-script-client',
)
