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
    echo [错误] 未检测到 Python，请先安装 Python 3.8 或更高版本。
    echo 下载地址: https://www.python.org/downloads/
    echo 安装时请勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

:: 安装依赖
echo 正在检查依赖包...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络连接后重试。
    echo 也可手动运行: pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo 依赖就绪，正在启动...
echo.

:: 启动客户端（首次运行时会引导配置服务端 IP）
python agent.py

echo.
echo 客户端已退出。
pause
