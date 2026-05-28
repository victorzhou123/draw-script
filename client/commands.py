import asyncio
import base64
import io
import json
import logging
import os
from typing import Any, Callable

logger = logging.getLogger(__name__)

MARKERS_FILE = os.path.join(os.path.dirname(__file__), "markers.json")


def _load_markers() -> dict:
    try:
        with open(MARKERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_markers(data: dict) -> None:
    with open(MARKERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_marker(project_id: str, name: str) -> dict | None:
    """Called by script nodes to look up a stored marker."""
    data = _load_markers()
    return data.get(project_id, {}).get(name)


def _run_blocking(fn, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, lambda: fn(*args, **kwargs))


def _wait_for_click_or_esc() -> tuple[int, int] | None:
    """Block until left-click (returns coords) or ESC (returns None)."""
    from pynput import mouse as _mouse, keyboard as _keyboard
    import threading

    result: dict = {}
    done = threading.Event()

    def on_click(x, y, button, pressed):
        if pressed and button == _mouse.Button.left:
            result["x"], result["y"] = x, y
            done.set()
            return False  # stop listener

    def on_press(key):
        if key == _keyboard.Key.esc:
            result["cancelled"] = True
            done.set()
            return False  # stop listener

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


def _capture_point(name: str) -> dict | None:
    print(f"\n  [{name}] 左键点击目标位置确认，ESC 取消全部标注")
    pos = _wait_for_click_or_esc()
    if pos is None:
        return None
    x, y = pos
    print(f"  已记录: ({x}, {y})")
    return {"x": x, "y": y}


def _capture_box(name: str) -> dict | None:
    print(f"\n  [{name}] 左键点击区域左上角，ESC 取消全部标注")
    pos1 = _wait_for_click_or_esc()
    if pos1 is None:
        return None
    x1, y1 = pos1
    print(f"  左上角: ({x1}, {y1})")

    print(f"  [{name}] 再次左键点击区域右下角，ESC 取消全部标注")
    pos2 = _wait_for_click_or_esc()
    if pos2 is None:
        return None
    x2, y2 = pos2
    print(f"  右下角: ({x2}, {y2})")

    x, y = min(x1, x2), min(y1, y2)
    w, h = abs(x2 - x1), abs(y2 - y1)
    print(f"  区域: x={x} y={y} w={w} h={h}")
    return {"x": x, "y": y, "w": w, "h": h}


def _run_annotation(project_id: str, project_name: str, markers: list[dict]) -> list[dict]:
    print(f"\n{'='*50}")
    print(f"  开始标注项目: {project_name}")
    print(f"  共 {len(markers)} 个标记")
    print(f"  操作：左键点击确认位置，ESC 取消全部标注")
    print(f"{'='*50}")

    results = []
    cancelled = False
    for i, marker in enumerate(markers, 1):
        name = marker["name"]
        mtype = marker["type"]
        print(f"\n[{i}/{len(markers)}] 标记: {name}  类型: {mtype}")

        try:
            coords = _capture_point(name) if mtype == "point" else _capture_box(name)
        except Exception as e:
            logger.error(f"标注 [{name}] 失败: {e}")
            results.append({"name": name, "type": mtype, "error": str(e)})
            continue

        if coords is None:
            print("\n  已取消标注")
            cancelled = True
            break

        results.append({"name": name, "type": mtype, **coords})

    # Persist whatever was captured before cancellation
    if results:
        data = _load_markers()
        project_data = data.get(project_id, {})
        for r in results:
            if "error" not in r:
                project_data[r["name"]] = {k: v for k, v in r.items() if k != "name"}
        data[project_id] = project_data
        _save_markers(data)
        saved = len([r for r in results if "error" not in r])
        print(f"\n  已保存 {saved}/{len(markers)} 个标记到 markers.json")

    if cancelled:
        print(f"  （剩余标记未完成）")
    print(f"{'='*50}\n")
    return results


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
            await self._send({
                "type": "markers_captured",
                "project_id": project_id,
                "markers": [],
            })
            return

        logger.info(f"Starting annotation for project '{project_name}' ({len(markers)} markers)")
        results = await _run_blocking(_run_annotation, project_id, project_name, markers)

        await self._send({
            "type": "markers_captured",
            "project_id": project_id,
            "markers": results,
        })

    async def handle_capture_screenshot(self, msg: dict) -> None:
        request_id = msg.get("request_id")
        try:
            import pyautogui
            screenshot = await _run_blocking(pyautogui.screenshot)
            buf = io.BytesIO()
            screenshot.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            await self._send({
                "type": "screenshot_response",
                "request_id": request_id,
                "data": b64,
            })
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            await self._send({
                "type": "error",
                "request_id": request_id,
                "message": str(e),
            })

    async def handle_execute_node(self, msg: dict) -> None:
        node_type = msg.get("node_type")
        params = msg.get("params", {})
        request_id = msg.get("request_id") or msg.get("node_id")

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
        await self._send({
            "type": "status_response",
            "status": "idle",
            "stop_flag": self._stop_flag,
        })
