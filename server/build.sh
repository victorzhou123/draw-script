#!/bin/bash
# 构建 Draw-Script 服务端发行包
# 用法: bash server/build.sh [版本号]
#
# 输出: server/dist/draw-script-server-<VERSION>-linux-amd64.tar.gz
# 目标用户只需要 Python 3.10+，无需 Node.js 或 npm。
set -e
cd "$(dirname "$0")"

VERSION="${1:-0.1.0}"
DIST_NAME="draw-script-server-${VERSION}"
DIST_DIR="dist/${DIST_NAME}"

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

# 2. 准备发行目录
echo "[2/3] 准备发行目录..."
rm -rf "${DIST_DIR}"
mkdir -p "${DIST_DIR}"

# 复制 kernel 源码，排除缓存、数据库、.pid 文件
find kernel -type f \
    ! -path '*/__pycache__/*' \
    ! -name '*.pyc' \
    ! -name '*.db' \
    ! -name '*.db-shm' \
    ! -name '*.db-wal' \
    ! -name '.ocr_autostart' \
    ! -name 'start.sh' \
    | while IFS= read -r f; do
        dest="${DIST_DIR}/${f}"
        mkdir -p "$(dirname "$dest")"
        cp "$f" "$dest"
    done

# requirements 放到根目录，方便 start.sh 引用
cp kernel/requirements.txt "${DIST_DIR}/requirements.txt"

# 3. 生成 start.sh
echo "[3/3] 生成启动脚本..."
cat > "${DIST_DIR}/start.sh" << 'STARTSH'
#!/bin/bash
# Draw-Script 服务端启动脚本
# 首次运行时自动创建 Python 虚拟环境并安装依赖（需联网）
cd "$(dirname "$0")"

if [ ! -f .venv/bin/python ]; then
    echo "[setup] 首次运行，正在初始化 Python 环境（需要 Python 3.10+）..."
    python3 -m venv .venv
    echo "[setup] 安装依赖..."
    .venv/bin/pip install -r requirements.txt --quiet
    echo "[setup] 初始化完成"
    echo ""
fi

DS_LOG_LEVEL="${DS_LOG_LEVEL:-info}"
exec .venv/bin/python kernel/main.py "$@"
STARTSH
chmod +x "${DIST_DIR}/start.sh"

# 打包成 tar.gz
echo ""
echo "正在压缩..."
tar -czf "dist/${DIST_NAME}-linux-amd64.tar.gz" -C dist "${DIST_NAME}"

echo ""
echo "完成: dist/${DIST_NAME}-linux-amd64.tar.gz"
echo ""
echo "部署方法:"
echo "  tar -xzf ${DIST_NAME}-linux-amd64.tar.gz"
echo "  cd ${DIST_NAME}"
echo "  ./start.sh          # 首次运行自动安装依赖"
echo "  DS_LOG_LEVEL=debug ./start.sh   # 调试模式"
