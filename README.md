<div align="center">

# DrawScript

**用流程图编写自动化脚本，让 Windows 桌面自动化更直观**

[English](./README_en.md) | 简体中文

<!-- 放一张流程图编辑器的截图，建议尺寸 1280×720，路径: docs/screenshots/editor.png -->
<!-- ![DrawScript Editor](./docs/screenshots/editor.png) -->

</div>

---

DrawScript 是一个可视化 RPA（机器人流程自动化）系统。你在浏览器里用拖拽方式画出流程图，服务端解析并驱动远程 Windows 客户端执行鼠标点击、键盘输入、图像识别等操作，无需在目标机器上安装复杂环境。

> **适合人群：** 想自动化重复性桌面操作的普通用户，以及希望用可视化方式管理自动化脚本的开发者 / 测试工程师。

---

## ✨ 核心特性

### 可视化流程编辑
- 基于 **AntV X6** 的拖拽式流程图编辑器，所见即所得
- 支持分支（条件节点）、循环、子脚本调用
- 执行时实时高亮当前运行节点，直观反馈执行状态

### 丰富的节点类型

| 分类 | 节点 | 说明 |
|------|------|------|
| 流程控制 | 开始 / 结束 | 流程入口与出口 |
| 流程控制 | 条件 | IF / ELSE 分支，支持多条件 AND / OR 组合 |
| 流程控制 | 循环 | 计数循环，支持变量控制次数 |
| 流程控制 | 子脚本 | 调用其他脚本，支持变量输入输出映射 |
| 桌面操作 | 动作 | 鼠标点击 / 双击 / 移动 / 拖拽 / 滚轮，键盘输入 / 热键 / 按键 |
| 桌面操作 | 截图 | 截取客户端屏幕并存入变量 |
| 桌面操作 | 等待 | 延时等待或等待条件满足 |
| 图像识别 | 视觉 | 模板匹配 / OCR / AI 视觉 / 颜色检测（见下方） |
| 数据处理 | 计算 | 在客户端执行任意 Python 代码 |
| 数据处理 | 变量 | 设置 / 修改全局变量，支持类型声明 |
| 网络 | HTTP | 发送 HTTP 请求，支持 `{{变量}}` 模板插值 |
| 网络 | 网页爬取 | CSS / XPath 选择器提取，或对接 Firecrawl API |
| 上下文 | 上下文编辑 | 读写执行上下文变量 |

### 四种 CV 图像识别后端

| 后端 | 技术 | 典型用途 |
|------|------|----------|
| 模板匹配 | OpenCV | 查找固定图标、按钮位置 |
| OCR | PaddleOCR | 读取屏幕文字 |
| AI 视觉 | Qwen-VL 等多模态大模型 | 理解复杂界面、自然语言定位元素 |
| 颜色检测 | OpenCV HSV | 检测特定颜色区域 |

### 多客户端管理
- 一个服务端可同时管理多台 Windows 客户端
- 脚本绑定到指定客户端执行，互不干扰

### 持久化执行日志
- 每次运行的日志写入 SQLite，支持多维查询
- 可从日志直接定位到流程图中对应节点

---

## 🏗️ 架构概览

```
┌─────────────────────────────────────────┐
│             浏览器（编辑端）              │
│   Vue 3 + AntV X6 + Ant Design Vue     │
│           http://localhost:9001         │
└──────────────┬──────────────────────────┘
               │  HTTP / WebSocket (/ws/ui)
┌──────────────▼──────────────────────────┐
│           服务端 (Linux / Mac / Win)     │
│    Python + FastAPI + SQLite            │
│    · 脚本存储 & 解析                     │
│    · 流程引擎执行                        │
│    · CV 推理（模板匹配 / OCR / AI）      │
└──────────────┬──────────────────────────┘
               │  WebSocket (/ws/client)
┌──────────────▼──────────────────────────┐
│        Windows 客户端代理               │
│   Python + PyAutoGUI                   │
│   · 执行鼠标 / 键盘指令                  │
│   · 截图上传                            │
│   · 运行 Python 计算节点                 │
└─────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 方式一：发行版本启动（推荐）

> 无需在目标机器安装 Python 或 Node.js，下载即可运行。

#### 1. 启动服务端（Linux）

从 [GitHub Releases](https://github.com/victorzhou123/draw-script/releases/latest) 下载 `draw-script-server-{版本号}-linux-amd64.tar.gz`，解压后启动：

```bash
tar -xzf draw-script-server-{版本号}-linux-amd64.tar.gz
cd draw-script-server-{版本号}
./start.sh
```

浏览器访问 `http://localhost:9001`。

如需自定义端口或日志级别，通过环境变量传入：

```bash
DS_PORT=8080 DS_LOG_LEVEL=debug ./start.sh
```

#### 2. 启动 Windows 客户端

