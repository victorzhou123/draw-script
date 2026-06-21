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

### 环境要求

- **服务端**：Python 3.10+，Node.js 18+
- **客户端**：Windows 10/11，Python 3.10+

---

### 1. 启动服务端

```bash
git clone https://github.com/<your-username>/draw-script.git
cd draw-script/server

# 安装后端依赖
pip install -r kernel/requirements.txt

# 安装前端依赖并构建（生产模式）
cd web && npm install && npm run build && cd ..

# 启动（生产模式，访问 http://localhost:9001）
make prod
```

**开发模式**（前后端热重载）：

```bash
make dev
# 后端: http://localhost:9001
# 前端 Vite: http://localhost:5173
```

---

### 2. 启动 Windows 客户端

在 **Windows 机器**上操作：

```bash
# 安装依赖
pip install -r requirements.txt

# 编辑配置文件，填写服务端地址和客户端 ID
# 编辑 config.toml:
# [server]
# url = "ws://YOUR_SERVER_IP:9001/ws/client"
# [client]
# id = "pc-001"
# name = "PC-001"

# 启动（双击或命令行）
start.bat
```

> **启用 CUDA 加速**（PaddleOCR 等 CV 功能）：参见 [CUDA 安装指南](./docs/cuda-setup.md)（需手动安装对应 CUDA 版本的 OpenCV wheel）。

---

### 3. 创建第一个脚本

1. 打开浏览器访问服务端地址
2. 在左侧边栏新建脚本
3. 从节点面板拖入 **开始** → **动作**（鼠标点击）→ **结束**
4. 点击动作节点，在右侧属性面板配置坐标
5. 顶部工具栏选择客户端，点击 **运行**
6. 观察 Windows 客户端执行鼠标操作，流程图中节点实时高亮

---

## ⚙️ 配置说明

### 服务端环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DS_LOG_LEVEL` | `info` | 日志级别（`debug` / `info` / `warning`） |
| `DS_RELOAD` | `false` | 是否启用 uvicorn 热重载（开发用） |

### 客户端配置（`client/config.toml`）

```toml
[server]
url = "ws://127.0.0.1:9001/ws/client"

[client]
id = "pc-001"       # 唯一标识，与服务端绑定脚本时对应
name = "PC-001"     # 显示名称
platform = "windows"
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
