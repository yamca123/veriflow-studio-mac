"""VeriFlow Studio - VS Code style Welcome / Get Started view, New Module & Project location wizard,
and the update notification card."""
from __future__ import annotations

import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

from config_manager import APP_NAME, APP_VERSION, RUN_GREEN, RUN_GREEN_HOVER, VS
from ui_components import entry_style, ghost_button, icon_button, seg_style, ui_font
from verilog_parser import generate_testbench_skeleton, new_module_template, parse_verilog_module

LINK = ("#005FB8", "#3794FF")
SUBTITLE = ("#0451A5", "#9CDCFE")
TITLE = ("#1F1F1F", "#FFFFFF")
IDENT_RE = re.compile(r"[A-Za-z_]\w*")
PORT_RE = re.compile(r"^(\[\s*[^\]\[]+:\s*[^\]\[]+\])?\s*([A-Za-z_]\w*)$")
TB_MODES = ("Exhaustive Truth-Table TB", "Empty Skeleton TB", "No TB yet")


# =========================================================================== pure helpers (unit-tested)
def parse_port_list(text: str) -> list[tuple[str, str]]:
    """'a, b, cin' / '[15:0] a, [15:0] b' -> [(range, name), ...]. Each width applies to the one name after it."""
    out, seen = [], set()
    for raw in text.split(","):
        tok = " ".join(raw.split())
        if not tok:
            continue
        m = PORT_RE.match(tok)
        if not m:
            raise ValueError(f"'{tok}' is not a port. Use a name like  a  or a bus like  [15:0] a")
        rng, name = (m.group(1) or "").replace(" ", ""), m.group(2)
        if name.lower() in seen:
            raise ValueError(f"Port '{name}' is listed twice.")
        seen.add(name.lower())
        out.append((rng, name))
    return out


def module_source(name: str, inputs: str = "", outputs: str = "") -> str:
    """Design file text. With no ports the classic NAND starter template is used."""
    ins, outs = parse_port_list(inputs), parse_port_list(outputs)
    clash = {n.lower() for _r, n in ins} & {n.lower() for _r, n in outs}
    if clash:
        raise ValueError(f"'{sorted(clash)[0]}' is both an input and an output.")
    if not ins and not outs:
        return new_module_template(name)
    decl = [f"    output {r + ' ' if r else ''}{n}" for r, n in outs] + [f"    input  {r + ' ' if r else ''}{n}" for r, n in ins]
    return (f"`timescale 1ns/1ns\n\nmodule {name} (\n" + ",\n".join(decl) + "\n);\n\n"
            "    // gates / module instances go here\n\nendmodule\n")


def create_module_files(folder: Path, name: str, inputs: str = "", outputs: str = "", tb_mode: str = TB_MODES[0]) -> list[Path]:
    """Create <folder>/<name>/<name>.v (+ <name>/<name>_tb.v)."""
    if not IDENT_RE.fullmatch(name or ""):
        raise ValueError("Module name must be a Verilog identifier: letters, digits, '_' (not starting with a digit).")
    if name.lower().endswith("_tb"):
        raise ValueError("Pick the design name (e.g. ALU16) - the _tb.v testbench is generated for you.")
    text = module_source(name, inputs, outputs)
    folder = Path(folder) / name
    folder.mkdir(parents=True, exist_ok=True)
    existing = {p.name.lower() for p in folder.glob("*.v")}
    design, tb = folder / f"{name}.v", folder / f"{name}_tb.v"
    if design.name.lower() in existing:
        raise FileExistsError(f"{design.name} (or a case-variant) already exists in\n{folder}")
    design.write_text(text, encoding="utf-8")
    made = [design]
    if tb_mode != TB_MODES[2] and tb.name.lower() not in existing:
        info = parse_verilog_module(design, text)
        if info.get("module_name"):
            tb.write_text(generate_testbench_skeleton(info, empty_stimulus=tb_mode == TB_MODES[1]), encoding="utf-8")
            made.append(tb)
    return made


