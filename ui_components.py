"""VeriFlow Studio - reusable IDE widgets: Verilog code editor, truth-table grid, mini waveform viewer."""
from __future__ import annotations

import math
import os
import re
import sys
import tkinter as tk
from collections import defaultdict
from tkinter import font as tkfont
from tkinter import ttk
from typing import Callable

import customtkinter as ctk
from pygments.lexers.hdl import SystemVerilogLexer   # direct import: PyInstaller-friendly
from pygments.token import Comment, Keyword, Name, Number, Operator, String

from config_manager import EDITOR_SCHEMES, RADIXES, VS, VSCODE_THEMES
from intellisense import build_items, completion_context, rank
from verilog_parser import parse_verilog_source

IS_WINDOWS = os.name == "nt"
IS_MAC = sys.platform == "darwin"
GATE_WORDS = {"and", "nand", "or", "nor", "xor", "xnor", "not", "buf", "bufif0", "bufif1", "notif0", "notif1"}
TOKEN_TAGS = ("keyword", "control", "type", "gate", "number", "string", "comment", "directive", "systask", "operator", "ident")
TAG_FALLBACK = {"control": "keyword", "ident": "fg"}
TYPE_WORDS = {"wire", "reg", "logic", "integer", "genvar", "signed", "unsigned", "bit", "byte", "int", "real", "time",
              "tri", "tri0", "tri1", "supply0", "supply1", "wand", "wor", "uwire", "var", "shortint", "longint", "realtime"}
CONTROL_WORDS = {"always", "always_comb", "always_ff", "always_latch", "initial", "final", "begin", "end", "if", "else",
                 "for", "foreach", "while", "do", "repeat", "forever", "case", "casex", "casez", "endcase", "default",
                 "posedge", "negedge", "fork", "join", "join_any", "join_none", "generate", "endgenerate", "wait",
                 "disable", "return", "break", "continue", "unique", "priority"}
BADGE = {"DESIGN": ("V", ("#0070C1", "#569CD6")), "TESTBENCH": ("TB", ("#267F99", "#4EC9B0"))}
CURSOR = "‸"   # caret marker inside snippets

SNIPPETS: dict[str, str] = {
    "module ... endmodule": "module NAME (\n    output y,\n    input  a,\n    input  b\n);\n\n    " + CURSOR + "\n\nendmodule\n",
    "initial begin ... end": "initial begin\n    " + CURSOR + "\nend",
    "always @(*)": "always @(*) begin\n    " + CURSOR + "\nend",
    "$monitor(...)": '$monitor("a=%b | b=%b | y=%b", a, b, y);' + CURSOR,
    "$display(...)": '$display("' + CURSOR + '");',
    "$dumpfile + $dumpvars": '$dumpfile("wave.vcd");\n$dumpvars(0, ' + CURSOR + ');',
    "exhaustive for-loop": "for (i = 0; i < (1 << N); i = i + 1) begin\n    {a, b} = i;\n    #10;\nend" + CURSOR,
    "wire declaration": "wire " + CURSOR + ";",
    "nand gate": "nand g1 (" + CURSOR + "y, a, b);",
    "nor gate": "nor g1 (" + CURSOR + "y, a, b);",
    "and gate": "and g1 (" + CURSOR + "y, a, b);",
    "or gate": "or g1 (" + CURSOR + "y, a, b);",
    "xor gate": "xor g1 (" + CURSOR + "y, a, b);",
    "xnor gate": "xnor g1 (" + CURSOR + "y, a, b);",
    "not gate": "not g1 (" + CURSOR + "y, a);",
}
# Windows virtual-key codes -> action (works with Hebrew / any non-Latin keyboard layout)
_VK = {83: "save", 70: "find", 72: "replace", 71: "goto", 191: "comment", 68: "dup", 187: "zoom_in", 107: "zoom_in",
       189: "zoom_out", 109: "zoom_out", 48: "zoom_reset", 96: "zoom_reset", 90: "undo", 89: "redo", 65: "select_all",
       67: "copy", 86: "paste", 88: "cut", 32: "complete"}
_KS = {"s": "save", "f": "find", "h": "replace", "g": "goto", "slash": "comment", "d": "dup", "equal": "zoom_in",
       "plus": "zoom_in", "kp_add": "zoom_in", "minus": "zoom_out", "kp_subtract": "zoom_out", "0": "zoom_reset",
       "z": "undo", "y": "redo", "a": "select_all", "c": "copy", "v": "paste", "x": "cut", "space": "complete"}
COMPLETION_WORDS = ["module", "endmodule", "input", "output", "inout", "wire", "reg", "logic", "integer", "genvar",
                    "parameter", "localparam", "assign", "always", "always_comb", "initial", "begin", "end", "if", "else",
                    "for", "case", "endcase", "default", "posedge", "negedge", "generate", "endgenerate",
                    "and", "or", "nand", "nor", "xor", "xnor", "not", "buf",
                    "$display", "$monitor", "$strobe", "$finish", "$stop", "$time", "$dumpfile", "$dumpvars", "$random",
                    "$readmemb", "$readmemh"]


def ui_scale(widget) -> float:
    """customtkinter's effective DPI x user scaling for the window holding `widget`."""
    try:
        return float(ctk.ScalingTracker.get_widget_scaling(widget))
    except Exception:
        return 1.0


def px_font(points: int | float, widget) -> int:
    """Negative Tk font size (= pixels) so raw tk widgets match CTk's DPI scaling."""
    return -max(6, round(float(points) * 4 / 3 * ui_scale(widget)))


class FontBook:
    """Shared, live-resizable UI fonts. Every CTk widget built with ui_font() holds one of these CTkFont objects,
    so changing the UI font size (A+/A-, Ctrl+wheel, presets) re-flows the whole interface instantly."""
    base = 13
    _fonts: dict = {}

    @classmethod
    def get(cls, delta: int = 0, weight: str = "normal", slant: str = "roman", family: str = "Segoe UI") -> ctk.CTkFont:
        key = (delta, weight, slant, family)
        if key not in cls._fonts:
            cls._fonts[key] = ctk.CTkFont(family=family, size=max(8, cls.base + delta), weight=weight, slant=slant)
        return cls._fonts[key]

    @classmethod
    def set_base(cls, size: int) -> None:
        cls.base = int(size)
        for (delta, _w, _s, _f), f in cls._fonts.items():
            f.configure(size=max(8, cls.base + delta))


def ui_font(delta: int = 0, weight: str = "normal", slant: str = "roman", family: str = "Segoe UI") -> ctk.CTkFont:
    """UI chrome font relative to the user's UI font size (delta 0 = the base size, e.g. 13)."""
    return FontBook.get(delta, weight, slant, family)


def ui_px(widget, delta: int = 0) -> int:
    """Pixel size of the UI font for raw tk widgets (menus, Treeview, canvases, status bar)."""
    return max(9, round((FontBook.base + delta) * ui_scale(widget)))


def style_menu(menu, widget, config) -> None:
    """Readable dark/light context menu: Segoe UI at the UI font size, VS Code colours (DarkMenu or a fallback tk.Menu)."""
    if isinstance(menu, DarkMenu):
        menu.cfg = config
        return
    dark = is_dark(config)
    th = VSCODE_THEMES["Dark" if dark else "Light"]
    menu.configure(font=("Segoe UI", -ui_px(widget, -1)), bg=th["group"], fg="#F0F0F0" if dark else "#1F1F1F",
                   activebackground=th["selected"], activeforeground="#FFFFFF" if dark else "#000000",
                   disabledforeground=th["muted"], bd=1, relief="solid", activeborderwidth=0, tearoff=0)


class DarkMenu:
    """VS Code style context menu: borderless dark popup, Segoe UI at the UI font size, 32px hover rows,
    right-aligned shortcuts and side-opening submenus. Closes on Escape, a click elsewhere or when the app loses focus.

    Drop-in for the tk.Menu calls the app uses: add_command / add_separator / add_cascade / tk_popup / grab_release."""

    _open: "DarkMenu | None" = None          # the root menu currently shown (only one at a time)

    def __init__(self, master, config=None):
        self.master, self.cfg = master, config
        self.items: list[dict] = []
        self.win: tk.Toplevel | None = None
        self.parent: DarkMenu | None = None
        self.child: DarkMenu | None = None
        self.rows: list[tuple[dict, tk.Frame, list]] = []
        self.active = -1
        self._bind_id = None

    # ---- tk.Menu-compatible building API
    def add_command(self, label: str, command=None, accelerator: str = "", state: str = "normal") -> None:
        self.items.append({"kind": "command", "label": label, "command": command, "accel": accelerator, "state": state})

    def add_separator(self) -> None:
        self.items.append({"kind": "sep"})

    def add_cascade(self, label: str, menu: "DarkMenu") -> None:
        menu.parent = self
        self.items.append({"kind": "cascade", "label": label, "menu": menu, "state": "normal"})

    def delete(self, *_a) -> None:
        self.items.clear()

    def configure(self, **_kw) -> None:      # tk.Menu styling calls are harmless no-ops
        pass

    def cget(self, key: str):
        return ("Segoe UI", -ui_px(self.master)) if key == "font" else self._theme().get(key)

    def grab_release(self) -> None:
        pass

    def index(self, _what="end") -> int:
        return len(self.items) - 1 if self.items else -1

    def _theme(self) -> dict:
        dark = is_dark(self.cfg) if self.cfg is not None else ctk.get_appearance_mode() == "Dark"
        return {"bg": "#252526" if dark else "#FFFFFF", "border": "#3C3C3C" if dark else "#CECECE",
                "fg": "#F0F0F0" if dark else "#1F1F1F", "muted": "#9D9D9D" if dark else "#767676",
                "activebackground": "#04395E" if dark else "#E4E6F1", "activeforeground": "#FFFFFF" if dark else "#000000",
                "sep": "#454545" if dark else "#E5E5E5", "disabled": "#6B6B6B" if dark else "#A0A0A0"}

    # ---- showing / hiding
    def tk_popup(self, x: int, y: int, _entry=None) -> None:
        if self.parent is None:
            if DarkMenu._open is not None:
                DarkMenu._open.close_all()
            DarkMenu._open = self
        self._build(x, y)

    def _build(self, x: int, y: int) -> None:
        self._destroy_window()
        th, sc = self._theme(), ui_scale(self.master)
        px = ui_px(self.master)
        f, fa = ("Segoe UI", -px), ("Segoe UI", -max(9, px - round(1 * sc)))
        row_h, pad = int(32 * sc * FontBook.base / 13), int(12 * sc)
        w = self.win = tk.Toplevel(self.master)
        w.withdraw()
        w.overrideredirect(True)
        try:
            w.attributes("-topmost", True)
        except tk.TclError:
            pass
        w.configure(bg=th["border"])
        body = tk.Frame(w, bg=th["bg"], bd=0, highlightthickness=0)
        body.pack(fill="both", expand=True, padx=1, pady=1)
        tk.Frame(body, height=int(4 * sc), bg=th["bg"]).pack(fill="x")
        self.rows, self.active = [], -1
        # rows have a fixed height (pack_propagate off), so they need an explicit width: measure the widest row
        fm, fam = tkfont.Font(root=w, font=f), tkfont.Font(root=w, font=fa)
        row_w = max([int(200 * sc)] + [
            pad + fm.measure(it["label"]) + int(32 * sc)
            + ((fam if it["kind"] == "command" else fm).measure(it.get("accel") or "›") + int(24 * sc) + pad
               if it.get("accel") or it["kind"] == "cascade" else 0)
            for it in self.items if it["kind"] != "sep"])
        for it in self.items:
            if it["kind"] == "sep":
                tk.Frame(body, height=max(1, int(1 * sc)), bg=th["sep"]).pack(fill="x", padx=int(8 * sc), pady=int(4 * sc))
                continue
            disabled = it.get("state") == "disabled"
            row = tk.Frame(body, bg=th["bg"], height=row_h, width=row_w, cursor="hand2" if not disabled else "")
            row.pack(fill="x", padx=int(4 * sc))
            row.pack_propagate(False)
            fg = th["disabled"] if disabled else th["fg"]
            lab = tk.Label(row, text=it["label"], font=f, bg=th["bg"], fg=fg, anchor="w")
            lab.pack(side="left", fill="y", padx=(pad, int(32 * sc)))
            right = it.get("accel") or ("›" if it["kind"] == "cascade" else "")
            widgets = [row, lab]
            if right:
                acc = tk.Label(row, text=right, font=fa if it["kind"] == "command" else f, bg=th["bg"],
                               fg=th["muted"] if not disabled else th["disabled"], anchor="e")
                acc.pack(side="right", fill="y", padx=(int(24 * sc), pad))
                widgets.append(acc)
            idx = len(self.rows)
            self.rows.append((it, row, widgets))
            for wd in widgets:
                wd.bind("<Enter>", lambda e, i=idx: self._hover(i))
                wd.bind("<ButtonRelease-1>", lambda e, i=idx: self._activate(i))
        tk.Frame(body, height=int(4 * sc), bg=th["bg"]).pack(fill="x")
        w.update_idletasks()
        ww, wh = w.winfo_reqwidth(), w.winfo_reqheight()
        sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
        x = min(x, sw - ww - 4) if self.parent is None else (x if x + ww <= sw else x - ww - self.parent.win.winfo_width())
        y = min(y, sh - wh - 4)
        w.geometry(f"+{max(0, x)}+{max(0, y)}")
        w.deiconify()
        w.lift()
        w.bind("<Escape>", lambda e: self.close_all())
        w.bind("<Up>", lambda e: self._move(-1))
        w.bind("<Down>", lambda e: self._move(1))
        w.bind("<Return>", lambda e: self.active >= 0 and self._activate(self.active))
        w.bind("<Right>", lambda e: self.active >= 0 and self.rows[self.active][0]["kind"] == "cascade" and self._activate(self.active))
        w.bind("<Left>", lambda e: self.parent is not None and self.close())
        w.bind("<FocusOut>", lambda e: self.master.after(80, self._check_focus))
        w.focus_force()
        if self.parent is None:      # a click anywhere else in the app closes the menu (armed after this event)
            self.master.after_idle(self._arm_outside_click)

    def _arm_outside_click(self) -> None:
        if self.win is None or self._bind_id is not None:
            return
        root = self.master.winfo_toplevel()
        # specific buttons: CustomTkinter binds <Button-1> on "all", which would shadow a generic <ButtonPress>
        self._bind_id = {seq: root.bind_all(seq, self._click_anywhere, add="+") for seq in ("<Button-1>", "<Button-2>", "<Button-3>")}

    def _hover(self, i: int) -> None:
        th = self._theme()
        for j, (it, row, widgets) in enumerate(self.rows):
            on = j == i and it.get("state") != "disabled"
            for wd in widgets:
                wd.configure(bg=th["activebackground"] if on else th["bg"])
                if wd is widgets[1] and it.get("state") != "disabled":
                    wd.configure(fg=th["activeforeground"] if on else th["fg"])
        self.active = i
        it = self.rows[i][0]
        if self.child is not None and (it["kind"] != "cascade" or it["menu"] is not self.child):
            self.child.close()
        if it["kind"] == "cascade" and self.child is None:
            self._open_child(i)

    def _move(self, d: int) -> None:
        if not self.rows:
            return
        i = self.active
        for _ in range(len(self.rows)):
            i = (i + d) % len(self.rows)
            if self.rows[i][0].get("state") != "disabled":
                break
        self._hover(i)

    def _open_child(self, i: int) -> None:
        it, row, _w = self.rows[i]
        menu: DarkMenu = it["menu"]
        self.child = menu
        menu.parent = self
        menu._build(self.win.winfo_rootx() + self.win.winfo_width() - 2, row.winfo_rooty() - int(4 * ui_scale(self.master)))

    def _activate(self, i: int) -> None:
        it = self.rows[i][0]
        if it.get("state") == "disabled":
            return
        if it["kind"] == "cascade":
            if self.child is None:
                self._open_child(i)
            if self.child is not None and self.child.rows:
                self.child.win.focus_force()
                self.child._hover(0)
            return
        cmd = it.get("command")
        self.close_all()
        if cmd:
            self.master.after_idle(cmd)

    def _windows(self) -> list:
        root = self
        while root.parent is not None:
            root = root.parent
        out, m = [], root
        while m is not None:
            if m.win is not None:
                out.append(m.win)
            m = m.child
        return out

    def _inside(self, widget) -> bool:
        wins = {str(w) for w in self._windows()}
        while widget is not None:
            if str(widget) in wins:
                return True
            widget = getattr(widget, "master", None)
        return False

    def _click_anywhere(self, e) -> None:
        try:
            inside = self._inside(e.widget) if not isinstance(e.widget, str) else False
        except Exception:
            inside = False
        if not inside:
            self.close_all()

    def _check_focus(self) -> None:
        if self.win is None:
            return
        try:
            focus = self.master.focus_get()
        except (KeyError, tk.TclError):
            focus = None
        if focus is None or not self._inside(focus):
            self.close_all()

    def _destroy_window(self) -> None:
        if self.child is not None:
            self.child.close()
        if self.win is not None:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
            self.win = None

    def close(self) -> None:
        self._destroy_window()
        if self.parent is not None:
            if self.parent.child is self:
                self.parent.child = None
            if self.parent.win is not None:
                self.parent.win.focus_force()

    def close_all(self) -> None:
        root = self
        while root.parent is not None and root.parent.win is not None:
            root = root.parent
        root._destroy_window()
        if root._bind_id is not None:
            top = root.master.winfo_toplevel()
            for seq, fid in root._bind_id.items():
                try:      # remove only our handler, keep CustomTkinter's (and anyone else's) "all" bindings
                    script = top.tk.call("bind", "all", seq)
                    top.tk.call("bind", "all", seq, "\n".join(l for l in str(script).split("\n") if fid not in l))
                    top.deletecommand(fid)
                except tk.TclError:
                    pass
            root._bind_id = None
        if DarkMenu._open is root:
            DarkMenu._open = None

    @property
    def is_open(self) -> bool:
        return self.win is not None


