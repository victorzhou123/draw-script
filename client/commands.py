import atexit
import asyncio
import base64
import ctypes
import ctypes.wintypes
import io
import json
import logging
import os
import queue as _queue
import threading
from typing import Callable

logger = logging.getLogger(__name__)

MARKERS_FILE = os.path.join(os.path.dirname(__file__), "markers.json")


# DPI awareness so tkinter coordinates match pyautogui on high-DPI screens
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


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

class _WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ("length",           ctypes.wintypes.UINT),
        ("flags",            ctypes.wintypes.UINT),
        ("showCmd",          ctypes.wintypes.UINT),
        ("ptMinPosition",    ctypes.wintypes.POINT),
        ("ptMaxPosition",    ctypes.wintypes.POINT),
        ("rcNormalPosition", ctypes.wintypes.RECT),
    ]


def _list_windows() -> list[dict]:
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
        # minimized windows report taskbar-button size via GetWindowRect;
        # use GetWindowPlacement to get the true restored rect instead
        if ctypes.windll.user32.IsIconic(hwnd):
            placement = _WINDOWPLACEMENT()
            placement.length = ctypes.sizeof(placement)
            ctypes.windll.user32.GetWindowPlacement(hwnd, ctypes.byref(placement))
            rc = placement.rcNormalPosition
        else:
            rc = ctypes.wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rc))
        w = rc.right - rc.left
        h = rc.bottom - rc.top
        if w < 50 or h < 50:
            return True
        windows.append({"hwnd": hwnd, "title": title, "process": process,
                         "x": rc.left, "y": rc.top, "w": w, "h": h})
        return True

    # use HWND (pointer-sized) not c_int to avoid truncation on 64-bit Windows
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    ctypes.windll.user32.EnumWindows(WNDENUMPROC(_callback), 0)
    return windows


def _find_window(title_pattern: str, process_name: str) -> dict | None:
    tp, pp = title_pattern.lower(), process_name.lower()
    for w in _list_windows():
        if tp in w["title"].lower() and pp == w["process"].lower():
            return w
    for w in _list_windows():
        if tp in w["title"].lower():
            return w
    return None


def _activate_window(hwnd: int) -> None:
    if ctypes.windll.user32.IsIconic(hwnd):
        ctypes.windll.user32.ShowWindow(hwnd, 9)   # SW_RESTORE only when minimized
    ctypes.windll.user32.SetForegroundWindow(hwnd)


def _select_window() -> dict | None:
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
                sel = windows[idx]
                print(f"  已选择: {sel['process']}  {sel['title']}")
                return sel
        except ValueError:
            pass
        print("  无效输入，请重新输入")


# ── Marker lookup ─────────────────────────────────────────────────────────────

def _resolve_window_offset(relative: dict) -> dict:
    """Apply window offset to relative marker coordinates, return absolute coords."""
    win_title = relative.get("window_title")
    win_process = relative.get("window_process", "")
    if win_title:
        win = _find_window(win_title, win_process)
        if win:
            win_x, win_y = win["x"], win["y"]
            try:
                _activate_window(win["hwnd"])
            except Exception:
                pass
        else:
            logger.warning(f"Window '{win_title}' not found; using stored position")
            win_x = relative.get("window_x", 0)
            win_y = relative.get("window_y", 0)
        abs_m = dict(relative)
        abs_m["x"] = relative["x"] + win_x
        abs_m["y"] = relative["y"] + win_y
        return _add_center(abs_m)
    return _add_center(dict(relative))


def get_marker(project_id: str, name: str) -> dict | None:
    """Look up a marker from local markers.json (fallback for legacy data)."""
    data = _load_markers()
    project_data = data.get(project_id, {})
    marker = project_data.get(name)
    if not marker:
        return None
    window = project_data.get("_window")
    if not window:
        return _add_center(marker)
    # Build a combined dict matching the server format for _resolve_window_offset
    combined = dict(marker)
    combined.update({
        "window_title": window["title"],
        "window_process": window["process"],
        "window_x": window.get("x", 0),
        "window_y": window.get("y", 0),
    })
    return _resolve_window_offset(combined)


def _get_marker_from_server(name: str, server_markers: dict) -> dict | None:
    """Resolve a marker from server-provided data (DB coordinates)."""
    m = server_markers.get(name)
    if not m or m.get("x") is None:
        return None
    return _resolve_window_offset(m)


def _add_center(marker: dict) -> dict:
    m = dict(marker)
    if m.get("w") is not None and m.get("h") is not None:
        m["cx"] = m["x"] + m["w"] // 2
        m["cy"] = m["y"] + m["h"] // 2
    return m


import re as _re

def _resolve_marker_params(params: dict, project_id: str, server_markers: dict | None = None) -> dict:
    """Resolve $markers.* and {{markers.*}} references.

    Prefers server_markers (DB coordinates) over local markers.json.
    """
    resolved = {}
    for k, v in params.items():
        if not isinstance(v, str):
            resolved[k] = v
            continue
        # {{markers.name.field}} format (used by PropertyPanel coord picker)
        tpl = _re.match(r'^\{\{markers\.([^.}]+)\.([^}]+)\}\}$', v)
        if tpl:
            marker_name, field = tpl.group(1), tpl.group(2)
            m = (_get_marker_from_server(marker_name, server_markers) if server_markers
                 else get_marker(project_id, marker_name))
            resolved[k] = m.get(field) if m else None
            continue
        # $markers.name.field format (legacy)
        if v.startswith("$markers."):
            parts = v[len("$markers."):].split(".", 1)
            if len(parts) == 2:
                m = (_get_marker_from_server(parts[0], server_markers) if server_markers
                     else get_marker(project_id, parts[0]))
                resolved[k] = m.get(parts[1]) if m else None
            else:
                resolved[k] = None
            continue
        resolved[k] = v
    return resolved


# ── Overlay helpers ───────────────────────────────────────────────────────────

_NAV_HINT = "[Enter/↓] 下一个   [↑] 上一个   [R] 重新标记   [ESC] 取消"
_FONT_UI   = ("Microsoft YaHei UI", 13)
_FONT_MONO = ("Consolas", 11)
_COLOR_CROSS = "#00d4ff"
_COLOR_OK    = "#52c41a"
_COLOR_PREV  = "#faad14"
_COLOR_FILL  = "#1a6aff"
_COLOR_MATCH = "#00ff41"   # CV result highlight colour
_TRANSP_KEY  = "#010203"   # near-black used as window transparency key

CV_OVERLAY_DURATION_S = 2.0  # fallback seconds when overlay_mode == "fixed"

# Single dedicated tkinter thread — one Toplevel window updated in place.
# Other threads send dicts via this queue; no Tk calls ever leave the mainloop thread.
_overlay_queue: _queue.SimpleQueue = _queue.SimpleQueue()
_overlay_thread: threading.Thread | None = None
_overlay_thread_lock = threading.Lock()


def _ensure_overlay_thread() -> None:
    global _overlay_thread
    with _overlay_thread_lock:
        if _overlay_thread is None or not _overlay_thread.is_alive():
            t = threading.Thread(target=_overlay_mainloop, daemon=False)
            t.start()
            _overlay_thread = t


def _shutdown_overlay_thread() -> None:
    with _overlay_thread_lock:
        t = _overlay_thread
    if t and t.is_alive():
        _overlay_queue.put({"action": "quit"})
        t.join(timeout=3.0)


atexit.register(_shutdown_overlay_thread)


