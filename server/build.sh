#!/bin/bash
# 构建 Draw-Script 服务端发行包（PyInstaller 独立二进制，无需目标机安装 Python）
# 用法: bash server/build.sh [版本号]
#
# 输出: server/dist/draw-script-server-<VERSION>-linux-amd64.tar.gz
set -e
cd "$(dirname "$0")"

VERSION="${1:-0.1.0}"
DIST_NAME="draw-script-server-${VERSION}"

echo "============================================"
echo "  Draw-Script 服务端打包  v${VERSION}"
echo "============================================"

# 1. 构建前端（生成 kernel/static/）
echo ""
echo "[1/3] 构建前端..."
cd web
npm install --silent
npm run build
cd ..

# 2. 安装打包工具和服务端依赖
echo "[2/3] 安装依赖 & PyInstaller..."
pip3 install pyinstaller pyinstaller-hooks-contrib --quiet
pip3 install -r kernel/requirements.txt --quiet

# 3. PyInstaller 打包
echo "[3/3] PyInstaller 打包（首次较慢，约 1-3 分钟）..."
pyinstaller draw-script-server.spec --noconfirm

# 重命名输出目录并加入启动脚本
mv dist/draw-script-server "dist/${DIST_NAME}"

cat > "dist/${DIST_NAME}/start.sh" << 'STARTSH'
#!/bin/bash
# Draw-Script 服务端启动脚本（无需安装 Python）
cd "$(dirname "$0")"
DS_LOG_LEVEL="${DS_LOG_LEVEL:-info}" exec ./draw-script-server "$@"
STARTSH
chmod +x "dist/${DIST_NAME}/start.sh"

# 打包成 tar.gz
echo ""
echo "正在压缩..."
tar -czf "dist/${DIST_NAME}-linux-amd64.tar.gz" -C dist "${DIST_NAME}"

echo ""
echo "完成: dist/${DIST_NAME}-linux-amd64.tar.gz"
echo ""
echo "部署方法（目标机无需安装 Python/Node）:"
echo "  tar -xzf ${DIST_NAME}-linux-amd64.tar.gz"
echo "  cd ${DIST_NAME}"
echo "  ./start.sh"