def is_dark(config) -> bool:
    mode = config["appearance_mode"]
    return ctk.get_appearance_mode() == "Dark" if mode == "System" else mode == "Dark"


def _tag_for(ttype, val: str) -> str | None:
    """Map a Pygments token to a VS Code Dark+/Light+ colour role."""
    if ttype in Comment.Preproc or ttype in Comment.PreprocFile:
        return "directive"
    if ttype in Comment:
        return "comment"
    if ttype in Keyword or ttype in Name:
        if val in GATE_WORDS:
            return "gate"
        if val in TYPE_WORDS or ttype in Keyword.Type:
            return "type"
        if val in CONTROL_WORDS:
            return "control"
        if val.startswith("$") or ttype in Name.Builtin:
            return "systask"
        if val.startswith("`"):
            return "directive"
        if ttype in Keyword:
            return "keyword"
        return "ident"
    if ttype in String:
        return "string"
    if ttype in Number:
        return "number"
    if ttype in Operator:
        return "operator"
    return None


def convert_value(value: str, radix: str, width: int | None = None) -> str:
    """Convert a %b string to the requested radix ('x'/'z' preserved)."""
    s = value.strip().replace("_", "")
    if not s or not re.fullmatch(r"[01xXzZ]+", s) or radix == "Binary":
        return value
    w = width or len(s)
    s = s.rjust(w, "0")
    if re.search(r"[xXzZ]", s):
        if radix != "Hex":
            return "x" if re.search(r"[xX]", s) else "z"
        out = []
        for k in range(len(s), 0, -4):
            nib = s[max(0, k - 4):k]
            out.append(nib[0].lower() if len(set(nib.lower())) == 1 and nib[0] in "xXzZ"
                       else "X" if re.search(r"[xXzZ]", nib) else f"{int(nib, 2):X}")
        return "".join(reversed(out))
    n = int(s, 2)
    if radix == "Hex":
        return f"{n:0{max(1, (w + 3) // 4)}X}"
    if radix == "Signed Dec" and w > 1 and n >> (w - 1) & 1:
        return str(n - (1 << w))
    return str(n)


class _Tooltip:
    def __init__(self, widget: tk.Widget):
        self.widget, self.tip = widget, None

    def show(self, text: str, x: int, y: int) -> None:
        self.hide()
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x + 14}+{y + 10}")
        tk.Label(self.tip, text=text, justify="left", bg="#FFFBE6", fg="#222", relief="solid", bd=1,
                 font=("Segoe UI", -ui_px(self.widget, -2)), wraplength=640, padx=6, pady=3).pack()

    def hide(self) -> None:
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None


def ghost_button(master, text: str, command=None, width: int = 0, height: int = 26, **kw) -> ctk.CTkButton:
    """Flat VS Code style secondary button (1px border, transparent fill)."""
    opts = dict(corner_radius=3, height=height, fg_color="transparent", hover_color=VS["hover"], border_width=1,
                border_color=VS["group_border"], text_color=VS["text"], font=ui_font(0))
    opts.update(kw)
    opts["width"] = width          # 0 = shrink to the text (CTk's default 140px is far too wide for a toolbar)
    return ctk.CTkButton(master, text=text, command=command, **opts)


def icon_button(master, text: str, command=None, width: int = 28, height: int = 24, **kw) -> ctk.CTkButton:
    """Borderless icon button (VS Code toolbar action)."""
    opts = dict(corner_radius=3, width=width, height=height, fg_color="transparent", hover_color=VS["hover"],
                text_color=VS["text"], border_width=0, font=ui_font(1))
    opts.update(kw)
    return ctk.CTkButton(master, text=text, command=command, **opts)


def seg_style() -> dict:
    return dict(corner_radius=3, height=24, fg_color=("#E5E5E5", "#2D2D2D"), selected_color=("#BCD9F5", "#04395E"),
                selected_hover_color=("#A9CDEF", "#0A4A75"), unselected_color=("#F3F3F3", "#2D2D2D"),
                unselected_hover_color=VS["hover"], text_color=("#1F1F1F", "#E0E0E0"), font=ui_font(0))


def entry_style() -> dict:
    return dict(corner_radius=2, border_width=1, border_color=VS["input_border"], fg_color=VS["input"], text_color=VS["text"])


def option_style() -> dict:
    return dict(corner_radius=3, height=26, fg_color=VS["input"], button_color=VS["input"], button_hover_color=VS["hover"],
                text_color=VS["text"], dropdown_fg_color=VS["group"], dropdown_hover_color=VS["hover"],
                dropdown_text_color=VS["text"], font=ui_font(0), dropdown_font=ui_font(0), dynamic_resizing=False)


def hline(master, **kw) -> ctk.CTkFrame:
    return ctk.CTkFrame(master, height=1, corner_radius=0, fg_color=VS["border"], **kw)


def vline(master, **kw) -> ctk.CTkFrame:
    return ctk.CTkFrame(master, width=1, corner_radius=0, fg_color=VS["border"], **kw)


def _skip_nested_idle(cls) -> None:
    """CTkScrollbar/CTkOptionMenu._draw() end with canvas.update_idletasks(), which forces a full re-layout of the whole
    window on every redraw: a font zoom made ~a dozen of them (10 s per zoom step). Painting at the next idle is enough."""
    orig = cls._draw

    def _draw(self, *a, **k):
        cv = getattr(self, "_canvas", None)
        if cv is not None and "update_idletasks" not in cv.__dict__:
            cv.update_idletasks = lambda: None
        return orig(self, *a, **k)
    cls._draw = _draw


for _cls in (ctk.CTkScrollbar, ctk.CTkOptionMenu):
    _skip_nested_idle(_cls)


class SafeScrollbar(ctk.CTkScrollbar):
    """CTkScrollbar whose set() redraws on a 1 ms timer. The stock set() draws immediately and its _draw() calls
    update_idletasks(), so a Text/Treeview re-laying out (font zoom, a covering Welcome page) could feed set() back into
    itself without end. Timer callbacks never run inside update_idletasks(), which breaks that cycle."""
    _vf_job = None

    def set(self, start_value: float, end_value: float) -> None:
        self._start_value, self._end_value = float(start_value), float(end_value)
        if self._vf_job is None:
            self._vf_job = self.after(1, self._vf_draw)

    def _vf_draw(self) -> None:
        self._vf_job = None
        try:
            self._draw()
        except tk.TclError:
            pass

    def destroy(self) -> None:
        if self._vf_job is not None:
            try:
                self.after_cancel(self._vf_job)
            except tk.TclError:
                pass
        super().destroy()


def slim_scrollbar(master, command, orientation: str = "vertical") -> ctk.CTkScrollbar:
    return SafeScrollbar(master, command=command, orientation=orientation, width=12, corner_radius=4,
                         fg_color="transparent", button_color=VS["scroll_thumb"], button_hover_color=VS["scroll_hover"])


