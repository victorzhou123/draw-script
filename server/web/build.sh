#!/bin/bash
# 构建前端并输出到 server/kernel/static
cd "$(dirname "$0")"
npm install
npm run build
echo "✅ 前端构建完成，已输出到 ../kernel/static/"