def _overlay_mainloop() -> None:
    """Single Tk thread: handles CV match overlay and interactive capture modals.
    All Tkinter operations live here so there is exactly one Tcl interpreter in one
    thread, preventing Tcl_AsyncDelete errors on process exit.
    """
    import tkinter as tk
    try:
        root = tk.Tk()
        root.withdraw()  # hidden master; keeps the Tcl interpreter alive

        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()

        top = tk.Toplevel(root)
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.geometry(f"{sw}x{sh}+0+0")
        top.configure(bg=_TRANSP_KEY)
        top.attributes("-transparentcolor", _TRANSP_KEY)
        top.withdraw()  # hide while we apply Win32 styles

        canvas = tk.Canvas(top, bg=_TRANSP_KEY, highlightthickness=0)
        canvas.pack(fill="both", expand=True)

        top.update()
        hwnd = top.winfo_id()
        GWL_EXSTYLE       = -20
        WS_EX_TRANSPARENT = 0x00000020
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                                            style | WS_EX_TRANSPARENT)
        top.deiconify()  # canvas is empty → fully transparent; no visual flash

        _pending: list = [None]  # [after_id | None]

        def _clear():
            if _pending[0] is not None:
                root.after_cancel(_pending[0])
                _pending[0] = None
            canvas.delete("all")

        def _draw(locations, tmpl_w, tmpl_h, duration_s):
            _clear()
            hw = max(tmpl_w // 2, 1)
            hh = max(tmpl_h // 2, 1)
            for loc in locations:
                cx, cy = loc["x"], loc["y"]
                canvas.create_rectangle(cx - hw, cy - hh, cx + hw, cy + hh,
                                        outline=_COLOR_MATCH, width=3, fill="")
                canvas.create_line(cx - 8, cy, cx + 8, cy,
                                   fill=_COLOR_MATCH, width=2)
                canvas.create_line(cx, cy - 8, cx, cy + 8,
                                   fill=_COLOR_MATCH, width=2)
            if duration_s is not None:
                _pending[0] = root.after(int(duration_s * 1000), _clear)

        def _process_queue():
            try:
                while True:
                    cmd = _overlay_queue.get_nowait()
                    if cmd["action"] == "show":
                        _draw(cmd["locations"], cmd["tmpl_w"],
                              cmd["tmpl_h"], cmd.get("duration_s"))
                    elif cmd["action"] == "dismiss":
                        _clear()
                    elif cmd["action"] == "modal":
                        try:
                            fn = _run_point_modal if cmd["kind"] == "point" else _run_box_modal
                            res = fn(root, **cmd["kwargs"])
                        except Exception:
                            res = ("cancel", None)
                        cmd["_result"].put(res)
                    elif cmd["action"] == "resize_modal":
                        try:
                            res = _run_resize_window_modal(root, **cmd["kwargs"])
                        except Exception:
                            res = None
                        cmd["_result"].put(res)
                    elif cmd["action"] == "window_select_modal":
                        try:
                            res = _run_window_select_modal(root)
                        except Exception:
                            res = None
                        cmd["_result"].put(res)
                    elif cmd["action"] == "quit":
                        root.quit()
                        return
            except _queue.Empty:
                pass
            root.after(50, _process_queue)

        root.after(50, _process_queue)
        root.mainloop()
    except Exception:
        pass


def _run_resize_window_modal(
    root,
    window_title: str,
    window_process: str,
    old_w: int,
    old_h: int,
) -> tuple[int, int] | None:
    """Small floating dialog: user resizes target window, then confirms."""
    import tkinter as tk

    result = [None]

    dialog = tk.Toplevel(root)
    dialog.title("自定义窗口大小")
    dialog.attributes("-topmost", True)
    dialog.configure(bg="#1a1a2e")
    dialog.resizable(False, False)

    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    ww, wh = 400, 210
    dialog.geometry(f"{ww}x{wh}+{(sw - ww) // 2}+{sh - wh - 80}")

    tk.Label(
        dialog, text="调整目标窗口大小",
        bg="#1a1a2e", fg="#d9d9d9",
        font=("Microsoft YaHei UI", 12, "bold"),
    ).pack(pady=(18, 4))

    short_title = window_title[:45] + "…" if len(window_title) > 45 else window_title
    tk.Label(
        dialog, text=f"窗口: {short_title}",
        bg="#1a1a2e", fg="#666",
        font=("Microsoft YaHei UI", 9),
        wraplength=370,
    ).pack(pady=(0, 6))

    tk.Label(
        dialog, text="请手动拖拽窗口边缘调整大小，完成后点击确认",
        bg="#1a1a2e", fg="#888",
        font=("Microsoft YaHei UI", 9),
    ).pack(pady=(0, 6))

    size_var = tk.StringVar(value=f"当前大小: {old_w} × {old_h}")
    size_label = tk.Label(
        dialog, textvariable=size_var,
        bg="#1a1a2e", fg="#1890ff",
        font=("Consolas", 11, "bold"),
    )
    size_label.pack(pady=(0, 14))

    def _poll_size():
        if not dialog.winfo_exists():
            return
        win = _find_window(window_title, window_process)
        if win:
            size_var.set(f"当前大小: {win['w']} × {win['h']}")
        dialog.after(200, _poll_size)

    dialog.after(200, _poll_size)

    btn_frame = tk.Frame(dialog, bg="#1a1a2e")
    btn_frame.pack()

    def _confirm():
        win = _find_window(window_title, window_process)
        result[0] = (win["x"], win["y"], win["w"], win["h"]) if win else None
        dialog.destroy()

    def _cancel():
        dialog.destroy()

    tk.Button(
        btn_frame, text="确认 (Enter)",
        command=_confirm,
        bg="#1d6b3e", fg="white",
        font=("Microsoft YaHei UI", 10, "bold"),
        relief="flat", cursor="hand2", padx=20, pady=5,
    ).pack(side="left", padx=8)

    tk.Button(
        btn_frame, text="取消 (ESC)",
        command=_cancel,
        bg="#2a2a2a", fg="#888",
        font=("Microsoft YaHei UI", 10),
        relief="flat", cursor="hand2", padx=20, pady=5,
    ).pack(side="left", padx=8)

    dialog.bind("<Return>", lambda e: _confirm())
    dialog.bind("<Escape>", lambda e: _cancel())

    dialog.deiconify()
    dialog.focus_force()
    root.wait_window(dialog)
    return result[0]


def _show_resize_window_dialog(
    window_title: str,
    window_process: str,
    old_w: int,
    old_h: int,
) -> tuple[int, int] | None:
    _ensure_overlay_thread()
    result_q: _queue.Queue = _queue.Queue()
    _overlay_queue.put({
        "action": "resize_modal",
        "kwargs": {
            "window_title": window_title,
            "window_process": window_process,
            "old_w": old_w,
            "old_h": old_h,
        },
        "_result": result_q,
    })
    return result_q.get()


def _run_window_select_modal(root) -> dict | None:
    """Tkinter dialog: list all open windows, user picks one."""
    import tkinter as tk

    windows = _list_windows()
    result = [None]

    dialog = tk.Toplevel(root)
    dialog.title("选择目标窗口")
    dialog.attributes("-topmost", True)
    dialog.configure(bg="#1a1a2e")
    dialog.resizable(True, True)

    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    ww, wh = 540, 360
    dialog.geometry(f"{ww}x{wh}+{(sw - ww) // 2}+{(sh - wh) // 2}")

    tk.Label(
        dialog, text="选择要截图的目标窗口",
        bg="#1a1a2e", fg="#d9d9d9",
        font=("Microsoft YaHei UI", 12, "bold"),
    ).pack(pady=(14, 6))

    frame = tk.Frame(dialog, bg="#1a1a2e")
    frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))

    scrollbar = tk.Scrollbar(frame, orient="vertical", bg="#2a2a3e", troughcolor="#1a1a2e")
    scrollbar.pack(side="right", fill="y")

    listbox = tk.Listbox(
        frame,
        yscrollcommand=scrollbar.set,
        bg="#0d0d1a", fg="#d9d9d9",
        selectbackground="#1890ff", selectforeground="white",
        font=("Consolas", 10),
        activestyle="none",
        borderwidth=0, highlightthickness=1, highlightcolor="#1890ff",
    )
    listbox.pack(side="left", fill="both", expand=True)
    scrollbar.config(command=listbox.yview)

    for w in windows:
        label = f"{w['process']:<20}  {w['title'][:40]:<40}  {w['w']}×{w['h']}"
        listbox.insert("end", label)

    btn_frame = tk.Frame(dialog, bg="#1a1a2e")
    btn_frame.pack(pady=(0, 12))

    def _confirm():
        sel = listbox.curselection()
        if sel:
            result[0] = windows[sel[0]]
        dialog.destroy()

    def _cancel():
        dialog.destroy()

    tk.Button(
        btn_frame, text="确认 (Enter)",
        command=_confirm,
        bg="#1d6b3e", fg="white",
        font=("Microsoft YaHei UI", 10, "bold"),
        relief="flat", cursor="hand2", padx=20, pady=5,
    ).pack(side="left", padx=8)

    tk.Button(
        btn_frame, text="取消 (ESC)",
        command=_cancel,
        bg="#2a2a2a", fg="#888",
        font=("Microsoft YaHei UI", 10),
        relief="flat", cursor="hand2", padx=20, pady=5,
    ).pack(side="left", padx=8)

    listbox.bind("<Double-Button-1>", lambda e: _confirm())
    dialog.bind("<Return>", lambda e: _confirm())
    dialog.bind("<Escape>", lambda e: _cancel())

    if windows:
        listbox.selection_set(0)
        listbox.activate(0)

    dialog.deiconify()
    dialog.focus_force()
    root.wait_window(dialog)
    return result[0]