# =========================================================================== Welcome / Get Started
class WelcomeView(ctk.CTkFrame):
    """Shown in the editor area on startup (startup_mode = welcome_screen), after Close Folder, or via 🏠."""

    def __init__(self, master, app):
        super().__init__(master, corner_radius=0, fg_color=VS["editor"])
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        sc = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color=VS["editor"], scrollbar_button_color=VS["scroll_thumb"],
                                    scrollbar_button_hover_color=VS["scroll_hover"])
        sc.grid(row=0, column=0, sticky="nsew")
        sc.grid_columnconfigure(0, weight=1)
        page = ctk.CTkFrame(sc, fg_color="transparent")
        page.grid(row=0, column=0, padx=48, pady=(40, 24), sticky="n")
        page.grid_columnconfigure((0, 1), weight=1, uniform="col")

        ctk.CTkLabel(page, text=APP_NAME, font=ui_font(11, "bold"), text_color=TITLE, anchor="w").grid(
            row=0, column=0, columnspan=2, sticky="w")
        ctk.CTkLabel(page, text="Icarus Verilog (-g2012) & VVP Native Hardware Design Environment",
                     font=ui_font(1), text_color=SUBTITLE, anchor="w").grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))
        ctk.CTkLabel(page, text=f"Version {APP_VERSION}", font=ui_font(-1), text_color=VS["muted"], anchor="w").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(0, 26))

        left = ctk.CTkFrame(page, fg_color="transparent")
        left.grid(row=3, column=0, sticky="nw", padx=(0, 40))
        ctk.CTkLabel(left, text="Start", font=ui_font(5), text_color=TITLE, anchor="w").pack(anchor="w", pady=(0, 8))
        self.actions = {}
        for key, icon, label, keys, cmd in (
                ("new", "📄", "New Verilog Module / File…", "Ctrl+N", app.new_module),
                ("project", "📁", "Create New Assignment / Project Folder…", "Ctrl+Shift+N", app.new_project),
                ("open", "📂", "Open Existing Folder…", "Ctrl+O", app.choose_folder),
                ("file", "📄", "Open Single .v File…", "", app.open_single_file),
                ("import", "📦", "Import Lecturer Modules / Package (.v / Folder / .zip)…", "", app.open_package_manager),
                ("sample", "🧪", "Open Built-in Sample Project (FullAdder)", "", app.open_sample_project)):
            self.actions[key] = self._card(left, icon, label, keys, cmd)

        right = ctk.CTkFrame(page, fg_color="transparent")
        right.grid(row=3, column=1, sticky="nw")
        head = ctk.CTkFrame(right, fg_color="transparent")
        head.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(head, text="Recent", font=ui_font(5), text_color=TITLE, anchor="w").pack(side="left")
        self.clear_btn = ctk.CTkLabel(head, text="Clear Recent", font=ui_font(-1), text_color=LINK, cursor="hand2")
        self.clear_btn.pack(side="right", padx=(20, 0))
        self.clear_btn.bind("<Button-1>", lambda e: self._clear_recent())
        self.recent_box = ctk.CTkFrame(right, fg_color="transparent")
        self.recent_box.pack(fill="x")

        self.show_var = tk.BooleanVar(value=app.cfg["startup_mode"] == "welcome_screen")
        foot = ctk.CTkFrame(page, fg_color="transparent")
        foot.grid(row=4, column=0, columnspan=2, sticky="w", pady=(34, 0))
        self.show_chk = ctk.CTkCheckBox(foot, text="Show Welcome screen on startup", variable=self.show_var, font=ui_font(0),
                                        text_color=VS["text"], checkbox_width=18, checkbox_height=18, border_width=1,
                                        command=self._toggle_startup)
        self.show_chk.pack(side="left")
        ctk.CTkLabel(foot, text="   Tip: F5 runs · Ctrl+Space autocompletes · Ctrl+wheel zooms the whole UI",
                     font=ui_font(-1), text_color=VS["muted"]).pack(side="left")
        self.refresh()

    def _card(self, parent, icon: str, label: str, keys: str, cmd: Callable) -> ctk.CTkFrame:
        row = ctk.CTkFrame(parent, corner_radius=4, fg_color="transparent", cursor="hand2")
        row.pack(fill="x", pady=1)
        ic = ctk.CTkLabel(row, text=icon, width=30, font=ui_font(3, family="Segoe UI Emoji"))
        ic.pack(side="left", padx=(8, 6), pady=5)
        lab = ctk.CTkLabel(row, text=label, font=ui_font(1), text_color=LINK, anchor="w")
        lab.pack(side="left", pady=5)
        widgets = [row, ic, lab]
        if keys:
            k = ctk.CTkLabel(row, text=keys, font=ui_font(-1), text_color=VS["muted"])
            k.pack(side="left", padx=(14, 10))
            widgets.append(k)
        for w in widgets:
            w.bind("<Button-1>", lambda e: cmd())
            w.bind("<Enter>", lambda e: row.configure(fg_color=VS["hover"]))
            w.bind("<Leave>", lambda e: row.configure(fg_color="transparent"))
        return row

    def refresh(self) -> None:
        for w in self.recent_box.winfo_children():
            w.destroy()
        recents = list(self.app.cfg["recent_workspaces"])[:8]
        if not recents:
            ctk.CTkLabel(self.recent_box, text="No recent folders yet - open or create one on the left.",
                         font=ui_font(0), text_color=VS["muted"], anchor="w").pack(anchor="w", padx=8, pady=4)
        for p in recents:
            row = ctk.CTkFrame(self.recent_box, corner_radius=4, fg_color="transparent", cursor="hand2")
            row.pack(fill="x", pady=1)
            exists = Path(p).is_dir()
            name = ctk.CTkLabel(row, text=Path(p).name or p, font=ui_font(1, "bold"), anchor="w",
                                text_color=LINK if exists else VS["muted"])
            name.pack(side="left", padx=(8, 10), pady=5)
            path = ctk.CTkLabel(row, text=p if exists else f"{p}  (missing)", font=ui_font(-1), text_color=VS["muted"], anchor="w")
            path.pack(side="left", pady=5)
            x = icon_button(row, "×", lambda q=p: self._remove(q), width=26, height=24, font=ui_font(2))
            x.pack(side="right", padx=6)
            for w in (row, name, path):
                w.bind("<Button-1>", lambda e, q=p: self.app.open_recent_path(q))
                w.bind("<Enter>", lambda e, r=row: r.configure(fg_color=VS["hover"]))
                w.bind("<Leave>", lambda e, r=row: r.configure(fg_color="transparent"))
        self.show_var.set(self.app.cfg["startup_mode"] == "welcome_screen")

    def _remove(self, path: str) -> None:
        self.app.cfg.update(recent_workspaces=[r for r in self.app.cfg["recent_workspaces"] if r != path])
        self.app._refresh_recent_menu()
        self.refresh()

    def _clear_recent(self) -> None:
        if self.app.cfg["recent_workspaces"] and messagebox.askyesno("Clear Recent", "Remove all recent folders from the list?\n"
                                                                     "(The folders themselves are not touched.)", parent=self):
            self.app.cfg.update(recent_workspaces=[])
            self.app._refresh_recent_menu()
            self.refresh()

    def _toggle_startup(self) -> None:
        self.app.cfg.update(startup_mode="welcome_screen" if self.show_var.get() else "reopen_last")


