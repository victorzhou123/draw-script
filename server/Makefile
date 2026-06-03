SHELL   := /bin/bash
ROOT    := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
KERNEL  := $(ROOT)kernel
WEB     := $(ROOT)web
LOG     := $(ROOT)server.log
BPID    := $(ROOT).backend.pid
FPID    := $(ROOT).frontend.pid

.PHONY: prod dev dev-bg stop

prod:
	@echo "[prod] 构建前端..."
	@cd "$(WEB)" && npm install --silent && npm run build
	@echo "[prod] 后台启动后端 (info)..."
	@cd "$(KERNEL)" && DS_LOG_LEVEL=info python3 main.py >> "$(LOG)" 2>&1 & echo $$! > "$(BPID)"
	@echo "[prod] 已启动 PID=$$(cat $(BPID))  日志: $(LOG)"

dev:
	@cleanup() { echo ""; echo "停止服务..."; kill "$$BACKEND" "$$FRONTEND" 2>/dev/null; wait; }; \
	trap cleanup EXIT INT TERM; \
	echo "[dev] 启动后端 (debug, http://localhost:9001)..."; \
	(cd "$(KERNEL)" && DS_LOG_LEVEL=debug DS_RELOAD=true python3 main.py) & BACKEND=$$!; \
	echo "[dev] 启动前端 Vite (http://localhost:5173)..."; \
	(cd "$(WEB)" && npm run dev) & FRONTEND=$$!; \
	echo "按 Ctrl+C 停止所有服务"; \
	wait

dev-bg:
	@echo "[dev-bg] 后台启动后端 (debug)..."
	@cd "$(KERNEL)" && DS_LOG_LEVEL=debug DS_RELOAD=true python3 main.py >> "$(LOG)" 2>&1 & echo $$! > "$(BPID)"
	@echo "[dev-bg] 后台启动前端 Vite..."
	@cd "$(WEB)" && npm run dev >> "$(LOG)" 2>&1 & echo $$! > "$(FPID)"
	@echo "[dev-bg] 已启动  日志: $(LOG)"

stop:
	@stopped=0; \
	if [ -f "$(BPID)" ]; then \
		kill $$(cat "$(BPID)") 2>/dev/null && echo "后端已停止" || echo "后端进程不存在"; \
		rm -f "$(BPID)"; \
		stopped=1; \
	fi; \
	if [ -f "$(FPID)" ]; then \
		kill $$(cat "$(FPID)") 2>/dev/null && echo "前端已停止" || echo "前端进程不存在"; \
		rm -f "$(FPID)"; \
		stopped=1; \
	fi; \
	[ "$$stopped" = "0" ] && echo "没有正在运行的服务" || true
