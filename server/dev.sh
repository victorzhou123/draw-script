#!/bin/bash
# 开发模式启动：后端 (9001) + Vite dev server (5173)
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
KERNEL="$ROOT/kernel"
WEB="$ROOT/web"

cleanup() {
  echo ""
  echo "正在停止所有服务..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  echo "已退出。"
}
trap cleanup EXIT INT TERM

# 后端
echo "[后端] 启动 FastAPI (http://localhost:9001)..."
cd "$KERNEL"
python3 main.py &
BACKEND_PID=$!

# 前端
echo "[前端] 启动 Vite dev server (http://localhost:5173)..."
cd "$WEB"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "  后端:  http://localhost:9001"
echo "  前端:  http://localhost:5173"
echo ""
echo "按 Ctrl+C 停止所有服务"

wait