# =========================================================================== code editor
class VerilogCodeEditor(ctk.CTkFrame):
    """tk.Text based Verilog editor with gutter, Pygments highlighting, find/replace, snippets and zoom."""

    def __init__(self, master, config, role: str = "DESIGN", on_save: Callable | None = None,
                 on_modified: Callable | None = None, on_cursor: Callable | None = None,
                 on_zoom: Callable | None = None, on_focus: Callable | None = None,
                 on_rename: Callable | None = None, **kw):
        super().__init__(master, corner_radius=0, fg_color=VS["editor"], **kw)
        self.cfg, self.role, self.path = config, role, None
        self.on_save, self.on_modified, self.on_cursor, self.on_zoom, self.on_focus = on_save, on_modified, on_cursor, on_zoom, on_focus
        self.on_rename = on_rename
        self.on_generate: Callable | None = None
        self.on_app_ctrl: Callable | None = None
        self.completion_provider: Callable | None = None     # -> list of module infos (dedup'd global index)
        self._comp: dict | None = None
        self.sibling: dict | None = None          # the other file's tab (Tabbed layout)
        self.missing = False
        self._saved_text, self._modified = "", False
        self._marks: dict[int, tuple[str, str]] = {}
        self._hl_job = self._change_job = None
        self._content_dirty = False
        self._crumb_text = ""
        self.lexer = SystemVerilogLexer(stripnl=False, ensurenl=False)
        self.font = tkfont.Font(family=config["editor_font_family"], size=config["editor_font_size"])
        self.bold = tkfont.Font(family=config["editor_font_family"], size=config["editor_font_size"], weight="bold")
        self.italic = tkfont.Font(family=config["editor_font_family"], size=config["editor_font_size"], slant="italic")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # VS Code editor tab strip (34px) + breadcrumb (20px) + hairline
        self.tabstrip = ctk.CTkFrame(self, corner_radius=0, fg_color=VS["tabstrip"], height=38)
        self.tabstrip.grid(row=0, column=0, sticky="ew")
        self.tabstrip.pack_propagate(False)
        self.crumb = ctk.CTkLabel(self, text="", anchor="w", height=24, corner_radius=0, text_color=VS["breadcrumb_fg"],
                                  font=ui_font(-1))
        self.crumb.grid(row=1, column=0, sticky="ew", padx=(14, 6))
        hline(self).grid(row=2, column=0, sticky="ew")

        # find / replace bar (hidden by default)
        self.find_bar = ctk.CTkFrame(self, height=34, corner_radius=0, fg_color=VS["group"])
        self.find_var, self.repl_var, self.case_var = tk.StringVar(), tk.StringVar(), tk.BooleanVar(value=False)
        self.find_entry = ctk.CTkEntry(self.find_bar, textvariable=self.find_var, placeholder_text="Find", width=170, height=24, **entry_style())
        self.repl_entry = ctk.CTkEntry(self.find_bar, textvariable=self.repl_var, placeholder_text="Replace", width=150, height=24, **entry_style())
        self.find_entry.pack(side="left", padx=(8, 3), pady=4)
        for txt, cmd in (("↑", lambda: self.find_next(False)), ("↓", lambda: self.find_next(True))):
            icon_button(self.find_bar, txt, cmd, width=26).pack(side="left", padx=1)
        ctk.CTkCheckBox(self.find_bar, text="Aa", variable=self.case_var, width=50, checkbox_width=15, checkbox_height=15,
                        corner_radius=2, border_width=1, command=self._refresh_find).pack(side="left", padx=4)
        self.repl_entry.pack(side="left", padx=3)
        ghost_button(self.find_bar, "Replace", self.replace_one, width=64, height=24).pack(side="left", padx=1)
        ghost_button(self.find_bar, "All", self.replace_all, width=40, height=24).pack(side="left", padx=1)
        self.find_info = ctk.CTkLabel(self.find_bar, text="", width=70, text_color=VS["muted"])
        self.find_info.pack(side="left", padx=4)
        icon_button(self.find_bar, "✕", self.hide_find, width=26).pack(side="right", padx=4)
        self.find_var.trace_add("write", lambda *_: self._refresh_find())
        self.find_entry.bind("<Return>", lambda e: (self.find_next(True), "break")[1])
        self.find_entry.bind("<Shift-Return>", lambda e: (self.find_next(False), "break")[1])
        self.find_entry.bind("<Escape>", lambda e: self.hide_find())
        self.repl_entry.bind("<Return>", lambda e: (self.replace_one(), "break")[1])
        self.repl_entry.bind("<Escape>", lambda e: self.hide_find())

        # body: gutter + text + slim scrollbars, edge to edge
        body = tk.Frame(self, bd=0, highlightthickness=0)
        body.grid(row=4, column=0, sticky="nsew")
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        self.body = body
        self.gutter = tk.Canvas(body, width=48, highlightthickness=0, bd=0)
        self.gutter.grid(row=0, column=0, sticky="ns")
        self.text = tk.Text(body, undo=True, maxundo=100, autoseparators=True, wrap="none", bd=0, highlightthickness=0,
                            padx=6, pady=4, font=self.font, exportselection=False, insertwidth=2, spacing1=2, spacing3=2)
        self.text.grid(row=0, column=1, sticky="nsew")
        self.vsb = slim_scrollbar(body, self.text.yview)
        self.vsb.grid(row=0, column=2, sticky="ns")
        self.hsb = slim_scrollbar(body, self.text.xview, "horizontal")
        self.hsb.grid(row=1, column=1, sticky="ew")
        self.text.configure(yscrollcommand=self._on_yscroll, xscrollcommand=self.hsb.set)
        self._install_proxy()
        self._tooltip = _Tooltip(self.gutter)
        self._build_menu()
        self._bind_keys()
        self.apply_editor_settings(config)

    # ------------------------------------------------------------------ infrastructure
    def _install_proxy(self) -> None:
        """Wrap the Tcl text command so every insert/delete/scroll raises <<Change>>."""
        self._orig = self.text._w + "_orig"
        self.tk.call("rename", self.text._w, self._orig)
        self.tk.createcommand(self.text._w, self._proxy)

    def _proxy(self, *args):
        try:
            result = self.tk.call((self._orig,) + args)
        except tk.TclError:
            return ""
        op = args[0] if args else ""
        if op in ("insert", "delete", "replace"):
            self._content_dirty = True
            self._schedule_change()
        elif op in ("xview", "yview") and len(args) > 1 or (op == "mark" and len(args) > 2 and args[1] == "set" and args[2] == "insert"):
            self._schedule_change()
        elif op == "edit" and len(args) > 1 and args[1] in ("undo", "redo"):
            self._content_dirty = True
            self._schedule_change()
        return result

    def _schedule_change(self) -> None:
        if self._change_job is None:
            self._change_job = self.after_idle(self._on_change)

    def _on_change(self) -> None:
        self._change_job = None
        self._redraw_gutter()
        self._update_current_line()
        line, col = map(int, self.text.index("insert").split("."))
        if self.on_cursor:
            self.on_cursor(self, line, col + 1, self._marks.get(line, (None, None))[1])
        if self._content_dirty:
            self._content_dirty = False
            if self._hl_job:
                self.after_cancel(self._hl_job)
            self._hl_job = self.after(140, self._rehighlight)
            self._check_modified()

    def _on_yscroll(self, first, last) -> None:
        self.vsb.set(first, last)
        self._redraw_gutter()

    def _check_modified(self) -> None:
        mod = self.get_content() != self._saved_text
        if mod != self._modified:
            self._modified = mod
            self._update_title()
            if self.on_modified:
                self.on_modified(self, mod)

    def _update_title(self) -> None:
        self._render_tabs()

    # ------------------------------------------------------------------ VS Code tab strip / breadcrumb
    def set_sibling(self, sibling: dict | None) -> None:
        """sibling = {text, role, dirty, command, before} -> the other file as an inactive tab (Tabbed layout)."""
        self.sibling = sibling
        self._render_tabs()

    def set_missing(self, missing: bool) -> None:
        self.missing = missing
        self._render_tabs()

    def _render_tabs(self) -> None:
        strip = self.tabstrip
        for w in strip.winfo_children():
            w.destroy()
        own = {"text": os.path.basename(self.path) if self.path else "(no file)", "role": self.role, "dirty": self._modified,
               "active": True, "command": lambda: self.text.focus_set(), "missing": self.missing}
        tabs = [own]
        if self.sibling:
            sib = {**self.sibling, "active": False}
            tabs.insert(0 if sib.get("before") else 1, sib)
        for t in tabs:
            self._make_tab(strip, t)
        actions = ctk.CTkFrame(strip, fg_color="transparent", corner_radius=0)
        actions.pack(side="right", padx=4)
        if self.missing and self.on_generate:
            ghost_button(actions, "🧪 Generate _tb.v", self.on_generate, height=24).pack(side="left", padx=2)
        icon_button(actions, "💾", self._fire_save, width=30).pack(side="left", padx=1)

    def _make_tab(self, strip, t: dict) -> None:
        sc = self.cfg.scheme
        active = t["active"]
        bg = sc["bg"] if active else VS["tab_inactive"]
        tab = ctk.CTkFrame(strip, corner_radius=0, fg_color=bg)
        tab.pack(side="left", fill="y")
        ctk.CTkFrame(tab, height=2, corner_radius=0, fg_color=VS["accent"] if active else bg).pack(side="top", fill="x")
        row = ctk.CTkFrame(tab, fg_color="transparent", corner_radius=0)
        row.pack(side="top", fill="both", expand=True, padx=(10, 8))
        text, color = BADGE.get(t["role"], ("V", VS["text"]))
        widgets = [ctk.CTkLabel(row, text=text, text_color=color, font=ui_font(-1, "bold"), width=18)]
        name = t["text"] + ("  (missing)" if t.get("missing") else "")
        fg = VS["tab_active_fg"] if active else VS["tab_inactive_fg"]
        widgets.append(ctk.CTkLabel(row, text=name, text_color=fg,
                                    font=ui_font(1, "bold", "italic" if t.get("missing") else "roman")))
        widgets.append(ctk.CTkLabel(row, text="●" if t.get("dirty") else " ", width=14, font=ui_font(-1), text_color=fg))
        for w in widgets:
            w.pack(side="left", padx=(0, 4))
        vline(strip).pack(side="left", fill="y")
        cmd = t.get("command")
        if cmd:
            for w in (tab, row, *widgets):
                w.bind("<Button-1>", lambda e, c=cmd: c())
        if active and self.on_rename:
            menu = DarkMenu(self, self.cfg)
            menu.add_command(label="Rename File / Module…", command=self.on_rename)
            for w in (tab, row, *widgets):
                w.bind("<Button-3>", lambda e, m=menu: (m.tk_popup(e.x_root, e.y_root),
                                                        m.grab_release())[0])

    def _update_breadcrumb(self, text: str | None = None) -> None:
        parts = []
        if self.path:
            p = os.path.abspath(self.path)
            parts += [os.path.basename(os.path.dirname(p)), os.path.basename(p)]
        try:
            mods = parse_verilog_source(text if text is not None else self.get_content())
        except Exception:
            mods = []
        if mods:
            m = mods[0]
            sig = ", ".join(f"{q['direction']} {q['range_text'] + ' ' if q['range_text'] else ''}{q['name']}" for q in m["ports"])
            parts.append(f"module {m['module_name']} ({sig})")
        crumb = "  ›  ".join(parts)
        crumb = crumb if len(crumb) < 170 else crumb[:167] + "…"
        if crumb != self._crumb_text:
            self._crumb_text = crumb
            self.crumb.configure(text=crumb)

    # ------------------------------------------------------------------ public API
    def set_content(self, text: str, path: str | None = None, keep_view: bool = False) -> None:
        view, ins = self.text.yview()[0], self.text.index("insert")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.text.edit_reset()
        self.text.edit_modified(False)
        if path is not None:
            self.path = str(path)
        self._saved_text = text
        self._modified = False
        self.clear_diagnostic_marks()
        if keep_view:
            self.text.mark_set("insert", ins)
            self.text.yview_moveto(view)
        else:
            self.text.mark_set("insert", "1.0")
            self.text.see("1.0")
        self._update_title()
        self._rehighlight()
        self._on_change()
        if self.on_modified:
            self.on_modified(self, False)

    def get_content(self) -> str:
        return self.text.get("1.0", "end-1c")

    def mark_saved(self) -> None:
        self._saved_text = self.get_content()
        self._check_modified()

    @property
    def is_modified(self) -> bool:
        # computed live: an edit made in the same event as Save/Run must not be missed
        return self.get_content() != self._saved_text

    def apply_editor_settings(self, config) -> None:
        self.cfg = config
        sc = config.scheme
        size = px_font(config["editor_font_size"], self)
        self.font.configure(family=config["editor_font_family"], size=size)
        self.bold.configure(family=config["editor_font_family"], size=size, weight="bold")
        tabw = self.font.measure(" " * int(config["tab_size"]))
        self.configure(fg_color=sc["bg"])
        self.crumb.configure(fg_color=sc["bg"])
        self.vsb.configure(fg_color=sc["bg"])
        self.hsb.configure(fg_color=sc["bg"])
        self.text.configure(bg=sc["bg"], fg=sc["fg"], insertbackground=sc["cursor"], selectbackground=sc["selection"],
                            inactiveselectbackground=sc["selection"], selectforeground=sc["fg"], font=self.font,
                            tabs=(tabw,), tabstyle="wordprocessor", wrap="word" if config["word_wrap"] else "none")
        self.body.configure(bg=sc["bg"])
        self.gutter.configure(bg=sc["gutter_bg"])
        for tag in TOKEN_TAGS:
            color = sc.get(tag) or sc[TAG_FALLBACK.get(tag, "fg")]
            self.text.tag_configure(tag, foreground=color, font=self.font)
        self.italic.configure(family=config["editor_font_family"], size=size)
        self.text.tag_configure("comment", font=self.italic)
        self.text.tag_configure("curline", background=sc["current_line"] if config["highlight_current_line"] else "")
        self.text.tag_configure("warnline", background=sc["warning_bg"])
        self.text.tag_configure("errline", background=sc["error_bg"])
        self.text.tag_configure("findhit", background=sc["find_bg"])
        self.text.tag_lower("curline")
        self.text.tag_raise("warnline", "curline")
        self.text.tag_raise("errline", "warnline")
        self.text.tag_raise("sel")
        if config["word_wrap"]:
            self.hsb.grid_remove()
        else:
            self.hsb.grid()
        style_menu(self.menu, self, config)
        style_menu(self.snippet_menu, self, config)
        self._update_current_line()
        self._redraw_gutter()
        self._render_tabs()

    def highlight_error_line(self, line_no: int, message: str = "") -> None:
        self._mark(line_no, "error", message)

    def highlight_warning_line(self, line_no: int, message: str = "") -> None:
        if self._marks.get(line_no, ("",))[0] != "error":
            self._mark(line_no, "warning", message)

    def _mark(self, line_no: int, sev: str, message: str) -> None:
        last = int(self.text.index("end-1c").split(".")[0])
        if not 1 <= line_no <= last:
            return
        prev = self._marks.get(line_no)
        msg = f"{prev[1]}\n{message}" if prev and prev[1] and message and message not in prev[1] else (message or (prev[1] if prev else ""))
        self._marks[line_no] = ("error" if sev == "error" or (prev and prev[0] == "error") else sev, msg)
        tag = "errline" if self._marks[line_no][0] == "error" else "warnline"
        self.text.tag_remove("warnline", f"{line_no}.0", f"{line_no}.0+1line")
        self.text.tag_add(tag, f"{line_no}.0", f"{line_no}.0+1line")
        self._redraw_gutter()

    def clear_diagnostic_marks(self) -> None:
        self._marks.clear()
        self.text.tag_remove("errline", "1.0", "end")
        self.text.tag_remove("warnline", "1.0", "end")
        self._redraw_gutter()

    def goto_line(self, line_no: int, col: int = 0) -> None:
        line_no = max(1, int(line_no))
        idx = f"{line_no}.{max(0, col - 1)}"
        self.text.mark_set("insert", idx)
        self.text.see(idx)
        self.text.tag_remove("sel", "1.0", "end")
        self.text.tag_add("sel", f"{line_no}.0", f"{line_no}.end")
        self.text.focus_set()

    def insert_text(self, s: str) -> None:
        self.text.edit_separator()
        if self.text.tag_ranges("sel"):
            self.text.delete("sel.first", "sel.last")
        self.text.insert("insert", s)
        self.text.edit_separator()
        self.text.focus_set()

    def insert_snippet(self, snippet: str) -> None:
        indent = re.match(r"[ \t]*", self.text.get("insert linestart", "insert lineend")).group(0)
        unit = self._indent_unit()
        body = snippet.replace("    ", unit).replace("\n", "\n" + indent)
        pos = body.find(CURSOR)
        body = body.replace(CURSOR, "")
        start = self.text.index("insert")
        self.insert_text(body)
        if pos >= 0:
            self.text.mark_set("insert", f"{start}+{pos}c")
        self.text.see("insert")

    # ------------------------------------------------------------------ highlighting / gutter
    def _rehighlight(self) -> None:
        self._hl_job = None
        text = self.get_content()
        self._update_breadcrumb(text)
        for t in TOKEN_TAGS:
            self.text.tag_remove(t, "1.0", "end")
        ranges: dict[str, list[str]] = defaultdict(list)
        line, col = 1, 0
        for ttype, val in self.lexer.get_tokens(text):
            if not val:
                continue
            tag = _tag_for(ttype, val)
            start = f"{line}.{col}"
            nl = val.count("\n")
            if nl:
                line += nl
                col = len(val) - val.rfind("\n") - 1
            else:
                col += len(val)
            if tag:
                ranges[tag].extend((start, f"{line}.{col}"))
        for tag, r in ranges.items():
            for k in range(0, len(r), 2000):        # tag_add arg-count chunks
                self.text.tag_add(tag, *r[k:k + 2000])
        if self.find_bar.winfo_ismapped():
            self._refresh_find(move=False)

    def _redraw_gutter(self) -> None:
        g = self.gutter
        g.delete("all")
        sc = self.cfg.scheme
        last = int(self.text.index("end-1c").split(".")[0])
        width = self.font.measure("0" * max(3, len(str(last)))) + 26
        if int(g.cget("width")) != width:
            g.configure(width=width)
        cur = self.text.index("insert").split(".")[0]
        idx = self.text.index("@0,0")
        while True:
            d = self.text.dlineinfo(idx)
            if d is None:
                break
            ln = idx.split(".")[0]
            y = d[1] + 1
            g.create_text(width - 6, y, anchor="ne", text=ln, font=self.font,
                          fill=sc["gutter_active"] if ln == cur else sc["gutter_fg"])
            mark = self._marks.get(int(ln))
            if mark:
                r, cy = 4, y + d[3] / 2
                g.create_oval(5, cy - r, 5 + 2 * r, cy + r, outline="",
                              fill="#EF4444" if mark[0] == "error" else "#F59E0B", tags=("mark", f"L{ln}"))
            nxt = self.text.index(f"{idx}+1line")
            if nxt == idx:
                break
            idx = nxt

    def _gutter_motion(self, e) -> None:
        idx = self.text.index(f"@0,{e.y}")
        ln = int(idx.split(".")[0])
        m = self._marks.get(ln)
        if m and m[1]:
            self._tooltip.show(m[1], e.x_root, e.y_root)
        else:
            self._tooltip.hide()

    def _update_current_line(self) -> None:
        self.text.tag_remove("curline", "1.0", "end")
        if self.cfg["highlight_current_line"]:
            self.text.tag_add("curline", "insert linestart", "insert linestart+1line")

    # ------------------------------------------------------------------ menus & keys
    def _build_menu(self) -> None:
        m = DarkMenu(self, self.cfg)
        m.add_command(label="Undo", command=lambda: self._action("undo"), accelerator="Ctrl+Z")
        m.add_command(label="Redo", command=lambda: self._action("redo"), accelerator="Ctrl+Y")
        m.add_separator()
        m.add_command(label="Cut", command=lambda: self._action("cut"), accelerator="Ctrl+X")
        m.add_command(label="Copy", command=lambda: self._action("copy"), accelerator="Ctrl+C")
        m.add_command(label="Paste", command=lambda: self._action("paste"), accelerator="Ctrl+V")
        m.add_separator()
        sub = DarkMenu(self, self.cfg)
        for name, snip in SNIPPETS.items():
            sub.add_command(label=name, command=lambda s=snip: self.insert_snippet(s))
        m.add_cascade(label="Insert Snippet", menu=sub)
        m.add_separator()
        m.add_command(label="Toggle Comment", command=self.toggle_comment, accelerator="Ctrl+/")
        m.add_command(label="Duplicate Line", command=self.duplicate_line, accelerator="Ctrl+D")
        m.add_command(label="Find / Replace", command=self.show_find, accelerator="Ctrl+F")
        m.add_command(label="Go to Line…", command=self.prompt_goto_line, accelerator="Ctrl+G")
        self.menu, self.snippet_menu = m, sub

    def _bind_keys(self) -> None:
        t = self.text
        t.bind("<Control-KeyPress>", self._on_ctrl)
        if IS_MAC:
            t.bind("<Command-KeyPress>", self._on_ctrl)
        t.bind("<F2>", lambda e: (self.on_rename() if self.on_rename else None, "break")[1])
        t.bind("<Control-MouseWheel>", lambda e: (self._zoom(1 if e.delta > 0 else -1), "break")[1])
        t.bind("<Control-Button-4>", lambda e: (self._zoom(1), "break")[1])
        t.bind("<Control-Button-5>", lambda e: (self._zoom(-1), "break")[1])
        t.bind("<Return>", self._on_return)
        t.bind("<KP_Enter>", self._on_return)
        t.bind("<Tab>", self._on_tab)
        t.bind("<Shift-Tab>", lambda e: self._indent_block(-1))
        if not IS_WINDOWS:
            t.bind("<ISO_Left_Tab>", lambda e: self._indent_block(-1))
        t.bind("<BackSpace>", self._on_backspace)
        t.bind("<KeyPress>", self._on_keypress)
        t.bind("<Button-3>", self._popup)
        t.bind("<FocusIn>", lambda e: self.on_focus and self.on_focus(self))
        t.bind("<F3>", lambda e: (self.find_next(True), "break")[1])
        t.bind("<Escape>", lambda e: "break" if self._close_completions() else self.hide_find())
        t.bind("<Up>", lambda e: self._comp_move(-1))
        t.bind("<Down>", lambda e: self._comp_move(1))
        t.bind("<Button-1>", lambda e: (self._close_completions(), None)[1], add="+")
        t.bind("<MouseWheel>", lambda e: (self._close_completions(), None)[1], add="+")
        t.bind("<FocusOut>", lambda e: self.after(120, self._close_if_unfocused), add="+")
        self.gutter.bind("<Motion>", self._gutter_motion)
        self.gutter.bind("<Leave>", lambda e: self._tooltip.hide())
        self.gutter.bind("<MouseWheel>", lambda e: self.text.yview_scroll(int(-e.delta / 40), "units"))
        self.gutter.bind("<Button-1>", lambda e: self.goto_line(int(self.text.index(f"@0,{e.y}").split(".")[0])))

    def add_menu_command(self, label: str, command: Callable) -> None:
        """Let the app append its own actions (e.g. Generate Testbench) to the editor's right-click menu."""
        if not getattr(self, "_extra_menu", False):
            self.menu.add_separator()
            self._extra_menu = True
        self.menu.add_command(label=label, command=command)

    def _popup(self, e) -> str:
        self.text.focus_set()
        try:
            self.menu.tk_popup(e.x_root, e.y_root)
        finally:
            self.menu.grab_release()
        return "break"

    def _on_ctrl(self, e):
        action = _VK.get(e.keycode) if IS_WINDOWS else None
        if action is None:
            action = _KS.get(e.keysym.lower())
        if action is None:     # app-level shortcuts (Ctrl+O/N/B/,): handled by the window, never by tk.Text's emacs bindings
            return self.on_app_ctrl(e) if self.on_app_ctrl else None
        if action == "undo" and e.state & 0x0001:     # Ctrl+Shift+Z
            action = "redo"
        self._action(action)
        return "break"

    def _action(self, action: str) -> None:
        t = self.text
        if action == "save":
            self._fire_save()
        elif action == "find":
            self.show_find()
        elif action == "replace":
            self.show_find(replace=True)
        elif action == "goto":
            self.prompt_goto_line()
        elif action == "comment":
            self.toggle_comment()
        elif action == "complete":
            self.show_completions()
        elif action == "dup":
            self.duplicate_line()
        elif action in ("zoom_in", "zoom_out", "zoom_reset"):
            self._zoom({"zoom_in": 1, "zoom_out": -1, "zoom_reset": 0}[action])
        elif action == "undo":
            t.edit_undo()
        elif action == "redo":
            t.edit_redo()
        elif action == "select_all":
            t.tag_add("sel", "1.0", "end-1c")
            t.mark_set("insert", "end-1c")
        else:
            t.event_generate({"copy": "<<Copy>>", "paste": "<<Paste>>", "cut": "<<Cut>>"}[action])

    def _fire_save(self) -> None:
        if self.on_save:
            self.on_save(self)

    def _zoom(self, delta: int) -> None:
        if self.on_zoom:
            self.on_zoom(delta)
        else:
            pts = 15 if delta == 0 else min(32, max(10, int(self.cfg["editor_font_size"]) + delta))
            self.font.configure(size=px_font(pts, self))
            self._redraw_gutter()

    def _indent_unit(self) -> str:
        return " " * int(self.cfg["tab_size"]) if self.cfg["insert_spaces_for_tabs"] else "\t"

    def _on_tab(self, e) -> str:
        if self._comp:
            return self._comp_accept()
        ranges = self.text.tag_ranges("sel")
        if ranges and self.text.index(ranges[0]).split(".")[0] != self.text.index(ranges[1]).split(".")[0]:
            return self._indent_block(1)
        self.text.insert("insert", self._indent_unit())
        return "break"

    def _indent_block(self, direction: int) -> str:
        ranges = self.text.tag_ranges("sel")
        first, last = (int(self.text.index(r).split(".")[0]) for r in ranges) if ranges else (int(self.text.index("insert").split(".")[0]),) * 2
        if ranges and self.text.index(ranges[1]).endswith(".0") and last > first:
            last -= 1
        unit = self._indent_unit()
        tsz = int(self.cfg["tab_size"])
        self.text.edit_separator()
        for ln in range(first, last + 1):
            if direction > 0:
                if self.text.get(f"{ln}.0", f"{ln}.end").strip():
                    self.text.insert(f"{ln}.0", unit)
            else:
                lead = re.match(r"[ \t]*", self.text.get(f"{ln}.0", f"{ln}.end")).group(0)
                n = 1 if lead.startswith("\t") else min(len(lead) - len(lead.lstrip(" ")), tsz)
                if n:
                    self.text.delete(f"{ln}.0", f"{ln}.{n}")
        self.text.edit_separator()
        if ranges:
            self.text.tag_add("sel", f"{first}.0", f"{last}.end")
        return "break"

    def _on_backspace(self, e):
        if self._comp:
            self.after_idle(self._comp_refilter)
        if self.text.tag_ranges("sel") or not self.cfg["insert_spaces_for_tabs"]:
            return None
        before = self.text.get("insert linestart", "insert")
        if before and not before.strip(" "):
            tsz = int(self.cfg["tab_size"])
            n = len(before) % tsz or tsz
            self.text.delete(f"insert-{n}c", "insert")
            return "break"
        nxt, prv = self.text.get("insert"), self.text.get("insert-1c")
        if self.cfg["auto_close_brackets_and_blocks"] and prv + nxt in ("()", "[]", "{}", '""'):
            self.text.delete("insert-1c", "insert+1c")
            return "break"
        return None

    def _on_keypress(self, e):
        ch = e.char
        if not e.state & 0x0004:              # live IntelliSense (not on Ctrl+key chords)
            self.after_idle(lambda c=ch: self._auto_trigger(c))
        if not self.cfg["auto_close_brackets_and_blocks"] or not ch or e.state & 0x0004:
            return None
        pairs = {"(": ")", "[": "]", "{": "}", '"': '"'}
        if ch in (")", "]", "}", '"') and self.text.get("insert") == ch and not self.text.tag_ranges("sel"):
            self.text.mark_set("insert", "insert+1c")
            return "break"
        if ch in pairs:
            if self.text.tag_ranges("sel"):
                sel = self.text.get("sel.first", "sel.last")
                self.text.edit_separator()
                self.text.delete("sel.first", "sel.last")
                self.text.insert("insert", ch + sel + pairs[ch])
                return "break"
            nxt = self.text.get("insert")
            if ch == '"' and self.text.get("insert-1c").isalnum():
                return None
            if nxt == "" or nxt in " \t\n)]};,":
                self.text.insert("insert", ch + pairs[ch])
                self.text.mark_set("insert", "insert-1c")
                return "break"
        return None

    def _on_return(self, e):
        if self._comp and self._comp_accept(newline_if_noop=True):
            return "break"
        if not self.cfg["auto_indent"]:
            return None
        if self.text.tag_ranges("sel"):
            self.text.delete("sel.first", "sel.last")
        line = self.text.get("insert linestart", "insert")
        after = self.text.get("insert", "insert lineend")
        indent = re.match(r"[ \t]*", line).group(0)
        code = re.sub(r"//.*$", "", line).rstrip()
        unit = self._indent_unit()
        opens = bool(re.search(r"(\bbegin|\bfork|\bcase[xz]?\s*\(.*\)|\bgenerate|^\s*(module|macromodule)\b.*|\bfunction\b.*|\btask\b.*|[(\[{])$", code)) \
            and not re.search(r"\b(end\w*)\s*$", code)
        self.text.edit_separator()
        between = after.strip()[:1] in (")", "]", "}") and code.endswith(("(", "[", "{"))
        if opens:
            self.text.insert("insert", "\n" + indent + unit)
            if between:
                pos = self.text.index("insert")
                self.text.insert("insert", "\n" + indent)
                self.text.mark_set("insert", pos)
            elif self.cfg["auto_close_brackets_and_blocks"] and re.search(r"\bbegin(\s*:\s*\w+)?$", code) and not self._has_matching_end(indent):
                pos = self.text.index("insert")
                self.text.insert(f"{pos} lineend", "\n" + indent + "end")
                self.text.mark_set("insert", pos)
        else:
            self.text.insert("insert", "\n" + indent)
        self.text.see("insert")
        self.text.edit_separator()
        return "break"

    def _has_matching_end(self, indent: str) -> bool:
        ln = int(self.text.index("insert").split(".")[0]) + 1
        last = int(self.text.index("end-1c").split(".")[0])
        while ln <= last:
            s = self.text.get(f"{ln}.0", f"{ln}.end")
            if s.strip():
                lead = re.match(r"[ \t]*", s).group(0)
                return lead == indent and bool(re.match(r"end\b", s.strip()))
            ln += 1
        return False

    def toggle_comment(self) -> None:
        ranges = self.text.tag_ranges("sel")
        first, last = (int(self.text.index(r).split(".")[0]) for r in ranges) if ranges else (int(self.text.index("insert").split(".")[0]),) * 2
        if ranges and self.text.index(ranges[1]).endswith(".0") and last > first:
            last -= 1
        lines = [self.text.get(f"{ln}.0", f"{ln}.end") for ln in range(first, last + 1)]
        nonempty = [s for s in lines if s.strip()]
        if not nonempty:
            return
        uncomment = all(s.lstrip().startswith("//") for s in nonempty)
        col = min(len(s) - len(s.lstrip()) for s in nonempty)
        self.text.edit_separator()
        for ln, s in zip(range(first, last + 1), lines):
            if not s.strip():
                continue
            if uncomment:
                i = s.index("//")
                n = 3 if s[i + 2:i + 3] == " " else 2
                self.text.delete(f"{ln}.{i}", f"{ln}.{i + n}")
            else:
                self.text.insert(f"{ln}.{col}", "// ")
        self.text.edit_separator()

    def duplicate_line(self) -> None:
        if self.text.tag_ranges("sel"):
            s = self.text.get("sel.first", "sel.last")
            self.text.insert("sel.last", s)
            return
        line = self.text.get("insert linestart", "insert lineend")
        col = self.text.index("insert").split(".")[1]
        self.text.insert("insert lineend", "\n" + line)
        ln = int(self.text.index("insert").split(".")[0]) + 1
        self.text.mark_set("insert", f"{ln}.{col}")

    def prompt_goto_line(self) -> None:
        dlg = ctk.CTkInputDialog(text=f"Line number (1-{self.text.index('end-1c').split('.')[0]}):", title="Go to Line")
        val = dlg.get_input()
        if val and val.strip().isdigit():
            self.goto_line(int(val.strip()))

    # ------------------------------------------------------------------ IntelliSense (live + Ctrl+Space)
    AC_ROWS = 10
    AC_BADGE = {"M": ("#4EC9B0", "#16825D"), "P": ("#9CDCFE", "#0070C1"), "W": ("#75BEFF", "#0451A5"),
                "K": ("#C586C0", "#AF00DB"), "G": ("#DCDCAA", "#795E26"), "S": ("#D7BA7D", "#A31515")}

    def word_at_cursor(self) -> str:
        line = self.text.get("insert linestart", "insert lineend")
        col = int(self.text.index("insert").split(".")[1])
        for m in re.finditer(r"[A-Za-z_$][\w$]*", line):
            if m.start() <= col <= m.end():
                return m.group(0)
        return ""

    def _prefix(self) -> str:
        m = re.search(r"[A-Za-z_$][\w$]*$", self.text.get("insert linestart", "insert"))
        return m.group(0) if m else ""

    def _ac_context(self) -> dict:
        return completion_context(self.text.get("1.0", "insert"))

    def _ac_items(self, ctx: dict) -> list[dict]:
        text = self.get_content()
        known = self.completion_provider() if self.completion_provider else []
        own = {m.group(1) for m in re.finditer(r"\bmodule\s+([A-Za-z_]\w*)", text)}
        return build_items(ctx, text, known, own)

    def show_completions(self, auto: bool = False) -> None:
        """Open the IntelliSense popup for the caret context (Ctrl+Space, or live while typing when auto=True)."""
        ctx = self._ac_context()
        if ctx["mode"] == "none" or (auto and ctx["mode"] == "word" and len(ctx["prefix"]) < 2):
            self._close_completions()
            return
        self._comp = {"ctx": ctx, "all": self._ac_items(ctx), "shown": [], "sel": 0, "top": 0, "auto": auto}
        if self._comp_refilter():
            self._ac_place()

    def _auto_trigger(self, ch: str) -> None:
        if not self.cfg.get("live_autocomplete", True) or self.text.tag_ranges("sel"):
            return
        if self._comp and ch and ch in " ;,)]}=":       # VS Code: a separator dismisses the list
            self._close_completions()
        elif self._comp:
            self._comp_refilter()
        elif ch and (ch.isalnum() or ch in "_$`."):
            self.show_completions(auto=True)

    def _comp_refilter(self) -> bool:
        c = self._comp
        if not c:
            return False
        ctx = self._ac_context()
        old = c["ctx"]
        if ctx["mode"] == "none" or (ctx["mode"] == "word" and not ctx["prefix"] and c["auto"]):
            self._close_completions()
            return False
        if ctx["mode"] != old["mode"] or ctx.get("module") != old.get("module"):
            c["all"] = self._ac_items(ctx)
        c["ctx"] = ctx
        shown = rank(c["all"], ctx["prefix"])
        if not shown:
            self._close_completions()
            return False
        c["shown"], c["sel"], c["top"] = shown, 0, 0
        self._ac_render()
        if self._ac_win.winfo_ismapped():
            self._ac_place()                          # shrink / grow with the list, follow the caret
        return True

    # ---- popup window (created once per editor, never takes the keyboard focus)
    def _ac_build(self) -> None:
        if getattr(self, "_ac_win", None) is not None and self._ac_win.winfo_exists():
            return
        w = self._ac_win = tk.Toplevel(self.text)
        w.withdraw()
        w.overrideredirect(True)
        try:
            w.attributes("-topmost", True)
        except tk.TclError:
            pass
        self._ac_body = tk.Frame(w, bd=0, highlightthickness=0)
        self._ac_body.pack(fill="both", expand=True, padx=1, pady=1)
        self._ac_rows = []
        for r in range(self.AC_ROWS):
            row = tk.Frame(self._ac_body, bd=0, highlightthickness=0)
            row.grid(row=r, column=0, sticky="ew")
            badge = tk.Label(row, bd=0, width=2, anchor="center")
            lab = tk.Label(row, bd=0, anchor="w")
            det = tk.Label(row, bd=0, anchor="e")
            badge.pack(side="left", padx=(4, 6), pady=1)
            lab.pack(side="left")
            det.pack(side="right", padx=(18, 8))
            for wd in (row, badge, lab, det):
                wd.bind("<Button-1>", lambda e, i=r: self._ac_click(i))
                wd.bind("<MouseWheel>", lambda e: self._ac_scroll(-1 if e.delta > 0 else 1))
            self._ac_rows.append((row, badge, lab, det))
        self._ac_body.grid_columnconfigure(0, weight=1)
        self._ac_doc = tk.Label(self._ac_body, bd=0, anchor="w", justify="left")
        self._ac_doc.grid(row=self.AC_ROWS, column=0, sticky="ew")
        if IS_WINDOWS:      # a tool window that never activates: the caret and keyboard stay in the editor
            try:
                import ctypes
                w.update_idletasks()
                hwnd = ctypes.windll.user32.GetParent(w.winfo_id()) or w.winfo_id()
                style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
                ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x08000000 | 0x00000080)   # NOACTIVATE|TOOLWINDOW
            except Exception:
                pass

    def _ac_render(self) -> None:
        c = self._comp
        self._ac_build()
        dark = is_dark(self.cfg)
        bg, border = ("#252526", "#454545") if dark else ("#F8F8F8", "#C8C8C8")
        fg, sel_bg, sel_fg = ("#CCCCCC", "#04395E", "#FFFFFF") if dark else ("#1F1F1F", "#0060C0", "#FFFFFF")
        muted, accent = ("#858585", "#4EC9B0") if dark else ("#767676", "#16825D")
        size = max(13, int(self.cfg["editor_font_size"]) - 1)
        fam = self.cfg["editor_font_family"]
        f, fb, fs = (fam, px_font(size, self)), (fam, px_font(size, self), "bold"), (fam, px_font(max(11, size - 2), self))
        self._ac_win.configure(bg=border)
        self._ac_body.configure(bg=bg)
        shown, sel = c["shown"], c["sel"]
        top = c["top"] = min(max(c["top"], sel - self.AC_ROWS + 1), sel)
        for r, (row, badge, lab, det) in enumerate(self._ac_rows):
            i = top + r
            if i >= len(shown):
                row.grid_remove()
                continue
            row.grid()
            it = shown[i]
            on = i == sel
            rb = sel_bg if on else bg
            bcol = self.AC_BADGE[it["kind"]][0 if dark else 1]
            row.configure(bg=rb)
            badge.configure(text=it["kind"], font=fb, bg=rb, fg=bcol)
            lab.configure(text=it["label"], font=f, bg=rb, fg=sel_fg if on else (muted if it.get("done") else fg))
            dcol = accent if it["kind"] in ("M", "P") else muted
            det.configure(text=it["detail"][:40], font=fs, bg=rb, fg=sel_fg if on else dcol)
        doc = shown[sel].get("doc", "") if shown else ""
        self._ac_doc.configure(text=doc, font=fs, bg="#1E1E1E" if dark else "#EDEDED", fg=accent if shown[sel]["kind"] in ("M", "P") else fg,
                               wraplength=int(620 * ui_scale(self)), padx=8, pady=4)
        if doc:
            self._ac_doc.grid()
        else:
            self._ac_doc.grid_remove()

    def _ac_place(self) -> None:
        if not self._comp:
            return
        w = self._ac_win
        bbox = self.text.bbox("insert")
        if not bbox:                                  # caret scrolled out of view: bring it back first
            self.text.see("insert")
            self.text.update_idletasks()
            bbox = self.text.bbox("insert")
        if not bbox:
            self._close_completions()
            return
        w.update_idletasks()
        ww, wh = max(w.winfo_reqwidth(), int(380 * ui_scale(self))), w.winfo_reqheight()
        x = self.text.winfo_rootx() + bbox[0]
        y = self.text.winfo_rooty() + bbox[1] + bbox[3] + 2
        sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
        if y + wh > sh - 8:
            y = self.text.winfo_rooty() + bbox[1] - wh - 2           # no room below: open above the line
        w.geometry(f"{ww}x{wh}+{max(0, min(x, sw - ww - 4))}+{max(0, y)}")
        if not w.winfo_ismapped():
            self._ac_showing = True
            w.deiconify()
            w.lift()
            self.after(150, lambda: setattr(self, "_ac_showing", False))
        if self.focus_get() not in (self.text, None):
            self.text.focus_set()

    def _ac_click(self, r: int) -> None:
        if self._comp:
            self._comp["sel"] = self._comp["top"] + r
            self._comp_accept()
            self.text.focus_set()

    def _ac_scroll(self, d: int) -> str:
        if self._comp:
            c = self._comp
            c["top"] = max(0, min(len(c["shown"]) - self.AC_ROWS, c["top"] + d))
            c["sel"] = min(max(c["sel"], c["top"]), c["top"] + self.AC_ROWS - 1)
            self._ac_render()
        return "break"

    def _comp_move(self, d: int):
        if not self._comp:
            return None
        c = self._comp
        c["sel"] = (c["sel"] + d) % len(c["shown"])
        self._ac_render()
        self._ac_place()
        return "break"

    def _comp_accept(self, newline_if_noop: bool = False):
        c = self._comp
        if not c:
            return "break"
        item = c["shown"][c["sel"]]
        ctx = self._ac_context()
        typed = self.text.get(f"insert-{ctx['replace']}c", "insert") if ctx["replace"] else ""
        self._close_completions()
        if newline_if_noop and item["insert"] == typed:
            return None                       # Enter after an already complete word ("end", "a"): normal newline
        self.text.edit_separator()
        if ctx["replace"]:
            self.text.delete(f"insert-{ctx['replace']}c", "insert")
        if CURSOR in item["insert"] or item.get("snippet"):
            self.insert_snippet(item["insert"])
        else:
            self.insert_text(item["insert"])
        return "break"

    def _close_completions(self) -> bool:
        if self._comp:
            self._comp = None
            try:
                self._ac_win.withdraw()
            except (AttributeError, tk.TclError):
                pass
            return True
        return False

    def _close_if_unfocused(self) -> None:
        """Focus left the editor (another widget, or another app): close - unless it was the popup appearing."""
        if not self._comp or getattr(self, "_ac_showing", False):
            return
        try:
            focus = self.focus_get()
        except (KeyError, tk.TclError):
            focus = None
        if focus is not self.text:
            self._close_completions()

    # ------------------------------------------------------------------ find / replace
    def show_find(self, replace: bool = False) -> None:
        self.find_bar.grid(row=1, column=0, sticky="ew", padx=6, pady=(4, 0))
        if self.text.tag_ranges("sel"):
            s = self.text.get("sel.first", "sel.last")
            if s and "\n" not in s:
                self.find_var.set(s)
        (self.repl_entry if replace and self.find_var.get() else self.find_entry).focus_set()
        self._refresh_find()

    def hide_find(self) -> None:
        self.find_bar.grid_remove()
        self.text.tag_remove("findhit", "1.0", "end")
        self.text.focus_set()

    def _refresh_find(self, move: bool = False) -> None:
        self.text.tag_remove("findhit", "1.0", "end")
        pat = self.find_var.get()
        if not pat:
            self.find_info.configure(text="")
            return
        idx, count = "1.0", 0
        nocase = not self.case_var.get()
        while True:
            idx = self.text.search(pat, idx, stopindex="end", nocase=nocase)
            if not idx:
                break
            end = f"{idx}+{len(pat)}c"
            self.text.tag_add("findhit", idx, end)
            idx, count = end, count + 1
            if count > 5000:
                break
        self.find_info.configure(text=f"{count} hit{'s' if count != 1 else ''}")

    def find_next(self, forward: bool = True) -> bool:
        pat = self.find_var.get()
        if not pat:
            return False
        start = "insert" if forward else ("sel.first" if self.text.tag_ranges("sel") else "insert")
        idx = self.text.search(pat, start, nocase=not self.case_var.get(), backwards=not forward,
                               stopindex=None)
        if not idx:
            return False
        end = f"{idx}+{len(pat)}c"
        self.text.tag_remove("sel", "1.0", "end")
        self.text.tag_add("sel", idx, end)
        self.text.mark_set("insert", end if forward else idx)
        self.text.see(idx)
        return True

    def replace_one(self) -> None:
        pat = self.find_var.get()
        if self.text.tag_ranges("sel") and pat:
            sel = self.text.get("sel.first", "sel.last")
            if sel == pat or (not self.case_var.get() and sel.lower() == pat.lower()):
                self.text.edit_separator()
                self.text.delete("sel.first", "sel.last")
                self.text.insert("insert", self.repl_var.get())
        self.find_next(True)
        self._refresh_find()

    def replace_all(self) -> None:
        pat = self.find_var.get()
        if not pat:
            return
        flags = 0 if self.case_var.get() else re.IGNORECASE
        text = self.get_content()
        new, n = re.subn(re.escape(pat), lambda m: self.repl_var.get(), text, flags=flags)
        if n:
            view = self.text.yview()[0]
            self.text.edit_separator()
            self.text.delete("1.0", "end")
            self.text.insert("1.0", new)
            self.text.edit_separator()
            self.text.yview_moveto(view)
        self.find_info.configure(text=f"{n} replaced")


