"""VeriFlow Studio - Verilog IDE, course linter and one-click iverilog/vvp runner for Computer Structure courses.

Layout follows the VS Code workbench: title/action bar, activity bar, side bar, editor group, panel, status bar.
"""
from __future__ import annotations

import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from config_manager import (TEXT_SIZE_PRESETS, ACCENT, APP_NAME, APP_VERSION, CHOICES, DARK_SCHEME, DEFAULT_CONFIG, EDITOR_SCHEMES,
                            FONT_FAMILIES, LIGHT_SCHEME, RADIXES, RUN_GREEN, RUN_GREEN_HOVER, STATUS_COLORS, STOP_RED,
                            STARTUP_LABELS, STOP_RED_HOVER, VS, VSCODE_THEMES, ConfigManager, detect_toolchains,
                            resource_dir)
from ui_components import (SNIPPETS, ActivityBar, MiniWaveformViewer, PanelTabs, SideSection, TruthTableGrid,
                           VerilogCodeEditor, entry_style, ghost_button, hline, icon_button, is_dark, option_style,
                           DarkMenu, FontBook, PinoutDiagram, _Tooltip, seg_style, slim_scrollbar, style_menu, style_treeview, ui_font,
                           ui_px, ui_scale, vline)
from verilog_parser import (analyze_hierarchy, describe_ports, generate_testbench_skeleton, instantiation_template,
                            new_module_template,
                            parse_vcd_file, parse_verilog_module, run_course_linter, scan_module_dir)
from verilog_runner import NO_WINDOW, STATUS_FAIL, STATUS_XZ, VerilogRunner, clean_binaries, format_cmd
from package_manager import DEFAULT_IMPORT_PACKAGE, PackageManager
from updater import AutoUpdater, app_dir, is_frozen
from welcome import NewModuleDialog, UpdateNotice, WelcomeView
from verilog_parser import parse_verilog_source

# file.v:12 / C:\\dir with spaces\\x.v:3:7 / mux_lib.vh:5 inside console text
LINK_RE = re.compile(r"((?:[A-Za-z]:[\\\\/][^:*?\"<>|\r\n]+?|[^\s:\"'()<>|]+?)\.(?:sv|vh|svh|v)):(\d+)(?::(\d+))?\b")

IS_WINDOWS = os.name == "nt"
IS_MAC = sys.platform == "darwin"
LAYOUT_LABELS = {"Side-by-Side": "Side-by-Side Split (.v + _tb.v)", "Tabbed": "Tabbed View"}
SEV_ICON = {"error": "⊗ error", "warning": "⚠ warning", "info": "ⓘ info"}
SNIPPET_LABEL = "+ Snippet ▾"
RECENT_LABEL = "Recent ▾"
WHITE = "#FFFFFF"
STOP_IDLE = ("#D5D5D5", "#3A3A3A")


def read_source(path: Path) -> tuple[str, str]:
    """Return (text, newline) - keeps the file's original line-ending style for round-trips."""
    raw = path.read_bytes()
    nl = "\r\n" if b"\r\n" in raw else "\n"
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1255" if IS_WINDOWS else "latin-1", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n"), nl


def font(size: int = 12, weight: str = "normal") -> ctk.CTkFont:
    """UI font relative to the user's UI text size: 12 = the base size, 11 = one step smaller, 14 = two larger...
    Fonts are shared FontBook objects, so A+/A-, Ctrl+wheel and the size presets re-flow the UI live."""
    return ui_font(size - 12, weight)


# =========================================================================== settings dialog
class SettingsDialog(ctk.CTkToplevel):
    """4-tab live-apply settings window. Every control writes straight into ConfigManager."""

    def __init__(self, app: "VeriFlowApp"):
        super().__init__(app)
        self.app, self.cfg = app, app.cfg
        self.title(f"{APP_NAME} - Settings")
        self.geometry("780x640")
        self.minsize(700, 560)
        self.transient(app)
        self.configure(fg_color=VS["editor"])
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.path_status: dict[str, ctk.CTkLabel] = {}
        tv = ctk.CTkTabview(self, corner_radius=3, fg_color=VS["sidebar"], border_width=1, border_color=VS["border"],
                            segmented_button_fg_color=("#E5E5E5", "#2D2D2D"), segmented_button_selected_color=("#BCD9F5", "#04395E"),
                            segmented_button_selected_hover_color=("#A9CDEF", "#0A4A75"),
                            segmented_button_unselected_color=("#F3F3F3", "#2D2D2D"),
                            segmented_button_unselected_hover_color=VS["hover"], text_color=("#1F1F1F", "#E0E0E0"))
        tv.grid(row=0, column=0, sticky="nsew", padx=12, pady=(8, 4))
        t1, t2, t3, t4, t5 = (tv.add(n) for n in ("Appearance & Font", "Editor Behavior", "Compiler & Toolchain",
                                                  "Linter & Sync", "Packages"))
        for t in (t1, t2, t3, t4, t5):
            t.grid_columnconfigure(1, weight=1)

        self._option(t1, 0, "Appearance mode", "appearance_mode", list(CHOICES["appearance_mode"]))
        self._option(t1, 1, "UI accent theme (restart)", "color_theme", list(CHOICES["color_theme"]))
        self._option(t1, 2, "Editor color scheme", "editor_color_scheme", list(EDITOR_SCHEMES))
        self._option(t1, 3, "UI scaling", "ui_scale_percent", [f"{v}%" for v in CHOICES["ui_scale_percent"]],
                     to_cfg=lambda s: int(s.rstrip("%")), to_ui=lambda v: f"{v}%")
        self._option(t1, 4, "Editor font family", "editor_font_family", list(FONT_FAMILIES))
        self._slider(t1, 5, "Editor font size", "editor_font_size", 10, 32, 22, "{:.0f} pt", int)
        self._slider(t1, 6, "Console font size", "console_font_size", 10, 28, 18, "{:.0f} pt", int)
        self._option(t1, 7, "Default radix", "default_radix", list(RADIXES))
        self._label(t1, 8, "UI & text size preset")
        self.preset_var = tk.StringVar(value=self._preset_name())
        ctk.CTkOptionMenu(t1, values=list(TEXT_SIZE_PRESETS) + ["Custom"], variable=self.preset_var, width=260,
                          command=self._apply_preset, **option_style()).grid(row=8, column=1, sticky="w", pady=5)
        self._slider(t1, 9, "UI font size (menus, tabs, tables, sidebar)", "ui_font_size", 10, 24, 14, "{:.0f} pt", int)

        self._option(t2, 0, "Editor layout", "editor_split_layout", list(LAYOUT_LABELS.values()),
                     to_cfg=lambda s: next(k for k, v in LAYOUT_LABELS.items() if v == s), to_ui=lambda v: LAYOUT_LABELS[v])
        self._option(t2, 1, "Tab size", "tab_size", ["2", "4", "8"], to_cfg=int, to_ui=str)
        for r, (label, key) in enumerate((("Insert spaces for Tab", "insert_spaces_for_tabs"), ("Word wrap", "word_wrap"),
                                          ("Highlight current line", "highlight_current_line"), ("Auto-indent", "auto_indent"),
                                          ("Auto-close brackets & begin/end", "auto_close_brackets_and_blocks"),
                                          ("Auto-save before Run (F5)", "auto_save_before_run"),
                                          ("Auto-save on focus loss", "auto_save_on_focus_loss")), start=2):
            self._switch(t2, r, label, key)
        self._option(t2, 9, "On startup", "startup_mode", list(STARTUP_LABELS.values()),
                     to_cfg=lambda s: next(k for k, v in STARTUP_LABELS.items() if v == s), to_ui=lambda v: STARTUP_LABELS[v])
        self._switch(t2, 10, "Check GitHub for updates (on startup and every 30 min)", "check_for_updates")
        ghost_button(t2, "🔔 Check for Updates Now", app.check_updates_now).grid(row=11, column=1, sticky="w", pady=(6, 4))
        self._switch(t2, 12, "Enable Live Autocomplete (IntelliSense) as you type - Ctrl+Space always works", "live_autocomplete")

        for r, (label, key, folder) in enumerate((("iverilog.exe", "iverilog_path", False), ("vvp.exe", "vvp_path", False),
                                                  ("gtkwave.exe", "gtkwave_path", False), ("Lecturer library (-y)", "lib_dir", True),
                                                  ("notepad++.exe", "notepad_pp_path", False))):
            self._path(t3, r, label, key, folder)
        ghost_button(t3, "🔍 Auto-Detect Paths", self._autodetect).grid(row=5, column=1, sticky="w", pady=(6, 10))
        self._option(t3, 6, "Verilog generation flag", "std_flag", list(CHOICES["std_flag"]))
        self._switch(t3, 7, "Include workspace folder as -y library", "include_workdir_as_ylib")
        self._switch(t3, 8, "Enable -Wall & -Winfloop warnings", "enable_wall_warnings")
        self._switch(t3, 9, "Non-interactive vvp -n ($stop acts as $finish)", "vvp_non_interactive_flag")
        self._slider(t3, 10, "Simulation timeout", "sim_timeout_sec", 1.0, 30.0, 58, "{:.1f} s", float)

        self._switch(t4, 0, "Enable static course linter (implicit wires, port mismatches)", "enable_course_linter")
        self._switch(t4, 1, "Strict gate-level course mode (flags assign/always/+/-/?: in .v designs)", "strict_gate_level_mode")
        self._switch(t4, 2, "Live Notepad++ sync (watch files on disk)", "live_sync_enabled")
        self._switch(t4, 3, "Auto-run when an external save is detected", "auto_run_on_external_save")
        self._slider(t4, 4, "Polling interval", "external_poll_interval_ms", 500, 3000, 25, "{:.0f} ms", int)
        self._switch(t4, 5, "Live compile check on save (background iverilog -tnull, marks errors in the gutter)",
                     "live_check_on_save")
        ctk.CTkLabel(t4, text="Tip: open the files in Notepad++ (📝), edit there, press Ctrl+S -\n"
                              "VeriFlow reloads the code and re-runs the simulation automatically.",
                     justify="left", text_color=VS["muted"]).grid(row=6, column=0, columnspan=3, sticky="w", pady=12)

        self._switch(t5, 0, "Auto-resolve package modules (-y per package folder, -l for multi-module / renamed files)",
                     "auto_resolve_packages_with_l_flag")
        ctk.CTkLabel(t5, text=f"Global package vault:\n{app.pkg.vault}", justify="left", anchor="w",
                     text_color=VS["muted"]).grid(row=1, column=0, columnspan=3, sticky="w", padx=6, pady=(8, 4))
        pk = ctk.CTkFrame(t5, fg_color="transparent")
        pk.grid(row=2, column=0, columnspan=3, sticky="w", padx=6, pady=6)
        ghost_button(pk, "📦 Open Package Manager", app.open_package_manager).pack(side="left", padx=(0, 6))
        ghost_button(pk, "📂 Open Vault Folder", app.open_vault_folder).pack(side="left")
        ctk.CTkLabel(t5, text="Load lecturer modules once (.v files, a folder or a Moodle .zip) and every new .v file you\n"
                              "create anywhere on this PC can instantiate them - no copying, no per-folder setup.",
                     justify="left", text_color=VS["muted"]).grid(row=3, column=0, columnspan=3, sticky="w", padx=6, pady=8)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
        ctk.CTkLabel(bottom, text=f"Settings file: {self.cfg.path}", text_color=VS["muted"], font=font(11)).pack(side="left")
        ctk.CTkButton(bottom, text="Close", width=90, height=26, corner_radius=3, fg_color=VS["accent"],
                      command=self.destroy).pack(side="right")
        ghost_button(bottom, "Reset to Defaults", self._reset, width=130).pack(side="right", padx=8)
        self.after(120, self._raise)

    def _raise(self) -> None:
        self.lift()
        self.focus_force()

    def _label(self, tab, row: int, text: str) -> None:
        ctk.CTkLabel(tab, text=text, anchor="w", text_color=VS["text"]).grid(row=row, column=0, sticky="w", padx=(6, 14), pady=5)

    def _option(self, tab, row, label, key, values, to_cfg=lambda s: s, to_ui=lambda v: v) -> None:
        self._label(tab, row, label)
        var = tk.StringVar(value=to_ui(self.cfg[key]))
        self.vars[key] = var
        var._to_ui = to_ui  # type: ignore[attr-defined]
        ctk.CTkOptionMenu(tab, values=values, variable=var, width=260, command=lambda s: self.cfg.update(**{key: to_cfg(s)}),
                          **option_style()).grid(row=row, column=1, sticky="w", pady=5)

    def _switch(self, tab, row, label, key) -> None:
        var = tk.BooleanVar(value=bool(self.cfg[key]))
        self.vars[key] = var
        ctk.CTkSwitch(tab, text=label, variable=var, switch_width=34, switch_height=16, progress_color=VS["accent"],
                      text_color=VS["text"], command=lambda: self.cfg.update(**{key: var.get()})).grid(
            row=row, column=0, columnspan=3, sticky="w", padx=6, pady=5)

    def _slider(self, tab, row, label, key, lo, hi, steps, fmt, cast) -> None:
        self._label(tab, row, label)
        var = tk.DoubleVar(value=float(self.cfg[key]))
        self.vars[key] = var
        val = ctk.CTkLabel(tab, text=fmt.format(self.cfg[key]), width=70, text_color=VS["text"])
        val.grid(row=row, column=2, padx=6)

        def moved(v):
            val.configure(text=fmt.format(v))
            self.cfg.update(**{key: cast(round(v, 1))})
        ctk.CTkSlider(tab, from_=lo, to=hi, number_of_steps=steps, variable=var, command=moved, height=14,
                      button_color=VS["accent"], progress_color=VS["accent"]).grid(row=row, column=1, sticky="ew", pady=5)
        var._fmt_label = (val, fmt)  # type: ignore[attr-defined]

    def _path(self, tab, row, label, key, folder) -> None:
        self._label(tab, row, label)
        var = tk.StringVar(value=self.cfg[key])
        self.vars[key] = var
        ent = ctk.CTkEntry(tab, textvariable=var, height=26, **entry_style())
        ent.grid(row=row, column=1, sticky="ew", pady=4)
        commit = lambda *_: (self.cfg.update(**{key: var.get().strip().strip('"')}), self._refresh_status())
        ent.bind("<Return>", commit)
        ent.bind("<FocusOut>", commit)
        cell = ctk.CTkFrame(tab, fg_color="transparent")
        cell.grid(row=row, column=2, padx=4)

        def browse():
            cur = Path(var.get()) if var.get() else Path("C:/")
            p = (filedialog.askdirectory(parent=self, initialdir=str(cur if cur.is_dir() else cur.parent)) if folder else
                 filedialog.askopenfilename(parent=self, initialdir=str(cur.parent), filetypes=[("Programs", "*.exe"), ("All", "*.*")]))
            if p:
                var.set(str(Path(p)))
                commit()
        ghost_button(cell, "Browse…", browse, width=72).pack(side="left")
        st = ctk.CTkLabel(cell, text="", width=24)
        st.pack(side="left", padx=4)
        self.path_status[key] = st
        self._refresh_status()

    def _refresh_status(self) -> None:
        for key, lab in self.path_status.items():
            p = Path(self.cfg[key])
            ok = p.is_dir() if key == "lib_dir" else p.is_file()
            lab.configure(text="✓" if ok else "✗", text_color=ACCENT["ok"] if ok else ACCENT["err"])

    def _autodetect(self) -> None:
        found = {k: v for k, v in detect_toolchains().items() if v}
        self.cfg.update(**found)
        self.sync_from_config()
        messagebox.showinfo("Auto-Detect", "Found:\n" + ("\n".join(f"  {k}: {v}" for k, v in found.items()) or "  nothing"), parent=self)

    def _reset(self) -> None:
        if messagebox.askyesno("Reset settings", "Reset every setting (except workspaces) to its default?", parent=self):
            self.cfg.reset()
            self.sync_from_config()

    def _preset_name(self) -> str:
        cur = (self.cfg["ui_font_size"], self.cfg["editor_font_size"], self.cfg["console_font_size"])
        return next((n for n, v in TEXT_SIZE_PRESETS.items() if v == cur), "Custom")

    def _apply_preset(self, name: str) -> None:
        if name in TEXT_SIZE_PRESETS:
            ui, ed, con = TEXT_SIZE_PRESETS[name]
            self.cfg.update(ui_font_size=ui, editor_font_size=ed, console_font_size=con)

    def sync_from_config(self) -> None:
        if hasattr(self, "preset_var"):
            self.preset_var.set(self._preset_name())
        for key, var in self.vars.items():
            v = self.cfg[key]
            if isinstance(var, tk.BooleanVar):
                var.set(bool(v))
            elif isinstance(var, tk.DoubleVar):
                var.set(float(v))
                lab, fmt = var._fmt_label  # type: ignore[attr-defined]
                lab.configure(text=fmt.format(v))
            else:
                var.set(getattr(var, "_to_ui", lambda x: x)(v))
        self._refresh_status()