# =========================================================================== New Module / Project wizard
class NewModuleDialog(ctk.CTkToplevel):
    """Ctrl+N (module in a folder you choose) / Ctrl+Shift+N (new assignment folder + module)."""

    def __init__(self, app, project: bool = False, location: Path | None = None):
        super().__init__(app)
        self.app, self.project, self.result = app, project, None
        self.title("Create New Assignment / Project" if project else "New Verilog Module")
        self.geometry("760x600")
        self.minsize(680, 540)
        self.transient(app)
        self.configure(fg_color=VS["editor"])
        self.grid_columnconfigure(1, weight=1)
        r = 0
        ctk.CTkLabel(self, text="📁  New Assignment / Project Folder" if project else "📄  New Verilog Module",
                     font=ui_font(5, "bold"), text_color=TITLE).grid(row=r, column=0, columnspan=3, sticky="w", padx=20, pady=(16, 10))
        r += 1
        self.name_var = tk.StringVar(value="")
        self.loc_var = tk.StringVar(value=str(location or Path.home() / "Documents"))
        self.sub_var = tk.StringVar(value="")
        self.in_var, self.out_var = tk.StringVar(), tk.StringVar()
        self.tb_var = tk.StringVar(value=TB_MODES[0])
        self.npp_var = tk.BooleanVar(value=False)

        def label(row, text):
            ctk.CTkLabel(self, text=text, font=ui_font(0), text_color=VS["text"], anchor="e").grid(
                row=row, column=0, sticky="e", padx=(20, 10), pady=6)

        label(r, "Module name")
        self.name_entry = ctk.CTkEntry(self, textvariable=self.name_var, height=32, font=ui_font(1, family="Consolas"),
                                       placeholder_text="e.g. ALU16", **entry_style())
        self.name_entry.grid(row=r, column=1, columnspan=2, sticky="ew", padx=(0, 20), pady=6)
        r += 1
        label(r, "Parent folder" if project else "Save in folder")
        ctk.CTkEntry(self, textvariable=self.loc_var, height=32, font=ui_font(0), **entry_style()).grid(
            row=r, column=1, sticky="ew", pady=6)
        ghost_button(self, "📂 Browse Folder…", self._browse, height=32).grid(row=r, column=2, sticky="w", padx=(8, 20))
        r += 1
        label(r, "New folder name" if project else "+ Create subfolder")
        ctk.CTkEntry(self, textvariable=self.sub_var, height=32, font=ui_font(0),
                     placeholder_text="e.g. Lab4 or HW5" if project else "optional - leave empty to save directly in the folder",
                     **entry_style()).grid(row=r, column=1, columnspan=2, sticky="ew", padx=(0, 20), pady=6)
        r += 1
        label(r, "Inputs")
        ctk.CTkEntry(self, textvariable=self.in_var, height=32, font=ui_font(0, family="Consolas"),
                     placeholder_text="a, b, cin    or    [15:0] a, [15:0] b", **entry_style()).grid(
            row=r, column=1, columnspan=2, sticky="ew", padx=(0, 20), pady=6)
        r += 1
        label(r, "Outputs")
        ctk.CTkEntry(self, textvariable=self.out_var, height=32, font=ui_font(0, family="Consolas"),
                     placeholder_text="sum, cout    or    [15:0] y", **entry_style()).grid(
            row=r, column=1, columnspan=2, sticky="ew", padx=(0, 20), pady=6)
        r += 1
        ctk.CTkLabel(self, text="Ports are optional - leave both empty for a starter NAND template. "
                                "Write the width before each bus name.", font=ui_font(-1), text_color=VS["muted"],
                     anchor="w").grid(row=r, column=1, columnspan=2, sticky="w")
        r += 1
        label(r, "Testbench")
        ctk.CTkSegmentedButton(self, values=list(TB_MODES), variable=self.tb_var, **seg_style()).grid(
            row=r, column=1, columnspan=2, sticky="w", pady=8)
        r += 1
        ctk.CTkCheckBox(self, text="Also open the new file(s) in Notepad++", variable=self.npp_var, font=ui_font(0),
                        text_color=VS["text"], checkbox_width=18, checkbox_height=18, border_width=1).grid(
            row=r, column=1, columnspan=2, sticky="w", pady=6)
        r += 1
        self.preview = ctk.CTkLabel(self, text="", font=ui_font(-1, family="Consolas"), text_color=SUBTITLE, anchor="w",
                                    justify="left", wraplength=640)
        self.preview.grid(row=r, column=0, columnspan=3, sticky="ew", padx=20, pady=(10, 4))
        self.grid_rowconfigure(r + 1, weight=1)
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=r + 2, column=0, columnspan=3, sticky="ew", padx=20, pady=(4, 16))
        ctk.CTkButton(bottom, text="✨ Create & Open Module", height=34, corner_radius=3, fg_color=RUN_GREEN,
                      hover_color=RUN_GREEN_HOVER, text_color="#FFFFFF", font=ui_font(1, "bold"), command=self._create).pack(side="right")
        ghost_button(bottom, "Cancel", self.destroy, width=90, height=34).pack(side="right", padx=8)
        for v in (self.name_var, self.loc_var, self.sub_var, self.tb_var):
            v.trace_add("write", lambda *_: self._update_preview())
        self.bind("<Return>", lambda e: self._create())
        self.bind("<Escape>", lambda e: self.destroy())
        self._update_preview()
        self.after(150, self._focus)

    def _focus(self) -> None:
        try:
            self.lift()
            self.focus_force()
            self.name_entry.focus_set()
            self.grab_set()
        except tk.TclError:
            pass

    def target_folder(self) -> Path:
        base = Path(self.loc_var.get().strip().strip('"') or ".")
        sub = self.sub_var.get().strip().strip("\\/")
        return base / sub if sub else base

    def module_folder(self) -> Path:
        name = self.name_var.get().strip() or "<Module>"
        return self.target_folder() / name

    def _update_preview(self) -> None:
        name = self.name_var.get().strip() or "<Module>"
        folder = self.target_folder() / name
        files = f"{name}.v" + ("" if self.tb_var.get() == TB_MODES[2] else f"  +  {name}_tb.v")
        new = "" if folder.is_dir() else "   (folder will be created)"
        self.preview.configure(text=f"Will create:  {files}\nIn:  {folder}{new}")

    def _browse(self) -> None:
        d = filedialog.askdirectory(parent=self, title="Choose where to save", initialdir=self.loc_var.get() or str(Path.home()))
        if d:
            self.loc_var.set(str(Path(d)))

    def _create(self) -> None:
        name = self.name_var.get().strip()
        if self.project and not self.sub_var.get().strip():
            messagebox.showerror(self.title(), "Type a name for the new assignment folder (e.g. Lab4).", parent=self)
            return
        if not Path(self.loc_var.get().strip().strip('"') or "").is_absolute():
            messagebox.showerror(self.title(), "Choose a full folder path (📂 Browse Folder…).", parent=self)
            return
        try:
            files = create_module_files(self.target_folder(), name, self.in_var.get(), self.out_var.get(), self.tb_var.get())
        except (ValueError, FileExistsError, OSError) as exc:
            messagebox.showerror(self.title(), str(exc), parent=self)
            return
        self.result = {"folder": self.module_folder(), "module": name, "files": files, "npp": self.npp_var.get()}
        self.app.cfg.update(last_parent_dir=str(Path(self.loc_var.get().strip().strip('"'))))
        self.grab_release()
        self.withdraw()                                  # destroy a moment later: CTkToplevel still has deferred
        self.after(300, self.destroy)                    # set-up callbacks right after it opens
        self.app.after_idle(lambda: self.app.finish_new_module(self.result))


