import asyncio
import base64
import ctypes
import ctypes.wintypes
import io
import json
import logging
import os
from typing import Callable

logger = logging.getLogger(__name__)

MARKERS_FILE = os.path.join(os.path.dirname(__file__), "markers.json")


# ── Marker storage ────────────────────────────────────────────────────────────

def _load_markers() -> dict:
    try:
        with open(MARKERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_markers(data: dict) -> None:
    with open(MARKERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Window helpers ────────────────────────────────────────────────────────────

def _list_windows() -> list[dict]:
    """Return visible windows with title, process name, and screen rect."""
    import psutil

    windows: list[dict] = []

    def _callback(hwnd, _):
        if not ctypes.windll.user32.IsWindowVisible(hwnd):
            return True
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip()
        if not title:
            return True

        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        try:
            process = psutil.Process(pid.value).name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            process = "unknown"

        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        if w < 50 or h < 50:
            return True

        windows.append({
            "hwnd": hwnd,
            "title": title,
            "process": process,
            "x": rect.left, "y": rect.top, "w": w, "h": h,
        })
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    ctypes.windll.user32.EnumWindows(WNDENUMPROC(_callback), 0)
    return windows


def _find_window(title_pattern: str, process_name: str) -> dict | None:
    """Find window by partial title match + exact process name."""
    tp = title_pattern.lower()
    pp = process_name.lower()
    for w in _list_windows():
        if tp in w["title"].lower() and pp == w["process"].lower():
            return w
    # Fall back to title only
    for w in _list_windows():
        if tp in w["title"].lower():
            return w
    return None


def _activate_window(hwnd: int) -> None:
    SW_RESTORE = 9
    ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
    ctypes.windll.user32.SetForegroundWindow(hwnd)


def _select_window() -> dict | None:
    """Prompt user to pick a window from the list. Returns window dict or None."""
    windows = _list_windows()
    if not windows:
        print("  未检测到可用窗口")
        return None

    print("\n  请选择要标注的目标窗口：")
    for i, w in enumerate(windows, 1):
        print(f"  [{i:2}] {w['process']:<25} {w['title'][:40]}  ({w['w']}×{w['h']})")
    print("  [ 0] 不绑定窗口（记录绝对坐标）")

    while True:
        raw = input("\n  输入序号: ").strip()
        if raw == "0":
            return None
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(windows):
                selected = windows[idx]
                print(f"  已选择: {selected['process']}  {selected['title']}")
                return selected
        except ValueError:
            pass
        print("  无效输入，请重新输入")


# ── Marker lookup (resolves relative → absolute) ──────────────────────────────

def get_marker(project_id: str, name: str) -> dict | None:
    """Return marker coords as absolute screen coords.

    If the project has a window binding, the stored relative coords are
    converted to absolute using the window's current screen position.
    If the window can't be found, the stored (last-known absolute) coords
    are returned as a fallback.
    """
    data = _load_markers()
    project_data = data.get(project_id, {})
    marker = project_data.get(name)
    if not marker:
        return None

    window = project_data.get("_window")
    if not window:
        return _add_center(marker)

    win = _find_window(window["title"], window["process"])
    if win:
        win_x, win_y = win["x"], win["y"]
        # Activate window so subsequent clicks land on the right target
        try:
            _activate_window(win["hwnd"])
        except Exception:
            pass
    else:
        logger.warning(
            f"Window '{window['title']}' ({window['process']}) not found; "
            "using stored fallback position"
        )
        win_x, win_y = window.get("x", 0), window.get("y", 0)

    abs_marker = dict(marker)
    abs_marker["x"] = marker["x"] + win_x
    abs_marker["y"] = marker["y"] + win_y
    return _add_center(abs_marker)


def _add_center(marker: dict) -> dict:
    m = dict(marker)
    if "w" in m and "h" in m:
        m["cx"] = m["x"] + m["w"] // 2
        m["cy"] = m["y"] + m["h"] // 2
    return m


def _resolve_marker_params(params: dict, project_id: str) -> dict:
    """Replace $markers.<name>.<field> strings with actual coords."""
    resolved = {}
    for k, v in params.items():
        if isinstance(v, str) and v.startswith("$markers."):
            parts = v[len("$markers."):].split(".", 1)
            if len(parts) == 2:
                marker_name, field = parts
                m = get_marker(project_id, marker_name)
                resolved[k] = m.get(field) if m else None
            else:
                resolved[k] = None
        else:
            resolved[k] = v
    return resolved


# ── Async helper ──────────────────────────────────────────────────────────────

def _run_blocking(fn, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, lambda: fn(*args, **kwargs))


# ── Annotation input helpers ──────────────────────────────────────────────────

def _wait_for_click_or_esc() -> tuple[int, int] | None:
    from pynput import mouse as _mouse, keyboard as _keyboard
    import threading

    result: dict = {}
    done = threading.Event()

    def on_click(x, y, button, pressed):
        if pressed and button == _mouse.Button.left:
            result["x"], result["y"] = x, y
            done.set()
            return False

    def on_press(key):
        if key == _keyboard.Key.esc:
            result["cancelled"] = True
            done.set()
            return False

    m_listener = _mouse.Listener(on_click=on_click, suppress=True)
    k_listener = _keyboard.Listener(on_press=on_press)
    m_listener.start()
    k_listener.start()
    done.wait()
    m_listener.stop()
    k_listener.stop()

    if result.get("cancelled"):
        return None
    return result["x"], result["y"]


def _wait_for_nav() -> str:
    """Returns 'next' | 'prev' | 'redo' | 'cancel'."""
    from pynput import keyboard as _keyboard
    import threading

    action: dict = {}
    done = threading.Event()

    def on_press(key):
        if key in (_keyboard.Key.enter, _keyboard.Key.down):
            action["v"] = "next"
        elif key == _keyboard.Key.up:
            action["v"] = "prev"
        elif key == _keyboard.Key.esc:
            action["v"] = "cancel"
        else:
            try:
                if key.char and key.char.lower() == "r":
                    action["v"] = "redo"
            except AttributeError:
                return
        if action:
            done.set()
            return False

    k = _keyboard.Listener(on_press=on_press)
    k.start()
    done.wait()
    k.stop()
    return action.get("v", "next")


# ── Per-marker capture ────────────────────────────────────────────────────────

def _capture_point(name: str, prev: dict | None = None, win_x: int = 0, win_y: int = 0) -> dict | None:
    if prev:
        print(f"  上次记录: ({prev['x']}, {prev['y']})")
    print(f"  [{name}] 左键点击目标位置，ESC 取消全部标注")
    pos = _wait_for_click_or_esc()
    if pos is None:
        return None
    x, y = pos
    rx, ry = x - win_x, y - win_y
    print(f"  已记录: 绝对({x}, {y})  相对窗口({rx}, {ry})")
    return {"x": rx, "y": ry}


def _capture_box(name: str, prev: dict | None = None, win_x: int = 0, win_y: int = 0) -> dict | None:
    if prev:
        print(f"  上次记录: x={prev['x']} y={prev['y']} w={prev['w']} h={prev['h']}")
    print(f"  [{name}] 左键点击区域左上角，ESC 取消全部标注")
    pos1 = _wait_for_click_or_esc()
    if pos1 is None:
        return None
    x1, y1 = pos1
    print(f"  左上角: ({x1}, {y1})")

    print(f"  [{name}] 左键点击区域右下角，ESC 取消全部标注")
    pos2 = _wait_for_click_or_esc()
    if pos2 is None:
        return None
    x2, y2 = pos2
    print(f"  右下角: ({x2}, {y2})")

    ax, ay = min(x1, x2), min(y1, y2)
    w, h = abs(x2 - x1), abs(y2 - y1)
    rx, ry = ax - win_x, ay - win_y
    print(f"  区域: 相对窗口 x={rx} y={ry} w={w} h={h}")
    return {"x": rx, "y": ry, "w": w, "h": h}


# ── Annotation session ────────────────────────────────────────────────────────

def _run_annotation(project_id: str, project_name: str, markers: list[dict]) -> list[dict]:
    total = len(markers)
    print(f"\n{'='*55}")
    print(f"  标注项目: {project_name}  共 {total} 个标记")
    print(f"{'='*55}")

    # Window selection
    window = _select_window()
    win_x = window["x"] if window else 0
    win_y = window["y"] if window else 0
    if window:
        print(f"\n  目标窗口: {window['process']}  {window['title']}")
        print(f"  窗口位置: ({win_x}, {win_y})  大小: {window['w']}×{window['h']}")
    else:
        print("\n  未绑定窗口，记录绝对坐标")

    print(f"\n  点击确认后：Enter/↓=下一个  ↑=上一个  R=重新标记  ESC=取消")
    print(f"{'='*55}")

    captured: dict[int, dict] = {}
    idx = 0
    cancelled = False

    while 0 <= idx < total:
        marker = markers[idx]
        name = marker["name"]
        mtype = marker["type"]
        prev = captured.get(idx)

        print(f"\n[{idx + 1}/{total}] {name}  ({'点' if mtype == 'point' else '框'})")

        try:
            coords = (
                _capture_point(name, prev, win_x, win_y) if mtype == "point"
                else _capture_box(name, prev, win_x, win_y)
            )
        except Exception as e:
            logger.error(f"标注 [{name}] 失败: {e}")
            idx += 1
            continue

        if coords is None:
            print("\n  已取消标注")
            cancelled = True
            break

        captured[idx] = coords

        print(f"  Enter/↓=下一个  ↑=上一个  R=重新标记  ESC=取消")
        nav = _wait_for_nav()

        if nav == "cancel":
            print("\n  已取消标注")
            cancelled = True
            break
        elif nav == "prev":
            idx = max(0, idx - 1)
        elif nav == "redo":
            pass
        else:
            idx += 1

    results = [
        {"name": markers[i]["name"], "type": markers[i]["type"], **captured[i]}
        for i in sorted(captured)
    ]

    if results:
        data = _load_markers()
        project_data = data.get(project_id, {})

        # Store window binding (persist current position as fallback)
        if window:
            project_data["_window"] = {
                "title": window["title"],
                "process": window["process"],
                "x": win_x, "y": win_y,
                "w": window["w"], "h": window["h"],
            }
        else:
            project_data.pop("_window", None)

        for r in results:
            project_data[r["name"]] = {k: v for k, v in r.items() if k not in ("name", "type")}
        data[project_id] = project_data
        _save_markers(data)
        print(f"\n  已保存 {len(results)}/{total} 个标记到 markers.json")
        if window:
            print(f"  窗口绑定: {window['process']}  {window['title']}")

    if cancelled and len(results) < total:
        print(f"  （{total - len(results)} 个标记未完成）")
    print(f"{'='*55}\n")
    return results


# ── Command handler ───────────────────────────────────────────────────────────

class CommandHandler:
    def __init__(self, send_fn: Callable):
        self._send = send_fn
        self._handlers: dict[str, Callable] = {
            "capture_screenshot": self.handle_capture_screenshot,
            "execute_node": self.handle_execute_node,
            "set_markers": self.handle_set_markers,
            "stop": self.handle_stop,
            "get_status": self.handle_get_status,
        }
        self._stop_flag = False

    async def dispatch(self, msg: dict) -> None:
        msg_type = msg.get("type")
        handler = self._handlers.get(msg_type)
        if handler:
            try:
                await handler(msg)
            except Exception as e:
                logger.exception(f"Error handling '{msg_type}': {e}")
        else:
            logger.debug(f"Unknown message type: {msg_type}")

    async def handle_set_markers(self, msg: dict) -> None:
        project_id = msg.get("project_id", "")
        project_name = msg.get("project_name", project_id)
        markers = msg.get("markers", [])

        if not markers:
            await self._send({"type": "markers_captured", "project_id": project_id, "markers": []})
            return

        logger.info(f"Starting annotation for project '{project_name}' ({len(markers)} markers)")
        results = await _run_blocking(_run_annotation, project_id, project_name, markers)

        await self._send({"type": "markers_captured", "project_id": project_id, "markers": results})

    async def handle_capture_screenshot(self, msg: dict) -> None:
        request_id = msg.get("request_id")
        try:
            import pyautogui
            screenshot = await _run_blocking(pyautogui.screenshot)
            buf = io.BytesIO()
            screenshot.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            await self._send({"type": "screenshot_response", "request_id": request_id, "data": b64})
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            await self._send({"type": "error", "request_id": request_id, "message": str(e)})

    async def handle_execute_node(self, msg: dict) -> None:
        node_type = msg.get("node_type")
        params = dict(msg.get("params", {}))
        project_id = msg.get("project_id")
        request_id = msg.get("request_id") or msg.get("node_id")

        # Resolve $markers.* references using local markers.json + current window position
        if project_id:
            params = _resolve_marker_params(params, project_id)

        try:
            success, output, error = await self._execute_action(node_type, params)
        except Exception as e:
            success, output, error = False, {}, str(e)

        await self._send({
            "type": "node_result",
            "node_id": msg.get("node_id"),
            "request_id": request_id,
            "success": success,
            "output": output,
            "error": error,
        })

    async def _execute_action(self, action_type: str, params: dict) -> tuple[bool, dict, str | None]:
        import pyautogui
        pyautogui.FAILSAFE = False

        if action_type == "mouse_click":
            x, y = int(params.get("x", 0)), int(params.get("y", 0))
            button = params.get("button", "left")
            clicks = int(params.get("clicks", 1))
            await _run_blocking(pyautogui.click, x, y, button=button, clicks=clicks)
            return True, {"x": x, "y": y}, None

        if action_type == "mouse_move":
            x, y = int(params.get("x", 0)), int(params.get("y", 0))
            duration = float(params.get("duration", 0.2))
            await _run_blocking(pyautogui.moveTo, x, y, duration=duration)
            return True, {"x": x, "y": y}, None

        if action_type == "mouse_drag":
            x1, y1 = int(params.get("x1", 0)), int(params.get("y1", 0))
            x2, y2 = int(params.get("x2", 0)), int(params.get("y2", 0))
            duration = float(params.get("duration", 0.3))
            await _run_blocking(pyautogui.moveTo, x1, y1)
            await _run_blocking(pyautogui.dragTo, x2, y2, duration=duration)
            return True, {}, None

        if action_type == "keyboard_type":
            text = params.get("text", "")
            interval = float(params.get("interval", 0.02))
            await _run_blocking(pyautogui.typewrite, text, interval=interval)
            return True, {"length": len(text)}, None

        if action_type == "keyboard_hotkey":
            keys = params.get("keys", [])
            if isinstance(keys, str):
                keys = keys.split("+")
            await _run_blocking(pyautogui.hotkey, *keys)
            return True, {"keys": keys}, None

        if action_type == "keyboard_press":
            key = params.get("key", "")
            presses = int(params.get("presses", 1))
            await _run_blocking(pyautogui.press, key, presses=presses)
            return True, {"key": key}, None

        if action_type == "mouse_scroll":
            x, y = int(params.get("x", 0)), int(params.get("y", 0))
            clicks = int(params.get("clicks", 3))
            await _run_blocking(pyautogui.scroll, clicks, x, y)
            return True, {}, None

        return False, {}, f"Unknown action_type: {action_type}"

    async def handle_stop(self, msg: dict) -> None:
        logger.info(f"Stop signal received: {msg.get('reason')}")
        self._stop_flag = True

    async def handle_get_status(self, msg: dict) -> None:
        await self._send({"type": "status_response", "status": "idle", "stop_flag": self._stop_flag})