# =========================================================================== package manager dialog
class PackageManagerDialog(ctk.CTkToplevel):
    """All registered packages: enable/disable, import, open folder, remove."""

    def __init__(self, app: "VeriFlowApp"):
        super().__init__(app)
        self.app, self.pkg = app, app.pkg
        self.title(f"{APP_NAME} - Packages & Global Module Library")
        self.geometry("900x580")
        self.minsize(760, 440)
        self.transient(app)
        self.configure(fg_color=VS["editor"])
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(self, text="📦  Packages & Global Module Library", anchor="w", text_color=VS["text"],
                     font=font(16, "bold")).grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 2))
        ctk.CTkLabel(self, text="Modules in enabled packages resolve from ANY folder on this PC: VeriFlow passes -y for every "
                                "enabled package folder and -l for files whose name differs from the module or that hold several "
                                "modules.", anchor="w", justify="left", wraplength=840, text_color=VS["muted"], font=font(12)).grid(
            row=1, column=0, sticky="ew", padx=16)
        acts = ctk.CTkFrame(self, fg_color="transparent")
        acts.grid(row=2, column=0, sticky="ew", padx=14, pady=10)
        for text, cmd in (("+ Load .v Files", app.import_v_files), ("+ Load Folder", app.import_folder),
                          ("+ Load .zip", app.import_zip), ("📂 Open Vault Folder", app.open_vault_folder)):
            ghost_button(acts, text, cmd).pack(side="left", padx=(0, 6))
        self.auto_var = tk.BooleanVar(value=bool(app.cfg["auto_resolve_packages_with_l_flag"]))
        ctk.CTkSwitch(acts, text="Auto-resolve with -l", variable=self.auto_var, switch_width=30, switch_height=15,
                      progress_color=VS["accent"], text_color=VS["text"],
                      command=lambda: app.cfg.update(auto_resolve_packages_with_l_flag=self.auto_var.get())).pack(side="right")
        self.list = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color=VS["sidebar"], scrollbar_button_color=VS["scroll_thumb"],
                                           scrollbar_button_hover_color=VS["scroll_hover"])
        self.list.grid(row=3, column=0, sticky="nsew", padx=14)
        self.list.grid_columnconfigure(1, weight=1)
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=4, column=0, sticky="ew", padx=14, pady=10)
        self.vault_lbl = ctk.CTkLabel(bottom, text="", text_color=VS["muted"], font=font(11))
        self.vault_lbl.pack(side="left")
        ctk.CTkButton(bottom, text="Close", width=90, height=26, corner_radius=3, fg_color=VS["accent"],
                      command=self.destroy).pack(side="right")
        self.refresh()
        self.after(120, lambda: (self.lift(), self.focus_force()))

    def refresh(self) -> None:
        for w in self.list.winfo_children():
            w.destroy()
        self.auto_var.set(bool(self.app.cfg["auto_resolve_packages_with_l_flag"]))
        self.vault_lbl.configure(text=f"Vault: {self.pkg.vault}")
        for c, h in enumerate(("On", "Package", "Type", "Modules", "")):
            ctk.CTkLabel(self.list, text=h.upper(), anchor="w", text_color=VS["muted"], font=font(10, "bold")).grid(
                row=0, column=c, sticky="w", padx=8, pady=(4, 2))
        kinds = {"builtin": "Course library", "vault": "Vault copy", "linked": "Linked folder"}
        for r, (p, mods) in enumerate(self.pkg.modules_by_package(), start=1):
            var = tk.BooleanVar(value=p["enabled"])
            ctk.CTkCheckBox(self.list, text="", variable=var, width=20, checkbox_width=15, checkbox_height=15, corner_radius=2,
                            border_width=1, command=lambda n=p["name"], v=var: self.app.set_package_enabled(n, v.get())).grid(
                row=r, column=0, padx=8, pady=4)
            cell = ctk.CTkFrame(self.list, fg_color="transparent")
            cell.grid(row=r, column=1, sticky="ew", pady=4)
            ctk.CTkLabel(cell, text=p["name"], anchor="w", text_color=VS["text"], font=font(13, "bold")).pack(anchor="w")
            ctk.CTkLabel(cell, text=p["path"] + ("" if p["exists"] else "   (folder not found)"), anchor="w",
                         text_color=VS["muted"] if p["exists"] else ACCENT["err"], font=font(10)).pack(anchor="w")
            ctk.CTkLabel(self.list, text=kinds[p["kind"]], text_color=VS["text"], font=font(12)).grid(row=r, column=2, sticky="w", padx=8)
            ctk.CTkLabel(self.list, text=str(len(mods)), text_color=VS["text"], font=font(12)).grid(row=r, column=3, sticky="w", padx=8)
            acts = ctk.CTkFrame(self.list, fg_color="transparent")
            acts.grid(row=r, column=4, padx=6)
            icon_button(acts, "📂", lambda q=p["path"]: self.app.open_folder(q), width=30).pack(side="left")
            rm = icon_button(acts, "🗑", lambda q=p: self._remove(q), width=30)
            rm.pack(side="left")
            if p["kind"] == "builtin":
                rm.configure(state="disabled")

    def _remove(self, p: dict) -> None:
        if p["kind"] == "vault":
            msg = (f"Delete package '{p['name']}'?\n\nIts copies in the vault are permanently deleted:\n{p['path']}\n\n"
                   f"The original files you imported from are not touched.")
        else:
            msg = f"Stop using the linked folder '{p['name']}'?\n\n{p['path']}\n\nThe folder and its files stay on disk."
        if messagebox.askyesno("Remove package", msg, parent=self):
            res = self.pkg.remove_package(p["name"])
            self.app.log(f"📦 {res['message']}", "ok" if res["ok"] else "warn")


# =========================================================================== self-checking testbench dialog
class SelfCheckDialog(ctk.CTkToplevel):
    """Ask for the expected expression of each output; generates PASS/FAIL checks after every vector."""

    def __init__(self, app: "VeriFlowApp", info: dict):
        super().__init__(app)
        self.app, self.info = app, info
        self.title(f"Self-Checking Testbench - {info['module_name']}")
        self.geometry("720x460")
        self.transient(app)
        self.configure(fg_color=VS["editor"])
        self.grid_columnconfigure(1, weight=1)
        ins = ", ".join(p["name"] + (p["range_text"] or "") for p in info["ports"] if p["direction"] == "input")
        ctk.CTkLabel(self, text="Expected value of each output (Verilog expression over the inputs)", anchor="w",
                     font=font(14, "bold"), text_color=VS["text"]).grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=(14, 2))
        ctk.CTkLabel(self, text=f"Inputs: {ins}\nExamples:  a ^ b ^ cin      (a & b) | (cin & (a ^ b))      a + b      s ? d1 : d0\n"
                                "Leave an output empty to skip its check.", anchor="w", justify="left",
                     text_color=VS["muted"], font=font(12)).grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 10))
        self.entries: dict[str, ctk.CTkEntry] = {}
        r = 2
        for p in info["ports"]:
            if p["direction"] == "input":
                continue
            ctk.CTkLabel(self, text=f"{p['name']}{p['range_text']} =", anchor="e", text_color=VS["text"],
                         font=ui_font(1, family="Consolas")).grid(row=r, column=0, sticky="e", padx=(16, 8), pady=4)
            e = ctk.CTkEntry(self, height=30, font=ui_font(1, family="Consolas"), **entry_style())
            e.grid(row=r, column=1, sticky="ew", padx=(0, 16), pady=4)
            self.entries[p["name"]] = e
            r += 1
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=r, column=0, columnspan=2, sticky="e", padx=16, pady=14)
        ghost_button(btns, "Cancel", self.destroy, width=90).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="🧪 Generate", width=120, height=28, corner_radius=3, fg_color=RUN_GREEN,
                      hover_color=RUN_GREEN_HOVER, command=self._ok).pack(side="left")
        if self.entries:
            next(iter(self.entries.values())).focus_set()
        self.bind("<Return>", lambda e: self._ok())
        self.after(120, self.lift)

    def _ok(self) -> None:
        checks = {k: e.get().strip() for k, e in self.entries.items() if e.get().strip()}
        if not checks:
            messagebox.showinfo("Self-checking testbench", "Enter at least one expected expression.", parent=self)
            return
        self.destroy()
        self.app.generate_tb(checks=checks)