从 [GitHub Releases](https://github.com/victorzhou123/draw-script/releases/latest) 下载 `draw-script-client-{版本号}-windows-amd64.zip`，解压后直接运行：

```
draw-script-client.exe
```

首次运行会出现**交互式配置向导**：输入服务端 IP / 端口、本机唯一 ID 和显示名称，CUDA DLL 目录自动检测。配置保存在同目录的 `config.toml`，之后启动直接读取。

> **注意：** 发行版客户端为 CPU 模式，OpenCV GPU 加速不可用。如需 CUDA 支持，请使用源码开发方式启动。

---

### 方式二：源码开发

> 需要 Python 3.10+、Node.js 18+（服务端），以及 Python 3.10+（Windows 客户端）。

#### 1. 启动服务端

**第一步：一次性环境搭建**

```bash
git clone https://github.com/victorzhou123/draw-script.git
cd draw-script/server

# 安装后端 Python 依赖（仅需执行一次）
pip install -r kernel/requirements.txt
```

**第二步：选择启动模式**

```bash
# 生产模式（推荐部署使用）
make prod
# · 自动构建前端（npm install + npm run build）
# · 后端在后台运行，日志写入 server.log（info 级别）
# · 浏览器访问 http://localhost:9001

# 开发模式（前台，支持热重载）
make dev
# · 后端前台运行，debug 日志输出到终端，代码改动自动重启
# · Vite 前端开发服务器同步启动（http://localhost:5173）
# · Ctrl+C 同时停止前后端

# 开发模式（后台）
make dev-bg
# · 前后端均在后台运行，日志写入 server.log
# · 适合远程 SSH 会话或不想占用终端的场景

# 停止所有服务
make stop
```

#### 2. 启动 Windows 客户端

将 `client/` 目录复制到 **Windows 机器**，直接运行：

```bat
start.bat
```

首次运行会自动完成：
1. 检测 Python 环境
2. **交互式配置引导**：输入服务端 IP / 端口、本机 ID 和显示名称，自动检测 CUDA DLL 目录
3. 根据服务端 GPU 设置自动安装对应依赖（CPU 版 / CUDA 版）
4. 启动客户端代理，连接服务端

之后每次运行 `start.bat` 会直接跳过配置步骤，自动更新依赖后启动。

---

### 创建第一个脚本

1. 打开浏览器访问服务端地址（默认 `http://localhost:9001`）
2. 在左侧边栏新建脚本
3. 从节点面板拖入 **开始** → **动作**（鼠标点击）→ **结束**
4. 点击动作节点，在右侧属性面板配置坐标
5. 顶部工具栏选择客户端，点击 **运行**
6. 观察 Windows 客户端执行鼠标操作，流程图中节点实时高亮

---

## ⚙️ 配置说明

### 服务端环境变量

服务端通过环境变量配置，Makefile 已为常用模式预设了合理默认值。如需手动启动或自定义配置：

```bash
# 示例：自定义端口和日志级别直接启动
cd server/kernel
DS_HOST=0.0.0.0 DS_PORT=8080 DS_LOG_LEVEL=debug python3 main.py
```

完整变量列表：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DS_HOST` | `0.0.0.0` | 监听地址 |
| `DS_PORT` | `9001` | 监听端口 |
| `DS_LOG_LEVEL` | `info` | 日志级别（`debug` / `info` / `warning`） |
| `DS_RELOAD` | `false` | 启用 uvicorn 热重载（开发用，设为 `true`） |
| `DS_DB_PATH` | `draw_script.db` | SQLite 数据库文件路径 |
| `DS_TEMPLATES_DIR` | `templates` | 模板图片存储目录 |
| `DS_AI_API_KEY` | — | AI 视觉默认 API Key（也可在 UI 配置中心配置） |
| `DS_AI_BASE_URL` | 阿里云 DashScope | AI 视觉 API Base URL |
| `DS_AI_MODEL` | `qwen-vl-plus` | 默认 AI 视觉模型 |

### 客户端配置（`client/config.toml`）

由首次运行向导自动生成，也可手动编辑：

```toml
[server]
url = "ws://YOUR_SERVER_IP:9001/ws/client"

[client]
id = "pc-001"       # 唯一标识，与服务端绑定脚本时对应
name = "PC-001"     # 显示名称
platform = "windows"

[cuda]
dll_dirs = []       # CUDA/cuDNN DLL 目录，首次运行自动检测填充
```

### AI 视觉 / Firecrawl API 密钥

在服务端 Web UI 的 **配置中心** 中添加 API Key，无需修改代码或环境变量。

---

## 🗺️ Roadmap

- [ ] 定时任务 / 计划执行
- [ ] 节点执行超时配置
- [ ] 脚本导入导出
- [ ] Linux / macOS 客户端支持
- [ ] 更多 CV 后端集成

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request。

添加新节点类型：在 `server/kernel/engine/nodes/` 新建文件，继承 `BaseNodeHandler` 并用 `@NodeRegistry.register("type_name")` 装饰器注册，前端在 `server/web/src/components/node-forms/` 添加对应的配置表单即可。

---

## 📄 License

<!-- TODO: 选择并添加 License -->
待定。