# =========================================================================== update notification card
class UpdateNotice(ctk.CTkFrame):
    """Bottom-right VS Code notification: 🔔 Update Available + Update & Restart / View Changes / Later."""

    def __init__(self, master, info, can_install: bool, on_update: Callable, on_view: Callable, on_later: Callable):
        super().__init__(master, corner_radius=4, fg_color=VS["group"], border_width=1, border_color=("#005FB8", "#007ACC"))
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(10, 2))
        ctk.CTkLabel(top, text=f"🔔  Update Available: {APP_NAME} v{info.version}", font=ui_font(0, "bold"),
                     text_color=VS["text"], anchor="w").pack(side="left")
        icon_button(top, "✕", on_later, width=24).pack(side="right")
        notes = (info.notes or "").strip().splitlines()
        sub = f"You have v{APP_VERSION}." + (f"  {notes[0][:160]}" if notes else "")
        ctk.CTkLabel(self, text=sub, font=ui_font(-1), text_color=VS["muted"], anchor="w", justify="left",
                     wraplength=440).pack(fill="x", padx=14)
        self.status = ctk.CTkLabel(self, text="", font=ui_font(-1), text_color=SUBTITLE, anchor="w")
        self.status.pack(fill="x", padx=14)
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=14, pady=(4, 12))
        self.update_btn = ctk.CTkButton(btns, text="↓  Update & Restart Now" if can_install else "↓  Open Download Page",
                                        height=30, corner_radius=3, fg_color="#2EA043", hover_color="#3FB950",
                                        text_color="#FFFFFF", font=ui_font(0, "bold"), command=on_update)
        self.update_btn.pack(side="left")
        ghost_button(btns, "View Changes", on_view, height=30).pack(side="left", padx=6)
        ghost_button(btns, "Later", on_later, height=30).pack(side="left")

    def set_status(self, text: str) -> None:
        self.status.configure(text=text)
