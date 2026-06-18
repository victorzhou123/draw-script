@echo off
chcp 65001 >nul 2>&1
setlocal

echo ============================================
echo     Draw-Script 客户端启动器
echo ============================================
echo.

:: 检测 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10 或更高版本。
    echo 下载地址: https://www.python.org/downloads/
    echo 安装时请勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

:: 初始化配置（首次运行时交互引导），并查询服务端 GPU 设置
echo 正在检查配置...
python preflight.py
set GPU_MODE=%errorlevel%

:: 根据 GPU 模式安装对应依赖
if %GPU_MODE%==1 (
    pip uninstall opencv-python -y >nul 2>&1
    echo 正在安装 CUDA 依赖...
    pip install -r requirements-cuda.txt --quiet
) else (
    echo 正在安装基础依赖...
    pip install -r requirements.txt --quiet
)

if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络连接后重试。
    echo.
    pause
    exit /b 1
)

echo 依赖就绪，正在启动...
echo.

:: 启动客户端
python agent.py

echo.
echo 客户端已退出。
pause
