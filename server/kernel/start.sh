#!/bin/bash
# 启动 Draw-Script 服务端
cd "$(dirname "$0")"
pip install -r requirements.txt --quiet
python3 main.py