def _show_window_select_modal() -> dict | None:
    _ensure_overlay_thread()
    result_q: _queue.Queue = _queue.Queue()
    _overlay_queue.put({
        "action": "window_select_modal",
        "_result": result_q,
    })
    return result_q.get()


def _dismiss_all_overlays() -> None:
    _overlay_queue.put({"action": "dismiss"})


def _show_match_overlay(
    node_id: str,
    locations: list[dict], tmpl_w: int, tmpl_h: int,
    duration_s: float | None = CV_OVERLAY_DURATION_S,
) -> None:
    """Queue a draw command to the dedicated overlay thread (non-blocking)."""
    _ensure_overlay_thread()
    _overlay_queue.put({
        "action": "show",
        "node_id": node_id,
        "locations": locations,
        "tmpl_w": tmpl_w,
        "tmpl_h": tmpl_h,
        "duration_s": duration_s,
    })


def _run_point_modal(
    root,
    name: str, win_x: int = 0, win_y: int = 0,
    prev: dict | None = None, idx: int = 0, total: int = 0,
) -> tuple[str, tuple[int, int] | None]:
    """Point capture UI, runs inside the dedicated Tk thread on a Toplevel."""
    import tkinter as tk
    from PIL import ImageEnhance, ImageTk
    import pyautogui

    screen = pyautogui.screenshot()
    sw, sh = screen.size
    dark_img = ImageEnhance.Brightness(screen).enhance(0.4)

    result = [("cancel", None)]
    captured = [None]

    top = tk.Toplevel(root)
    top.withdraw()
    top.overrideredirect(True)
    top.attributes("-topmost", True)
    top.geometry(f"{sw}x{sh}+0+0")

    cv = tk.Canvas(top, cursor="crosshair", highlightthickness=0, bg="#000")
    cv.pack(fill="both", expand=True)

    bg_photo = ImageTk.PhotoImage(dark_img)
    bg_item = cv.create_image(0, 0, anchor="nw", image=bg_photo)
    photo_ref = [bg_photo]  # keep reference alive; replaced on resume

    # ── Header bar ──
    cv.create_rectangle(0, 0, sw, 48, fill="#111", outline="")
    progress = f"[{idx}/{total}]  " if total else ""
    header_lbl = cv.create_text(
        sw // 2, 24,
        text=f"{progress}标记 [{name}]  (点)  —  左键点击确认  |  ESC 取消",
        fill="#ccc", font=_FONT_UI, anchor="center",
    )

    # ── Crosshair ──
    h_line = cv.create_line(0, sh // 2, sw, sh // 2, fill=_COLOR_CROSS, width=1)
    v_line = cv.create_line(sw // 2, 0, sw // 2, sh, fill=_COLOR_CROSS, width=1)
    dot    = cv.create_oval(0, 0, 0, 0, outline=_COLOR_CROSS, fill="", width=2)

    # ── Coord tooltip ──
    tip_bg  = cv.create_rectangle(0, 0, 1, 1, fill="#111", outline="", state="hidden")
    tip_lbl = cv.create_text(0, 0, text="", fill="white", font=_FONT_MONO,
                              anchor="nw", state="hidden")

    # ── Confirm footer (hidden until capture) ──
    fy = sh - 54
    cv.create_rectangle(0, fy, sw, sh, fill="#111", outline="", tags="footer")
    ok_lbl  = cv.create_text(20, fy + 16, text="", fill=_COLOR_OK,
                              font=_FONT_MONO, anchor="nw", tags="footer")
    cv.create_text(sw // 2, fy + 16, text=_NAV_HINT,
                   fill="#888", font=("Microsoft YaHei UI", 11),
                   anchor="n", tags="footer")
    confirm_dot = cv.create_oval(0, 0, 0, 0, outline=_COLOR_OK, fill="", width=2,
                                  tags="footer")
    cv.itemconfig("footer", state="hidden")

    # ── Pause button (top right of header) ──
    cv.create_rectangle(sw-90, 9, sw-10, 39, fill="#333", outline="#555", tags="pause_btn")
    cv.create_text(sw-50, 24, text="暂停 [P]", fill="#aaa",
                   font=("Microsoft YaHei UI", 10), anchor="center", tags="pause_btn")

    # ── Previous value hint ──
    if prev:
        px, py = prev["x"] + win_x, prev["y"] + win_y
        cv.create_oval(px-5, py-5, px+5, py+5, outline=_COLOR_PREV, fill="", width=1)
        cv.create_text(px+8, py-16, text=f"上次({px},{py})",
                       fill=_COLOR_PREV, font=("Consolas", 9), anchor="nw")

    def _pause():
        top.withdraw()
        resume_win = tk.Toplevel(root)
        resume_win.attributes("-topmost", True)
        resume_win.overrideredirect(True)
        ww, wh = 300, 72
        resume_win.geometry(f"{ww}x{wh}+{(sw - ww) // 2}+{sh - wh - 60}")
        resume_win.configure(bg="#1a1a2e")
        tk.Label(
            resume_win, text=f"标注已暂停  [{name}]",
            bg="#1a1a2e", fg="#aaa", font=("Microsoft YaHei UI", 10),
        ).pack(pady=(10, 4))
        def _resume():
            resume_win.destroy()
            def _refresh():
                new_screen = pyautogui.screenshot()
                new_dark = ImageEnhance.Brightness(new_screen).enhance(0.4)
                new_photo = ImageTk.PhotoImage(new_dark)
                cv.itemconfig(bg_item, image=new_photo)
                photo_ref[0] = new_photo
                top.deiconify()
                top.lift()
                top.focus_force()
            top.after(80, _refresh)
        tk.Button(
            resume_win, text="继续标注 ▶", command=_resume,
            bg="#1d6b3e", fg="white", font=("Microsoft YaHei UI", 10, "bold"),
            relief="flat", cursor="hand2", padx=20, pady=2,
        ).pack()

    def _enter_capture():
        captured[0] = None
        cv.configure(cursor="crosshair")
        cv.itemconfig(h_line, state="normal")
        cv.itemconfig(v_line, state="normal")
        cv.itemconfig(dot,    state="normal")
        cv.itemconfig("footer", state="hidden")
        cv.itemconfig(tip_bg,  state="hidden")
        cv.itemconfig(tip_lbl, state="hidden")
        cv.itemconfig(header_lbl,
            text=f"{progress}标记 [{name}]  (点)  —  左键点击确认  |  P 暂停  |  ESC 取消")
        cv.bind("<Motion>",   _on_motion)
        cv.bind("<Button-1>", _on_click)
        for seq in ("<Return>", "<Down>", "<Up>", "r", "R"):
            top.unbind(seq)

    def _enter_confirm(x, y):
        cv.configure(cursor="")
        for item in (h_line, v_line, dot, tip_bg, tip_lbl):
            cv.itemconfig(item, state="hidden")
        cv.itemconfig("footer", state="normal")
        r = 9
        cv.coords(confirm_dot, x-r, y-r, x+r, y+r)
        if win_x or win_y:
            txt = f"已记录  绝对({x}, {y})  →  相对({x-win_x}, {y-win_y})"
        else:
            txt = f"已记录  ({x}, {y})"
        cv.itemconfig(ok_lbl, text=txt)
        cv.itemconfig(header_lbl, text=f"{progress}标记 [{name}]  (点)  —  确认或导航  |  P 暂停")
        cv.unbind("<Motion>")
        cv.unbind("<Button-1>")
        top.bind("<Return>", lambda e: _done("next"))
        top.bind("<Down>",   lambda e: _done("next"))
        top.bind("<Up>",     lambda e: _done("prev"))
        top.bind("r",        lambda e: _enter_capture())
        top.bind("R",        lambda e: _enter_capture())

    def _done(action):
        result[0] = (action, captured[0])
        top.destroy()

    def _on_motion(event):
        x, y = event.x, event.y
        cv.coords(h_line, 0, y, sw, y)
        cv.coords(v_line, x, 0, x, sh)
        cv.coords(dot, x-5, y-5, x+5, y+5)
        if win_x or win_y:
            txt = f"({x}, {y})  相对({x-win_x}, {y-win_y})"
        else:
            txt = f"({x}, {y})"
        tw = len(txt) * 7 + 10
        tx = min(x+16, sw-tw-4)
        ty = max(y-30, 52)
        cv.coords(tip_bg, tx-2, ty-2, tx+tw, ty+18)
        cv.coords(tip_lbl, tx, ty)
        cv.itemconfig(tip_lbl, text=txt)
        cv.itemconfig(tip_bg,  state="normal")
        cv.itemconfig(tip_lbl, state="normal")
        cv.tag_raise(tip_lbl)

    def _on_click(event):
        captured[0] = (event.x, event.y)
        _enter_confirm(event.x, event.y)

    cv.tag_bind("pause_btn", "<Button-1>", lambda e: _pause())
    top.bind("p", lambda e: _pause())
    top.bind("P", lambda e: _pause())
    top.bind("<Escape>", lambda e: (result.__setitem__(0, ("cancel", None)), top.destroy()))

    if prev:
        abs_x, abs_y = prev["x"] + win_x, prev["y"] + win_y
        captured[0] = (abs_x, abs_y)
        _enter_confirm(abs_x, abs_y)
        cv.itemconfig(header_lbl,
            text=f"{progress}标记 [{name}]  (点)  —  已标注，↑↓ 导航 | R 重标 | P 暂停 | ESC 取消")
    else:
        _enter_capture()

    top.deiconify()
    top.focus_force()
    root.wait_window(top)
    return result[0]


def _show_point_overlay(
    name: str, win_x: int = 0, win_y: int = 0,
    prev: dict | None = None, idx: int = 0, total: int = 0,
) -> tuple[str, tuple[int, int] | None]:
    _ensure_overlay_thread()
    result_q: _queue.Queue = _queue.Queue()
    _overlay_queue.put({
        "action": "modal",
        "kind": "point",
        "kwargs": {"name": name, "win_x": win_x, "win_y": win_y,
                   "prev": prev, "idx": idx, "total": total},
        "_result": result_q,
    })
    return result_q.get()


def _run_box_modal(
    root,
    name: str, win_x: int = 0, win_y: int = 0,
    prev: dict | None = None, idx: int = 0, total: int = 0,
) -> tuple[str, dict | None]:
    """Box capture UI, runs inside the dedicated Tk thread on a Toplevel."""
    import tkinter as tk
    from PIL import ImageEnhance, ImageTk
    import pyautogui

    screen = pyautogui.screenshot()
    sw, sh = screen.size
    dark_img = ImageEnhance.Brightness(screen).enhance(0.4)

    result = [("cancel", None)]
    start  = [None, None]
    box    = [None]       # {x,y,w,h} absolute
    state  = ["idle"]     # idle | dragging | confirm

    top = tk.Toplevel(root)
    top.withdraw()
    top.overrideredirect(True)
    top.attributes("-topmost", True)
    top.geometry(f"{sw}x{sh}+0+0")

    cv = tk.Canvas(top, cursor="crosshair", highlightthickness=0, bg="#000")
    cv.pack(fill="both", expand=True)

    bg_photo = ImageTk.PhotoImage(dark_img)
    bg_item = cv.create_image(0, 0, anchor="nw", image=bg_photo)
    photo_ref = [bg_photo]  # keep reference alive; replaced on resume

    # ── Header ──
    cv.create_rectangle(0, 0, sw, 48, fill="#111", outline="")
    progress = f"[{idx}/{total}]  " if total else ""
    header_lbl = cv.create_text(
        sw // 2, 24,
        text=f"{progress}标记 [{name}]  (框)  —  按住左键拖拽选框  |  ESC 取消",
        fill="#ccc", font=_FONT_UI, anchor="center",
    )

    # ── Idle crosshair ──
    h_line = cv.create_line(0, sh//2, sw, sh//2, fill=_COLOR_CROSS, width=1)
    v_line = cv.create_line(sw//2, 0, sw//2, sh, fill=_COLOR_CROSS, width=1)

    # ── Selection rectangle (hidden until drag) ──
    sel_fill   = cv.create_rectangle(0,0,0,0, fill=_COLOR_FILL, stipple="gray25",
                                      outline="", state="hidden")
    sel_border = cv.create_rectangle(0,0,0,0, outline=_COLOR_CROSS, width=2,
                                      dash=(6,3), fill="", state="hidden")
    size_lbl   = cv.create_text(0,0, text="", fill="white", font=_FONT_MONO,
                                 anchor="nw", state="hidden")

    # ── Confirm footer ──
    fy = sh - 54
    cv.create_rectangle(0, fy, sw, sh, fill="#111", outline="", tags="footer")
    ok_lbl  = cv.create_text(20, fy+16, text="", fill=_COLOR_OK,
                              font=_FONT_MONO, anchor="nw", tags="footer")
    cv.create_text(sw//2, fy+16, text=_NAV_HINT,
                   fill="#888", font=("Microsoft YaHei UI", 11),
                   anchor="n", tags="footer")
    cv.itemconfig("footer", state="hidden")

    # ── Pause button (top right of header) ──
    cv.create_rectangle(sw-90, 9, sw-10, 39, fill="#333", outline="#555", tags="pause_btn")
    cv.create_text(sw-50, 24, text="暂停 [P]", fill="#aaa",
                   font=("Microsoft YaHei UI", 10), anchor="center", tags="pause_btn")

    # ── Previous value hint ──
    if prev:
        px, py = prev["x"]+win_x, prev["y"]+win_y
        pw, ph = prev.get("w",0), prev.get("h",0)
        if pw and ph:
            cv.create_rectangle(px, py, px+pw, py+ph,
                                outline=_COLOR_PREV, dash=(4,4), fill="", width=1)
            cv.create_text(px+2, py-14, text=f"上次 {pw}×{ph}",
                           fill=_COLOR_PREV, font=("Consolas",9), anchor="nw")

    def _pause():
        top.withdraw()
        resume_win = tk.Toplevel(root)
        resume_win.attributes("-topmost", True)
        resume_win.overrideredirect(True)
        ww, wh = 300, 72
        resume_win.geometry(f"{ww}x{wh}+{(sw - ww) // 2}+{sh - wh - 60}")
        resume_win.configure(bg="#1a1a2e")
        tk.Label(
            resume_win, text=f"标注已暂停  [{name}]",
            bg="#1a1a2e", fg="#aaa", font=("Microsoft YaHei UI", 10),
        ).pack(pady=(10, 4))
        def _resume():
            resume_win.destroy()
            def _refresh():
                new_screen = pyautogui.screenshot()
                new_dark = ImageEnhance.Brightness(new_screen).enhance(0.4)
                new_photo = ImageTk.PhotoImage(new_dark)
                cv.itemconfig(bg_item, image=new_photo)
                photo_ref[0] = new_photo
                top.deiconify()
                top.lift()
                top.focus_force()
            top.after(80, _refresh)
        tk.Button(
            resume_win, text="继续标注 ▶", command=_resume,
            bg="#1d6b3e", fg="white", font=("Microsoft YaHei UI", 10, "bold"),
            relief="flat", cursor="hand2", padx=20, pady=2,
        ).pack()

    def _enter_idle():
        state[0] = "idle"
        box[0] = None
        start[0] = start[1] = None
        cv.configure(cursor="crosshair")
        cv.itemconfig(h_line, state="normal")
        cv.itemconfig(v_line, state="normal")
        cv.itemconfig(sel_fill,   state="hidden")
        cv.itemconfig(sel_border, state="hidden")
        cv.itemconfig(size_lbl,   state="hidden")
        cv.itemconfig("footer",   state="hidden")
        cv.itemconfig(header_lbl,
            text=f"{progress}标记 [{name}]  (框)  —  按住左键拖拽选框  |  P 暂停  |  ESC 取消")
        for seq in ("<Return>","<Down>","<Up>","r","R"):
            top.unbind(seq)

    def _enter_confirm():
        state[0] = "confirm"
        cv.configure(cursor="")
        cv.itemconfig(h_line,   state="hidden")
        cv.itemconfig(v_line,   state="hidden")
        cv.itemconfig(size_lbl, state="hidden")
        cv.itemconfig("footer", state="normal")
        b = box[0]
        bx,by,bw,bh = b["x"],b["y"],b["w"],b["h"]
        cv.coords(sel_fill,   bx, by, bx+bw, by+bh)
        cv.coords(sel_border, bx, by, bx+bw, by+bh)
        if win_x or win_y:
            txt = f"已记录  绝对({bx},{by})  →  相对({bx-win_x},{by-win_y})  {bw}×{bh}"
        else:
            txt = f"已记录  ({bx},{by})  {bw}×{bh}"
        cv.itemconfig(ok_lbl, text=txt)
        cv.itemconfig(header_lbl, text=f"{progress}标记 [{name}]  (框)  —  确认或导航  |  P 暂停")
        top.bind("<Return>", lambda e: _done("next"))
        top.bind("<Down>",   lambda e: _done("next"))
        top.bind("<Up>",     lambda e: _done("prev"))
        top.bind("r",        lambda e: _enter_idle())
        top.bind("R",        lambda e: _enter_idle())

    def _done(action):
        result[0] = (action, box[0])
        top.destroy()

    def _on_motion(event):
        if state[0] == "idle":
            cv.coords(h_line, 0, event.y, sw, event.y)
            cv.coords(v_line, event.x, 0, event.x, sh)

    def _on_press(event):
        if state[0] != "idle":
            return
        state[0] = "dragging"
        start[0], start[1] = event.x, event.y
        cv.itemconfig(h_line, state="hidden")
        cv.itemconfig(v_line, state="hidden")

    def _on_drag(event):
        if state[0] != "dragging":
            return
        x1,y1 = start[0],start[1]
        x2,y2 = event.x, event.y
        rx1,ry1 = min(x1,x2), min(y1,y2)
        rx2,ry2 = max(x1,x2), max(y1,y2)
        w,h = rx2-rx1, ry2-ry1
        cv.coords(sel_fill,   rx1,ry1,rx2,ry2)
        cv.coords(sel_border, rx1,ry1,rx2,ry2)
        cv.itemconfig(sel_fill,   state="normal")
        cv.itemconfig(sel_border, state="normal")
        lx = min(rx2+6, sw-100)
        ly = max(ry1-22, 52)
        cv.coords(size_lbl, lx, ly)
        cv.itemconfig(size_lbl, text=f"{w}×{h}", state="normal")

    def _on_release(event):
        if state[0] != "dragging":
            return
        x1,y1 = start[0],start[1]
        x2,y2 = event.x, event.y
        w,h = abs(x2-x1), abs(y2-y1)
        if w > 5 and h > 5:
            box[0] = {"x": min(x1,x2), "y": min(y1,y2), "w": w, "h": h}
            _enter_confirm()
        else:
            _enter_idle()

    cv.bind("<Motion>",          _on_motion)
    cv.bind("<ButtonPress-1>",   _on_press)
    cv.bind("<B1-Motion>",       _on_drag)
    cv.bind("<ButtonRelease-1>", _on_release)
    cv.tag_bind("pause_btn", "<Button-1>", lambda e: _pause())
    top.bind("p", lambda e: _pause())
    top.bind("P", lambda e: _pause())
    top.bind("<Escape>", lambda e: (result.__setitem__(0, ("cancel", None)), top.destroy()))

    if prev and prev.get("w") and prev.get("h"):
        abs_x, abs_y = prev["x"] + win_x, prev["y"] + win_y
        box[0] = {"x": abs_x, "y": abs_y, "w": prev["w"], "h": prev["h"]}
        _enter_confirm()
        cv.itemconfig(header_lbl,
            text=f"{progress}标记 [{name}]  (框)  —  已标注，↑↓ 导航 | R 重标 | P 暂停 | ESC 取消")
    else:
        _enter_idle()

    top.deiconify()
    top.focus_force()
    root.wait_window(top)
    return result[0]


def _show_box_overlay(
    name: str, win_x: int = 0, win_y: int = 0,
    prev: dict | None = None, idx: int = 0, total: int = 0,
) -> tuple[str, dict | None]:
    _ensure_overlay_thread()
    result_q: _queue.Queue = _queue.Queue()
    _overlay_queue.put({
        "action": "modal",
        "kind": "box",
        "kwargs": {"name": name, "win_x": win_x, "win_y": win_y,
                   "prev": prev, "idx": idx, "total": total},
        "_result": result_q,
    })
    return result_q.get()


# ── Per-marker capture (wraps overlay) ───────────────────────────────────────

def _capture_point(
    name: str, prev: dict | None = None,
    win_x: int = 0, win_y: int = 0,
    idx: int = 0, total: int = 0,
) -> tuple[str, dict | None]:
    action, pos = _show_point_overlay(name, win_x, win_y, prev, idx, total)
    if action == "cancel" or pos is None:
        return "cancel", None
    x, y = pos
    return action, {"x": x - win_x, "y": y - win_y}


def _capture_box(
    name: str, prev: dict | None = None,
    win_x: int = 0, win_y: int = 0,
    idx: int = 0, total: int = 0,
) -> tuple[str, dict | None]:
    action, raw = _show_box_overlay(name, win_x, win_y, prev, idx, total)
    if action == "cancel" or raw is None:
        return "cancel", None
    return action, {"x": raw["x"] - win_x, "y": raw["y"] - win_y,
                    "w": raw["w"], "h": raw["h"]}


# ── Annotation session ────────────────────────────────────────────────────────

def _run_annotation(project_id: str, project_name: str, markers: list[dict]) -> list[dict]:
    total = len(markers)
    print(f"\n{'='*55}")
    print(f"  标注项目: {project_name}  共 {total} 个标记")
    print(f"{'='*55}")

    window = _select_window()
    win_x = window["x"] if window else 0
    win_y = window["y"] if window else 0
    if window:
        print(f"\n  目标窗口: {window['process']}  {window['title']}")
        print(f"  窗口位置: ({win_x}, {win_y})  大小: {window['w']}×{window['h']}")
    else:
        print("\n  未绑定窗口，记录绝对坐标")
    print(f"{'='*55}\n")

    # Pre-populate from server-provided existing captures
    captured: dict[int, dict] = {}
    for i, marker in enumerate(markers):
        existing = marker.get("existing")
        if existing and existing.get("x") is not None:
            captured[i] = {k: v for k, v in existing.items() if k in ("x", "y", "w", "h")}

    idx = 0
    cancelled = False

    while 0 <= idx < total:
        marker = markers[idx]
        name, mtype = marker["name"], marker["type"]
        prev = captured.get(idx)

        try:
            if mtype == "point":
                action, coords = _capture_point(name, prev, win_x, win_y, idx+1, total)
            else:
                action, coords = _capture_box(name, prev, win_x, win_y, idx+1, total)
        except Exception as e:
            logger.error(f"标注 [{name}] 失败: {e}")
            idx += 1
            continue

        if action == "cancel":
            cancelled = True
            break

        if coords is not None:
            captured[idx] = coords

        if action == "prev":
            idx = max(0, idx - 1)
        else:
            idx += 1

    results = [
        {"name": markers[i]["name"], "type": markers[i]["type"], **captured[i]}
        for i in sorted(captured)
    ]

    if results:
        data = _load_markers()
        project_data = data.get(project_id, {})
        if window:
            project_data["_window"] = {
                "title": window["title"], "process": window["process"],
                "x": win_x, "y": win_y, "w": window["w"], "h": window["h"],
            }
        else:
            project_data.pop("_window", None)
        for r in results:
            project_data[r["name"]] = {k: v for k, v in r.items() if k not in ("name","type")}
        data[project_id] = project_data
        _save_markers(data)
        print(f"  已保存 {len(results)}/{total} 个标记到 markers.json")
        if window:
            print(f"  窗口绑定: {window['process']}  {window['title']}")

    if cancelled and len(results) < total:
        print(f"  （{total - len(results)} 个标记未完成）")
    print(f"{'='*55}\n")
    return results


# ── Unicode text input via clipboard ─────────────────────────────────────────

def _type_text(text: str) -> None:
    """Input *text* into the focused field via clipboard paste.

    Ctrl+A clears any existing content, then the text is pasted via Ctrl+V.
    Handles all Unicode characters (Chinese, etc.) without key-mapping issues.
    """
    import pyperclip
    import pyautogui
    import time

    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.05)
    pyperclip.copy(text)
    pyautogui.hotkey("ctrl", "v")


# ── Async helper ──────────────────────────────────────────────────────────────

def _run_blocking(fn, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return loop.run_in_executor(None, lambda: fn(*args, **kwargs))


def _int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _require_int(v, field_name: str) -> int:
    """Like _int, but raises instead of silently defaulting — for coordinates
    where a wrong-but-unnoticed value (e.g. 0,0) could click the wrong thing."""
    try:
        return int(v)
    except (TypeError, ValueError):
        raise ValueError(f"参数 '{field_name}' 不是合法整数: {v!r}")


# ── Command handler ───────────────────────────────────────────────────────────

class CommandHandler:
    def __init__(self, send_fn: Callable):
        self._send = send_fn
        self._handlers: dict[str, Callable] = {
            "capture_screenshot":         self.handle_capture_screenshot,
            "execute_node":               self.handle_execute_node,
            "set_markers":                self.handle_set_markers,
            "restore_window":             self.handle_restore_window,
            "resize_window_interactive":  self.handle_resize_window_interactive,
            "resize_window_to_size":      self.handle_resize_window_to_size,
            "stop":                       self.handle_stop,
            "get_status":                 self.handle_get_status,
            "compute_node":               self.handle_compute_node,
            "get_window_list":            self.handle_get_window_list,
            "capture_template_region":    self.handle_capture_template_region,
        }
        self._stop_flag = False
        self._active_tasks = 0

    @property
    def status(self) -> str:
        return "busy" if self._active_tasks > 0 else "idle"

    async def dispatch(self, msg: dict) -> None:
        msg_type = msg.get("type")
        handler  = self._handlers.get(msg_type)
        if handler:
            busy_types = {"execute_node", "compute_node", "capture_screenshot"}
            if msg_type in busy_types:
                self._active_tasks += 1
            try:
                await handler(msg)
            except Exception as e:
                logger.exception(f"Error handling '{msg_type}': {e}")
            finally:
                if msg_type in busy_types:
                    self._active_tasks -= 1
        else:
            logger.debug(f"Unknown message type: {msg_type}")

    async def handle_set_markers(self, msg: dict) -> None:
        project_id   = msg.get("project_id", "")
        project_name = msg.get("project_name", project_id)
        markers      = msg.get("markers", [])
        if not markers:
            await self._send({"type": "markers_captured", "project_id": project_id, "markers": []})
            return
        logger.info(f"Starting annotation for '{project_name}' ({len(markers)} markers)")
        results = await _run_blocking(_run_annotation, project_id, project_name, markers)
        # Include window binding so server can persist it for cross-device sync
        saved = _load_markers()
        window_info = saved.get(project_id, {}).get("_window")
        await self._send({
            "type": "markers_captured",
            "project_id": project_id,
            "markers": results,
            "window": window_info,
        })

    async def handle_restore_window(self, msg: dict) -> None:
        title   = msg.get("title", "")
        process = msg.get("process", "")
        x, y    = msg.get("x", 0), msg.get("y", 0)
        w, h    = msg.get("w"), msg.get("h")
        if not (title and w and h):
            logger.warning("restore_window: missing title/w/h, skipping")
            return
        win = _find_window(title, process)
        if not win:
            logger.warning(f"restore_window: window '{title}' not found")
            return
        try:
            hwnd = win["hwnd"]
            if ctypes.windll.user32.IsIconic(hwnd) or ctypes.windll.user32.IsZoomed(hwnd):
                ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE before MoveWindow
            ctypes.windll.user32.MoveWindow(hwnd, x, y, w, h, True)
            logger.info(f"restore_window: moved '{title}' to ({x},{y}) size {w}×{h}")
        except Exception as e:
            logger.error(f"restore_window: MoveWindow failed: {e}")

    async def handle_resize_window_interactive(self, msg: dict) -> None:
        project_id     = msg.get("project_id", "")
        window_title   = msg.get("window_title", "")
        window_process = msg.get("window_process", "")
        old_w          = int(msg.get("window_w") or 0)
        old_h          = int(msg.get("window_h") or 0)

        if not window_title:
            logger.warning("resize_window_interactive: missing window_title")
            return

        logger.info(f"resize_window_interactive: '{window_title}' current {old_w}×{old_h}")
        result = await _run_blocking(
            _show_resize_window_dialog,
            window_title, window_process, old_w, old_h,
        )

        if result is None:
            logger.info("resize_window_interactive: cancelled by user")
            return

        new_x, new_y, new_w, new_h = result
        logger.info(f"resize_window_interactive: new pos ({new_x},{new_y}) size {new_w}×{new_h}")
        await self._send({
            "type":           "window_resized",
            "project_id":     project_id,
            "window_title":   window_title,
            "window_process": window_process,
            "new_x":          new_x,
            "new_y":          new_y,
            "new_w":          new_w,
            "new_h":          new_h,
        })

    async def handle_resize_window_to_size(self, msg: dict) -> None:
        project_id     = msg.get("project_id", "")
        window_title   = msg.get("window_title", "")
        window_process = msg.get("window_process", "")
        target_w       = int(msg.get("target_w") or 0)
        target_h       = int(msg.get("target_h") or 0)

        if not window_title or not target_w or not target_h:
            logger.warning("resize_window_to_size: missing window_title/target_w/target_h")
            return

        win = _find_window(window_title, window_process)
        if not win:
            logger.warning(f"resize_window_to_size: window '{window_title}' not found")
            return

        hwnd = win["hwnd"]
        new_x, new_y = win["x"], win["y"]
        try:
            if ctypes.windll.user32.IsIconic(hwnd) or ctypes.windll.user32.IsZoomed(hwnd):
                ctypes.windll.user32.ShowWindow(hwnd, 9)
            ctypes.windll.user32.MoveWindow(hwnd, new_x, new_y, target_w, target_h, True)
            logger.info(f"resize_window_to_size: '{window_title}' → {target_w}×{target_h}")
        except Exception as e:
            logger.error(f"resize_window_to_size: MoveWindow failed: {e}")
            return

        await self._send({
            "type":           "window_resized",
            "project_id":     project_id,
            "window_title":   window_title,
            "window_process": window_process,
            "new_x":          new_x,
            "new_y":          new_y,
            "new_w":          target_w,
            "new_h":          target_h,
        })

    async def handle_capture_screenshot(self, msg: dict) -> None:
        request_id = msg.get("request_id")
        params: dict = msg.get("params") or {}
        server_markers: dict | None = msg.get("_markers")
        project_id: str = msg.get("project_id", "")
        try:
            import pyautogui
            range_marker_name = params.get("range_marker", "").strip()
            window_title = params.get("window_title", "").strip()
            window_process = params.get("window_process", "").strip()

            region = None

            if range_marker_name:
                # Screenshot node: lock to marker's window, error if no binding
                raw = (server_markers or {}).get(range_marker_name)
                if raw is None and project_id:
                    _ld = _load_markers()
                    _m = _ld.get(project_id, {}).get(range_marker_name)
                    _w = _ld.get(project_id, {}).get("_window")
                    if _m and _w:
                        raw = dict(_m)
                        raw["window_title"] = _w.get("title", "")
                        raw["window_process"] = _w.get("process", "")
                if not raw:
                    await self._send({"type": "screenshot_response", "request_id": request_id,
                                      "success": False, "error": f"Screenshot: marker '{range_marker_name}' not found"})
                    return
                m_win_title = raw.get("window_title", "").strip()
                m_win_process = raw.get("window_process", "").strip()
                if not m_win_title:
                    await self._send({"type": "screenshot_response", "request_id": request_id,
                                      "success": False, "error": f"Screenshot: marker '{range_marker_name}' 未绑定窗口，请先完成标注"})
                    return
                win = _find_window(m_win_title, m_win_process)
                if not win:
                    await self._send({"type": "screenshot_response", "request_id": request_id,
                                      "success": False, "error": f"Screenshot: 绑定窗口「{m_win_title}」未找到，请确认窗口已打开"})
                    return
                try:
                    _activate_window(win["hwnd"])
                except Exception:
                    pass
                mx = _int(raw.get("x"), 0)
                my = _int(raw.get("y"), 0)
                mw = _int(raw.get("w"), 0)
                mh = _int(raw.get("h"), 0)
                if mw <= 0 or mh <= 0:
                    await self._send({"type": "screenshot_response", "request_id": request_id,
                                      "success": False, "error": f"Screenshot: marker '{range_marker_name}' 不是方框标记"})
                    return
                region = (win["x"] + mx, win["y"] + my, mw, mh)

            elif window_title:
                # Preview mode: screenshot just the bound window area
                win = _find_window(window_title, window_process)
                if not win:
                    await self._send({"type": "screenshot_response", "request_id": request_id,
                                      "success": False, "error": f"Screenshot: 绑定窗口「{window_title}」未找到，请确认窗口已打开"})
                    return
                try:
                    _activate_window(win["hwnd"])
                except Exception:
                    pass
                region = (win["x"], win["y"], win["w"], win["h"])

            screenshot = await _run_blocking(pyautogui.screenshot, region=region)
            buf = io.BytesIO()
            screenshot.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            await self._send({"type": "screenshot_response", "request_id": request_id,
                              "success": True, "screenshot": b64})
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            await self._send({"type": "screenshot_response", "request_id": request_id,
                              "success": False, "error": str(e)})

    async def handle_execute_node(self, msg: dict) -> None:
        node_type     = msg.get("node_type")
        params        = dict(msg.get("params", {}))
        project_id    = msg.get("project_id", "")
        node_id       = msg.get("node_id", "")
        request_id    = msg.get("request_id") or node_id
        server_markers = msg.get("_markers")  # DB coordinates from server (authoritative)
        try:
            if project_id or server_markers:
                params = _resolve_marker_params(params, project_id, server_markers)
            if node_type in ("template_match", "ocr", "ai_vision", "color_detect"):
                success, output, error = await self._execute_vision(
                    node_type, params, project_id, server_markers, node_id
                )
            else:
                success, output, error = await self._execute_action(node_type, params)
        except Exception as e:
            success, output, error = False, {}, str(e)
        await self._send({
            "type": "node_result",
            "node_id":    msg.get("node_id"),
            "request_id": request_id,
            "success": success, "output": output, "error": error,
        })

    async def _execute_action(self, action_type: str, params: dict) -> tuple[bool, dict, str | None]:
        import pyautogui
        pyautogui.FAILSAFE = False

        try:
            if action_type == "mouse_click":
                x, y = _require_int(params.get("x"), "x"), _require_int(params.get("y"), "y")
                await _run_blocking(pyautogui.click, x, y,
                                    button=params.get("button","left"),
                                    clicks=_int(params.get("clicks"), 1))
                return True, {"x": x, "y": y}, None

            if action_type == "mouse_double_click":
                x, y = _require_int(params.get("x"), "x"), _require_int(params.get("y"), "y")
                interval = _int(params.get("interval_ms"), 100) / 1000.0
                button = params.get("button") or "left"
                await _run_blocking(pyautogui.click, x, y,
                                    clicks=2,
                                    interval=interval,
                                    button=button)
                return True, {"x": x, "y": y}, None

            if action_type == "mouse_move":
                x, y = _require_int(params.get("x"), "x"), _require_int(params.get("y"), "y")
                await _run_blocking(pyautogui.moveTo, x, y, duration=float(params.get("duration") or 0.2))
                return True, {"x": x, "y": y}, None

            if action_type == "mouse_drag":
                x1, y1 = _require_int(params.get("x1"), "x1"), _require_int(params.get("y1"), "y1")
                x2, y2 = _require_int(params.get("x2"), "x2"), _require_int(params.get("y2"), "y2")
                await _run_blocking(pyautogui.moveTo, x1, y1)
                await _run_blocking(pyautogui.dragTo, x2, y2,
                                    duration=float(params.get("duration") or 0.3))
                return True, {}, None

            if action_type == "keyboard_type":
                text = str(params.get("text", ""))
                await _run_blocking(_type_text, text)
                return True, {"length": len(text)}, None

            if action_type == "keyboard_hotkey":
                keys = params.get("keys", [])
                if isinstance(keys, str):
                    keys = keys.split("+")
                hold_ms = _int(params.get("hold_ms"), 0)
                if hold_ms > 0:
                    import time
                    def _hold():
                        for key in keys:
                            pyautogui.keyDown(key)
                        time.sleep(hold_ms / 1000.0)
                        for key in reversed(keys):
                            pyautogui.keyUp(key)
                    await _run_blocking(_hold)
                else:
                    await _run_blocking(pyautogui.hotkey, *keys)
                return True, {"keys": keys}, None

            if action_type == "keyboard_press":
                key = params.get("key", "")
                await _run_blocking(pyautogui.press, key, presses=_int(params.get("presses"), 1))
                return True, {"key": key}, None

            if action_type == "mouse_scroll":
                if "direction" in params:
                    amount = _int(params.get("amount"), 3)
                    clicks = amount if params["direction"] == "up" else -amount
                else:
                    clicks = _int(params.get("clicks"), 3)  # backward compat
                x = params.get("x")
                y = params.get("y")
                if x is not None and y is not None:
                    await _run_blocking(pyautogui.scroll, clicks, _require_int(x, "x"), _require_int(y, "y"))
                else:
                    await _run_blocking(pyautogui.scroll, clicks)
                return True, {}, None
        except ValueError as e:
            return False, {}, str(e)

        return False, {}, f"Unknown action_type: {action_type}"

    async def _execute_vision(
        self, vision_type: str, params: dict, project_id: str,
        server_markers: dict | None = None,
        node_id: str = "",
    ) -> tuple[bool, dict, str | None]:
        import pyautogui

        range_marker_name = params.get("range_marker", "").strip()
        if range_marker_name:
            # Get raw (window-relative) coords — server_markers is authoritative
            raw = (server_markers or {}).get(range_marker_name)
            if raw is None and project_id:
                # Legacy fallback: read raw coords from markers.json without resolving
                _ld = _load_markers()
                _m = _ld.get(project_id, {}).get(range_marker_name)
                _w = _ld.get(project_id, {}).get("_window")
                if _m and _w:
                    raw = dict(_m)
                    raw["window_title"] = _w.get("title", "")
                    raw["window_process"] = _w.get("process", "")
            if not raw:
                hint = "请先完成标记标注" if server_markers is not None else f"project '{project_id}'"
                return False, {}, f"Vision node: marker '{range_marker_name}' not found ({hint})"

            mx = _int(raw.get("x"), 0)
            my = _int(raw.get("y"), 0)
            mw = _int(raw.get("w"), 0)
            mh = _int(raw.get("h"), 0)

            if mw <= 0 or mh <= 0:
                return False, {}, f"Vision node: marker '{range_marker_name}' 不是方框标记（缺少 w/h）"

            # Lock to the marker's bound window (error if no binding)
            m_win_title = (raw.get("window_title") or "").strip()
            m_win_process = (raw.get("window_process") or "").strip()
            if not m_win_title:
                return False, {}, f"Vision node: marker '{range_marker_name}' 未绑定窗口，请先完成标注"
            win = _find_window(m_win_title, m_win_process)
            if not win:
                return False, {}, f"Vision node: 绑定窗口「{m_win_title}」未找到，请确认窗口已打开"
            try:
                _activate_window(win["hwnd"])
            except Exception:
                pass
            abs_x = win["x"] + mx
            abs_y = win["y"] + my
        else:
            # No range marker — use the full project bound window as detection area
            win_title = win_process = ""
            if server_markers:
                for m_data in server_markers.values():
                    if m_data.get("window_title"):
                        win_title = m_data["window_title"]
                        win_process = m_data.get("window_process", "")
                        break
            if not win_title:
                return False, {}, "Vision node: 未选择检测范围且项目未绑定窗口"
            win = _find_window(win_title, win_process)
            if not win:
                return False, {}, f"Vision node: 未找到绑定窗口「{win_title}」，请确认窗口已打开"
            try:
                _activate_window(win["hwnd"])
            except Exception:
                pass
            abs_x, abs_y, mw, mh = win["x"], win["y"], win["w"], win["h"]

        screenshot = await _run_blocking(pyautogui.screenshot, region=(abs_x, abs_y, mw, mh))

        if vision_type == "template_match":
            template_b64 = params.get("template_b64", "")
            if not template_b64:
                return False, {}, "Template match: no template configured"

            threshold = float(params.get("threshold", 0.8))
            match_mode = params.get("mode") or "single"
            use_gpu = bool(params.get("use_gpu", False))
            region_offset = (abs_x, abs_y)

            def _do_match():
                import cv2
                import numpy as np

                buf = io.BytesIO()
                screenshot.save(buf, format="PNG")
                sc_arr = np.frombuffer(buf.getvalue(), np.uint8)
                sc_img = cv2.imdecode(sc_arr, cv2.IMREAD_COLOR)

                tmpl_bytes = base64.b64decode(template_b64)
                tmpl_arr = np.frombuffer(tmpl_bytes, np.uint8)
                tmpl_img = cv2.imdecode(tmpl_arr, cv2.IMREAD_COLOR)

                if sc_img is None or tmpl_img is None:
                    return {"found": False, "confidence": 0.0, "location": None, "error": "Failed to decode images"}

                th, tw = tmpl_img.shape[:2]

                # Try CUDA path; fall back to CPU if unavailable
                cuda_ok = False
                cuda_error: str | None = None
                if use_gpu:
                    try:
                        cuda_matcher = cv2.cuda.createTemplateMatching(cv2.CV_8UC3, cv2.TM_CCOEFF_NORMED)
                        gpu_sc = cv2.cuda_GpuMat()
                        gpu_tmpl = cv2.cuda_GpuMat()
                        gpu_sc.upload(sc_img)
                        gpu_tmpl.upload(tmpl_img)
                        gpu_res = cuda_matcher.match(gpu_sc, gpu_tmpl)
                        res = gpu_res.download()
                        cuda_ok = True
                    except Exception as _cuda_exc:
                        cuda_error = str(_cuda_exc)

                if not cuda_ok:
                    res = cv2.matchTemplate(sc_img, tmpl_img, cv2.TM_CCOEFF_NORMED)

                if match_mode == "all_matches":
                    ys, xs = np.where(res >= threshold)
                    candidates = sorted(
                        zip(xs.tolist(), ys.tolist()),
                        key=lambda p: float(res[p[1], p[0]]),
                        reverse=True,
                    )
                    accepted: list[tuple[int, int]] = []
                    locations = []
                    for mx2, my2 in candidates:
                        if any(abs(mx2 - ax) < tw // 2 and abs(my2 - ay) < th // 2 for ax, ay in accepted):
                            continue
                        accepted.append((mx2, my2))
                        locations.append({
                            "x": region_offset[0] + mx2 + tw // 2,
                            "y": region_offset[1] + my2 + th // 2,
                        })
                    max_conf = float(res[candidates[0][1], candidates[0][0]]) if candidates else 0.0
                    return {"found": len(locations) > 0, "confidence": max_conf,
                            "locations": locations, "_tmpl_w": tw, "_tmpl_h": th,
                            "_cuda": cuda_ok, "_cuda_error": cuda_error}

                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                found = float(max_val) >= threshold
                cx = region_offset[0] + max_loc[0] + tw // 2
                cy = region_offset[1] + max_loc[1] + th // 2
                return {
                    "found": found,
                    "confidence": float(max_val),
                    "location": {"x": cx, "y": cy} if found else None,
                    "_tmpl_w": tw, "_tmpl_h": th, "_cuda": cuda_ok, "_cuda_error": cuda_error,
                }

            try:
                result = await _run_blocking(_do_match)
                tmpl_w = result.pop("_tmpl_w", 0)
                tmpl_h = result.pop("_tmpl_h", 0)
                cuda_used = result.pop("_cuda", False)
                # cuda_error stays in result so the server can log it
                if use_gpu:
                    if cuda_used:
                        logger.info("Template match: CUDA")
                    else:
                        logger.warning(f"Template match: GPU requested but CUDA failed, using CPU. reason={result.get('cuda_error')}")
                if result.get("found") and params.get("show_overlay"):
                    locs = result.get("locations") or (
                        [result["location"]] if result.get("location") else []
                    )
                    overlay_mode = params.get("overlay_mode", "fixed")
                    duration = (
                        None if overlay_mode == "until_next"
                        else float(params.get("overlay_duration") or CV_OVERLAY_DURATION_S)
                    )
                    _show_match_overlay(node_id, locs, tmpl_w, tmpl_h, duration)
                return True, result, None
            except Exception as e:
                return False, {}, str(e)

        else:
            # OCR / AI vision / color detect: return cropped screenshot to server
            buf = io.BytesIO()
            screenshot.save(buf, format="PNG")
            screenshot_b64 = base64.b64encode(buf.getvalue()).decode()
            return True, {"screenshot": screenshot_b64}, None

    async def handle_compute_node(self, msg: dict) -> None:
        request_id = msg.get("request_id") or msg.get("node_id")
        code: str = msg.get("code", "")
        context: dict = dict(msg.get("context", {}))
        try:
            namespace: dict = {**context, "context": context}
            exec(compile(code, "<compute>", "exec"), namespace)
            import json, types
            def _json_serializable(v):
                try:
                    json.dumps(v)
                    return True
                except (TypeError, ValueError):
                    return False

            # Collect direct variable assignments (both existing and new keys)
            updated_context = dict(context)
            for k, v in namespace.items():
                if not k.startswith("__") and k != "context" and not isinstance(v, types.ModuleType) and _json_serializable(v):
                    updated_context[k] = v
            # Also apply context["x"] = y style updates
            for k, v in namespace.get("context", {}).items():
                if _json_serializable(v):
                    updated_context[k] = v
            await self._send({
                "type": "node_result",
                "request_id": request_id,
                "node_id": msg.get("node_id"),
                "success": True,
                "output": {"updated_context": updated_context},
                "error": None,
            })
        except Exception as e:
            logger.error(f"Compute node execution failed: {e}")
            await self._send({
                "type": "node_result",
                "request_id": request_id,
                "node_id": msg.get("node_id"),
                "success": False,
                "output": {},
                "error": str(e),
            })

    async def handle_get_window_list(self, msg: dict) -> None:
        request_id = msg.get("request_id")
        windows = await _run_blocking(_list_windows)
        await self._send({
            "type": "window_list_response",
            "request_id": request_id,
            "windows": [
                {"title": w["title"], "process": w["process"],
                 "x": w["x"], "y": w["y"], "w": w["w"], "h": w["h"]}
                for w in windows
            ],
        })

    async def handle_capture_template_region(self, msg: dict) -> None:
        request_id = msg.get("request_id")

        win = await _run_blocking(_show_window_select_modal)
        if win is None:
            await self._send({
                "type": "template_region_response",
                "request_id": request_id,
                "success": False,
                "error": "用户取消选择窗口",
            })
            return

        try:
            await _run_blocking(_activate_window, win["hwnd"])
        except Exception:
            pass
        win_x, win_y = win["x"], win["y"]

        action, box = await _run_blocking(
            _show_box_overlay,
            "__template__", win_x, win_y, None, 0, 0,
        )
        if action == "cancel" or box is None:
            await self._send({
                "type": "template_region_response",
                "request_id": request_id,
                "success": False,
                "error": "用户取消截图",
            })
            return

        import pyautogui
        # box["x"/"y"] are absolute screen coords from the full-screen overlay;
        # win_x/y is passed to _show_box_overlay only for the "相对" display label.
        abs_x = box["x"]
        abs_y = box["y"]
        screenshot = await _run_blocking(
            pyautogui.screenshot, region=(abs_x, abs_y, box["w"], box["h"])
        )
        buf = io.BytesIO()
        screenshot.save(buf, format="PNG")
        image_b64 = base64.b64encode(buf.getvalue()).decode()

        await self._send({
            "type": "template_region_response",
            "request_id": request_id,
            "success": True,
            "image_b64": image_b64,
            "window_w": win["w"],
            "window_h": win["h"],
            "window_title": win["title"],
        })

    async def handle_stop(self, msg: dict) -> None:
        logger.info(f"Stop signal received: {msg.get('reason')}")
        self._stop_flag = True
        _dismiss_all_overlays()

    async def handle_get_status(self, msg: dict) -> None:
        await self._send({"type": "status_response", "status": self.status,
                          "stop_flag": self._stop_flag})
