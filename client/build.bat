@echo off
chcp 65001 >nul 2>&1
setlocal

echo ============================================
echo     Draw-Script 客户端打包
echo ============================================
echo.
echo 此脚本使用 PyInstaller 将客户端打包为独立 .exe
echo 打包后用户无需安装 Python 即可运行。
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10 或更高版本。
    pause & exit /b 1
)

:: 安装 PyInstaller
pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo 正在安装 PyInstaller...
    pip install pyinstaller --quiet
    if errorlevel 1 (
        echo [错误] PyInstaller 安装失败。
        pause & exit /b 1
    )
)

:: 安装客户端依赖（CPU 模式，不含 CUDA）
echo 正在安装客户端依赖（CPU 模式）...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络连接。
    pause & exit /b 1
)

:: 运行 PyInstaller
echo.
echo 开始打包...
pyinstaller draw-script-client.spec --noconfirm
if errorlevel 1 (
    echo [错误] 打包失败，请查看上方错误信息。
    pause & exit /b 1
)

echo.
echo ============================================
echo  打包完成！
echo  发行文件位于: dist\draw-script-client\
echo.
echo  将整个 dist\draw-script-client\ 文件夹
echo  发送给用户，用户运行其中的 draw-script-client.exe 即可。
echo ============================================
echo.
pause
