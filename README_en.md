<div align="center">

# DrawScript

**Visual flow-based automation for Windows desktop — draw your script, run it anywhere.**

English | [简体中文](./README.md)

<!-- Screenshot of the flow editor, recommended size 1280×720, path: docs/screenshots/editor.png -->
<!-- ![DrawScript Editor](./docs/screenshots/editor.png) -->

</div>

---

DrawScript is a visual RPA (Robotic Process Automation) system. Design automation workflows by dragging and connecting nodes in a browser-based flowchart editor. The server parses the flow and drives a lightweight Python agent on a remote Windows machine to perform mouse clicks, keyboard input, image recognition, and more — no heavy installation required on the target machine.

> **Who it's for:** Anyone who wants to automate repetitive desktop tasks, from non-programmers who prefer a visual approach to developers and QA engineers who want structured, reusable automation scripts.

---

## ✨ Features

### Visual Flow Editor
- Drag-and-drop flowchart editor powered by **AntV X6**
- Branching (condition nodes), loops, and sub-script calls
- Live node highlighting during execution for real-time feedback

### Rich Node Library

| Category | Node | Description |
|----------|------|-------------|
| Control flow | Start / End | Flow entry and exit |
| Control flow | Condition | IF / ELSE branching with multi-condition AND / OR logic |
| Control flow | Loop | Counted loops; loop count can come from a variable |
| Control flow | Script | Call another script; supports variable input/output mapping |
| Desktop | Action | Mouse click / double-click / move / drag / scroll; keyboard type / hotkey / key press |
| Desktop | Screenshot | Capture the client screen and store as a variable |
| Desktop | Wait / Delay | Timed delay or wait for a condition |
| Vision | Vision | Template match / OCR / AI vision / color detection (see below) |
| Data | Compute | Run arbitrary Python code on the client |
| Data | Variable | Set / modify typed global variables |
| Network | HTTP | Send HTTP requests with `{{variable}}` template interpolation |
| Network | Crawl | Extract data with CSS / XPath selectors, or via the Firecrawl API |
| Context | Context Edit | Read and write execution context variables |

### Four Computer Vision Backends

| Backend | Technology | Typical Use |
|---------|-----------|-------------|
| Template matching | OpenCV | Locate fixed icons or buttons |
| OCR | PaddleOCR | Read text from the screen |
| AI vision | Qwen-VL and other multimodal LLMs | Understand complex UI; locate elements with natural language |
| Color detection | OpenCV HSV | Detect specific color regions |

### Multi-client Management
- One server controls multiple Windows clients simultaneously
- Scripts are bound to a specific client; executions are isolated

### Persistent Execution Logs
- Every run is logged to SQLite with multi-dimension query support
- Jump from a log entry directly to the corresponding node in the flow editor

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│            Browser (Editor)             │
│   Vue 3 + AntV X6 + Ant Design Vue     │
│           http://localhost:9001         │
└──────────────┬──────────────────────────┘
               │  HTTP / WebSocket (/ws/ui)
┌──────────────▼──────────────────────────┐
│         Server (Linux / Mac / Win)      │
│    Python + FastAPI + SQLite            │
│    · Script storage & parsing           │
│    · Flow execution engine              │
│    · CV inference (template / OCR / AI) │
└──────────────┬──────────────────────────┘
               │  WebSocket (/ws/client)
┌──────────────▼──────────────────────────┐
│          Windows Client Agent           │
│   Python + PyAutoGUI                   │
│   · Execute mouse / keyboard commands   │
│   · Upload screenshots                  │
│   · Run Python compute nodes            │
└─────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Requirements

- **Server**: Python 3.10+, Node.js 18+
- **Client**: Windows 10/11, Python 3.10+

---

### 1. Start the Server

```bash
git clone https://github.com/<your-username>/draw-script.git
cd draw-script/server

# Install backend dependencies
pip install -r kernel/requirements.txt

# Install frontend dependencies and build (production)
cd web && npm install && npm run build && cd ..

# Start (production mode, access at http://localhost:9001)
make prod
```

**Development mode** (hot reload for both frontend and backend):

```bash
make dev
# Backend:  http://localhost:9001
# Frontend Vite: http://localhost:5173
```

---

### 2. Start the Windows Client Agent

On the **Windows machine**:

```bash
# Install dependencies
pip install -r requirements.txt

# Edit config.toml — set your server address and a unique client ID
# [server]
# url = "ws://YOUR_SERVER_IP:9001/ws/client"
# [client]
# id = "pc-001"
# name = "PC-001"

# Launch (double-click or from command line)
start.bat
```

> **CUDA acceleration** (for PaddleOCR and other CV features): see the [CUDA Setup Guide](./docs/cuda-setup.md). You need to manually install the matching OpenCV CUDA wheel before running `start.bat`.

---

### 3. Create Your First Script

1. Open the server URL in your browser
2. Create a new script in the left sidebar
3. Drag in **Start** → **Action** (mouse click) → **End**
4. Click the Action node and configure the target coordinates in the right panel
5. Select a client in the toolbar and click **Run**
6. Watch the Windows client move the mouse while the active node highlights in real time

---

## ⚙️ Configuration

### Server Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DS_LOG_LEVEL` | `info` | Log level: `debug` / `info` / `warning` |
| `DS_RELOAD` | `false` | Enable uvicorn hot reload (development only) |

### Client Config (`client/config.toml`)

```toml
[server]
url = "ws://127.0.0.1:9001/ws/client"

[client]
id = "pc-001"       # unique ID — must match what you bind scripts to in the UI
name = "PC-001"     # display name
platform = "windows"
```

### AI Vision / Firecrawl API Keys

Add API keys in the server's **Config Center** UI. No code changes or environment variables needed.

---

## 🗺️ Roadmap

- [ ] Scheduled / cron execution
- [ ] Per-node execution timeout
- [ ] Script import / export
- [ ] Linux / macOS client support
- [ ] Additional CV backend integrations

---

## 🤝 Contributing

Issues and pull requests are welcome.

**Adding a new node type:** create a file under `server/kernel/engine/nodes/`, subclass `BaseNodeHandler`, decorate it with `@NodeRegistry.register("type_name")`, then add a matching config form under `server/web/src/components/node-forms/`.

---

## 📄 License

<!-- TODO: add license -->
To be determined.
