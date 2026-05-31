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
        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        if w < 50 or h < 50:
            return True
        windows.append({"hwnd": hwnd, "title": title, "process": process,
                         "x": rect.left, "y": rect.top, "w": w, "h": h})
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
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
    ctypes.windll.user32.ShowWindow(hwnd, 9)   # SW_RESTORE
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


def _show_point_overlay(
    name: str, win_x: int = 0, win_y: int = 0,
    prev: dict | None = None, idx: int = 0, total: int = 0,
) -> tuple[str, tuple[int, int] | None]:
    """Full-screen point capture overlay.
    Returns (action, (abs_x, abs_y)):
      action = 'next' | 'prev' | 'cancel'
    Redo is handled internally (R re-enters capture mode).
    """
    import tkinter as tk
    from PIL import ImageEnhance, ImageTk
    import pyautogui

    screen = pyautogui.screenshot()
    sw, sh = screen.size
    dark_img = ImageEnhance.Brightness(screen).enhance(0.4)

    result = [("cancel", None)]
    captured = [None]

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.geometry(f"{sw}x{sh}+0+0")
    root.focus_force()

    cv = tk.Canvas(root, cursor="crosshair", highlightthickness=0, bg="#000")
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
    nav_lbl = cv.create_text(sw // 2, fy + 16, text=_NAV_HINT,
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
        root.withdraw()
        resume_win = tk.Toplevel()
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
                photo_ref[0] = new_photo
                cv.itemconfig(bg_item, image=new_photo)
                root.deiconify()
                root.lift()
                root.focus_force()
            root.after(80, _refresh)
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
            root.unbind(seq)

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
        root.bind("<Return>", lambda e: _done("next"))
        root.bind("<Down>",   lambda e: _done("next"))
        root.bind("<Up>",     lambda e: _done("prev"))
        root.bind("r",        lambda e: _enter_capture())
        root.bind("R",        lambda e: _enter_capture())

    def _done(action):
        result[0] = (action, captured[0])
        root.destroy()

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
    root.bind("p", lambda e: _pause())
    root.bind("P", lambda e: _pause())
    root.bind("<Escape>", lambda e: (result.__setitem__(0, ("cancel", None)), root.destroy()))

    if prev:
        # Start in confirm mode showing the existing annotation
        abs_x, abs_y = prev["x"] + win_x, prev["y"] + win_y
        captured[0] = (abs_x, abs_y)
        _enter_confirm(abs_x, abs_y)
        cv.itemconfig(header_lbl,
            text=f"{progress}标记 [{name}]  (点)  —  已标注，↑↓ 导航 | R 重标 | P 暂停 | ESC 取消")
    else:
        _enter_capture()

    root.mainloop()
    return result[0]


def _show_box_overlay(
    name: str, win_x: int = 0, win_y: int = 0,
    prev: dict | None = None, idx: int = 0, total: int = 0,
) -> tuple[str, dict | None]:
    """Full-screen box capture overlay (drag to select).
    Returns (action, {x,y,w,h} absolute) or ('cancel', None).
    """
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

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.geometry(f"{sw}x{sh}+0+0")
    root.focus_force()

    cv = tk.Canvas(root, cursor="crosshair", highlightthickness=0, bg="#000")
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
    nav_lbl = cv.create_text(sw//2, fy+16, text=_NAV_HINT,
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
        root.withdraw()
        resume_win = tk.Toplevel()
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
                photo_ref[0] = new_photo
                cv.itemconfig(bg_item, image=new_photo)
                root.deiconify()
                root.lift()
                root.focus_force()
            root.after(80, _refresh)
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
            root.unbind(seq)

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
        root.bind("<Return>", lambda e: _done("next"))
        root.bind("<Down>",   lambda e: _done("next"))
        root.bind("<Up>",     lambda e: _done("prev"))
        root.bind("r",        lambda e: _enter_idle())
        root.bind("R",        lambda e: _enter_idle())

    def _done(action):
        result[0] = (action, box[0])
        root.destroy()

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
    root.bind("p", lambda e: _pause())
    root.bind("P", lambda e: _pause())
    root.bind("<Escape>", lambda e: (result.__setitem__(0, ("cancel", None)), root.destroy()))

    if prev and prev.get("w") and prev.get("h"):
        # Start in confirm mode showing the existing box annotation
        abs_x, abs_y = prev["x"] + win_x, prev["y"] + win_y
        box[0] = {"x": abs_x, "y": abs_y, "w": prev["w"], "h": prev["h"]}
        _enter_confirm()
        cv.itemconfig(header_lbl,
            text=f"{progress}标记 [{name}]  (框)  —  已标注，↑↓ 导航 | R 重标 | P 暂停 | ESC 取消")
    else:
        _enter_idle()

    root.mainloop()
    return result[0]


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


# ── Command handler ───────────────────────────────────────────────────────────

class CommandHandler:
    def __init__(self, send_fn: Callable):
        self._send = send_fn
        self._handlers: dict[str, Callable] = {
            "capture_screenshot": self.handle_capture_screenshot,
            "execute_node":       self.handle_execute_node,
            "set_markers":        self.handle_set_markers,
            "stop":               self.handle_stop,
            "get_status":         self.handle_get_status,
            "compute_node":       self.handle_compute_node,
        }
        self._stop_flag = False

    async def dispatch(self, msg: dict) -> None:
        msg_type = msg.get("type")
        handler  = self._handlers.get(msg_type)
        if handler:
            try:
                await handler(msg)
            except Exception as e:
                logger.exception(f"Error handling '{msg_type}': {e}")
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
        node_type     = msg.get("node_type")
        params        = dict(msg.get("params", {}))
        project_id    = msg.get("project_id", "")
        request_id    = msg.get("request_id") or msg.get("node_id")
        server_markers = msg.get("_markers")  # DB coordinates from server (authoritative)
        if project_id or server_markers:
            params = _resolve_marker_params(params, project_id, server_markers)
        try:
            if node_type in ("template_match", "ocr", "ai_vision", "color_detect"):
                success, output, error = await self._execute_vision(
                    node_type, params, project_id, server_markers
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

        if action_type == "mouse_click":
            x, y = _int(params.get("x"), 0), _int(params.get("y"), 0)
            await _run_blocking(pyautogui.click, x, y,
                                button=params.get("button","left"),
                                clicks=_int(params.get("clicks"), 1))
            return True, {"x": x, "y": y}, None

        if action_type == "mouse_double_click":
            x, y = _int(params.get("x"), 0), _int(params.get("y"), 0)
            await _run_blocking(pyautogui.doubleClick, x, y,
                                button=params.get("button","left"))
            return True, {"x": x, "y": y}, None

        if action_type == "mouse_move":
            x, y = _int(params.get("x"), 0), _int(params.get("y"), 0)
            await _run_blocking(pyautogui.moveTo, x, y, duration=float(params.get("duration") or 0.2))
            return True, {"x": x, "y": y}, None

        if action_type == "mouse_drag":
            x1, y1 = _int(params.get("x1"), 0), _int(params.get("y1"), 0)
            x2, y2 = _int(params.get("x2"), 0), _int(params.get("y2"), 0)
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
            await _run_blocking(pyautogui.hotkey, *keys)
            return True, {"keys": keys}, None

        if action_type == "keyboard_press":
            key = params.get("key", "")
            await _run_blocking(pyautogui.press, key, presses=_int(params.get("presses"), 1))
            return True, {"key": key}, None

        if action_type == "mouse_scroll":
            x, y = _int(params.get("x"), 0), _int(params.get("y"), 0)
            await _run_blocking(pyautogui.scroll, _int(params.get("clicks"), 3), x, y)
            return True, {}, None

        return False, {}, f"Unknown action_type: {action_type}"

    async def _execute_vision(
        self, vision_type: str, params: dict, project_id: str,
        server_markers: dict | None = None,
    ) -> tuple[bool, dict, str | None]:
        import pyautogui

        range_marker_name = params.get("range_marker", "").strip()
        if range_marker_name:
            # Prefer server-provided coordinates (single source of truth)
            if server_markers:
                marker = _get_marker_from_server(range_marker_name, server_markers)
            else:
                marker = get_marker(project_id, range_marker_name) if project_id else None
            if not marker:
                hint = "请先完成标记标注" if server_markers is not None else f"project '{project_id}'"
                return False, {}, f"Vision node: marker '{range_marker_name}' not found ({hint})"

            mx = _int(marker.get("x"), 0)
            my = _int(marker.get("y"), 0)
            mw = _int(marker.get("w"), 0)
            mh = _int(marker.get("h"), 0)

            if mw <= 0 or mh <= 0:
                return False, {}, f"Vision node: marker '{range_marker_name}' 不是方框标记（缺少 w/h）"
        else:
            # No range marker specified — fall back to the project's bound window
            win_title = win_process = ""
            if server_markers:
                for m_data in server_markers.values():
                    if m_data.get("window_title"):
                        win_title = m_data["window_title"]
                        win_process = m_data.get("window_process", "")
                        break
            if not win_title and project_id:
                local_data = _load_markers()
                bound = local_data.get(project_id, {}).get("_window")
                if bound:
                    win_title = bound.get("title", "")
                    win_process = bound.get("process", "")
            if not win_title:
                return False, {}, "Vision node: 未选择检测范围且项目未绑定窗口"
            win = _find_window(win_title, win_process)
            if not win:
                return False, {}, f"Vision node: 未找到绑定窗口 '{win_title}'，请确认窗口已打开"
            mx, my, mw, mh = win["x"], win["y"], win["w"], win["h"]

        screenshot = await _run_blocking(pyautogui.screenshot, region=(mx, my, mw, mh))

        if vision_type == "template_match":
            template_b64 = params.get("template_b64", "")
            if not template_b64:
                return False, {}, "Template match: no template configured"

            threshold = float(params.get("threshold", 0.8))
            # marker offset for converting local match coords back to screen coords
            region_offset = (mx, my)

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

                res = cv2.matchTemplate(sc_img, tmpl_img, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)

                found = float(max_val) >= threshold
                h, w = tmpl_img.shape[:2]
                cx = region_offset[0] + max_loc[0] + w // 2
                cy = region_offset[1] + max_loc[1] + h // 2

                return {
                    "found": found,
                    "confidence": float(max_val),
                    "location": {"x": cx, "y": cy} if found else None,
                }

            try:
                result = await _run_blocking(_do_match)
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
            namespace: dict = {"context": context}
            exec(compile(code, "<compute>", "exec"), namespace)
            updated_context = namespace.get("context", context)
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

    async def handle_stop(self, msg: dict) -> None:
        logger.info(f"Stop signal received: {msg.get('reason')}")
        self._stop_flag = True

    async def handle_get_status(self, msg: dict) -> None:
        await self._send({"type": "status_response", "status": "idle",
                          "stop_flag": self._stop_flag})