# =========================================================================== truth table
class TruthTableGrid(ctk.CTkFrame):
    """Treeview truth table with radix conversion, x/z + FAIL row tags and Markdown/CSV export."""

    def __init__(self, master, config, on_radix: Callable | None = None, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.cfg, self.on_radix = config, on_radix
        self.table: dict = {"columns": [], "rows": [], "counts": {}, "outputs": []}
        self.widths: dict[str, int] = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.filter_mode, self.filter_text = "All", ""
        bar = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(6, 2))
        fbar = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        fbar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 6))
        ctk.CTkLabel(fbar, text="SHOW", text_color=VS["muted"], font=ui_font(-1)).pack(side="left", padx=(2, 6))
        self.filter_seg = ctk.CTkSegmentedButton(fbar, values=["All", "x/z Floating", "FAIL"], command=self._set_filter, **seg_style())
        self.filter_seg.set("All")
        self.filter_seg.pack(side="left")
        self.search = ctk.CTkEntry(fbar, placeholder_text="🔍 Filter rows (e.g. 1, sum=1, 1010)…", width=260, height=24, **entry_style())
        self.search.pack(side="left", padx=10)
        self.search.bind("<KeyRelease>", lambda e: self._set_search(self.search.get()))
        ctk.CTkLabel(bar, text="RADIX", text_color=VS["muted"], font=ui_font(-1)).pack(side="left", padx=(2, 6))
        self.radix = ctk.CTkSegmentedButton(bar, values=list(RADIXES), command=self._radix_changed, **seg_style())
        self.radix.set(config["default_radix"])
        self.radix.pack(side="left")
        ghost_button(bar, "📋 Copy CSV", lambda: self.copy("csv"), width=96, height=24).pack(side="right", padx=2)
        ghost_button(bar, "📋 Copy Markdown", lambda: self.copy("md"), width=130, height=24).pack(side="right", padx=2)
        self.summary = ctk.CTkLabel(bar, text="No simulation yet", anchor="w", text_color=VS["text"], font=ui_font(0))
        self.summary.pack(side="left", padx=14)
        self.style = ttk.Style(self)
        self.tree = ttk.Treeview(self, show="headings", style="VF.Treeview", selectmode="extended")
        self.tree.grid(row=2, column=0, sticky="nsew")
        vsb = slim_scrollbar(self, self.tree.yview)
        vsb.grid(row=2, column=1, sticky="ns")
        hsb = slim_scrollbar(self, self.tree.xview, "horizontal")
        hsb.grid(row=3, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.apply_theme(config)

    def apply_theme(self, config) -> None:
        self.cfg = config
        style_treeview(self.style, config, ui_scale(self))
        dark = is_dark(config)
        th = VSCODE_THEMES["Dark" if dark else "Light"]
        self.tree.tag_configure("tag_ok", background=th["table_row"], foreground=th["table_fg"])
        self.tree.tag_configure("tag_ok_alt", background=th["table_alt"], foreground=th["table_fg"])
        self.tree.tag_configure("tag_xz", background="#4D3209" if dark else "#FFF1D6", foreground="#E9A23B" if dark else "#9A5B00")
        self.tree.tag_configure("tag_fail", background="#5A1D1D" if dark else "#FDE2E2", foreground="#F48771" if dark else "#A1260D")

    def _radix_changed(self, value: str) -> None:
        self.render()
        if self.on_radix:
            self.on_radix(value)

    def set_radix(self, value: str) -> None:
        self.radix.set(value)
        self.render()

    def set_data(self, table: dict, widths: dict[str, int] | None = None) -> None:
        self.table, self.widths = table, widths or {}
        self.render()

    def clear(self, message: str = "No simulation yet") -> None:
        self.table = {"columns": [], "rows": [], "counts": {}, "outputs": []}
        self.render()
        self.summary.configure(text=message)

    def _set_filter(self, mode: str) -> None:
        self.filter_mode = mode
        self.render()

    def _set_search(self, text: str) -> None:
        self.filter_text = text.strip().lower()
        self.render()

    def _keep(self, r: dict, shown_vals: list[str]) -> bool:
        if self.filter_mode == "FAIL" and r["status"] != "FAIL":
            return False
        if self.filter_mode.startswith("x/z") and not r["status"].startswith("FLOATING"):
            return False
        if self.filter_text:
            hay = " ".join(shown_vals + [r.get("line", "")]).lower()
            return all(tok in hay for tok in self.filter_text.split())
        return True

    def _display_rows(self, filtered: bool = False) -> tuple[list[str], list[list[str]], list[str]]:
        radix = self.radix.get()
        cols = self.table.get("columns", [])
        outs = set(self.table.get("outputs", []))
        heads = ["#"] + [f"{c} ⇐ out" if c in outs else c for c in cols] + ["Status"]
        rows, statuses = [], []
        for k, r in enumerate(self.table.get("rows", []), 1):
            vals = [convert_value(v, radix, self.widths.get(c)) for c, v in zip(cols, r["values"])]
            if filtered and not self._keep(r, vals):
                continue
            rows.append([str(k)] + vals + [r["status"]])
            statuses.append(r["status"])
        return heads, rows, statuses

    def render(self) -> None:
        heads, rows, statuses = self._display_rows(filtered=True)
        self.tree.delete(*self.tree.get_children())
        ids = [f"c{i}" for i in range(len(heads))]
        self.tree.configure(columns=ids)
        f = tkfont.Font(family=self.cfg["editor_font_family"], size=-ui_px(self))
        fh = tkfont.Font(family="Segoe UI", size=-ui_px(self), weight="bold")      # headings are bold Segoe UI
        pad = int(28 * ui_scale(self))
        for i, (cid, h) in enumerate(zip(ids, heads)):
            width = max([fh.measure(h) + pad] + [f.measure(r[i]) + pad for r in rows[:200]])
            self.tree.heading(cid, text=h, anchor="center")
            self.tree.column(cid, width=min(max(width, 44), 260), minwidth=36, anchor="center",
                             stretch=(i == len(heads) - 1))
        for k, (r, st) in enumerate(zip(rows, statuses)):
            tag = "tag_fail" if st == "FAIL" else "tag_xz" if st != "OK" else ("tag_ok_alt" if k % 2 else "tag_ok")
            self.tree.insert("", "end", values=r, tags=(tag,))
        c = self.table.get("counts", {})
        total = len(self.table.get("rows", []))
        if total:
            parts = [f"{len(rows)} of {total} rows" if len(rows) != total else f"{total} rows"]
            if c.get("FLOATING/CONFLICT (x/z)"):
                parts.append(f"⚠ {c['FLOATING/CONFLICT (x/z)']} x/z")
            if c.get("FAIL"):
                parts.append(f"✖ {c['FAIL']} FAIL")
            if not c.get("FLOATING/CONFLICT (x/z)") and not c.get("FAIL"):
                parts.append("✔ all clean")
            self.summary.configure(text="   ".join(parts))

    def export(self, fmt: str) -> str:
        heads, rows, _ = self._display_rows()
        if not heads or not rows:
            return ""
        if fmt == "csv":
            esc = lambda s: f'"{s}"' if any(ch in s for ch in ',"') else s
            return "\n".join(",".join(esc(c.replace(" ⇐ out", "")) for c in line) for line in [heads] + rows) + "\n"
        out = ["| " + " | ".join(h.replace(" ⇐ out", " (out)") for h in heads) + " |",
               "|" + "|".join("---" for _ in heads) + "|"]
        out += ["| " + " | ".join(r) + " |" for r in rows]
        return "\n".join(out) + "\n"

    def copy(self, fmt: str) -> None:
        s = self.export(fmt)
        if s:
            self.clipboard_clear()
            self.clipboard_append(s)
            self.summary.configure(text=f"Copied {len(self.table.get('rows', []))} rows as {'CSV' if fmt == 'csv' else 'Markdown'}")


def style_treeview(style: ttk.Style, config, scale: float = 1.0) -> None:
    dark = is_dark(config)
    if style.theme_use() != "clam":
        style.theme_use("clam")
    th = VSCODE_THEMES["Dark" if dark else "Light"]
    bg, fg = th["table_row"], th["table_fg"]
    head_bg, head_fg = th["table_head"], th["table_head_fg"]
    px = max(9, round(int(config.get("ui_font_size", FontBook.base)) * scale))
    style.configure("VF.Treeview", background=bg, fieldbackground=bg, foreground=fg, borderwidth=0,
                    rowheight=int(px * 1.75) + 8, font=(config["editor_font_family"], -px))      # spacious, never clipped
    style.configure("VF.Treeview.Heading", background=head_bg, foreground=head_fg, relief="flat", borderwidth=0,
                    font=("Segoe UI", -px, "bold"), padding=(8, 6))
    style.map("VF.Treeview", background=[("selected", th["selected"])], foreground=[("selected", th["selected_fg"])])
    style.map("VF.Treeview.Heading", background=[("active", th["hover"])], relief=[("active", "flat")])
    style.layout("VF.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])


# =========================================================================== waveform viewer
class MiniWaveformViewer(ctk.CTkFrame):
    """Canvas waveform viewer for VCD dumps or truth-table rows (scalar lines + bus hexagons)."""
    ROW_H, AXIS_H, NAME_W = 34, 26, 170

    def __init__(self, master, config, on_open_gtkwave: Callable | None = None, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.cfg, self.radix = config, config["default_radix"]
        self.signals: list[dict] = []
        self._all_signals: list[dict] = []
        self.end_time, self.px, self.cursor_t = 0, 4.0, None
        self.source = ""
        bar = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        bar.grid(row=0, column=0, columnspan=3, sticky="ew", padx=8, pady=6)
        for txt, cmd, w in (("＋ Zoom", lambda: self.zoom(1.5), 70), ("－ Zoom", lambda: self.zoom(1 / 1.5), 70), ("⤢ Fit", self.fit, 56)):
            ghost_button(bar, txt, cmd, width=w, height=24).pack(side="left", padx=2)
        self.all_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(bar, text="Internal signals", variable=self.all_var, command=self._refilter, checkbox_width=15,
                        checkbox_height=15, corner_radius=2, border_width=1, text_color=VS["text"],
                        font=ui_font(0)).pack(side="left", padx=12)
        self.info = ctk.CTkLabel(bar, text="No waveform yet", anchor="w", text_color=VS["muted"], font=ui_font(0))
        self.info.pack(side="left", padx=8)
        self.gtk_btn = ghost_button(bar, "📈 Open in GTKWave", lambda: on_open_gtkwave and on_open_gtkwave(), width=150, height=24)
        self.gtk_btn.pack(side="right", padx=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.names = tk.Canvas(self, width=self.NAME_W, highlightthickness=0, bd=0)
        self.names.grid(row=1, column=0, sticky="ns")
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0)
        self.canvas.grid(row=1, column=1, sticky="nsew")
        self.vsb = slim_scrollbar(self, self._yview)
        self.vsb.grid(row=1, column=2, sticky="ns")
        self.hsb = slim_scrollbar(self, self.canvas.xview, "horizontal")
        self.hsb.grid(row=2, column=1, sticky="ew")
        self.canvas.configure(xscrollcommand=self.hsb.set, yscrollcommand=self.vsb.set)
        self.canvas.bind("<Configure>", lambda e: self.render() if self.px_auto else None)
        self.canvas.bind("<Button-1>", self._click)
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.names.bind("<MouseWheel>", self._wheel)
        self.canvas.bind("<Control-MouseWheel>", lambda e: (self.zoom(1.25 if e.delta > 0 else 0.8), "break")[1])
        self.canvas.bind("<Shift-MouseWheel>", lambda e: self.canvas.xview_scroll(int(-e.delta / 40), "units"))
        self.px_auto = True
        self.apply_theme(config)

    # ---- data
    def set_vcd(self, vcd: dict) -> None:
        sigs = []
        for s in vcd["signals"]:
            ch = vcd["values"].get(s["full_name"], [])
            if any(x["full"] == s["full_name"] for x in sigs):
                continue
            sigs.append({"name": s["name"], "full": s["full_name"], "width": s["width"], "changes": ch,
                         "depth": s["depth"], "kind": s["kind"]})
        self._all_signals = sigs
        self.end_time = max(vcd["end_time"], 1)
        self.source = f"VCD · timescale {vcd['timescale'] or '?'}" + (" · truncated" if vcd.get("truncated") else "")
        self._refilter(fit=True)

    def set_from_table(self, columns: list[str], rows: list[dict], step: int = 10) -> None:
        sigs = []
        for i, c in enumerate(columns):
            vals = [r["values"][i] if i < len(r["values"]) else "x" for r in rows]
            width = max((len(v) for v in vals if re.fullmatch(r"[01xXzZ]+", v)), default=1)
            changes = []
            for k, v in enumerate(vals):
                v = v.lower()
                if not changes or changes[-1][1] != v:
                    changes.append((k * step, v))
            sigs.append({"name": c, "full": c, "width": width, "changes": changes, "depth": 1, "kind": "wire"})
        self._all_signals = sigs
        self.end_time = max(len(rows) * step, 1)
        self.source = f"synthesized from {len(rows)} truth-table rows (#{step} per row)"
        self._refilter(fit=True)

    def clear(self, msg: str = "No waveform yet") -> None:
        self._all_signals, self.signals, self.end_time = [], [], 0
        self.source = msg
        self.render()

    def _refilter(self, fit: bool = False) -> None:
        if not self._all_signals:
            self.signals = []
        else:
            top = min(s["depth"] for s in self._all_signals)
            self.signals = [s for s in self._all_signals if self.all_var.get()
                            or (s["depth"] == top and s["kind"] not in ("integer", "real", "parameter", "event"))]
        if fit:
            self.fit()
        else:
            self.render()

    # ---- view
    def apply_theme(self, config) -> None:
        self.cfg = config
        dark = is_dark(config)
        th = VSCODE_THEMES["Dark" if dark else "Light"]
        self.col = {
            "bg": th["editor"], "names_bg": th["sidebar"], "grid": th["border"], "text": th["text"], "dim": th["muted"],
            "wave": "#4EC9B0" if dark else "#16825D", "bus": "#16352F" if dark else "#E0F2EC",
            "x": "#F14C4C", "x_fill": "#3B1414" if dark else "#FDE2E2", "z": "#CCA700",
            "cursor": "#3794FF" if dark else "#005FB8",
        }
        self.canvas.configure(bg=self.col["bg"])
        self.names.configure(bg=self.col["names_bg"])
        self.render()

    def set_radix(self, radix: str) -> None:
        self.radix = radix
        self.render()

    def zoom(self, factor: float) -> None:
        self.px_auto = False
        self.px = min(max(self.px * factor, 0.02), 400.0)
        self.render()

    def fit(self) -> None:
        self.px_auto = True
        self.render()

    def _yview(self, *args) -> None:
        self.canvas.yview(*args)
        self.names.yview(*args)

    def _wheel(self, e) -> str:
        d = int(-e.delta / 40) or (-1 if e.delta > 0 else 1)
        self.canvas.yview_scroll(d, "units")
        self.names.yview_scroll(d, "units")
        return "break"

    def _x(self, t: float) -> float:
        return 10 + t * self.px

    def _click(self, e) -> None:
        if not self.signals:
            return
        x = self.canvas.canvasx(e.x)
        self.cursor_t = max(0, min(self.end_time, (x - 10) / self.px))
        self.render()

    @staticmethod
    def _value_at(changes: list[tuple[int, str]], t: float) -> str:
        v = "x"
        for ct, cv in changes:
            if ct > t:
                break
            v = cv
        return v

    def render(self) -> None:
        c, n = self.canvas, self.names
        c.delete("all")
        n.delete("all")
        col = self.col
        sc = ui_scale(self)
        k = FontBook.base / 13                                # canvas geometry grows with the UI text size
        self.row_h, self.axis_h, name_w = int(self.ROW_H * sc * k), int(self.AXIS_H * sc * k), int(self.NAME_W * sc * k)
        if int(n.cget("width")) != name_w:
            n.configure(width=name_w)
        fpx = -ui_px(self, -1)
        fsz = -fpx * 0.75
        fam = self.cfg["editor_font_family"]
        font, bold = (fam, fpx), (fam, fpx, "bold")
        self.names.configure(width=name_w)
        if not self.signals:
            c.create_text(20, 30, anchor="w", text=self.source or "No waveform yet - press ▶ RUN", fill=col["dim"], font=font)
            self.info.configure(text=self.source or "No waveform yet")
            return
        if self.px_auto:
            avail = max(c.winfo_width() - 30, 200)
            self.px = avail / max(self.end_time, 1)
        total_w = self._x(self.end_time) + 30
        total_h = self.axis_h + len(self.signals) * self.row_h + 10
        c.configure(scrollregion=(0, 0, total_w, total_h))
        n.configure(scrollregion=(0, 0, name_w, total_h))
        # time axis
        raw = 80 / self.px
        mag = 10 ** math.floor(math.log10(max(raw, 1e-9)))
        tick = next(m * mag for m in (1, 2, 5, 10) if m * mag >= raw)
        t = 0.0
        while t <= self.end_time + 1e-9:
            x = self._x(t)
            c.create_line(x, self.axis_h - 6, x, total_h, fill=col["grid"])
            c.create_text(x + 3, 4, anchor="nw", text=f"{t:g}", fill=col["dim"], font=font)
            t += tick
        n.create_text(8, 6, anchor="nw", text="signal", fill=col["dim"], font=bold)
        for r, s in enumerate(self.signals):
            y0 = self.axis_h + r * self.row_h
            hi, lo = y0 + 7, y0 + self.row_h - 9
            mid = (hi + lo) / 2
            c.create_line(0, y0 + self.row_h - 1, total_w, y0 + self.row_h - 1, fill=col["grid"])
            label = s["name"] + (f" [{s['width']}]" if s["width"] > 1 and "[" not in s["name"] else "")
            n.create_text(8, mid, anchor="w", text=label, fill=col["text"], font=bold if s["width"] == 1 else font)
            if self.cursor_t is not None:
                v = self._value_at(s["changes"], self.cursor_t)
                n.create_text(name_w - 6, mid, anchor="e", text=convert_value(v, self.radix, s["width"]),
                              fill=col["cursor"], font=bold)
            prev_level = None
            for k, (ct, v) in enumerate(s["changes"]):
                nt = s["changes"][k + 1][0] if k + 1 < len(s["changes"]) else self.end_time
                x0, x1 = self._x(ct), self._x(nt)
                if x1 <= x0:
                    continue
                if s["width"] == 1 and v in ("0", "1"):
                    yl = hi if v == "1" else lo
                    if prev_level is not None and prev_level != yl:
                        c.create_line(x0, prev_level, x0, yl, fill=col["wave"], width=2)
                    c.create_line(x0, yl, x1, yl, fill=col["wave"], width=2)
                    prev_level = yl
                elif s["width"] == 1 and v == "z":
                    c.create_line(x0, mid, x1, mid, fill=col["z"], width=2)
                    prev_level = None
                elif s["width"] == 1:
                    self._hatch(x0, x1, hi, lo)
                    prev_level = None
                else:
                    d = min(4, (x1 - x0) / 2)
                    has_x, has_z = "x" in v, "z" in v and set(v) <= {"z"}
                    outline = col["x"] if has_x else col["z"] if has_z else col["wave"]
                    fill = col["x_fill"] if has_x else col["bg"] if has_z else col["bus"]
                    c.create_polygon(x0, mid, x0 + d, hi, x1 - d, hi, x1, mid, x1 - d, lo, x0 + d, lo,
                                     outline=outline, fill=fill, width=1.5)
                    txt = convert_value(v, self.radix, s["width"])
                    if self.radix != "Binary" or len(txt) <= 16:
                        tw = len(txt) * fsz * 0.75
                        if x1 - x0 > tw + 8:
                            c.create_text((x0 + x1) / 2, mid, text=txt, fill=col["text"], font=font)
                    prev_level = None
        if self.cursor_t is not None:
            x = self._x(self.cursor_t)
            c.create_line(x, 0, x, total_h, fill=col["cursor"], dash=(4, 3))
            c.create_text(x + 4, self.axis_h - 2, anchor="sw", text=f"t={self.cursor_t:.4g}", fill=col["cursor"], font=bold)
        self.info.configure(text=f"{len(self.signals)} signals · 0-{self.end_time} · {self.source}"
                                 + ("  ·  click to place cursor" if self.cursor_t is None else ""))

    def _hatch(self, x0: float, x1: float, hi: float, lo: float) -> None:
        c, col = self.canvas, self.col
        c.create_rectangle(x0, hi, x1, lo, fill=col["x_fill"], outline=col["x"])
        h = lo - hi
        x = x0
        while x < x1:
            xa, xb = x, min(x + h, x1)
            c.create_line(xa, lo, xb, lo - (xb - xa), fill=col["x"])
            x += 7


# =========================================================================== VS Code workbench chrome
class ActivityBar(ctk.CTkFrame):
    """48px icon rail on the far left (VS Code activity bar) with a 2px accent on the active item."""

    def __init__(self, master, items: list[tuple[str, str, str]], bottom: list[tuple[str, str, str]],
                 on_click: Callable[[str], None], **kw):
        super().__init__(master, width=48, corner_radius=0, fg_color=VS["activity"], **kw)
        self.on_click, self.active = on_click, None
        self.cells: dict[str, tuple[ctk.CTkFrame, ctk.CTkLabel]] = {}
        self._tip = _Tooltip(self)
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        for r, item in enumerate(items):
            self._add(item).grid(row=r, column=0, sticky="ew")
        self.grid_rowconfigure(len(items), weight=1)
        for r, item in enumerate(bottom, start=len(items) + 1):
            self._add(item).grid(row=r, column=0, sticky="ew", pady=(0, 4) if r == len(items) + len(bottom) else 0)

    def _add(self, item: tuple[str, str, str]) -> ctk.CTkFrame:
        key, icon, tip = item
        cell = ctk.CTkFrame(self, width=48, height=46, corner_radius=0, fg_color="transparent")
        cell.grid_propagate(False)
        cell.grid_columnconfigure(1, weight=1)
        bar = ctk.CTkFrame(cell, width=2, corner_radius=0, fg_color=VS["activity"])
        bar.grid(row=0, column=0, sticky="ns")
        cell.grid_rowconfigure(0, weight=1)
        lab = ctk.CTkLabel(cell, text=icon, font=ui_font(7, family="Segoe UI Symbol"), text_color=VS["activity_fg"])
        lab.grid(row=0, column=1, sticky="nsew")
        for w in (cell, lab):
            w.bind("<Button-1>", lambda e, k=key: self.on_click(k))
            w.bind("<Enter>", lambda e, k=key, t=tip, l=lab: self._hover(k, l, True, t, e))
            w.bind("<Leave>", lambda e, k=key, l=lab: self._hover(k, l, False))
        self.cells[key] = (bar, lab)
        return cell

    def _hover(self, key, lab, inside, tip="", e=None) -> None:
        if inside:
            lab.configure(text_color=VS["activity_active"])
            if tip and e is not None:
                self._tip.show(tip, e.x_root, e.y_root)
        else:
            self._tip.hide()
            if key != self.active:
                lab.configure(text_color=VS["activity_fg"])

    def set_active(self, key: str | None) -> None:
        self.active = key
        for k, (bar, lab) in self.cells.items():
            on = k == key
            bar.configure(fg_color=VS["accent"] if on else VS["activity"])
            lab.configure(text_color=VS["activity_active"] if on else VS["activity_fg"])


class PanelTabs(ctk.CTkFrame):
    """VS Code bottom panel: flat UPPERCASE tabs with a 2px accent underline, count badges and a right-hand slot."""

    def __init__(self, master, command: Callable | None = None, **kw):
        super().__init__(master, corner_radius=0, fg_color=VS["panel"], **kw)
        self.command = command
        self._tabs: dict[str, dict] = {}
        self._current: str | None = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.header = ctk.CTkFrame(self, height=38, corner_radius=0, fg_color=VS["panel"])
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_propagate(False)
        self.header.grid_columnconfigure(1, weight=1)
        self.header.grid_rowconfigure(0, weight=1)
        self.tabs_frame = ctk.CTkFrame(self.header, fg_color="transparent", corner_radius=0)
        self.tabs_frame.grid(row=0, column=0, sticky="nsw", padx=(8, 0))
        self.right = ctk.CTkFrame(self.header, fg_color="transparent", corner_radius=0)
        self.right.grid(row=0, column=1, sticky="nsew", padx=(12, 6))
        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color=VS["panel_content"])
        self.content.grid(row=1, column=0, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

    def add(self, key: str, title: str) -> ctk.CTkFrame:
        col = len(self._tabs)
        cell = ctk.CTkFrame(self.tabs_frame, width=1, height=1, fg_color="transparent", corner_radius=0)
        cell.grid(row=0, column=col, sticky="ns", padx=(0, 4))
        cell.grid_rowconfigure(0, weight=1)
        inner = ctk.CTkFrame(cell, width=1, height=1, fg_color="transparent", corner_radius=0)
        inner.grid(row=0, column=0, sticky="nsew", padx=6)
        lab = ctk.CTkLabel(inner, text=title.upper(), font=ui_font(-1, "bold"), text_color=VS["muted"], cursor="hand2")
        lab.pack(side="left")
        badge = ctk.CTkLabel(inner, text="", width=20, height=16, corner_radius=8, fg_color=VS["badge"], text_color=VS["badge_fg"],
                             font=ui_font(-2, "bold"))
        under = ctk.CTkFrame(cell, width=1, height=2, corner_radius=0, fg_color=VS["panel"])   # width=1: hug the label
        under.grid(row=1, column=0, sticky="ew")
        frame = ctk.CTkFrame(self.content, corner_radius=0, fg_color=VS["panel_content"])
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        for w in (cell, inner, lab, badge):
            w.bind("<Button-1>", lambda e, k=key: self.set(k))
            w.bind("<Enter>", lambda e, k=key: self._tabs[k]["label"].configure(text_color=VS["text"]))
            w.bind("<Leave>", lambda e, k=key: self._paint(k))
        self._tabs[key] = {"label": lab, "badge": badge, "under": under, "frame": frame, "title": title}
        if self._current is None:
            self.set(key, notify=False)
        return frame

    def _paint(self, key: str) -> None:
        t = self._tabs[key]
        on = key == self._current
        t["label"].configure(text_color=VS["tab_active_fg"] if on else VS["muted"])
        t["under"].configure(fg_color=VS["accent"] if on else VS["panel"])

    def set(self, key: str, notify: bool = True) -> None:
        if key not in self._tabs:
            return
        self._current = key
        for k, t in self._tabs.items():
            if k == key:
                t["frame"].grid(row=0, column=0, sticky="nsew")
            else:
                t["frame"].grid_remove()
            self._paint(k)
        if notify and self.command:
            self.command()

    def get(self) -> str | None:
        return self._current

    def set_badge(self, key: str, count: int | None) -> None:
        b = self._tabs[key]["badge"]
        if count is not None:
            b.configure(text=f" {count} ")
            b.pack(side="left", padx=(6, 0))
        else:
            b.pack_forget()


class SideSection(ctk.CTkFrame):
    """VS Code accordion section: '▾ TITLE (n)' header that collapses its body."""

    def __init__(self, master, title: str, on_toggle: Callable | None = None, **kw):
        super().__init__(master, corner_radius=0, fg_color=VS["sidebar"], **kw)
        self.title, self.open, self.on_toggle = title, True, on_toggle
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.head = ctk.CTkLabel(self, text="", anchor="w", height=28, font=ui_font(-1, "bold"),
                                 text_color=VS["sidebar_header"], cursor="hand2")
        self.head.grid(row=0, column=0, sticky="ew", padx=4)
        self.head.bind("<Button-1>", lambda e: self.toggle())
        self.body = ctk.CTkFrame(self, corner_radius=0, fg_color=VS["sidebar"])
        self.body.grid(row=1, column=0, sticky="nsew")
        self.body.grid_columnconfigure(0, weight=1)
        self.set_count(None)

    def set_count(self, n: int | None) -> None:
        self.head.configure(text=f"{'▾' if self.open else '▸'} {self.title}" + (f" ({n})" if n is not None else ""))
        self._n = n

    def toggle(self) -> None:
        self.open = not self.open
        if self.open:
            self.body.grid()
        else:
            self.body.grid_remove()
        self.set_count(self._n)
        if self.on_toggle:
            self.on_toggle(self)



class PinoutDiagram(tk.Canvas):
    """VS Code-styled IC block: inputs on the left, outputs/inouts on the right, buses drawn as double lines."""

    def __init__(self, master, config, **kw):
        super().__init__(master, highlightthickness=0, bd=0, **kw)
        self.cfg, self.info, self.gates = config, None, 0
        self.bind("<Configure>", lambda e: self.render())

    def set_module(self, info: dict | None, gate_total: int = 0, depth: int = 0) -> None:
        self.info, self.gates, self.depth = info, gate_total, depth
        self.render()

    def render(self) -> None:
        self.delete("all")
        dark = is_dark(self.cfg)
        th = VSCODE_THEMES["Dark" if dark else "Light"]
        bg, body, border, fg, muted = th["editor"], th["group"], "#007ACC", th["text"], th["muted"]
        wire, bus = ("#4EC9B0", "#DCDCAA") if dark else ("#16825D", "#795E26")
        self.configure(bg=bg)
        w, h = max(self.winfo_width(), 200), max(self.winfo_height(), 160)
        sc = ui_scale(self)
        f = (self.cfg["editor_font_family"], -ui_px(self, -1), "bold")      # pin names: Consolas bold
        fb = ("Segoe UI", -ui_px(self, 1), "bold")                         # chip title
        if not self.info:
            self.create_text(w / 2, h / 2, text="Open a module to see its pinout", fill=muted, font=f)
            return
        ins = [p for p in self.info["ports"] if p["direction"] == "input"]
        outs = [p for p in self.info["ports"] if p["direction"] != "input"]
        rows = max(len(ins), len(outs), 1)
        head = 46 * sc                                   # header band: module name + gate count, never under a pin
        pitch = max(18 * sc, min(32 * sc, (h - head - 40 * sc) / rows))
        chip_h = head + rows * pitch + 12 * sc
        lead = max(36 * sc, min(70 * sc, w * 0.16))
        chip_w = max(130 * sc, min(260 * sc, w - 2 * lead - 120 * sc))      # leave room for the in/out labels
        x0, y0 = (w - chip_w) / 2, max(10 * sc, (h - chip_h) / 2)
        x1, y1 = x0 + chip_w, y0 + chip_h
        self.create_rectangle(x0, y0, x1, y1, fill=body, outline=border, width=max(2, int(2 * sc)))
        self.create_arc(x0 + chip_w / 2 - 10 * sc, y0 - 10 * sc, x0 + chip_w / 2 + 10 * sc, y0 + 10 * sc,
                        start=180, extent=180, style="arc", outline=border, width=max(2, int(2 * sc)))
        self.create_text((x0 + x1) / 2, y0 + 20 * sc, text=self.info["module_name"], fill=fg, font=fb)
        self.create_text((x0 + x1) / 2, y0 + 37 * sc, fill=muted, font=f, text=f"{self.gates} gates · depth ~{self.depth}")
        self.create_line(x0 + 8 * sc, y0 + head, x1 - 8 * sc, y0 + head, fill=th["border"])
        pin_y = lambda k, n: y0 + head + (k + 0.5) * (chip_h - head - 12 * sc) / max(n, 1)

        def pin(p, y, left: bool) -> None:
            is_bus = isinstance(p.get("bits"), int) and p["bits"] > 1 or bool(p.get("range_text") and p.get("bits") is None)
            xa, xb = (x0 - lead, x0) if left else (x1, x1 + lead)
            color = bus if is_bus else wire
            if is_bus:
                gap = 2.5 * sc
                self.create_line(xa, y - gap, xb, y - gap, fill=color, width=max(1, int(1.5 * sc)))
                self.create_line(xa, y + gap, xb, y + gap, fill=color, width=max(1, int(1.5 * sc)))
                mid = (xa + xb) / 2
                self.create_line(mid - 5 * sc, y + 7 * sc, mid + 5 * sc, y - 7 * sc, fill=color, width=max(1, int(1.5 * sc)))
                self.create_text(mid, y - 9 * sc, text=p["range_text"] or f"[{p['bits'] - 1}:0]", fill=color, font=f, anchor="s")
            else:
                self.create_line(xa, y, xb, y, fill=color, width=max(1, int(2 * sc)))
            arrow_x = xb if left else xb + 2 * sc     # inputs point into the chip, outputs point away from it
            d = 6 * sc
            if p["direction"] != "inout":
                self.create_polygon(arrow_x - d, y - 5 * sc, arrow_x, y, arrow_x - d, y + 5 * sc, fill=color, outline="")
            self.create_text(x0 + 10 * sc if left else x1 - 10 * sc, y, text=p["name"], fill=fg, font=f,
                             anchor="w" if left else "e")
            self.create_text(xa - 4 * sc if left else xb + 4 * sc, y, anchor="e" if left else "w", fill=muted, font=f,
                             text="in" if left else ("inout" if p["direction"] == "inout" else "out"))
        for k, p in enumerate(ins):
            pin(p, pin_y(k, len(ins)), True)
        for k, p in enumerate(outs):
            pin(p, pin_y(k, len(outs)), False)