# =========================================================================== main window
class VeriFlowApp(ctk.CTk):
    def __init__(self):
        self.cfg = ConfigManager()
        ctk.set_appearance_mode(self.cfg["appearance_mode"])
        ctk.set_default_color_theme(self.cfg["color_theme"])
        ctk.set_widget_scaling(self.cfg["ui_scale_percent"] / 100)
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry(self.cfg["window_geometry"])
        if self.cfg["window_geometry"] == DEFAULT_CONFIG["window_geometry"] and IS_WINDOWS:
            self.after(0, lambda: self.state("zoomed"))      # first run: fill the screen
        self.minsize(1180, 680)
        self.configure(fg_color=VS["editor"])
        self.events: queue.Queue = queue.Queue()
        self.runner = VerilogRunner(self.cfg, self.events)
        self.pkg = PackageManager(self.cfg)
        self.runner.package_manager = self.pkg
        self._pkg_groups: list = []
        self._pkg_collapsed: set[str] = set()
        self._pkg_stats = (0, 0)
        self._pkg_dialog: PackageManagerDialog | None = None
        self._known_cache: dict[str, dict] = {}
        self._hier_items: dict[str, tuple[str | None, int, dict | None]] = {}
        self._hier_job = None
        self.live_diags: list[dict] = []
        self._links: dict[str, tuple[str, int, int]] = {}
        self._live_job = None
        self._toast_job = None
        self._toast: ctk.CTkFrame | None = None
        self._upd_q: queue.Queue = queue.Queue()
        self._update_info = None
        self._update_dismissed = ""
        self._update_notice: UpdateNotice | None = None
        self._update_busy = False
        self._update_manual = False
        self.work_dir: Path | None = None
        self.module: str | None = None
        self.modules: dict[str, dict] = {}
        self.extra_vars: dict[str, tk.BooleanVar] = {}
        self.ws_modules: dict[str, dict] = {}
        self._parse_cache: dict = {}
        self.lint_diags: list[dict] = []
        self.run_diags: list[dict] = []
        self.diag_rows: dict[str, dict] = {}
        self.last_vcd: str | None = None
        self.known_mtime: dict[str, float] = {}
        self._ws_signature = None
        self._sync_job = self._lint_job = None
        self._last_focus_check = 0.0
        self._settings: SettingsDialog | None = None
        self._lib_selected: dict | None = None
        self._port_widths: dict[str, int] = {}
        self._recent_map: dict[str, str] = {}
        self._tool_text = ""
        self._probe_result = ""
        self._status_state = "ready"
        self.active_editor: VerilogCodeEditor | None = None
        self.tab_shown = "design"
        self.cmd_mode = "Actual"
        self.sidebar_visible = bool(self.cfg["sidebar_visible"])
        self.style = ttk.Style(self)
        self.sc = ui_scale(self)
        FontBook.set_base(self.cfg["ui_font_size"])           # every ui_font() created from here on starts at this size
        self.option_add("*Menu.font", ("Segoe UI", -ui_px(self, -1)))     # no tiny native menus anywhere

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._build_titlebar()
        self._build_banner()
        self._build_body()
        self._build_statusbar()
        self.cfg.subscribe(self._on_config_changed)
        self._bind_shortcuts()
        self._apply_theme()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(60, self._poll_events)
        self.after(120, self._startup)

    # ================================================================== Zone 1: title / action bar
    def _tb(self, widget, full: str, short: str, tip: str):
        """Register a toolbar control that collapses to its icon (with a hover tooltip) when the bar is too narrow."""
        self._tb_items.append((widget, full, short, tip))
        widget.bind("<Enter>", lambda e, t=tip: self._tb_tip.show(t, e.x_root, e.y_root) if self._tb_compact else None, add="+")
        widget.bind("<Leave>", lambda e: self._tb_tip.hide(), add="+")
        return widget

    def _set_toolbar_compact(self, compact: bool) -> None:
        self._tb_compact = compact
        self._tb_tip.hide()
        for w, full, short, _tip in self._tb_items:
            w.configure(text=short if compact else full)
        self.recent_menu.configure(width=86 if compact else 96)
        self.snippet_menu.configure(width=100)

    def _schedule_fit_toolbar(self, reset: bool = False) -> None:
        if reset:                                   # fonts changed: re-measure from the full labels
            self._tb_full_need = 0
            if self._tb_compact:
                self._set_toolbar_compact(False)
        if not self._tb_fit_pending:
            self._tb_fit_pending = True
            self.after_idle(self._fit_toolbar)

    def _fit_toolbar(self) -> None:
        self._tb_fit_pending = False
        avail = self.titlebar.winfo_width()
        if avail <= 1:
            return
        need = sum(f.winfo_reqwidth() for f in self._tb_frames) + int(36 * self.sc)
        if not self._tb_compact and need > avail:
            self._tb_full_need = need
            self._set_toolbar_compact(True)
        elif self._tb_compact and self._tb_full_need and avail >= self._tb_full_need:
            self._set_toolbar_compact(False)

    def _build_titlebar(self) -> None:
        self._tb_items, self._tb_compact, self._tb_full_need, self._tb_fit_pending = [], False, 0, False
        self._tb_tip = _Tooltip(self)
        bar = ctk.CTkFrame(self, height=int(40 * FontBook.base / 13), corner_radius=0, fg_color=VS["toolbar"])
        self.titlebar = bar
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_rowconfigure(0, weight=1)
        bar.grid_columnconfigure(3, weight=1)
        hline(self).grid(row=1, column=0, sticky="ew")

        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.grid(row=0, column=0, padx=(8, 0))
        self._tb(icon_button(left, "🏠 Welcome", self.show_welcome, width=0, height=26, font=font(12)), "🏠 Welcome", "🏠",
                 "Welcome / Get Started").pack(side="left", padx=(0, 4))
        self._tb(ghost_button(left, "📂 Open…", self.choose_folder, height=26), "📂 Open…", "📂",
                 "Open a workspace folder").pack(side="left", padx=(0, 4))
        self.recent_menu = ctk.CTkOptionMenu(left, values=[RECENT_LABEL], width=96, command=self._open_recent, **option_style())
        self.recent_menu.set(RECENT_LABEL)
        self.recent_menu.pack(side="left", padx=(0, 10))
        self._tb(ctk.CTkLabel(left, text="Module:", text_color=VS["muted"], font=font(12)), "Module:", "",
                 "Active module").pack(side="left", padx=(0, 4))
        self.module_menu = ctk.CTkOptionMenu(left, values=["(no modules)"], width=124, command=self._module_selected, **option_style())
        self.module_menu.pack(side="left", padx=(0, 4))
        self._tb(ghost_button(left, "+ New .v", self.new_module, height=26), "+ New .v", "+",
                 "New Verilog module").pack(side="left")
        vline(bar).grid(row=0, column=1, sticky="ns", padx=10, pady=9)

        group = ctk.CTkFrame(bar, corner_radius=3, fg_color=VS["group"], border_width=1, border_color=VS["group_border"])
        group.grid(row=0, column=2)
        self.run_btn = ctk.CTkButton(group, text="▶  Run (F5)", width=96, height=26, corner_radius=3, fg_color=RUN_GREEN,
                                     hover_color=RUN_GREEN_HOVER, text_color=WHITE, text_color_disabled="#E6FFEC",
                                     font=font(12, "bold"), command=self.run_pipeline)
        self.run_btn.pack(side="left", padx=(3, 2), pady=3)
        self.stop_btn = ctk.CTkButton(group, text="■ Stop", width=62, height=26, corner_radius=3, fg_color=STOP_IDLE,
                                      hover_color=STOP_RED_HOVER, text_color=WHITE, text_color_disabled=("#8A8A8A", "#8A8A8A"),
                                      font=font(12), state="disabled", command=self.stop_run)
        self.stop_btn.pack(side="left", padx=2, pady=3)
        for text, cmd, tip in (("🔍 Lint (F7)", lambda: self.run_lint(show=True), "Lint (F7)"),
                               ("🧪 Gen _tb.v", self.generate_tb, "Generate a _tb.v testbench"),
                               ("💾 Save All", self.save_all, "Save all (Ctrl+S)")):
            vline(group).pack(side="left", fill="y", pady=6)
            self._tb(icon_button(group, text, cmd, width=0, height=26, font=font(12)), text, text.split()[0],
                     tip).pack(side="left", padx=2, pady=3)
        vline(group).pack(side="left", fill="y", pady=6)
        self.sync_switch = ctk.CTkSwitch(group, text="⚡ N++ Sync", switch_width=30, switch_height=15, progress_color=VS["accent"],
                                         text_color=VS["text"], font=font(12),
                                         command=lambda: self.cfg.update(live_sync_enabled=bool(self.sync_switch.get())))
        self._tb(self.sync_switch, "⚡ N++ Sync", "⚡", "Notepad++ live sync")
        self.sync_switch.pack(side="left", padx=(8, 6), pady=3)

        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.grid(row=0, column=4, padx=(0, 8))
        for text, cmd, tip in (("📦 Packages", self.open_package_manager, "Package & library manager"),
                               ("📝 N++", self.open_in_npp, "Open in Notepad++"),
                               ("🧹 Clean", self.clean, "Clean build outputs")):
            self._tb(icon_button(right, text, cmd, width=0, font=font(12)), text, text.split()[0], tip).pack(side="left", padx=1)
        self.snippet_menu = ctk.CTkOptionMenu(right, values=list(SNIPPETS), width=100, command=self._insert_snippet, **option_style())
        self.snippet_menu.set(SNIPPET_LABEL)
        self.snippet_menu.pack(side="left", padx=(4, 6))
        vline(right).pack(side="left", fill="y", pady=9, padx=4)
        icon_button(right, "A-", lambda: self.zoom(-1), width=28, font=font(12)).pack(side="left")
        self.font_lbl = ctk.CTkLabel(right, text="13pt", width=38, text_color=VS["text"], font=font(12))
        self.font_lbl.pack(side="left")
        icon_button(right, "A+", lambda: self.zoom(1), width=28, font=font(12)).pack(side="left")
        vline(right).pack(side="left", fill="y", pady=9, padx=4)
        self.theme_btn = icon_button(right, "☀", self.toggle_theme, width=32, font=font(15))
        self.theme_btn.pack(side="left", padx=1)
        icon_button(right, "⚙", self.open_settings, width=32, font=font(15)).pack(side="left", padx=1)
        self._tb_frames = (left, group, right)
        for w in (bar, left, group, right):          # bar resized, or a control's text/width changed
            w.bind("<Configure>", lambda e: self._schedule_fit_toolbar(), add="+")

    def _build_banner(self) -> None:
        self.banner = ctk.CTkFrame(self, corner_radius=0, height=30, fg_color=("#FFF4CE", "#3D3313"))
        self.banner_lbl = ctk.CTkLabel(self.banner, text="", text_color=("#7A5A00", "#E9C46A"), anchor="w", font=font(12, "bold"))
        self.banner_lbl.pack(side="left", padx=12, pady=3)
        ghost_button(self.banner, "Auto-Detect", self._banner_detect, width=100, height=22).pack(side="right", padx=6)
        ghost_button(self.banner, "⚙ Configure paths", self.open_settings, width=140, height=22).pack(side="right", padx=6)

    # ================================================================== Zones 2-4: activity bar, side bar, editors, panel
    def _build_body(self) -> None:
        sc = self.sc
        body = ctk.CTkFrame(self, corner_radius=0, fg_color=VS["editor"])
        body.grid(row=3, column=0, sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(2, weight=1)
        self.activity = ActivityBar(body, [("explorer", "📁", "Explorer  (Ctrl+B)"), ("library", "📚", "Library & Packages"),
                                           ("run", "▶", "Run & Compile"), ("npp", "📝", "Open in Notepad++")],
                                    [("welcome", "🏠", "Welcome / Get Started"), ("settings", "⚙", "Settings  (Ctrl+,)")],
                                    self._on_activity)
        self.activity.grid(row=0, column=0, sticky="ns")
        vline(body).grid(row=0, column=1, sticky="ns")
        self.hpane = tk.PanedWindow(body, orient="horizontal", sashwidth=max(2, int(2 * sc)), bd=0, sashrelief="flat")
        self.hpane.grid(row=0, column=2, sticky="nsew")

        self.sidebar = ctk.CTkFrame(self.hpane, corner_radius=0, fg_color=VS["sidebar"])
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(0, weight=1)
        self.views = {"explorer": self._build_explorer(self.sidebar), "library": self._build_library(self.sidebar),
                      "run": self._build_run_view(self.sidebar)}
        self.vpane = tk.PanedWindow(self.hpane, orient="vertical", sashwidth=max(2, int(2 * sc)), bd=0, sashrelief="flat")
        if self.sidebar_visible:
            self.hpane.add(self.sidebar, minsize=int(200 * sc), width=int(250 * sc))
        self.hpane.add(self.vpane, minsize=int(500 * sc), stretch="always")

        self.ed_area = ctk.CTkFrame(self.vpane, corner_radius=0, fg_color=VS["editor"])
        self.ed_area.grid_rowconfigure(0, weight=1)
        common = dict(on_save=self.save_editor, on_modified=self._on_editor_modified, on_cursor=self._on_cursor,
                      on_zoom=self.zoom, on_focus=self._on_editor_focus)
        self.design_ed = VerilogCodeEditor(self.ed_area, self.cfg, role="DESIGN", **common)
        self.tb_ed = VerilogCodeEditor(self.ed_area, self.cfg, role="TESTBENCH", **common)
        self.ed_split = vline(self.ed_area)
        for ed in (self.design_ed, self.tb_ed):
            ed.on_app_ctrl = self._on_ctrl
        self.tb_ed.on_generate = self.generate_tb
        self.design_ed.add_menu_command("🧪 Generate Testbench (exhaustive)", lambda: self.generate_tb())
        self.design_ed.add_menu_command("🧪 Generate Skeleton Testbench (empty initial)", lambda: self.generate_tb(skeleton=True))
        self.design_ed.add_menu_command("🧪 Generate Self-Checking Testbench…", lambda: self.self_check_dialog())
        for ed in (self.design_ed, self.tb_ed):
            ed.completion_provider = lambda: list(self._known_cache.values())
        self.active_editor = self.design_ed
        self.welcome = WelcomeView(self.ed_area, self)        # overlays the editor group while shown
        self.vpane.add(self.ed_area, minsize=int(200 * sc), stretch="always")
        self.vpane.add(self._build_panel(self.vpane), minsize=int(150 * sc), height=int(300 * sc))
        self._layout_editors()
        self._show_view(self.cfg["sidebar_view"])

    def _side_header(self, parent, title: str, actions: list) -> ctk.CTkLabel:
        head = ctk.CTkFrame(parent, height=35, corner_radius=0, fg_color=VS["sidebar"])
        head.grid(row=0, column=0, sticky="ew")
        head.grid_propagate(False)
        head.grid_columnconfigure(0, weight=1)
        head.grid_rowconfigure(0, weight=1)
        lab = ctk.CTkLabel(head, text=title, anchor="w", text_color=VS["sidebar_header"], font=font(11, "bold"))
        lab.grid(row=0, column=0, sticky="ew", padx=(14, 4))
        for c, (icon, cmd) in enumerate(actions, start=1):
            icon_button(head, icon, cmd, width=24, height=22, font=font(14)).grid(row=0, column=c, padx=1)
        ctk.CTkFrame(head, width=6, fg_color="transparent").grid(row=0, column=len(actions) + 1)
        return lab

    def _scroll_list(self, parent, **kw) -> ctk.CTkScrollableFrame:
        f = ctk.CTkScrollableFrame(parent, corner_radius=0, fg_color=VS["sidebar"], scrollbar_button_color=VS["scroll_thumb"],
                                   scrollbar_button_hover_color=VS["scroll_hover"], **kw)
        f.grid_columnconfigure(0, weight=1)
        return f

    def _build_explorer(self, parent) -> ctk.CTkFrame:
        v = ctk.CTkFrame(parent, corner_radius=0, fg_color=VS["sidebar"])
        v.grid_columnconfigure(0, weight=1)
        self.explorer_title = self._side_header(v, "EXPLORER", [("+", self.new_module), ("↻", self._refresh_workspace),
                                                                ("📂", self.choose_folder), ("📤", self.export_submission),
                                                                ("✕", self.close_folder)])
        weights = {1: 3, 2: 1}

        def toggled(sec):
            r = 1 if sec is self.sec_modules else 2
            v.grid_rowconfigure(r, weight=weights[r] if sec.open else 0)
        self.sec_modules = SideSection(v, "MODULES", on_toggle=toggled)
        self.sec_modules.grid(row=1, column=0, sticky="nsew")
        self.sec_modules.body.grid_rowconfigure(0, weight=1)
        self.mod_list = self._scroll_list(self.sec_modules.body)
        self.mod_list.grid(row=0, column=0, sticky="nsew")
        self.sec_extra = SideSection(v, "EXTRA .V FILES", on_toggle=toggled)
        self.sec_extra.grid(row=2, column=0, sticky="nsew")
        self.sec_extra.body.grid_rowconfigure(0, weight=1)
        self.extra_list = self._scroll_list(self.sec_extra.body, height=110)
        self.extra_list.grid(row=0, column=0, sticky="nsew")
        for r, w in weights.items():
            v.grid_rowconfigure(r, weight=w)
        self.ws_label = ctk.CTkLabel(v, text="No folder open", anchor="w", justify="left", wraplength=230,
                                     text_color=VS["muted"], font=font(10))
        self.ws_label.grid(row=3, column=0, sticky="ew", padx=14, pady=(2, 2))
        ghost_button(v, "📦 Export HW .zip", self.export_submission, height=26).grid(row=4, column=0, sticky="ew", padx=10, pady=(2, 8))
        return v

    def _build_library(self, parent) -> ctk.CTkFrame:
        v = ctk.CTkFrame(parent, corner_radius=0, fg_color=VS["sidebar"])
        v.grid_columnconfigure(0, weight=1)
        v.grid_rowconfigure(4, weight=3)
        v.grid_rowconfigure(6, weight=2)
        self.library_title = self._side_header(v, "LIBRARY & PACKAGES", [("📦", self.open_package_manager),
                                                                          ("↻", self._load_library)])
        acts = ctk.CTkFrame(v, fg_color="transparent")
        acts.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 4))
        acts.grid_columnconfigure((0, 1, 2), weight=1)
        for c, (text, cmd) in enumerate((("+ .v Files", self.import_v_files), ("+ Folder", self.import_folder),
                                         ("+ .zip", self.import_zip))):
            ghost_button(acts, text, cmd, height=24).grid(row=0, column=c, sticky="ew", padx=(0 if c == 0 else 3, 0))
        self.lib_search = ctk.CTkEntry(v, placeholder_text="🔍 Search all loaded modules (e.g. Mux, Adder, DFF)…", height=26,
                                       **entry_style())
        self.lib_search.grid(row=2, column=0, sticky="ew", padx=10, pady=(2, 4))
        self.lib_search.bind("<KeyRelease>", lambda e: self._render_library())
        self.lib_label = ctk.CTkLabel(v, text="", anchor="w", justify="left", wraplength=230, text_color=VS["muted"], font=font(10))
        self.lib_label.grid(row=3, column=0, sticky="ew", padx=14)
        self.lib_list = self._scroll_list(v)
        self.lib_list.grid(row=4, column=0, sticky="nsew")
        hline(v).grid(row=5, column=0, sticky="ew")
        self.lib_detail = ctk.CTkTextbox(v, height=150, font=ui_font(-1, family="Consolas"), wrap="none", corner_radius=0, border_width=0,
                                         fg_color=VS["editor"], text_color=VS["text"])
        self.lib_detail.grid(row=6, column=0, sticky="nsew")
        btns = ctk.CTkFrame(v, fg_color="transparent")
        btns.grid(row=7, column=0, sticky="ew", padx=8, pady=6)
        btns.grid_columnconfigure((0, 1), weight=1)
        ghost_button(btns, "📋 Copy Instantiation", self._copy_inst, height=24).grid(row=0, column=0, sticky="ew", padx=(0, 3))
        ghost_button(btns, "⤵ Insert at Cursor", self._insert_inst, height=24).grid(row=0, column=1, sticky="ew", padx=(3, 0))
        return v

    def _build_run_view(self, parent) -> ctk.CTkFrame:
        v = ctk.CTkFrame(parent, corner_radius=0, fg_color=VS["sidebar"])
        v.grid_columnconfigure(0, weight=1)
        self._side_header(v, "RUN & COMPILE", [])
        ctk.CTkButton(v, text="▶  Run (F5)", height=28, corner_radius=3, fg_color=RUN_GREEN, hover_color=RUN_GREEN_HOVER,
                      text_color=WHITE, font=font(12, "bold"), command=self.run_pipeline).grid(
            row=1, column=0, sticky="ew", padx=12, pady=(4, 10))
        self.run_vars: dict[str, tk.Variable] = {}
        ctk.CTkLabel(v, text="LANGUAGE STANDARD", anchor="w", text_color=VS["sidebar_header"], font=font(11, "bold")).grid(
            row=2, column=0, sticky="ew", padx=14)
        std = tk.StringVar(value=self.cfg["std_flag"])
        self.run_vars["std_flag"] = std
        ctk.CTkOptionMenu(v, values=list(CHOICES["std_flag"]), variable=std, command=lambda s: self.cfg.update(std_flag=s),
                          **option_style()).grid(row=3, column=0, sticky="ew", padx=12, pady=(2, 10))
        ctk.CTkLabel(v, text="FLAGS", anchor="w", text_color=VS["sidebar_header"], font=font(11, "bold")).grid(
            row=4, column=0, sticky="ew", padx=14)
        row = 5
        for key, label in (("include_workdir_as_ylib", "-y <workspace>  (find your own modules)"),
                           ("enable_wall_warnings", "-Wall -Winfloop warnings"),
                           ("vvp_non_interactive_flag", "vvp -n  ($stop never hangs)"),
                           ("enable_course_linter", "Course linter"),
                           ("strict_gate_level_mode", "Strict gate-level mode"),
                           ("auto_save_before_run", "Auto-save before run"),
                           ("live_check_on_save", "Live -tnull check on save")):
            var = tk.BooleanVar(value=bool(self.cfg[key]))
            self.run_vars[key] = var
            ctk.CTkCheckBox(v, text=label, variable=var, checkbox_width=15, checkbox_height=15, corner_radius=2, border_width=1,
                            text_color=VS["text"], font=font(12), command=lambda k=key, vv=var: self.cfg.update(**{k: vv.get()})).grid(
                row=row, column=0, sticky="w", padx=14, pady=3)
            row += 1
        self.timeout_lbl = ctk.CTkLabel(v, text="", anchor="w", text_color=VS["muted"], font=font(11))
        self.timeout_lbl.grid(row=row, column=0, sticky="ew", padx=14, pady=(6, 8))
        ctk.CTkLabel(v, text="COMMAND LINE", anchor="w", text_color=VS["sidebar_header"], font=font(11, "bold")).grid(
            row=row + 1, column=0, sticky="ew", padx=14)
        self.run_cmd_box = ctk.CTkTextbox(v, height=130, wrap="char", corner_radius=0, border_width=1, border_color=VS["border"],
                                          fg_color=VS["editor"], text_color=VS["text"], font=ui_font(-1, family="Consolas"))
        self.run_cmd_box.grid(row=row + 2, column=0, sticky="nsew", padx=12, pady=(2, 8))
        v.grid_rowconfigure(row + 2, weight=1)
        btns = ctk.CTkFrame(v, fg_color="transparent")
        btns.grid(row=row + 3, column=0, sticky="ew", padx=10, pady=(0, 10))
        btns.grid_columnconfigure((0, 1, 2), weight=1)
        ghost_button(btns, "📋 Copy", self._copy_cmd, height=24).grid(row=0, column=0, sticky="ew", padx=2)
        ghost_button(btns, "🧹 Clean", self.clean, height=24).grid(row=0, column=1, sticky="ew", padx=2)
        ghost_button(btns, "📈 GTKWave", self.open_gtkwave, height=24).grid(row=0, column=2, sticky="ew", padx=2)
        return v

    def _build_panel(self, parent) -> PanelTabs:
        self.panel = PanelTabs(parent, command=self._on_btab)
        t_console = self.panel.add("console", "Console Output")
        t_prob = self.panel.add("problems", "Problems & Linter")
        t_table = self.panel.add("table", "Truth Table")
        t_wave = self.panel.add("wave", "Waveform")
        t_hier = self.panel.add("hier", "Hierarchy & Gates")
        r = self.panel.right
        r.grid_columnconfigure(1, weight=1)
        r.grid_rowconfigure(0, weight=1)
        ctk.CTkLabel(r, text="CMD:", text_color=VS["muted"], font=font(11, "bold")).grid(row=0, column=0, padx=(0, 6))
        self.cmd_var = tk.StringVar(value="Open a workspace to see the exact iverilog / vvp command line")
        self.cmd_entry = ctk.CTkEntry(r, textvariable=self.cmd_var, font=ui_font(-1, family="Consolas"), height=26, state="readonly", **entry_style())
        self.cmd_entry.grid(row=0, column=1, sticky="ew")
        self.cmd_seg = ctk.CTkSegmentedButton(r, values=["Actual", "Baseline"], command=self._cmd_mode, **{**seg_style(), "height": 22})
        self.cmd_seg.set("Actual")
        self.cmd_seg.grid(row=0, column=2, padx=6)
        ghost_button(r, "📋 Copy CMD", self._copy_cmd, width=96, height=22).grid(row=0, column=3)

        self.console = ctk.CTkTextbox(t_console, wrap="none", corner_radius=0, border_width=0,
                                      font=(self.cfg["editor_font_family"], self.cfg["console_font_size"]))
        self.console.grid(row=0, column=0, sticky="nsew", padx=(8, 0))
        self.console.configure(state="disabled")
        self.console.tag_bind("link", "<Enter>", lambda e: self.console._textbox.configure(cursor="hand2"))
        self.console.tag_bind("link", "<Leave>", lambda e: self.console._textbox.configure(cursor="xterm"))
        pf = ctk.CTkFrame(t_prob, fg_color="transparent", corner_radius=0)
        pf.grid(row=0, column=0, sticky="nsew")
        pf.grid_columnconfigure(0, weight=1)
        pf.grid_rowconfigure(0, weight=1)
        self.prob_tree = ttk.Treeview(pf, columns=("sev", "file", "line", "msg", "src"), show="headings", style="VF.Treeview")
        for cid, text, w, stretch in (("sev", "Severity", 100, False), ("file", "File", 170, False), ("line", "Line", 60, False),
                                      ("msg", "Message", 600, True), ("src", "Source", 80, False)):
            self.prob_tree.heading(cid, text=text, anchor="w")
            self.prob_tree.column(cid, width=int(w * self.sc), stretch=stretch, anchor="w")
        self.prob_tree.grid(row=0, column=0, sticky="nsew")
        psb = slim_scrollbar(pf, self.prob_tree.yview)
        psb.grid(row=0, column=1, sticky="ns")
        self.prob_tree.configure(yscrollcommand=psb.set)
        self.prob_tree.bind("<ButtonRelease-1>", self._on_problem_click)
        self.prob_tree.bind("<Return>", self._on_problem_click)
        self.truth = TruthTableGrid(t_table, self.cfg, on_radix=lambda rr: self.wave.set_radix(rr))
        self.truth.grid(row=0, column=0, sticky="nsew")
        self.wave = MiniWaveformViewer(t_wave, self.cfg, on_open_gtkwave=self.open_gtkwave)
        self.wave.grid(row=0, column=0, sticky="nsew")
        hf = ctk.CTkFrame(t_hier, fg_color="transparent", corner_radius=0)
        hf.grid(row=0, column=0, sticky="nsew")
        hf.grid_columnconfigure(0, weight=3)
        hf.grid_columnconfigure(2, weight=2, minsize=int(380 * self.sc))     # room for the pinout diagram
        hf.grid_rowconfigure(1, weight=1)
        hbar = ctk.CTkFrame(hf, fg_color="transparent")
        hbar.grid(row=0, column=0, columnspan=3, sticky="ew", padx=8, pady=6)
        ghost_button(hbar, "↻ Refresh", self._refresh_hierarchy, height=24).pack(side="left")
        self.hier_summary = ctk.CTkLabel(hbar, text="", anchor="w", justify="left", text_color=VS["text"], font=font(12))
        self.hier_summary.pack(side="left", padx=12)
        self.hier_tree = ttk.Treeview(hf, columns=("type", "where"), show="tree headings", style="VF.Treeview")
        self.hier_tree.heading("#0", text="Instance", anchor="w")
        self.hier_tree.heading("type", text="Module / gate", anchor="w")
        self.hier_tree.heading("where", text="Defined in", anchor="w")
        self.hier_tree.column("#0", width=int(200 * self.sc), anchor="w")
        self.hier_tree.column("type", width=int(150 * self.sc), anchor="w")
        self.hier_tree.column("where", width=int(230 * self.sc), anchor="w", stretch=True)
        self.hier_tree.grid(row=1, column=0, sticky="nsew", padx=(8, 0))
        hsb2 = slim_scrollbar(hf, self.hier_tree.yview)
        hsb2.grid(row=1, column=1, sticky="ns")
        self.hier_tree.configure(yscrollcommand=hsb2.set)
        self.hier_tree.bind("<ButtonRelease-1>", self._on_hier_click)
        self.pinout = PinoutDiagram(hf, self.cfg)
        self.pinout.grid(row=1, column=2, sticky="nsew", padx=8)
        self.panel.set_badge("problems", 0)
        return self.panel

    # ================================================================== Zone 5: status bar
    def _build_statusbar(self) -> None:
        # plain tk widgets: one solid colour band that recolours instantly (blue / orange / red)
        color = STATUS_COLORS["ready"]
        sb = tk.Frame(self, bg=color, height=int(26 * self.sc * FontBook.base / 13), bd=0, highlightthickness=0)
        sb.grid(row=4, column=0, sticky="ew")
        sb.grid_propagate(False)
        sb.grid_rowconfigure(0, weight=1)
        self.statusbar = sb
        self._st_labels: list[tk.Label] = []
        st_font = ("Segoe UI", -ui_px(self, -1))

        def item(col, text="", click=None, weight=0):
            lab = tk.Label(sb, text=text, bg=color, fg=WHITE, font=st_font, bd=0, padx=int(6 * self.sc),
                           anchor="w" if weight else "center", cursor="hand2" if click else "")
            lab.grid(row=0, column=col, sticky="nsew" if weight else "ns")
            if weight:
                sb.grid_columnconfigure(col, weight=weight)
            if click:
                lab.bind("<Button-1>", lambda e: click())
                lab.bind("<Enter>", lambda e, l=lab: l.configure(bg=self._status_hover()))
                lab.bind("<Leave>", lambda e, l=lab: l.configure(bg=STATUS_COLORS[self._status_state]))
            self._st_labels.append(lab)
            return lab
        self.st_state = item(0, "⚡ Ready")
        self.st_saved = item(1, "✔ Saved")
        self.st_time = item(2, "⏱ Pipeline: -")
        self.st_sync = item(3, "⇄ N++ Sync: OFF", click=lambda: self.cfg.update(live_sync_enabled=not self.cfg["live_sync_enabled"]))
        self.st_pkg = item(4, "📦 Packages: -", click=lambda: self._show_view("library", force=True))
        self.st_msg = item(5, "", weight=1)
        self.st_module = item(6, "Module: -")
        self.st_pos = item(7, "Ln 1, Col 1")
        self.st_spaces = item(8, "Spaces: 4", click=self.open_settings)
        self.st_font = item(9, "Font: 13pt", click=self.open_settings)
        item(10, "UTF-8")
        self.st_std = item(11, "SystemVerilog (-g2012)", click=lambda: self._show_view("run", force=True))
        self.st_tool = item(12, "", click=self.open_settings)
        self.st_update = item(13, "", click=self._reopen_update_notice)
        self.st_update.grid_remove()

    def _status_hover(self) -> str:
        """VS Code lightens a status-bar item on hover."""
        c = STATUS_COLORS[self._status_state].lstrip("#")
        r, g, b = (min(255, int(c[i:i + 2], 16) + 28) for i in (0, 2, 4))
        return f"#{r:02X}{g:02X}{b:02X}"

    def _set_status(self, state: str, text: str) -> None:
        self._status_state = state
        color = STATUS_COLORS[state]
        self.statusbar.configure(bg=color)
        for lab in self._st_labels:
            lab.configure(bg=color)
        self.st_state.configure(text=text)

    def _refresh_status_items(self) -> None:
        c = self.cfg
        self.st_sync.configure(text=f"⇄ N++ Sync: {'ON' if c['live_sync_enabled'] else 'OFF'}")
        self.st_module.configure(text=f"Module: {self.module or '-'}")
        self.st_spaces.configure(text=f"Spaces: {c['tab_size']}" if c["insert_spaces_for_tabs"] else f"Tab Size: {c['tab_size']}")
        self.st_font.configure(text=f"Font: {c['editor_font_size']}pt · UI {c['ui_font_size']}pt")
        std = c["std_flag"]
        self.st_std.configure(text=f"{'SystemVerilog' if 'sv' in std or '2012' in std else 'Verilog'} ({std})")
        self.st_tool.configure(text=self._tool_text)
        active, total = self._pkg_stats
        self.st_pkg.configure(text=f"📦 Packages: {active} active ({total} modules indexed)")

    # ================================================================== startup / theme
    def _startup(self) -> None:
        self._refresh_recent_menu()
        self._update_toolchain_ui()
        self._load_library()
        if self.cfg["live_sync_enabled"]:
            self.sync_switch.select()
        mode = self.cfg["startup_mode"]
        folder = Path(self.cfg["last_workspace_dir"]) if self.cfg["last_workspace_dir"] else None
        if self.work_dir is not None:
            pass                                    # a folder was passed on the command line
        elif mode == "reopen_last" and folder and folder.is_dir():
            self.open_workspace(folder)
        elif mode != "empty_window":
            self.show_welcome()                     # welcome_screen, or nothing to reopen
        self._restart_sync()
        if self.cfg["check_for_updates"]:
            self.after(1500, self._check_updates)
        self._sync_run_view()
        self._refresh_status_items()
        self.log(f"{APP_NAME} {APP_VERSION} ready.  F5 Run · F7 Lint · Ctrl+B side bar · Ctrl+F find · Ctrl+G go to line · "
                 f"Ctrl+/ comment · Ctrl+wheel zoom", "dim")

    def _sample_dir(self) -> Path | None:
        src = resource_dir() / "sample_project"
        if not src.is_dir():
            return None
        if getattr(sys, "frozen", False):        # bundled exe: copy the demo to a writable place once
            dst = Path.home() / "Documents" / "VeriFlow Studio" / "sample_project"
            if not dst.exists():
                try:
                    shutil.copytree(src, dst)
                except OSError:
                    return None
            return dst
        return src

    def _apply_theme(self) -> None:
        dark = is_dark(self.cfg)
        th = VSCODE_THEMES["Dark" if dark else "Light"]
        sc = self.cfg.scheme
        self.hpane.configure(bg=th["border"])
        self.vpane.configure(bg=th["border"])
        self._theme_job = None
        style_treeview(self.style, self.cfg, ui_scale(self))
        if FontBook.base != self.cfg["ui_font_size"]:      # re-flowing every CTk widget is the costly part of a zoom
            FontBook.set_base(self.cfg["ui_font_size"])
            self.option_add("*Menu.font", ("Segoe UI", -ui_px(self, -1)))
            self.statusbar.configure(height=int(26 * self.sc * FontBook.base / 13))
            self.titlebar.configure(height=int(40 * FontBook.base / 13))
            self._schedule_fit_toolbar(reset=True)
        for lab in self._st_labels:
            lab.configure(font=("Segoe UI", -ui_px(self, -1)))
        for ed in (self.design_ed, self.tb_ed):
            ed.apply_editor_settings(self.cfg)
        self.console.configure(fg_color=sc["console_bg"], text_color=sc["console_fg"],
                               font=(self.cfg["editor_font_family"], self.cfg["console_font_size"]))
        light = not sc["dark"]
        for tag, color in (("err", "#A1260D" if light else "#F48771"), ("warn", "#9A5B00" if light else "#CCA700"),
                           ("ok", "#16825D" if light else "#89D185"), ("cmd", "#005FB8" if light else "#3794FF"),
                           ("dim", "#767676" if light else "#858585"), ("head", "#AF00DB" if light else "#C586C0")):
            self.console.tag_config(tag, foreground=color)
        self.console.tag_config("link", underline=True, foreground="#005FB8" if light else "#3794FF")
        self.console.tag_raise("link")                       # link colour wins over err/warn line colours
        for tag, (lc, dc) in {"error": ("#A1260D", "#F48771"), "warning": ("#9A5B00", "#CCA700"), "info": ("#005FB8", "#3794FF")}.items():
            self.prob_tree.tag_configure(tag, foreground=dc if dark else lc)
        self.truth.apply_theme(self.cfg)
        self.wave.apply_theme(self.cfg)
        self.theme_btn.configure(text="☀" if dark else "🌙")
        self.font_lbl.configure(text=f"{self.cfg['editor_font_size']}pt")
        self.pinout.render()
        self._render_module_list()
        self._refresh_siblings()
        self._refresh_status_items()

    def _on_config_changed(self, keys: set[str]) -> None:
        if "appearance_mode" in keys:
            ctk.set_appearance_mode(self.cfg["appearance_mode"])
        if "ui_scale_percent" in keys:
            ctk.set_widget_scaling(self.cfg["ui_scale_percent"] / 100)
        if "color_theme" in keys:
            self.log(f"Accent theme '{self.cfg['color_theme']}' will apply after restarting {APP_NAME}.", "dim")
        if "editor_split_layout" in keys:
            self._layout_editors()
        if "default_radix" in keys:
            self.truth.set_radix(self.cfg["default_radix"])
            self.wave.set_radix(self.cfg["default_radix"])
        if keys & {"iverilog_path", "vvp_path", "gtkwave_path", "notepad_pp_path", "lib_dir"}:
            self._update_toolchain_ui()
        if keys & {"library_packages", "lib_dir", "global_packages_dir", "auto_resolve_packages_with_l_flag"}:
            self._load_library()
            self.run_lint()
            self._update_cmd()
            if self._pkg_dialog is not None and self._pkg_dialog.winfo_exists():
                self._pkg_dialog.refresh()
        if keys & {"live_sync_enabled", "external_poll_interval_ms"}:
            (self.sync_switch.select if self.cfg["live_sync_enabled"] else self.sync_switch.deselect)()
            self._restart_sync()
        if keys & {"enable_course_linter", "strict_gate_level_mode"}:
            self.run_lint()
        if keys & {"std_flag", "include_workdir_as_ylib", "enable_wall_warnings", "vvp_non_interactive_flag",
                   "iverilog_path", "vvp_path", "lib_dir"}:
            self._update_cmd()
        visual = {"appearance_mode", "editor_color_scheme", "editor_font_family", "editor_font_size", "console_font_size",
                  "ui_font_size",
                  "tab_size", "word_wrap", "highlight_current_line", "insert_spaces_for_tabs", "ui_scale_percent"}
        if keys & visual:          # debounced: a burst of Ctrl+wheel / A+ steps re-flows the UI once
            if getattr(self, "_theme_job", None):
                self.after_cancel(self._theme_job)
            self._theme_job = self.after(150, self._apply_theme)
        if keys - {"sidebar_view", "sidebar_visible", "last_module", "last_workspace_dir", "recent_workspaces"}:
            self._sync_run_view()
            self._refresh_status_items()
        if self._settings is not None and self._settings.winfo_exists():
            self._settings.sync_from_config()

    def _sync_run_view(self) -> None:
        for key, var in self.run_vars.items():
            v = self.cfg[key]
            if var.get() != v:
                var.set(v)
        self.timeout_lbl.configure(text=f"Simulation timeout: {self.cfg['sim_timeout_sec']:.1f} s  (Settings → Compiler)")

    def _update_toolchain_ui(self) -> None:
        st = self.cfg.toolchain_status()
        if st["iverilog"] and st["vvp"]:
            self.banner.grid_remove()
            self._tool_text = "iverilog ✓"
            self._probe_version()
        else:
            self.banner_lbl.configure(text=f"⚠  Icarus Verilog not found at {self.cfg['iverilog_path']} - DEMO MODE: "
                                           f"the built-in Python gate-level simulator runs instead (1-bit gate designs only).")
            self.banner.grid(row=2, column=0, sticky="ew")
            self._tool_text = "⚠ DEMO MODE (no iverilog)"
        if not st["lib"]:
            self.lib_label.configure(text=f"Library folder not found:\n{self.cfg['lib_dir']}")
        self._refresh_status_items()

    def _probe_version(self) -> None:
        def work():
            try:
                r = subprocess.run([self.cfg["iverilog_path"], "-V"], capture_output=True, timeout=6, stdin=subprocess.DEVNULL,
                                   creationflags=NO_WINDOW)
                first = (r.stdout or r.stderr).decode(errors="replace").splitlines()[0]
                m = re.search(r"version\s+([\d.]+)", first)
                text = f"iverilog {m.group(1)} ✓" if m else "iverilog ✓"
            except (OSError, subprocess.SubprocessError, IndexError):
                text = "iverilog: cannot execute ✗"
            self._probe_result = text          # picked up by _poll_events on the Tk thread
        threading.Thread(target=work, daemon=True).start()

    def _banner_detect(self) -> None:
        found = {k: v for k, v in detect_toolchains().items() if v}
        self.cfg.update(**found)
        if not self.cfg.toolchain_available():
            if IS_MAC:
                messagebox.showwarning("Auto-Detect",
                                       "Icarus Verilog was not found.\nInstall it with:\nbrew install icarus-verilog\n"
                                       "Then use Auto-Detect again or set the paths in ⚙ Settings.")
            else:
                messagebox.showwarning("Auto-Detect",
                                       "Icarus Verilog was not found.\nInstall it to C:\\iverilog or set the paths in ⚙ Settings.")

    def toggle_theme(self) -> None:
        if is_dark(self.cfg):
            self.cfg.update(appearance_mode="Light", editor_color_scheme=LIGHT_SCHEME)
        else:
            scheme = self.cfg["editor_color_scheme"]
            self.cfg.update(appearance_mode="Dark",
                            editor_color_scheme=DARK_SCHEME if scheme in (LIGHT_SCHEME, "GitHub Light") else scheme)

    def zoom(self, delta: int) -> None:
        """A-/A+, Ctrl+wheel, Ctrl+Plus/Minus/0: editor, console AND the UI (tabs, menus, tables, diagrams) together."""
        if delta == 0:
            self.cfg.update(editor_font_size=DEFAULT_CONFIG["editor_font_size"], console_font_size=DEFAULT_CONFIG["console_font_size"],
                            ui_font_size=DEFAULT_CONFIG["ui_font_size"])
        else:
            self.cfg.update(editor_font_size=self.cfg["editor_font_size"] + delta,
                            console_font_size=self.cfg["console_font_size"] + delta,
                            ui_font_size=self.cfg["ui_font_size"] + delta)
        self.font_lbl.configure(text=f"{self.cfg['editor_font_size']}pt")      # instant feedback; the re-flow is debounced

    def open_settings(self) -> None:
        if self._settings is not None and self._settings.winfo_exists():
            self._settings.lift()
            self._settings.focus_force()
            return
        self._settings = SettingsDialog(self)

    # ================================================================== activity bar / side bar
    def _on_activity(self, key: str) -> None:
        if key == "welcome":
            self.show_welcome()
        elif key == "npp":
            self.open_in_npp()
        elif key == "settings":
            self.open_settings()
        elif self.sidebar_visible and self.cfg["sidebar_view"] == key:
            self.toggle_sidebar()                 # VS Code: clicking the active view collapses the side bar
        else:
            self._show_view(key, force=True)

    def _show_view(self, key: str, force: bool = False) -> None:
        if key not in self.views:
            key = "explorer"
        for k, v in self.views.items():
            if k == key:
                v.grid(row=0, column=0, sticky="nsew")
            else:
                v.grid_remove()
        if force and not self.sidebar_visible:
            self.toggle_sidebar()
        if self.cfg["sidebar_view"] != key:
            self.cfg.update(sidebar_view=key)
        self.activity.set_active(key if self.sidebar_visible else None)

    def toggle_sidebar(self) -> None:
        if self.sidebar_visible:
            self.hpane.forget(self.sidebar)
        else:
            self.hpane.add(self.sidebar, before=self.vpane, minsize=int(200 * self.sc), width=int(250 * self.sc))
        self.sidebar_visible = not self.sidebar_visible
        self.activity.set_active(self.cfg["sidebar_view"] if self.sidebar_visible else None)
        self.cfg.update(sidebar_visible=self.sidebar_visible)

    def _refresh_workspace(self) -> None:
        if self.work_dir:
            self._scan_workspace(force=True)
            self.st_msg.configure(text="Workspace refreshed")

    # ================================================================== editor group layout
    def _layout_editors(self) -> None:
        for w in (self.design_ed, self.tb_ed, self.ed_split):
            w.grid_forget()
        if self.cfg["editor_split_layout"] == "Side-by-Side":
            self.ed_area.grid_columnconfigure(0, weight=1, uniform="ed")
            self.ed_area.grid_columnconfigure(1, weight=0, uniform="")
            self.ed_area.grid_columnconfigure(2, weight=1, uniform="ed")
            self.design_ed.grid(row=0, column=0, sticky="nsew")
            self.ed_split.grid(row=0, column=1, sticky="ns")
            self.tb_ed.grid(row=0, column=2, sticky="nsew")
        else:
            for c in range(3):
                self.ed_area.grid_columnconfigure(c, weight=1 if c == 0 else 0, uniform="")
            self._switch_tab(self.tab_shown, focus=False)
        self._refresh_siblings()

    def _switch_tab(self, which: str, focus: bool = True) -> None:
        self.tab_shown = which
        if self.cfg["editor_split_layout"] == "Side-by-Side":
            return
        show, hide = (self.tb_ed, self.design_ed) if which == "tb" else (self.design_ed, self.tb_ed)
        hide.grid_forget()
        show.grid(row=0, column=0, columnspan=3, sticky="nsew")
        self.active_editor = show
        if focus:
            show.text.focus_set()

    def _refresh_siblings(self) -> None:
        if self.cfg["editor_split_layout"] == "Side-by-Side" or not self.module:
            for ed in (self.design_ed, self.tb_ed):
                if ed.sibling is not None:
                    ed.set_sibling(None)
            return
        self.design_ed.set_sibling({"text": os.path.basename(self.tb_ed.path or ""), "role": "TESTBENCH",
                                    "dirty": self.tb_ed.is_modified, "before": False, "command": lambda: self._switch_tab("tb")})
        self.tb_ed.set_sibling({"text": os.path.basename(self.design_ed.path or ""), "role": "DESIGN",
                                "dirty": self.design_ed.is_modified, "before": True, "command": lambda: self._switch_tab("design")})

    def _show_editor(self, ed: VerilogCodeEditor) -> None:
        if self.cfg["editor_split_layout"] != "Side-by-Side":
            self._switch_tab("tb" if ed is self.tb_ed else "design")

    # ================================================================== workspace
    def choose_folder(self) -> None:
        init = self.work_dir or Path.home()
        d = filedialog.askdirectory(parent=self, title="Open Verilog workspace folder", initialdir=str(init))
        if d:
            self.open_workspace(Path(d))

    def _open_recent(self, label: str) -> None:
        self.recent_menu.set(RECENT_LABEL)
        path = self._recent_map.get(label)
        if path and Path(path).is_dir():
            self.open_workspace(Path(path))
        elif path:
            messagebox.showwarning("Recent workspace", f"Folder no longer exists:\n{path}")

    def _refresh_recent_menu(self) -> None:
        self._recent_map = {}
        for p in self.cfg["recent_workspaces"]:
            label = Path(p).name or p
            k = 2
            while label in self._recent_map:
                label = f"{Path(p).name} ({k})"
                k += 1
            self._recent_map[label] = p
        self.recent_menu.configure(values=list(self._recent_map) or ["(none yet)"])
        self.recent_menu.set(RECENT_LABEL)

    def open_workspace(self, folder: Path) -> None:
        if not self._confirm_discard():
            return
        self.work_dir = folder.resolve()
        self.hide_welcome()
        self.cfg.add_recent_workspace(self.work_dir)
        self._refresh_recent_menu()
        self.ws_label.configure(text=str(self.work_dir))
        self.explorer_title.configure(text=f"EXPLORER: {self.work_dir.name.upper()}")
        self.title(f"{self.work_dir.name} - {APP_NAME} {APP_VERSION}")
        self.module = None
        self._scan_workspace(force=True)
        pick = self.cfg["last_module"] if self.cfg["last_module"] in self.modules else next(iter(self.modules), None)
        if pick:
            self.select_module(pick, confirm=False)
        else:
            self.design_ed.set_content("", None)
            self.tb_ed.set_content("", None)
            self.log(f"No *.v modules in {self.work_dir} - use '+ New .v' to create one.", "warn")
        self.log(f"Workspace: {self.work_dir}", "head")

    def _workspace_signature(self):
        if not self.work_dir or not self.work_dir.is_dir():
            return None
        try:
            return tuple(sorted((p.name, p.stat().st_mtime) for p in self.work_dir.glob("*.v")))
        except OSError:
            return None

    def _scan_workspace(self, force: bool = False) -> bool:
        sig = self._workspace_signature()
        if not force and sig == self._ws_signature:
            return False
        self._ws_signature = sig
        self.modules = {}
        files = sorted(self.work_dir.glob("*.v"), key=lambda p: p.name.lower()) if self.work_dir else []
        for f in files:
            if f.stem.lower().endswith("_tb"):
                continue
            tb = f.with_name(f"{f.stem}_tb.v")
            self.modules[f.stem] = {"design": f, "tb": tb if tb.is_file() else None}
        self.ws_modules = scan_module_dir(self.work_dir, self._parse_cache) if self.work_dir else {}
        self._render_module_list()
        self._render_extra_files()
        names = list(self.modules) or ["(no modules)"]
        self.module_menu.configure(values=names)
        self.module_menu.set(self.module or names[0])
        return True

    def _render_module_list(self) -> None:
        for w in self.mod_list.winfo_children():
            w.destroy()
        self.sec_modules.set_count(len(self.modules))
        for r, (name, info) in enumerate(self.modules.items()):
            ready = info["tb"] is not None
            active = name == self.module
            bg = VS["selected"] if active else "transparent"
            row = ctk.CTkFrame(self.mod_list, height=int(32 * FontBook.base / 13), corner_radius=0, fg_color=bg, cursor="hand2")
            row.grid(row=r, column=0, sticky="ew")
            row.pack_propagate(False)
            ctk.CTkFrame(row, width=2, corner_radius=0, fg_color=VS["accent"] if active else bg).pack(side="left", fill="y")
            dot = ctk.CTkLabel(row, text="●", width=18, font=font(11), text_color=VS["ready_dot"] if ready else VS["warn_dot"])
            dot.pack(side="left", padx=(10, 2))
            lab = ctk.CTkLabel(row, text=name, anchor="w", font=font(12), text_color=VS["selected_fg"] if active else VS["text"])
            lab.pack(side="left", fill="x", expand=True)
            badge = ctk.CTkLabel(row, text=" Ready " if ready else " No TB ", height=20, corner_radius=9, font=font(10),
                                 fg_color=VS["badge"] if ready else ("#F5E3B3", "#4D3B0F"),
                                 text_color=VS["badge_fg"] if ready else ("#7A5A00", "#E9C46A"))
            badge.pack(side="right", padx=8)
            for w in (row, dot, lab, badge):
                w.bind("<Button-1>", lambda e, n=name: self.select_module(n))
                w.bind("<Button-3>", lambda e, n=name: self._module_menu(e, n))
                if not active:
                    w.bind("<Enter>", lambda e, rw=row: rw.configure(fg_color=VS["hover"]))
                    w.bind("<Leave>", lambda e, rw=row: rw.configure(fg_color="transparent"))

    def _render_extra_files(self) -> None:
        for w in self.extra_list.winfo_children():
            w.destroy()
        old = {k: v.get() for k, v in self.extra_vars.items()}
        self.extra_vars = {}
        if not self.work_dir:
            self.sec_extra.set_count(0)
            return
        skip = {f"{self.module}.v", f"{self.module}_tb.v"} if self.module else set()
        files = [p.name for p in sorted(self.work_dir.glob("*.v")) if p.name not in skip and not p.stem.lower().endswith("_tb")]
        self.sec_extra.set_count(len(files))
        if not files:
            ctk.CTkLabel(self.extra_list, text="Other modules are found automatically through -y",
                         text_color=VS["muted"], font=font(11), wraplength=220, justify="left").grid(row=0, column=0, sticky="w", padx=14)
        for r, name in enumerate(files):
            var = tk.BooleanVar(value=old.get(name, False))
            self.extra_vars[name] = var
            ctk.CTkCheckBox(self.extra_list, text=name, variable=var, checkbox_width=14, checkbox_height=14, corner_radius=2,
                            border_width=1, text_color=VS["text"], font=font(12),
                            command=self._update_cmd).grid(row=r, column=0, sticky="w", padx=14, pady=2)

    def _extra_files(self) -> list[str]:
        return [n for n, v in self.extra_vars.items() if v.get()]

    def _module_selected(self, name: str) -> None:
        if name in self.modules and name != self.module:
            self.select_module(name)

    def select_module(self, name: str, confirm: bool = True) -> None:
        if confirm and not self._confirm_discard():
            self.module_menu.set(self.module or "(no modules)")
            return
        info = self.modules.get(name)
        if not info:
            return
        self.module = name
        self.cfg.update(last_module=name)
        self.module_menu.set(name)
        self._load_editor(self.design_ed, info["design"])
        tb_path = info["design"].with_name(f"{name}_tb.v")
        if tb_path.is_file():
            self._load_editor(self.tb_ed, tb_path)
            self.tb_ed.set_missing(False)
        else:
            self.tb_ed.set_content("", str(tb_path))
            self.tb_ed.set_missing(True)
        self.tab_shown = "design"
        self._layout_editors()
        self._render_module_list()
        self._render_extra_files()
        self.run_diags = []
        self.truth.clear()
        self.wave.clear()
        self.last_vcd = None
        self._set_status("ready", "⚡ Ready")
        self._update_cmd()
        self._refresh_status_items()
        self.run_lint()

    def _load_editor(self, ed: VerilogCodeEditor, path: Path) -> None:
        try:
            text, nl = read_source(path)
        except OSError as exc:
            self.log(f"Cannot read {path}: {exc}", "err")
            return
        ed.newline = nl
        ed.set_content(text, str(path))
        self.known_mtime[os.path.normcase(str(path))] = path.stat().st_mtime

    def _confirm_discard(self) -> bool:
        dirty = [ed for ed in (self.design_ed, self.tb_ed) if ed.is_modified and ed.path]
        if not dirty:
            return True
        names = ", ".join(os.path.basename(ed.path) for ed in dirty)
        ans = messagebox.askyesnocancel("Unsaved changes", f"Save changes to {names}?", parent=self)
        if ans is None:
            return False
        if ans:
            for ed in dirty:
                self.save_editor(ed, lint=False)
        return True

    # ================================================================== saving
    def save_editor(self, ed: VerilogCodeEditor, lint: bool = True, quiet: bool = False) -> bool:
        if not ed.path:
            return False
        p = Path(ed.path)
        text = ed.get_content()
        if not p.exists() and not text.strip():
            return False
        try:
            with open(p, "w", encoding="utf-8", newline=getattr(ed, "newline", "\n")) as fh:
                fh.write(text)
        except OSError as exc:
            messagebox.showerror("Save failed", f"Cannot write {p}:\n{exc}", parent=self)
            return False
        self.known_mtime[os.path.normcase(str(p))] = p.stat().st_mtime
        ed.mark_saved()
        if ed is self.tb_ed and ed.missing:
            ed.set_missing(False)
        if not quiet:
            self.st_msg.configure(text=f"Saved {p.name}")
        if self.module and p.name == f"{self.module}_tb.v" and self.modules.get(self.module, {}).get("tb") is None:
            self._scan_workspace(force=True)
        if lint:
            self.run_lint()
        self._schedule_live_check()
        return True

    def save_all(self, quiet: bool = False) -> None:
        for ed in (self.design_ed, self.tb_ed):
            if ed.is_modified:
                self.save_editor(ed, lint=False, quiet=quiet)
        self.run_lint()

    def _on_editor_modified(self, ed: VerilogCodeEditor, modified: bool) -> None:
        any_mod = self.design_ed.is_modified or self.tb_ed.is_modified
        self.st_saved.configure(text="● Modified" if any_mod else "✔ Saved")
        self._refresh_siblings()
        if modified and self.cfg["enable_course_linter"]:
            if self._lint_job:
                self.after_cancel(self._lint_job)
            self._lint_job = self.after(900, self.run_lint)

    def _on_cursor(self, ed: VerilogCodeEditor, line: int, col: int, msg: str | None) -> None:
        self.st_pos.configure(text=f"Ln {line}, Col {col}")
        if msg:
            self.st_msg.configure(text=msg.splitlines()[0][:160])
            return
        word = ed.word_at_cursor()
        info = self._known_cache.get(word)
        if info and info.get("ports") is not None:
            sig = ", ".join(f"{p['direction']} {p['range_text'] + ' ' if p['range_text'] else ''}{p['name']}" for p in info["ports"])
            self.st_msg.configure(text=f"◆ {word} ({sig})  ·  {info.get('package_name', '')}"[:170])

    def _on_editor_focus(self, ed: VerilogCodeEditor) -> None:
        self.active_editor = ed

    # ================================================================== library
    def _load_library(self) -> None:
        self._pkg_groups = self.pkg.modules_by_package()
        self._pkg_stats = self.pkg.stats()
        active, total = self._pkg_stats
        self.lib_label.configure(text=f"{active} active package(s) · {total} modules indexed · double-click = preview")
        self.lib_search.configure(placeholder_text=f"🔍 Search {total} loaded modules (e.g. Mux, Adder, DFF)…")
        self._render_library()
        self._refresh_status_items()

    def _toggle_pkg_collapsed(self, name: str) -> None:
        self._pkg_collapsed ^= {name}
        self._render_library()

    def _render_library(self) -> None:
        for w in self.lib_list.winfo_children():
            w.destroy()
        q = self.lib_search.get().strip().lower()
        r = 0
        for pkg, mods in self._pkg_groups:
            shown = [m for m in mods if not q or q in m["module_name"].lower() or q in pkg["name"].lower()]
            if q and not shown:
                continue
            collapsed = pkg["name"] in self._pkg_collapsed and not q
            head = ctk.CTkFrame(self.lib_list, height=26, corner_radius=0, fg_color="transparent")
            head.grid(row=r, column=0, sticky="ew", pady=(4 if r else 0, 0))
            head.grid_columnconfigure(0, weight=1)
            r += 1
            lab = ctk.CTkLabel(head, text=f"{'▸' if collapsed else '▾'} 📦 {pkg['name']}  [{len(mods)}]", anchor="w",
                               font=font(11, "bold"), cursor="hand2",
                               text_color=VS["sidebar_header"] if pkg["enabled"] else VS["muted"])
            lab.grid(row=0, column=0, sticky="ew", padx=(6, 2))
            lab.bind("<Button-1>", lambda e, n=pkg["name"]: self._toggle_pkg_collapsed(n))
            var = tk.BooleanVar(value=pkg["enabled"])
            ctk.CTkCheckBox(head, text="", variable=var, width=18, checkbox_width=14, checkbox_height=14, corner_radius=2,
                            border_width=1, command=lambda n=pkg["name"], vv=var: self.set_package_enabled(n, vv.get())).grid(
                row=0, column=1, padx=(0, 8))
            if not pkg["exists"]:
                ctk.CTkLabel(self.lib_list, text="      folder not found", anchor="w", text_color=ACCENT["err"],
                             font=font(10)).grid(row=r, column=0, sticky="ew")
                r += 1
            if collapsed:
                continue
            for m in shown:
                sig = ", ".join(p["name"] for p in m["ports"])
                sel = (self._lib_selected is not None and self._lib_selected.get("module_name") == m["module_name"]
                       and self._lib_selected.get("filepath") == m["filepath"])
                b = ctk.CTkButton(self.lib_list, text=f"    {m['module_name']}  ({sig})", anchor="w", height=24, corner_radius=0,
                                  border_width=0, fg_color=VS["selected"] if sel else "transparent", hover_color=VS["hover"],
                                  text_color=(VS["selected_fg"] if sel else VS["text"]) if pkg["enabled"] else VS["muted"],
                                  font=font(12), command=lambda mm=m: self._show_lib(mm))
                b.grid(row=r, column=0, sticky="ew")
                b.bind("<Double-Button-1>", lambda e, mm=m: self._preview_module(mm))
                r += 1
        if q != getattr(self, "_lib_last_query", None):      # new filter -> show results from the top
            self._lib_last_query = q
            self.lib_list._parent_canvas.yview_moveto(0)

    def _show_lib(self, m: dict) -> None:
        self._lib_selected = m
        how = "loaded with -l (multi-module / renamed file)" if m.get("needs_l_flag") else "found through -y"
        head = f"// package: {m.get('package_name', '?')}\n// file:    {Path(m['filepath']).name}  ({how})\n" if m.get("filepath") else ""
        self.lib_detail.configure(state="normal")
        self.lib_detail.delete("1.0", "end")
        self.lib_detail.insert("1.0", head + describe_ports(m) + "\n\n" + instantiation_template(m, "u1"))
        self.lib_detail.configure(state="disabled")
        self._render_library()

    def _preview_module(self, m: dict) -> None:
        """Read-only source preview of a package module (double-click in the library)."""
        self._preview_file(Path(m["filepath"]), m.get("line") or 1, m["module_name"])

    def _preview_file(self, path: Path, line: int = 1, title: str | None = None) -> None:
        """Read-only editor window on any .v file (library modules, hierarchy clicks)."""
        try:
            text, _nl = read_source(path)
        except OSError as exc:
            messagebox.showerror("Preview", f"Cannot read {path}:\n{exc}", parent=self)
            return
        win = ctk.CTkToplevel(self)
        win.title(f"{title + ' - ' if title else ''}{path.name}  (read-only)")
        win.geometry("860x640")
        win.transient(self)
        ed = VerilogCodeEditor(win, self.cfg, role="DESIGN")
        ed.pack(fill="both", expand=True)
        ed.set_content(text, str(path))
        ed.goto_line(line or 1)
        ed.text.configure(state="disabled")
        win.after(150, win.lift)

    # ---- package imports
    def import_v_files(self) -> None:
        files = filedialog.askopenfilenames(parent=self, title="Load Verilog module files into the global package vault",
                                            filetypes=[("Verilog", "*.v *.sv"), ("All files", "*.*")])
        if not files:
            return
        name = ctk.CTkInputDialog(text=f"Package name (leave empty for '{DEFAULT_IMPORT_PACKAGE}'):", title="Load .v Files").get_input()
        if name is None:
            return
        self._after_import(lambda: self.pkg.import_files_to_package(list(files), name.strip() or DEFAULT_IMPORT_PACKAGE))

    def import_folder(self) -> None:
        d = filedialog.askdirectory(parent=self, title="Load a folder of Verilog modules as a global package")
        if not d:
            return
        ans = messagebox.askyesnocancel(
            "Load Folder", f"{d}\n\nYes  -  copy its .v files into the global vault\n          (keeps working even if the folder "
                           f"is moved or deleted)\nNo   -  link the folder in place\n          (always uses the folder's latest "
                           f"files)", parent=self)
        if ans is None:
            return
        self._after_import(lambda: self.pkg.add_external_library_folder(Path(d), copy_to_vault=ans))

    def import_zip(self) -> None:
        f = filedialog.askopenfilename(parent=self, title="Load a course .zip of Verilog modules",
                                       filetypes=[("Zip archives", "*.zip"), ("All files", "*.*")])
        if f:
            self._after_import(lambda: self.pkg.import_zip_package(Path(f)))

    def _after_import(self, action) -> None:
        try:
            r = action()
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            messagebox.showerror("Import failed", str(exc), parent=self)
            return
        mods = r["modules"]
        dups = r.get("duplicates", [])
        for d in dups:
            self.log(f"   ↷ skipped duplicate '{d['module']}' in {d['file']} - already provided by "
                     f"{self._package_of(d['existing'])} ({Path(d['existing']).name})", "dim")
        if r["skipped"]:
            self.log(f"   skipped (not .v/.sv/.vh): {', '.join(r['skipped'][:12])}", "dim")
        by_pkg: dict[str, list[str]] = {}
        for d in dups:
            by_pkg.setdefault(self._package_of(d["existing"]), []).append(d["module"])
        skipped_txt = "; ".join(f"{len(v)} already provided by {k}: {', '.join(sorted(set(v))[:6])}" for k, v in by_pkg.items())
        if r["package"] is None:
            self.st_msg.configure(text="Nothing new loaded - every module in the selection is already provided")
            self.toast(f"Nothing new loaded - all modules are already provided ({skipped_txt})", "warn")
            self.panel.set("console")
            return
        msg = (f"Loaded {len(mods)} new module(s) from {r['package']}"
               + (f" (skipped {len(dups)} duplicate{'s' if len(dups) != 1 else ''} - {skipped_txt})" if dups else ""))
        self.log(f"📦 {msg}: {', '.join(mods[:24])}{' …' if len(mods) > 24 else ''}", "ok")
        self.st_msg.configure(text=msg[:170])
        self.toast(("📦 " + msg) if not dups else ("📦 " + msg + ". Details in the Console."), "ok" if not dups else "info")
        self._show_view("library", force=True)

    def _package_of(self, path: str) -> str:
        key = os.path.normcase(os.path.abspath(path))
        for p in self.pkg.packages():
            root = os.path.normcase(os.path.abspath(p["path"]))
            if key.startswith(root + os.sep):
                return "compstruct\\lib" if p["kind"] == "builtin" else f"'{p['name']}'"
        return Path(path).parent.name

    def open_package_manager(self) -> None:
        if self._pkg_dialog is not None and self._pkg_dialog.winfo_exists():
            self._pkg_dialog.refresh()
            self._pkg_dialog.lift()
            self._pkg_dialog.focus_force()
            return
        self._pkg_dialog = PackageManagerDialog(self)

    def open_vault_folder(self) -> None:
        self.open_folder(self.pkg.open_vault_folder())

    def open_folder(self, path) -> None:
        p = Path(path)
        if p.is_dir() and IS_WINDOWS:
            os.startfile(str(p))  # type: ignore[attr-defined]
        elif p.is_dir() and IS_MAC:
            subprocess.Popen(["open", str(p)])
        elif not p.is_dir():
            messagebox.showwarning("Open folder", f"Folder not found:\n{p}", parent=self)

    def _copy_inst(self) -> None:
        if self._lib_selected:
            self.clipboard_clear()
            self.clipboard_append(instantiation_template(self._lib_selected, "u1"))
            self.st_msg.configure(text=f"Copied {self._lib_selected['module_name']} instantiation")

    def _insert_inst(self) -> None:
        if self._lib_selected and self.active_editor:
            self.active_editor.insert_snippet(instantiation_template(self._lib_selected, "u1").rstrip("\n"))

    def _insert_snippet(self, name: str) -> None:
        self.snippet_menu.set(SNIPPET_LABEL)
        if self.active_editor:
            self._show_editor(self.active_editor)
            self.active_editor.insert_snippet(SNIPPETS[name])

    # ================================================================== linting & problems
    def _known_modules(self) -> dict[str, dict]:
        """Workspace + every enabled package (the same index the compiler resolves -y / -l from)."""
        return self.pkg.build_index(self.work_dir)

    def run_lint(self, show: bool = False) -> list[dict]:
        self._lint_job = None
        self.lint_diags = []
        known = self._index_with_editors() if self.module else {}     # unsaved buffers win (renames seen at once)
        self._schedule_hierarchy()
        if self.cfg["enable_course_linter"] and self.module:
            eds = [ed for ed in (self.design_ed, self.tb_ed) if ed.path and (Path(ed.path).exists() or ed.get_content().strip())]
            for ed in eds:
                self.lint_diags += run_course_linter(ed.path, known, self.cfg["strict_gate_level_mode"], text=ed.get_content())
                self.lint_diags += self.pkg.editor_collisions(ed.path, ed.get_content(), self.work_dir, self._extra_files())
        self._refresh_problems()
        if show:
            self.panel.set("problems")
            n = len([d for d in self.lint_diags if d["severity"] != "info"])
            self.st_msg.configure(text=f"Linter: {n} issue(s)" if self.cfg["enable_course_linter"] else "Linter disabled in settings")
        return self.lint_diags

    def _refresh_problems(self) -> None:
        seen, diags = set(), []
        for d in self.run_diags + self.live_diags + self.lint_diags:      # drop exact duplicates across sources
            key = (os.path.normcase(d["file"]) if d["file"] else "", d["line"], d["message"])
            if key not in seen:
                seen.add(key)
                diags.append(d)
        self.prob_tree.delete(*self.prob_tree.get_children())
        self.diag_rows = {}
        order = {"error": 0, "warning": 1, "info": 2}
        for k, d in enumerate(sorted(diags, key=lambda d: (order.get(d["severity"], 3), d["file"], d["line"]))):
            iid = f"d{k}"
            fname = os.path.basename(d["file"]) if d["file"] else "-"
            self.prob_tree.insert("", "end", iid=iid, tags=(d["severity"],),
                                  values=(SEV_ICON.get(d["severity"], d["severity"]), fname, d["line"] or "", d["message"], d["source"]))
            self.diag_rows[iid] = d
        self.panel.set_badge("problems", sum(1 for d in diags if d["severity"] in ("error", "warning")))
        for ed in (self.design_ed, self.tb_ed):
            ed.clear_diagnostic_marks()
            if not ed.path:
                continue
            key = os.path.normcase(os.path.abspath(ed.path))
            for d in diags:
                if d["line"] and d["file"] and os.path.normcase(os.path.abspath(d["file"])) == key:
                    if d["severity"] == "error":
                        ed.highlight_error_line(d["line"], d["message"])
                    elif d["severity"] == "warning":
                        ed.highlight_warning_line(d["line"], d["message"])

    def _on_problem_click(self, _e=None) -> None:
        sel = self.prob_tree.selection()
        if sel and sel[0] in self.diag_rows:
            self.jump_to(self.diag_rows[sel[0]])

    def jump_to(self, d: dict) -> None:
        if not d.get("file"):
            return
        key = os.path.normcase(os.path.abspath(d["file"]))
        for ed in (self.design_ed, self.tb_ed):
            if ed.path and os.path.normcase(os.path.abspath(ed.path)) == key:
                self._show_editor(ed)
                if d["line"]:
                    ed.goto_line(d["line"], d.get("col") or 0)
                return
        p = Path(d["file"])
        if p.is_file():
            npp = self.cfg["notepad_pp_path"]
            if Path(npp).is_file():
                subprocess.Popen([npp, f"-n{d['line'] or 1}", str(p)], creationflags=NO_WINDOW)
            elif IS_WINDOWS:
                os.startfile(str(p))  # type: ignore[attr-defined]
            elif IS_MAC:
                subprocess.Popen(["open", "-t", str(p)])

    # ================================================================== command preview
    def _update_cmd(self) -> None:
        if not self.module or not self.work_dir:
            return
        extra = self._extra_files()
        if self.cmd_mode == "Actual":
            self.cmd_var.set(self.runner.display_cmd(self.work_dir, self.module, extra))
        else:
            self.cmd_var.set(self.runner.course_baseline_cmd(self.module))
        body = (f"# compile\n{format_cmd(self.runner.build_compile_cmd(self.work_dir, self.module, extra))}\n\n"
                f"# simulate\n{format_cmd(self.runner.build_sim_cmd(self.module))}\n\n"
                f"# course baseline\n{self.runner.course_baseline_cmd(self.module)}")
        self.run_cmd_box.configure(state="normal")
        self.run_cmd_box.delete("1.0", "end")
        self.run_cmd_box.insert("1.0", body)
        self.run_cmd_box.configure(state="disabled")

    def _cmd_mode(self, mode: str) -> None:
        self.cmd_mode = "Actual" if mode == "Actual" else "Course"
        self._update_cmd()

    def _copy_cmd(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.cmd_var.get())
        self.st_msg.configure(text="Command copied - paste it into cmd.exe inside the workspace folder")

    # ================================================================== run pipeline
    def _set_running(self, running: bool) -> None:
        if running:
            self.run_btn.configure(text="⟳  Running…", state="disabled")
            self.stop_btn.configure(state="normal", fg_color=STOP_RED)
        else:
            self.run_btn.configure(text="▶  Run (F5)", state="normal")
            self.stop_btn.configure(state="disabled", fg_color=STOP_IDLE)

    def run_pipeline(self, reason: str = "manual") -> None:
        if self.runner.is_running():
            return
        if not self.module or not self.work_dir:
            messagebox.showinfo(APP_NAME, "Open a workspace folder and select a module first.", parent=self)
            return
        if self.cfg["auto_save_before_run"]:
            self.save_all(quiet=True)
        elif self.design_ed.is_modified or self.tb_ed.is_modified:
            self.log("Note: unsaved editor changes are NOT compiled (auto-save before run is off).", "warn")
        tb = self.work_dir / f"{self.module}_tb.v"
        if not tb.is_file():
            self.log(f"✖ {tb.name} does not exist - click 🧪 Gen _tb.v first.", "err")
            self.panel.set("console")
            return
        self._clear_console()
        self.run_diags = []
        self.live_diags = []
        self.run_lint()
        self._update_cmd()
        mock = not self.cfg.toolchain_available()
        info = parse_verilog_module(self.work_dir / f"{self.module}.v")
        self._port_widths = {p["name"]: p["bits"] for p in info.get("ports", []) if isinstance(p.get("bits"), int)}
        outputs = {p["name"] for p in info.get("ports", []) if p["direction"] != "input"}
        errs = [d for d in self.lint_diags if d["severity"] == "error"]
        self.log(f"━━ {time.strftime('%H:%M:%S')}  {self.module}  ({reason})" + ("  [DEMO MODE]" if mock else ""), "head")
        if errs:
            self.log(f"Linter found {len(errs)} error(s) - compiling anyway so you see iverilog's view too.", "warn")
        self.runner.start(self.work_dir, self.module, self._extra_files(), mock=mock, outputs=outputs)
        self._set_running(True)
        self._set_status("running", "⟳ Running…")

    def stop_run(self) -> None:
        self.runner.stop()

    def _poll_events(self) -> None:
        if self._probe_result:
            self._tool_text = self._probe_result
            self._probe_result = ""
            self._refresh_status_items()
        while True:
            try:
                ev = self.events.get_nowait()
            except queue.Empty:
                break
            try:
                self._handle_event(ev)
            except Exception as exc:      # a UI bug must never leave the Run button stuck
                self.log(f"✖ Internal UI error while handling {ev.kind}: {exc!r}", "err")
                if ev.kind == "FINISHED":
                    self._set_running(False)
        self.after(40, self._poll_events)

    def _handle_event(self, ev) -> None:
        p = ev.payload
        if ev.kind == "LIVE_CHECK":
            self._on_live_check(p)
            return
        if ev.kind == "STAGE_START":
            self.log(f"$ {p['cmd']}", "cmd")
            res = p.get("resolution") or {}
            if res.get("l_files"):
                self.log(f"📦 auto-loaded with -l: {', '.join(Path(f).name for f in res['l_files'])}", "dim")
            for note in res.get("notes", []):
                self.log(f"📦 {note}", "dim")
            if res.get("missing"):
                self.log(f"⚠ not found in the workspace or any enabled package: {', '.join(res['missing'])} - "
                         f"load them with 📦 Packages", "warn")
            self._set_status("running", "⟳ Compiling…" if p["stage"] == "compile" else "⟳ Simulating…")
        elif ev.kind == "COMPILE_DONE":
            for line in (p.get("stderr", "") + "\n" + p.get("stdout", "")).splitlines():
                if line.strip():
                    self.log(line, self._line_tag(line))
            self.run_diags = list(p.get("diagnostics", []))
            self._refresh_problems()
            if p["ok"]:
                warn = sum(d["severity"] == "warning" for d in self.run_diags)
                self.log(f"✔ Compiled in {p.get('duration', 0):.2f}s" + (f" with {warn} warning(s)" if warn else ""), "ok")
            else:
                n = sum(d["severity"] == "error" for d in self.run_diags) or 1
                self.log(f"✖ Compilation failed (exit code {p.get('rc')}, {n} error(s)) - binary not executed.", "err")
                self._set_status("error", f"⊗ Compile failed ({n} error{'s' if n != 1 else ''})")
                self.panel.set("problems")
                first = next((d for d in self.run_diags if d["severity"] == "error" and d["line"]), None)
                if first:
                    self.jump_to(first)
        elif ev.kind in ("SIM_DONE", "TIMEOUT"):
            self._show_sim(p, timed_out=ev.kind == "TIMEOUT")
        elif ev.kind == "ERROR":
            self.log(f"✖ {p.get('message')}", "err")
            if "stdout" in p:
                self._show_sim(p, timed_out=False, stopped=True)
            else:
                self._set_status("error", "⊗ Error")
        elif ev.kind == "FINISHED":
            self._set_running(False)
            if self._status_state == "running":
                self._set_status("ready", "⚡ Ready")
            self.st_time.configure(text=f"⏱ Pipeline: {p.get('duration', 0):.2f}s")

    def _show_sim(self, p: dict, timed_out: bool, stopped: bool = False) -> None:
        for line in p.get("stdout", "").splitlines():
            self.log(line, self._line_tag(line))
        for line in p.get("stderr", "").splitlines():
            if line.strip():
                self.log(line, "err")
        if p.get("diagnostics"):
            self.run_diags += p["diagnostics"]
            self._refresh_problems()
        table = p.get("table") or {"columns": [], "rows": [], "counts": {}}
        self.truth.set_data(table, self._port_widths)
        self.last_vcd = p.get("vcd")
        if self.last_vcd:
            try:
                self.wave.set_vcd(parse_vcd_file(self.last_vcd, max_steps=4096))
            except (OSError, ValueError) as exc:
                self.log(f"Could not read VCD: {exc}", "warn")
                self.last_vcd = None
        if not self.last_vcd:
            if table["rows"]:
                self.wave.set_from_table(table["columns"], table["rows"])
            else:
                self.wave.clear("No VCD and no truth-table rows to draw")
        counts = table.get("counts", {})
        extra_fail = [m for m in table.get("fail_messages", []) if not m.startswith("SELF-CHECK:")]   # summary line != a failure
        rows, xz, fail = len(table["rows"]), counts.get(STATUS_XZ, 0), counts.get(STATUS_FAIL, 0) + len(extra_fail)
        if timed_out:
            t = p.get("timeout", self.cfg["sim_timeout_sec"])
            self.log(f"⏱ Simulation killed after {t:.1f}s timeout - the testbench probably has no $finish, waits forever, "
                     f"or has a zero-delay loop (e.g. 'always a = ~a;'). Process tree terminated.", "err")
            self.run_diags.append({"file": str(self.work_dir / f"{self.module}_tb.v"), "line": 0, "col": 0, "severity": "error",
                                   "code": "timeout", "source": "runner", "message": f"Simulation timed out after {t:.1f}s (no $finish / infinite loop?)"})
            self._refresh_problems()
            self._set_status("error", f"⏱ Timeout ({t:.1f}s)")
            self.panel.set("console")
            return
        if stopped:
            self._set_status("ready", "■ Stopped")
            return
        if p.get("mock"):
            self.log("(demo mode) results computed by the built-in Python gate-level simulator", "dim")
        ok = fail == 0 and xz == 0 and (p.get("rc") in (0, None))
        summary = f"{rows} rows · {xz} x/z · {fail} FAIL"
        self.log(("✔ Simulation OK - " if ok else "⚠ Simulation finished - ") + summary + f"  ({p.get('duration', 0):.2f}s)",
                 "ok" if ok else "warn")
        self._set_status("ready", ("✔ " if ok else "⚠ ") + summary)
        self._schedule_hierarchy()
        self.panel.set("table" if rows else "console")

    @staticmethod
    def _line_tag(line: str) -> str | None:
        low = line.lower()
        if re.search(r"\b(error|fail\w*|mismatch|syntax error|i give up)\b", low):
            return "err"
        if "warning" in low or re.search(r"=\s*[01]*[xz]", low):
            return "warn"
        if re.search(r"\b(pass(ed)?|ok)\b", low):
            return "ok"
        if low.startswith(("vcd info", "$finish", "[demo]")) or "$finish called" in low:
            return "dim"
        return None

    # ================================================================== console
    def log(self, text: str, tag: str | None = None) -> None:
        """Append a console line; every `file.v:line[:col]` in it becomes a link that opens that line."""
        self.console.configure(state="normal")
        pos = 0
        for m in LINK_RE.finditer(text):
            if m.start() > pos:
                self.console.insert("end", text[pos:m.start()], tag)
            path = Path(m.group(1))
            if not path.is_absolute() and self.work_dir:
                path = self.work_dir / path
            lid = f"lnk{len(self._links)}"
            self._links[lid] = (str(path), int(m.group(2)), int(m.group(3) or 0))
            self.console.insert("end", m.group(0), (tag, "link", lid) if tag else ("link", lid))
            self.console.tag_bind(lid, "<Button-1>", lambda e, k=lid: self._follow_link(k))
            pos = m.end()
        self.console.insert("end", text[pos:] + "\n", tag)
        self.console.see("end")
        self.console.configure(state="disabled")

    def _follow_link(self, lid: str) -> None:
        f, line, col = self._links[lid]
        self.jump_to({"file": f, "line": line, "col": col})
        self.st_msg.configure(text=f"→ {Path(f).name}:{line}")

    def _clear_console(self) -> None:
        self.console.configure(state="normal")
        self.console.delete("1.0", "end")
        self.console.configure(state="disabled")
        for lid in self._links:
            self.console.tag_delete(lid)
        self._links = {}

    # ---- live compile check (iverilog -tnull after every save)
    def _schedule_live_check(self) -> None:
        if not (self.cfg["live_check_on_save"] and self.module and self.work_dir and self.cfg.toolchain_available()):
            return
        if self._live_job:
            self.after_cancel(self._live_job)
        self._live_job = self.after(250, self._start_live_check)

    def _start_live_check(self) -> None:
        self._live_job = None
        if self.module and self.work_dir and (self.work_dir / f"{self.module}.v").is_file():
            include_tb = (self.work_dir / f"{self.module}_tb.v").is_file()
            self.runner.start_syntax_check(self.work_dir, self.module, self._extra_files(), include_tb=include_tb)

    def _on_live_check(self, p: dict) -> None:
        if p.get("module") != self.module or not self.work_dir or os.path.normcase(p.get("work_dir", "")) != os.path.normcase(str(self.work_dir)):
            return                                       # stale result for a module/folder no longer open
        if p.get("error"):
            self.st_msg.configure(text=f"Live check could not run: {p['error']}")
            return
        self.live_diags = p["diagnostics"]
        self.run_diags = [d for d in self.run_diags if d["source"] not in ("iverilog",)]   # older compile errors are stale now
        self._refresh_problems()
        errs = sum(d["severity"] == "error" for d in self.live_diags)
        warns = sum(d["severity"] == "warning" for d in self.live_diags)
        if errs:
            self._set_status("error", f"⊗ {errs} error{'s' if errs != 1 else ''} (live check)")
        elif self._status_state == "error":
            self._set_status("ready", "✔ Live check clean")
        self.st_msg.configure(text=f"Live check (iverilog -tnull, {p['duration']:.2f}s): "
                                   + (f"{errs} error(s), {warns} warning(s)" if errs or warns else "no errors"))

    # ---- toast notifications
    def toast(self, text: str, kind: str = "info", ms: int = 6000) -> None:
        if self._toast is not None:
            self._toast.destroy()
        if self._toast_job:
            self.after_cancel(self._toast_job)
        bg = {"warn": ("#FFF4CE", "#4D3B0F"), "ok": ("#DFF6DD", "#1E3A23"), "info": VS["group"]}.get(kind, VS["group"])
        fg = {"warn": ("#7A5A00", "#F2CC60"), "ok": ("#16825D", "#89D185")}.get(kind, VS["text"])
        t = ctk.CTkFrame(self, corner_radius=4, fg_color=bg, border_width=1, border_color=VS["group_border"])
        ctk.CTkLabel(t, text=text, text_color=fg, font=font(12), wraplength=460, justify="left").pack(side="left", padx=(12, 6), pady=8)
        icon_button(t, "✕", lambda: t.destroy(), width=24).pack(side="right", padx=6)
        t.place(relx=1.0, rely=1.0, anchor="se", x=-18, y=-int(34 * self.sc))
        t.lift()
        self._toast = t
        self._toast_job = self.after(ms, lambda: t.winfo_exists() and t.destroy())

    # ---- module context menus
    def _module_menu(self, e, name: str) -> None:
        m = DarkMenu(self, self.cfg)
        m.add_command(label=f"Open {name}", command=lambda: self.select_module(name))
        m.add_separator()
        m.add_command(label="🧪 Generate Testbench (exhaustive)", command=lambda: self._tb_for(name, False))
        m.add_command(label="🧪 Generate Skeleton Testbench (empty initial)", command=lambda: self._tb_for(name, True))
        m.add_command(label="🧪 Generate Self-Checking Testbench…", command=lambda: self.self_check_dialog(name))
        m.add_separator()
        m.add_command(label="📝 Open in Notepad++", command=lambda: (self.select_module(name), self.open_in_npp()))
        m.add_command(label="📂 Reveal in Explorer", command=lambda: self.open_folder(self.work_dir))
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def _tb_for(self, name: str, skeleton: bool) -> None:
        if name != self.module:
            self.select_module(name)
            if self.module != name:              # user cancelled the unsaved-changes prompt
                return
        self.generate_tb(skeleton=skeleton)

    def _on_btab(self) -> None:
        if self.panel.get() == "wave":
            self.after(30, self.wave.render)
        elif self.panel.get() == "hier":
            self.after(30, self._refresh_hierarchy)

    # ---- hierarchy & gate count & pinout
    def _schedule_hierarchy(self) -> None:
        if self.panel.get() == "hier":
            if self._hier_job:
                self.after_cancel(self._hier_job)
            self._hier_job = self.after(400, self._refresh_hierarchy)

    def _refresh_hierarchy(self) -> None:
        self._hier_job = None
        self.hier_tree.delete(*self.hier_tree.get_children())
        self._hier_items = {}
        mods = parse_verilog_source(self.design_ed.get_content(), self.design_ed.path or "") if self.module else []
        if not mods:
            self.hier_summary.configure(text="Open a module to see its hierarchy")
            self.pinout.set_module(None)
            return
        known = self._index_with_editors()
        root = next((m for m in mods if m["module_name"] == self.module), mods[0])
        h = analyze_hierarchy(root["module_name"], known)

        def where(node: dict) -> str:
            if node.get("primitive"):
                return "Verilog primitive"
            if node.get("missing"):
                return "⚠ not found"
            pkg = node.get("package") or ""
            return f"{Path(node['file']).name}  ({pkg})" if node.get("file") else pkg

        def add(parent: str, node: dict, is_root: bool = False) -> None:
            label = node["type"] if is_root else (node["name"] or "(unnamed)")
            iid = self.hier_tree.insert(parent, "end", text=("⬢ " if not node["primitive"] else "· ") + label,
                                        values=(node["type"].upper() if node["primitive"] else node["type"], where(node)),
                                        open=is_root or len(node["children"]) <= 8)
            target = (node.get("inst_file"), node.get("inst_line", 0)) if node["primitive"] else (node.get("file"), node.get("line", 0))
            if node["primitive"]:
                target = (node.get("file"), node.get("line", 0))
            self._hier_items[iid] = (target[0], target[1] or 1, None if node["primitive"] else known.get(node["type"]))
            for ch in node["children"]:
                add(iid, ch)
        add("", h["tree"], is_root=True)
        g = " · ".join(f"{k.upper()} {v}" for k, v in h["gates"].items() if v) or "no primitive gates"
        extra = " · ".join(f"{k} {v}" for k, v in h["other_primitives"].items())
        miss = f"   ⚠ missing: {', '.join(h['missing'])}" if h["missing"] else ""
        self.hier_summary.configure(text=f"{h['total_gates']} gates ({g}{' · ' + extra if extra else ''})   ·   "
                                         f"{h['instances']} sub-module instances   ·   est. logic depth ~{h['depth']} levels{miss}")
        self.pinout.set_module(root, h["total_gates"], h["depth"])

    def _on_hier_click(self, _e=None) -> None:
        sel = self.hier_tree.selection()
        if not sel or sel[0] not in self._hier_items:
            return
        f, line, _info = self._hier_items[sel[0]]
        if f:
            self._open_location(f, line)

    def _open_location(self, f: str, line: int) -> None:
        key = os.path.normcase(os.path.abspath(f))
        for ed in (self.design_ed, self.tb_ed):
            if ed.path and os.path.normcase(os.path.abspath(ed.path)) == key:
                self._show_editor(ed)
                ed.goto_line(line)
                return
        self._preview_file(Path(f), line)

    def _index_with_editors(self) -> dict[str, dict]:
        """Global index (workspace + enabled packages) with the unsaved editor buffers layered on top."""
        known = self._known_modules()
        for ed in (self.design_ed, self.tb_ed):
            if not ed.path:
                continue
            for name in [n for n, e in known.items() if os.path.normcase(str(e["filepath"])) == os.path.normcase(ed.path)]:
                del known[name]
            for m in parse_verilog_source(ed.get_content(), ed.path):
                known[m["module_name"]] = {**m, "filepath": Path(ed.path), "package_name": "Workspace", "needs_l_flag": False}
        self._known_cache = known
        return known

    # ---- package enable/disable with conflict check
    def set_package_enabled(self, name: str, enabled: bool) -> None:
        res = self.pkg.toggle_package_enabled(name, enabled)
        if not res["ok"] and res.get("conflicts"):
            mods = ", ".join(sorted({c["module"] for c in res["conflicts"]}))
            others = sorted({c["package"] for c in res["conflicts"]})
            if messagebox.askyesno("Package conflict",
                                   f"Can't enable '{name}': it defines {mods}, which "
                                   f"{', '.join(others)} already provide{'s' if len(others) == 1 else ''}.\n\n"
                                   f"iverilog fails when a module is defined twice.\n\n"
                                   f"Disable {', '.join(others)} and enable '{name}' instead?", parent=self):
                res = self.pkg.toggle_package_enabled(name, True, force=True)
                self.log(f"📦 enabled '{name}', disabled {', '.join(res['disabled'])} (duplicate {mods})", "warn")
            else:
                self.toast(f"'{name}' stays disabled - {mods} already provided by {', '.join(others)}", "warn")
            self._load_library()
            if self._pkg_dialog is not None and self._pkg_dialog.winfo_exists():
                self._pkg_dialog.refresh()

    # ---- self-checking testbench
    def self_check_dialog(self, name: str | None = None) -> None:
        if name and name != self.module:
            self.select_module(name)
            if self.module != name:
                return
        if not self.module or not self.work_dir:
            return
        info = parse_verilog_module(self.work_dir / f"{self.module}.v", self.design_ed.get_content())
        if not info.get("module_name"):
            messagebox.showerror("Self-checking testbench", f"Cannot parse {self.module}.v", parent=self)
            return
        SelfCheckDialog(self, info)

    # ---- homework submission packager
    def export_submission(self) -> None:
        if not self.work_dir:
            messagebox.showinfo(APP_NAME, "Open a workspace folder first.", parent=self)
            return
        self.save_all(quiet=True)
        plan = self.pkg.submission_plan(self.work_dir)
        if not plan["files"]:
            messagebox.showinfo("Export HW .zip", "No .v files in this folder.", parent=self)
            return
        include = True
        if plan["helpers"]:
            lst = "\n".join(f"  • {h['module']}   (package '{h['package']}')" for h in plan["helpers"][:15])
            ans = messagebox.askyesnocancel(
                "Export HW .zip", f"Your design uses {len(plan['helpers'])} module(s) that are NOT in the course library "
                                  f"and NOT in this folder:\n\n{lst}\n\nThe grader will not have them.\n"
                                  f"Include them in the zip (one file per module)?", parent=self)
            if ans is None:
                return
            include = ans
        out = filedialog.asksaveasfilename(parent=self, title="Save homework submission", defaultextension=".zip",
                                           initialdir=str(self.work_dir.parent), initialfile=f"{self.work_dir.name}_Submission.zip",
                                           filetypes=[("Zip archive", "*.zip")])
        if not out:
            return
        try:
            r = self.pkg.build_submission_zip(self.work_dir, out, include_helpers=include, plan=plan)
        except OSError as exc:
            messagebox.showerror("Export HW .zip", str(exc), parent=self)
            return
        self.log(f"📦 Exported {r['zip']}: {', '.join(r['files'] + r['helpers'])}", "ok")
        if r["excluded"]:
            self.log(f"   left out (binaries, .vcd, temp files): {', '.join(r['excluded'][:20])}", "dim")
        self.toast(f"📦 {Path(r['zip']).name} ready - {len(r['files']) + len(r['helpers'])} file(s)"
                   + (f" incl. {len(r['helpers'])} helper module(s)" if r["helpers"] else ""), "ok")

    # ================================================================== tools
    def generate_tb(self, skeleton: bool = False, checks: dict | None = None) -> None:
        if not self.module or not self.work_dir:
            return
        design = self.work_dir / f"{self.module}.v"
        info = parse_verilog_module(design, self.design_ed.get_content())
        if not info.get("module_name"):
            messagebox.showerror("Generate testbench", f"Cannot parse {design.name}: {info.get('error')}", parent=self)
            return
        tb = self.work_dir / f"{self.module}_tb.v"
        if (tb.is_file() and tb.read_text(encoding="utf-8", errors="replace").strip()) or self.tb_ed.get_content().strip():
            if not messagebox.askyesno("Generate testbench", f"{tb.name} already has content.\nOverwrite it with a fresh skeleton?", parent=self):
                return
        if info["module_name"] != self.module:
            self.log(f"Note: file {design.name} declares module '{info['module_name']}' - the testbench instantiates that name.", "warn")
        tb.write_text(generate_testbench_skeleton(info, empty_stimulus=skeleton, checks=checks), encoding="utf-8")
        self._scan_workspace(force=True)
        self._load_editor(self.tb_ed, tb)
        self.tb_ed.set_missing(False)
        self._render_module_list()
        self._show_editor(self.tb_ed)
        self.run_lint()
        ins = sum(p["bits"] or 1 for p in info["ports"] if p["direction"] == "input")
        kind = ("skeleton with an empty stimulus block" if skeleton and not checks
                else f"{'exhaustive loop over' if ins <= 7 else '8 corner-case vectors for'} {ins} input bit(s)"
                + (f", self-checking {', '.join(checks)}" if checks else ""))
        self.log(f"🧪 Generated {tb.name} ({kind}). Press F5 to run.", "ok")

    def _default_parent(self) -> Path:
        p = Path(self.cfg["last_parent_dir"]) if self.cfg["last_parent_dir"] else None
        return p if p and p.is_dir() else Path.home() / "Documents"

    def new_module(self) -> NewModuleDialog:
        """Ctrl+N: module name, target folder (browse / create a subfolder), optional ports and testbench."""
        return NewModuleDialog(self, project=False, location=self.work_dir or self._default_parent())

    def new_project(self) -> NewModuleDialog:
        """Ctrl+Shift+N: a new assignment folder (e.g. Documents\\CompStruct\\Lab4) with its first module + testbench."""
        return NewModuleDialog(self, project=True, location=self.work_dir.parent if self.work_dir else self._default_parent())

    def finish_new_module(self, result: dict) -> None:
        folder, name = Path(result["folder"]).resolve(), result["module"]
        if self.work_dir is not None and self.work_dir == folder:
            self._scan_workspace(force=True)
            self.select_module(name)
        else:
            self.open_workspace(folder)
            if self.work_dir == folder and self.module != name:
                self.select_module(name, confirm=False)
        made = ", ".join(p.name for p in result["files"])
        self.log(f"✨ Created {made} in {folder}" + (" - press F5 to run." if len(result["files"]) > 1
                                                     else " - add a testbench with 🧪 Gen _tb.v."), "ok")
        if result.get("npp") and self.work_dir == folder:
            self.open_in_npp()

    def open_single_file(self) -> None:
        f = filedialog.askopenfilename(parent=self, title="Open a Verilog file", initialdir=str(self.work_dir or self._default_parent()),
                                       filetypes=[("Verilog", "*.v *.sv *.vh"), ("All files", "*.*")])
        if not f:
            return
        path = Path(f)
        self.open_workspace(path.parent)
        stem = path.stem[:-3] if path.stem.lower().endswith("_tb") else path.stem
        if self.work_dir == path.parent.resolve():
            if stem in self.modules and self.module != stem:
                self.select_module(stem, confirm=False)
            elif stem not in self.modules:
                self._preview_file(path)

    def open_sample_project(self) -> None:
        sample = self._sample_dir()
        if sample:
            self.open_workspace(sample)
        else:
            messagebox.showwarning(APP_NAME, "The built-in sample project could not be found.", parent=self)

    def open_recent_path(self, path: str) -> None:
        if Path(path).is_dir():
            self.open_workspace(Path(path))
        elif messagebox.askyesno("Recent", f"This folder no longer exists:\n{path}\n\nRemove it from the Recent list?", parent=self):
            self.cfg.update(recent_workspaces=[r for r in self.cfg["recent_workspaces"] if r != path])
            self._refresh_recent_menu()
            self.welcome.refresh()

    # ---- Welcome page / Close Folder
    def show_welcome(self) -> None:
        self.welcome.refresh()
        self.welcome.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.welcome.lift()
        if not getattr(self, "_welcome_shown", False):
            self.after(60, self._welcome_room)
        self._welcome_shown = True

    def _welcome_room(self) -> None:
        """Like VS Code's Welcome tab: give the editor area most of the height while it is shown (panel restored later)."""
        try:
            self.update_idletasks()
            total = self.vpane.winfo_height()
            y = self.vpane.sash_coord(0)[1]
            want = total - int(170 * self.sc)
            if total > 300 and y < want:
                self._panel_sash = y
                self.vpane.sash_place(0, 0, want)
        except tk.TclError:
            pass

    def hide_welcome(self) -> None:
        self.welcome.place_forget()
        self._welcome_shown = False
        y, self._panel_sash = getattr(self, "_panel_sash", None), None
        if y is not None:
            try:
                self.vpane.sash_place(0, 0, y)
            except tk.TclError:
                pass

    def close_folder(self) -> None:
        """VS Code 'Close Folder': back to the Welcome page; the next start does not reopen this folder."""
        if self.work_dir is None:
            self.show_welcome()
            return
        if not self._confirm_discard():
            return
        self.runner.stop()
        self.work_dir, self.module = None, None
        self.modules, self.ws_modules, self.extra_vars = {}, {}, {}
        self.lint_diags, self.run_diags, self.live_diags = [], [], []
        self._ws_signature = None
        for ed in (self.design_ed, self.tb_ed):
            ed.set_content("", None)
        self._render_module_list()
        self._render_extra_files()
        self.module_menu.configure(values=["(no modules)"])
        self.module_menu.set("(no modules)")
        self.ws_label.configure(text="No folder open")
        self.explorer_title.configure(text="EXPLORER: NO FOLDER OPENED")
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.cfg.update(last_workspace_dir="")
        self._refresh_problems()
        self._refresh_status_items()
        self.show_welcome()

    # ---- GitHub auto-update
    def _check_updates(self, manual: bool = False) -> None:
        if not manual:                       # keep the 30-minute cadence even if this tick overlaps a running check
            self.after(30 * 60 * 1000, lambda: self.cfg["check_for_updates"] and self._check_updates())
        self._update_manual = manual or self._update_manual
        if self._update_busy:
            return
        self._update_busy = True

        def work():
            try:
                if getattr(self, "updater", None) is None:
                    self.updater = AutoUpdater()
                self._upd_q.put(("checked", self.updater.check()))
            except Exception as exc:          # never let the checker disturb the IDE
                self._upd_q.put(("checked", None))
                self._upd_q.put(("error", str(exc)))
        threading.Thread(target=work, daemon=True, name="veriflow-update-check").start()
        self.after(300, self._poll_updates)

    def check_updates_now(self) -> None:
        self._update_dismissed = ""
        self._check_updates(manual=True)

    def _poll_updates(self) -> None:
        again = True
        while True:
            try:
                kind, data = self._upd_q.get_nowait()
            except queue.Empty:
                break
            if kind == "checked":
                self._update_busy, again = False, False
                if data is not None:
                    self._show_update(data)
                elif self._update_manual:
                    self.toast(f"✔ {APP_NAME} {APP_VERSION} is up to date.", "ok")
                self._update_manual = False
            elif kind == "progress" and self._update_notice is not None:
                self._update_notice.set_status(data)
            elif kind == "installed":
                self._finish_update(data)
                again = False
            elif kind == "failed":
                self._update_busy, again = False, False
                self.log(f"Update failed: {data}", "err")
                if self._update_notice is not None:
                    self._update_notice.set_status(f"Update failed: {data}")
                    self._update_notice.update_btn.configure(state="normal")
            elif kind == "error":
                self.log(f"Update check: {data}", "dim")
        if again:
            self.after(300, self._poll_updates)

    def _show_update(self, info) -> None:
        self._update_info = info
        self.st_update.configure(text=f"🔔 Update v{info.version}")
        self.st_update.grid()
        if self._update_dismissed != info.version:
            self._reopen_update_notice()

    def _reopen_update_notice(self) -> None:
        info = self._update_info
        if info is None:
            return
        if self._update_notice is not None and self._update_notice.winfo_exists():
            self._update_notice.destroy()
        n = UpdateNotice(self, info, self.updater.can_self_update(info), self._apply_update,
                         lambda: webbrowser.open(info.page_url), self._later_update)
        n.place(relx=1.0, rely=1.0, anchor="se", x=-18, y=-int(34 * self.sc))
        n.lift()
        self._update_notice = n

    def _later_update(self) -> None:
        if self._update_info is not None:
            self._update_dismissed = self._update_info.version
        if self._update_notice is not None:
            self._update_notice.destroy()
            self._update_notice = None

    def _apply_update(self) -> None:
        info = self._update_info
        if info is None or self._update_busy:
            return
        if not self.updater.can_self_update(info):          # exe without a matching release asset yet
            webbrowser.open(f"https://github.com/{self.updater.repo}/releases/latest")
            return
        if not self._confirm_discard():
            return
        self._update_busy = True
        self._update_notice.update_btn.configure(state="disabled")
        self._update_notice.set_status("Downloading the update…" if is_frozen() else "Updating the source checkout…")
        q = self._upd_q

        def work():
            try:
                if is_frozen():
                    self.updater.update_frozen(info, progress=lambda n: q.put(("progress", f"Downloading… {n / 1e6:.1f} MB")))
                    q.put(("installed", "exe"))
                else:
                    lines: list[str] = []
                    ok = self.updater.update_source(log=lines.append)
                    q.put(("installed", "source") if ok else ("failed", " ".join(lines)[-300:] or "git pull failed"))
            except Exception as exc:
                q.put(("failed", str(exc)))
        threading.Thread(target=work, daemon=True, name="veriflow-self-update").start()
        self.after(300, self._poll_updates)

    def _finish_update(self, how: str) -> None:
        self.log(f"✔ Updated to v{self._update_info.version} - restarting…", "ok")
        self.runner.stop()
        if self.state() == "normal":
            self.cfg.update(window_geometry=self.geometry())
        if how == "source":
            try:
                subprocess.Popen(AutoUpdater.restart_command(), cwd=str(app_dir()), creationflags=0)
            except OSError as exc:
                messagebox.showinfo(APP_NAME, f"Updated. Please start {APP_NAME} again.\n({exc})", parent=self)
        self.destroy()                      # the frozen helper waits for this process, swaps the .exe and relaunches

    def open_in_npp(self) -> None:
        if not self.module or not self.work_dir:
            return
        self.save_all(quiet=True)
        files = [str(self.work_dir / f"{self.module}.v")]
        tb = self.work_dir / f"{self.module}_tb.v"
        if tb.is_file():
            files.append(str(tb))
        npp = self.cfg["notepad_pp_path"]
        try:
            if Path(npp).is_file():
                subprocess.Popen([npp, *files], creationflags=NO_WINDOW)
            elif IS_MAC:
                for f in files:
                    subprocess.Popen(["open", "-t", f])
            elif IS_WINDOWS:
                for f in files:
                    os.startfile(f)  # type: ignore[attr-defined]
            else:
                raise OSError("No external editor configured")
        except OSError as exc:
            messagebox.showerror("Open in Notepad++", str(exc), parent=self)
            return
        if not self.cfg["live_sync_enabled"]:
            self.cfg.update(live_sync_enabled=True)
            self.log("⚡ Live Notepad++ Sync enabled - save in Notepad++ (Ctrl+S) and VeriFlow re-runs automatically.", "ok")

    def clean(self) -> None:
        if not self.work_dir:
            return
        removed = clean_binaries(self.work_dir)
        self.log(f"🧹 Removed {len(removed)} compiled vvp binar{'y' if len(removed) == 1 else 'ies'}: {', '.join(removed) or '-'}", "ok")
        self.st_msg.configure(text=f"Cleaned {len(removed)} binaries")

    def open_gtkwave(self) -> None:
        gtk = self.cfg["gtkwave_path"]
        if not self.last_vcd:
            messagebox.showinfo("GTKWave", "No .vcd file from the last run. Add $dumpfile/$dumpvars to the testbench "
                                           "(Gen _tb.v does this) and press F5.", parent=self)
            return
        if not Path(gtk).is_file():
            messagebox.showwarning("GTKWave", f"GTKWave not found at\n{gtk}\nSet it in ⚙ Settings → Compiler & Toolchain.", parent=self)
            return
        subprocess.Popen([gtk, self.last_vcd], cwd=str(self.work_dir), creationflags=NO_WINDOW)

    # ================================================================== live sync
    def _restart_sync(self) -> None:
        if self._sync_job:
            self.after_cancel(self._sync_job)
            self._sync_job = None
        if self.cfg["live_sync_enabled"]:
            self._sync_job = self.after(int(self.cfg["external_poll_interval_ms"]), self._sync_tick)

    def _sync_tick(self) -> None:
        self._sync_job = None
        try:
            self.check_external_changes(autorun=True)
            if self._scan_workspace():
                self.log("↻ Workspace files changed - module list refreshed.", "dim")
        finally:
            if self.cfg["live_sync_enabled"]:
                self._sync_job = self.after(int(self.cfg["external_poll_interval_ms"]), self._sync_tick)

    def check_external_changes(self, autorun: bool) -> bool:
        changed = []
        for ed in (self.design_ed, self.tb_ed):
            if not ed.path:
                continue
            p = Path(ed.path)
            key = os.path.normcase(str(p))
            try:
                m = p.stat().st_mtime
            except OSError:
                continue
            if self.known_mtime.get(key) == m:
                continue
            if time.time() - m < 0.15:          # file may still be being written - check again next tick
                continue
            self.known_mtime[key] = m
            try:
                text, nl = read_source(p)
            except OSError:
                continue
            if text == ed.get_content():
                continue
            if ed.is_modified:
                self.log(f"⚠ {p.name} changed on disk but has unsaved edits here - not reloaded (save or revert first).", "warn")
                continue
            ed.newline = nl
            ed.set_content(text, keep_view=True)
            if ed is self.tb_ed and ed.missing:
                ed.set_missing(False)
            changed.append(p.name)
        if changed:
            self.log(f"↻ Reloaded external change: {', '.join(changed)}", "head")
            self.run_lint()
            if autorun and self.cfg["auto_run_on_external_save"] and not self.runner.is_running():
                self.run_pipeline(reason="external save")
        return bool(changed)

    def _on_app_focus_in(self, _e=None) -> None:
        if time.time() - self._last_focus_check < 1.0 or self.cfg["live_sync_enabled"]:
            return
        self._last_focus_check = time.time()
        self.check_external_changes(autorun=False)
        self._scan_workspace()

    def _on_app_focus_out(self, _e=None) -> None:
        if self.cfg["auto_save_on_focus_loss"]:
            self.after(250, self._autosave_if_away)

    def _autosave_if_away(self) -> None:
        try:
            away = self.focus_displayof() is None
        except (KeyError, tk.TclError):
            away = True
        if away and (self.design_ed.is_modified or self.tb_ed.is_modified):
            self.save_all(quiet=True)
            self.st_msg.configure(text="Auto-saved on focus loss")

    # ================================================================== shortcuts / close
    def _bind_shortcuts(self) -> None:
        self.bind_all("<F5>", lambda e: (self.run_pipeline(), "break")[1])
        self.bind_all("<Shift-F5>", lambda e: self.stop_run())
        self.bind_all("<F7>", lambda e: self.run_lint(show=True))
        self.bind("<Control-KeyPress>", self._on_ctrl)
        if IS_MAC:
            self.bind("<Command-KeyPress>", self._on_ctrl)
        self.bind("<FocusIn>", self._on_app_focus_in)
        self.bind("<FocusOut>", self._on_app_focus_out)

    def _on_ctrl(self, e):
        code = e.keycode if IS_WINDOWS else None
        ks = e.keysym.lower()
        if code == 79 or ks == "o":
            self.choose_folder()
        elif code == 78 or ks == "n":
            self.new_project() if e.state & 0x1 else self.new_module()
        elif code == 66 or ks == "b":
            self.toggle_sidebar()
        elif code == 83 or ks == "s":
            self.save_all()
        elif code == 188 or ks == "comma":
            self.open_settings()
        elif code in (187, 107) or ks in ("equal", "plus"):
            self.zoom(1)
        elif code in (189, 109) or ks == "minus":
            self.zoom(-1)
        elif code in (48, 96) or ks == "0":
            self.zoom(0)
        else:
            return None
        return "break"

    def _on_close(self) -> None:
        if not self._confirm_discard():
            return
        self.runner.stop()
        if self.state() == "normal":
            self.cfg.update(window_geometry=self.geometry())
        self.destroy()


def main() -> None:
    if IS_WINDOWS:
        try:   # DPI awareness is handled by customtkinter; this only groups the taskbar icon
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("VeriFlow.Studio")
        except (AttributeError, OSError):
            pass
    app = VeriFlowApp()
    if len(sys.argv) > 1 and Path(sys.argv[1]).is_dir():
        app.after(200, lambda: app.open_workspace(Path(sys.argv[1])))
    app.mainloop()


if __name__ == "__main__":
    main()
