"""VeriFlow Studio - persistent IDE settings, editor colour schemes and toolchain auto-discovery."""
from __future__ import annotations

import copy
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Callable

APP_NAME = "VeriFlow Studio"
APP_VERSION = "1.5.1"
IS_WINDOWS = os.name == "nt"
IS_MAC = sys.platform == "darwin"

if IS_MAC:
    DEFAULT_EDITOR_FONT = "SF Mono"
    DEFAULT_UI_FONT = "SF Pro"
else:
    DEFAULT_EDITOR_FONT = "Consolas"
    DEFAULT_UI_FONT = "Segoe UI"

DEFAULT_CONFIG: dict[str, Any] = {
    "appearance_mode": "Dark",
    "color_theme": "blue",
    "editor_color_scheme": "Dark Modern",
    "ui_scale_percent": 100,
    "editor_font_family": DEFAULT_EDITOR_FONT,
    "editor_font_size": 15,
    "console_font_size": 13,
    "ui_font_size": 13,                 # UI chrome: toolbar, tabs, sidebar, menus, tables, status bar, diagrams
    "tab_size": 4,
    "insert_spaces_for_tabs": True,
    "word_wrap": False,
    "highlight_current_line": True,
    "auto_indent": True,
    "auto_close_brackets_and_blocks": True,
    "editor_split_layout": "Side-by-Side",
    "auto_save_before_run": True,
    "auto_save_on_focus_loss": False,
    "auto_run_on_external_save": True,
    "external_poll_interval_ms": 800,
    "iverilog_path": "" if IS_MAC else "C:\\iverilog\\bin\\iverilog.exe",
    "vvp_path": "" if IS_MAC else "C:\\iverilog\\bin\\vvp.exe",
    "gtkwave_path": "" if IS_MAC else "C:\\iverilog\\gtkwave\\bin\\gtkwave.exe",
    "lib_dir": "" if IS_MAC else "C:\\iverilog\\compstruct\\lib",
    "notepad_pp_path": "" if IS_MAC else "C:\\Program Files\\Notepad++\\notepad++.exe",
    "std_flag": "-g2012",
    "include_workdir_as_ylib": True,
    "enable_wall_warnings": True,
    "vvp_non_interactive_flag": True,
    "sim_timeout_sec": 3.0,
    "enable_course_linter": True,
    "strict_gate_level_mode": False,
    "default_radix": "Binary",
    "last_workspace_dir": "",
    "recent_workspaces": [],
    # --- additions beyond the base schema (UI state) ---
    "live_sync_enabled": False,
    "last_module": "",
    "window_geometry": "1480x900",
    "sidebar_visible": True,
    "sidebar_view": "explorer",
    "ui_revision": 0,
    # --- global Verilog package manager ("import once, resolve anywhere")
    "global_packages_dir": str(Path.home() / ".veriflow_studio" / "packages"),
    "library_packages": [
        {"name": "Course Built-in Library", "path": "" if IS_MAC else "C:\\iverilog\\compstruct\\lib",
         "enabled": True, "builtin": True, "kind": "builtin"},
    ],
    "auto_resolve_packages_with_l_flag": True,
    "live_check_on_save": True,          # background `iverilog -tnull` after every save
    # --- startup & updates
    "startup_mode": "welcome_screen",    # welcome_screen | reopen_last | empty_window
    "last_parent_dir": "",               # where the New Module / Project wizard saved last time
    "check_for_updates": True,
    "live_autocomplete": True,           # IntelliSense pops up while typing (Ctrl+Space always works)           # GitHub release + main/version.json, on startup and every 30 min
}
BUILTIN_PACKAGE_NAME = "Course Built-in Library (compstruct\\lib)"

# Allowed values / numeric clamps, used to sanitise a hand-edited or stale config.json.
CHOICES: dict[str, tuple] = {
    "appearance_mode": ("Dark", "Light", "System"),
    "color_theme": ("blue", "green", "dark-blue"),
    "editor_color_scheme": ("Dark Modern", "Light Modern", "One Dark", "Monokai", "GitHub Light", "High Contrast"),
    "ui_scale_percent": (80, 90, 100, 110, 125, 150),
    "tab_size": (2, 4, 8),
    "editor_split_layout": ("Side-by-Side", "Tabbed"),
    "std_flag": ("-g2012", "-g2005-sv", "-g2005", "-g2001"),
    "default_radix": ("Binary", "Hex", "Unsigned Dec", "Signed Dec"),
    "sidebar_view": ("explorer", "library", "run"),
    "startup_mode": ("welcome_screen", "reopen_last", "empty_window"),
}
STARTUP_LABELS = {"welcome_screen": "Show the Welcome screen", "reopen_last": "Reopen the last folder",
                  "empty_window": "Empty window"}
RANGES: dict[str, tuple[float, float]] = {
    "editor_font_size": (10, 32),
    "console_font_size": (10, 28),
    "ui_font_size": (10, 24),
    "sim_timeout_sec": (1.0, 30.0),
    "external_poll_interval_ms": (500, 3000),
}
FONT_FAMILIES = (("SF Mono", "Menlo", "Monaco", "JetBrains Mono", "Courier") if IS_MAC
                 else ("Consolas", "Cascadia Code", "JetBrains Mono", "Courier New", "Lucida Console"))
UI_FAMILY, MONO_FAMILY = (DEFAULT_UI_FONT, DEFAULT_EDITOR_FONT)
# "UI & Text Size" presets: (ui_font_size, editor_font_size, console_font_size)
TEXT_SIZE_PRESETS = {
    "Compact (12pt)": (12, 13, 12),
    "Comfortable (14-15pt)": (13, 15, 13),
    "Large / High-Visibility (17pt)": (15, 17, 15),
    "Extra Large (20pt)": (18, 20, 18),
}
RADIXES = CHOICES["default_radix"]

# --------------------------------------------------------------------------- VS Code workbench chrome
VSCODE_THEMES: dict[str, dict[str, str]] = {
    "Dark": {   # VS Code "Dark Modern"
        "activity": "#181818", "activity_fg": "#858585", "activity_active": "#FFFFFF", "accent": "#007ACC",
        "sidebar": "#181818", "sidebar_header": "#CCCCCC", "hover": "#2A2D2E", "selected": "#04395E", "selected_fg": "#FFFFFF",
        "toolbar": "#181818", "border": "#2B2B2B", "editor": "#1E1E1E", "tabstrip": "#181818", "tab_active": "#1E1E1E",
        "tab_active_fg": "#FFFFFF", "tab_inactive": "#2D2D2D", "tab_inactive_fg": "#969696", "breadcrumb_fg": "#BBBBBB",
        "panel": "#181818", "panel_content": "#1E1E1E", "text": "#CCCCCC", "muted": "#858585", "group": "#252526",
        "group_border": "#3C3C3C", "input": "#313131", "input_border": "#3C3C3C", "badge": "#4D4D4D", "badge_fg": "#FFFFFF",
        "scroll_thumb": "#424242", "scroll_hover": "#4F4F4F", "table_head": "#252526", "table_row": "#1E1E1E",
        "table_alt": "#222222", "table_fg": "#CCCCCC", "table_head_fg": "#CCCCCC", "ready_dot": "#4EC9B0", "warn_dot": "#CCA700",
    },
    "Light": {  # VS Code "Light Modern"
        "activity": "#F8F8F8", "activity_fg": "#616161", "activity_active": "#1F1F1F", "accent": "#005FB8",
        "sidebar": "#F8F8F8", "sidebar_header": "#3B3B3B", "hover": "#F2F2F2", "selected": "#E4E6F1", "selected_fg": "#000000",
        "toolbar": "#F8F8F8", "border": "#E5E5E5", "editor": "#FFFFFF", "tabstrip": "#F8F8F8", "tab_active": "#FFFFFF",
        "tab_active_fg": "#3B3B3B", "tab_inactive": "#F8F8F8", "tab_inactive_fg": "#868686", "breadcrumb_fg": "#4D4D4D",
        "panel": "#F8F8F8", "panel_content": "#FFFFFF", "text": "#3B3B3B", "muted": "#767676", "group": "#FFFFFF",
        "group_border": "#CECECE", "input": "#FFFFFF", "input_border": "#CECECE", "badge": "#CCCCCC", "badge_fg": "#1F1F1F",
        "scroll_thumb": "#C1C1C1", "scroll_hover": "#A8A8A8", "table_head": "#F3F3F3", "table_row": "#FFFFFF",
        "table_alt": "#FAFAFA", "table_fg": "#3B3B3B", "table_head_fg": "#3B3B3B", "ready_dot": "#16825D", "warn_dot": "#BF8803",
    },
}
# (light, dark) tuples - customtkinter switches them automatically with the appearance mode
VS: dict[str, tuple[str, str]] = {k: (VSCODE_THEMES["Light"][k], VSCODE_THEMES["Dark"][k]) for k in VSCODE_THEMES["Dark"]}
STATUS_COLORS = {"ready": "#007ACC", "running": "#CC6633", "error": "#A1260D"}
RUN_GREEN, RUN_GREEN_HOVER, STOP_RED, STOP_RED_HOVER = "#2EA043", "#3FB950", "#C93C37", "#E5534B"
UI_REVISION = 3      # bump to migrate stored settings after a visual redesign (3 = comfortable typography)

# --------------------------------------------------------------------------- editor colour schemes
EDITOR_SCHEMES: dict[str, dict[str, str]] = {
    "Dark Modern": {   # VS Code Dark+ token colours
        "dark": "1", "bg": "#1E1E1E", "fg": "#D4D4D4", "gutter_bg": "#1E1E1E", "gutter_fg": "#858585",
        "gutter_active": "#C6C6C6", "current_line": "#282828", "selection": "#264F78", "cursor": "#AEAFAD",
        "keyword": "#569CD6", "control": "#C586C0", "type": "#4EC9B0", "gate": "#DCDCAA", "number": "#B5CEA8",
        "string": "#CE9178", "comment": "#6A9955", "directive": "#C586C0", "systask": "#C586C0", "operator": "#D4D4D4",
        "punct": "#D4D4D4", "ident": "#9CDCFE", "error_bg": "#4B1818", "warning_bg": "#3D3313", "find_bg": "#613214",
        "console_bg": "#1E1E1E", "console_fg": "#CCCCCC",
    },
    "Light Modern": {  # VS Code Light+ token colours
        "dark": "", "bg": "#FFFFFF", "fg": "#3B3B3B", "gutter_bg": "#FFFFFF", "gutter_fg": "#6E7681",
        "gutter_active": "#171184", "current_line": "#F5F5F5", "selection": "#ADD6FF", "cursor": "#000000",
        "keyword": "#0000FF", "control": "#AF00DB", "type": "#267F99", "gate": "#795E26", "number": "#098658",
        "string": "#A31515", "comment": "#008000", "directive": "#AF00DB", "systask": "#AF00DB", "operator": "#3B3B3B",
        "punct": "#3B3B3B", "ident": "#001080", "error_bg": "#FFE0E0", "warning_bg": "#FFF5CC", "find_bg": "#F8C9AB",
        "console_bg": "#FFFFFF", "console_fg": "#3B3B3B",
    },
    "One Dark": {
        "dark": "1", "bg": "#1E1E2E", "fg": "#ABB2BF", "gutter_bg": "#181825", "gutter_fg": "#5C6370",
        "gutter_active": "#E5C07B", "current_line": "#2A2B3D", "selection": "#3E4451", "cursor": "#528BFF",
        "keyword": "#C678DD", "type": "#E5C07B", "gate": "#56B6C2", "number": "#D19A66", "string": "#98C379",
        "comment": "#7F848E", "directive": "#E06C75", "systask": "#61AFEF", "operator": "#56B6C2",
        "punct": "#ABB2BF", "error_bg": "#4B1F27", "warning_bg": "#4A3B12", "find_bg": "#5A4A16",
        "console_bg": "#14141F", "console_fg": "#C8CCD4",
    },
    "Monokai": {
        "dark": "1", "bg": "#272822", "fg": "#F8F8F2", "gutter_bg": "#1F201B", "gutter_fg": "#75715E",
        "gutter_active": "#E6DB74", "current_line": "#3A3B32", "selection": "#49483E", "cursor": "#F8F8F0",
        "keyword": "#F92672", "type": "#66D9EF", "gate": "#A6E22E", "number": "#AE81FF", "string": "#E6DB74",
        "comment": "#88846F", "directive": "#FD971F", "systask": "#66D9EF", "operator": "#F92672",
        "punct": "#F8F8F2", "error_bg": "#5A1E28", "warning_bg": "#55481A", "find_bg": "#6B5B1C",
        "console_bg": "#1E1F1A", "console_fg": "#F8F8F2",
    },
    "GitHub Light": {
        "dark": "", "bg": "#FFFFFF", "fg": "#24292F", "gutter_bg": "#F6F8FA", "gutter_fg": "#8C959F",
        "gutter_active": "#0969DA", "current_line": "#F1F5FB", "selection": "#B6D7FF", "cursor": "#0969DA",
        "keyword": "#CF222E", "type": "#953800", "gate": "#0550AE", "number": "#0550AE", "string": "#0A3069",
        "comment": "#6E7781", "directive": "#8250DF", "systask": "#8250DF", "operator": "#CF222E",
        "punct": "#24292F", "error_bg": "#FFE1E1", "warning_bg": "#FFF4CC", "find_bg": "#FFE58F",
        "console_bg": "#FAFBFC", "console_fg": "#24292F",
    },
    "High Contrast": {
        "dark": "1", "bg": "#090D16", "fg": "#FFFFFF", "gutter_bg": "#000000", "gutter_fg": "#9DA5B4",
        "gutter_active": "#FFFF00", "current_line": "#1B2335", "selection": "#264F78", "cursor": "#FFFF00",
        "keyword": "#FF79C6", "type": "#FFD700", "gate": "#00FFFF", "number": "#B5FF6B", "string": "#7CFC00",
        "comment": "#9AA5B1", "directive": "#FF8C42", "systask": "#6CB6FF", "operator": "#FFFFFF",
        "punct": "#FFFFFF", "error_bg": "#6E0A1E", "warning_bg": "#5C4A00", "find_bg": "#7A6A00",
        "console_bg": "#000000", "console_fg": "#FFFFFF",
    },
}
LIGHT_SCHEME, DARK_SCHEME = "Light Modern", "Dark Modern"
ACCENT = {"run": "#10B981", "run_hover": "#059669", "stop": "#EF4444", "stop_hover": "#DC2626",
          "ok": "#10B981", "warn": "#F59E0B", "err": "#EF4444", "info": "#60A5FA"}


def resource_dir() -> Path:
    """Folder that holds bundled resources (PyInstaller-aware)."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def config_path() -> Path:
    if IS_MAC:
        base = Path.home() / "Library" / "Application Support" / "VeriFlowStudio"
    else:
        base = Path(os.environ.get("APPDATA") or Path.home() / ".config") / "VeriFlowStudio"
    return base / "config.json"


def _first_existing(*cands: str | Path | None) -> str:
    for c in cands:
        if c and Path(c).is_file():
            return str(c)
    return ""


def detect_toolchains() -> dict[str, str]:
    """Locate iverilog/vvp/gtkwave/external editor and the lecturer library. Empty string = not found."""
    if IS_MAC:
        which_iv = shutil.which("iverilog")
        which_vvp = shutil.which("vvp")
        gtkwave = _first_existing(
            shutil.which("gtkwave"),
            "/Applications/gtkwave.app/Contents/Resources/bin/gtkwave",
            "/opt/homebrew/bin/gtkwave",
            "/usr/local/bin/gtkwave",
        )
        iverilog = _first_existing(which_iv, "/opt/homebrew/bin/iverilog", "/usr/local/bin/iverilog")
        vvp = _first_existing(which_vvp, "/opt/homebrew/bin/vvp", "/usr/local/bin/vvp")
        lib_candidates = (
            Path("/opt/homebrew/share/iverilog"),
            Path("/usr/local/share/iverilog"),
            Path.home() / "iverilog" / "lib",
        )
        lib = next((str(p) for p in lib_candidates if p.is_dir()), "")
        return {"iverilog_path": iverilog, "vvp_path": vvp, "gtkwave_path": gtkwave,
                "notepad_pp_path": "", "lib_dir": lib}
    pf, pf86 = os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    which_iv = shutil.which("iverilog")
    bin_dirs = [Path(r"C:\iverilog\bin"), Path(pf) / "iverilog" / "bin"]
    if which_iv:
        bin_dirs.insert(0, Path(which_iv).parent)
    exe = ".exe" if IS_WINDOWS else ""
    iverilog = _first_existing(*(d / f"iverilog{exe}" for d in bin_dirs), which_iv)
    root = Path(iverilog).parent.parent if iverilog else Path(r"C:\iverilog")
    vvp = _first_existing(Path(iverilog).with_name(f"vvp{exe}") if iverilog else None,
                          *(d / f"vvp{exe}" for d in bin_dirs), shutil.which("vvp"))
    gtkwave = _first_existing(root / "gtkwave" / "bin" / f"gtkwave{exe}", root / "bin" / f"gtkwave{exe}", shutil.which("gtkwave"))
    npp = _first_existing(Path(pf) / "Notepad++" / "notepad++.exe", Path(pf86) / "Notepad++" / "notepad++.exe",
                          r"C:\Program Files\Notepad++\notepad++.exe", r"C:\Program Files (x86)\Notepad++\notepad++.exe",
                          shutil.which("notepad++"))
    lib = next((str(p) for p in (root / "compstruct" / "lib", Path(r"C:\iverilog\compstruct\lib")) if p.is_dir()), "")
    return {"iverilog_path": iverilog, "vvp_path": vvp, "gtkwave_path": gtkwave, "notepad_pp_path": npp, "lib_dir": lib}


class ConfigManager:
    """Dict-like settings store with validation, atomic persistence and live-apply listeners."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else config_path()
        self.data: dict[str, Any] = copy.deepcopy(DEFAULT_CONFIG)
        self._listeners: list[Callable[[set[str]], None]] = []
        self.load()

    # ---- persistence
    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for k, v in raw.items():
                    if k in DEFAULT_CONFIG:
                        self.data[k] = self._sanitize(k, v)
        except (OSError, ValueError):
            pass
        if self.data["ui_revision"] < UI_REVISION:      # 1.0 -> VS Code look: move old default schemes to Dark+/Light+
            self.data["editor_color_scheme"] = {"One Dark": DARK_SCHEME, "GitHub Light": LIGHT_SCHEME}.get(
                self.data["editor_color_scheme"], self.data["editor_color_scheme"])
            # v1.4 comfortable typography (runs once): lift sizes saved under the old, too-small defaults
            if self.data["editor_font_size"] < 14:
                self.data["editor_font_size"] = 15
            if self.data["console_font_size"] < 13:
                self.data["console_font_size"] = 13
            self.data["ui_font_size"] = max(self.data["ui_font_size"], 13)
            self.data["ui_revision"] = UI_REVISION
            self.save()
        if not Path(self.data["iverilog_path"]).is_file():      # first run on a non-default install
            found = detect_toolchains()
            for k, v in found.items():
                if v and not Path(str(self.data[k])).exists():
                    self.data[k] = v

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            pass

    @staticmethod
    def _sanitize_packages(value: Any) -> list[dict]:
        """library_packages: keep well-formed entries, exactly one built-in entry, unique names."""
        out, seen = [], set()
        for item in value if isinstance(value, list) else []:
            if not isinstance(item, dict) or not item.get("name") or not item.get("path"):
                continue
            kind = str(item.get("kind") or ("builtin" if item.get("builtin") else "linked"))
            if kind not in ("builtin", "vault", "linked") or str(item["name"]) in seen:
                continue
            if kind == "builtin" and any(p["kind"] == "builtin" for p in out):
                continue
            seen.add(str(item["name"]))
            excluded = sorted({str(x) for x in item.get("excluded_modules") or [] if isinstance(x, str) and x})
            out.append({"name": str(item["name"]), "path": str(item["path"]), "enabled": bool(item.get("enabled", True)),
                        "builtin": kind == "builtin", "kind": kind, "excluded_modules": excluded})
        if not any(p["kind"] == "builtin" for p in out):
            out.insert(0, copy.deepcopy(DEFAULT_CONFIG["library_packages"][0]))
        return out

    @staticmethod
    def _sanitize(key: str, value: Any) -> Any:
        if key == "library_packages":
            return ConfigManager._sanitize_packages(value)
        default = DEFAULT_CONFIG[key]
        try:
            if isinstance(default, bool):
                value = bool(value)
            elif isinstance(default, int):
                value = int(value)
            elif isinstance(default, float):
                value = float(value)
            elif isinstance(default, list):
                value = [str(v) for v in value] if isinstance(value, list) else []
            elif isinstance(default, str):
                value = str(value)
        except (TypeError, ValueError):
            return copy.deepcopy(default)
        if key in CHOICES and value not in CHOICES[key]:
            return copy.deepcopy(default)
        if key in RANGES:
            lo, hi = RANGES[key]
            value = type(default)(min(max(value, lo), hi))
        return value

    # ---- access
    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def __getattr__(self, key: str) -> Any:      # config.std_flag, config.lib_dir ...
        data = self.__dict__.get("data")
        if data is not None and key in data:
            return data[key]
        raise AttributeError(key)

    def update(self, **changes: Any) -> set[str]:
        changed = set()
        for k, v in changes.items():
            if k not in DEFAULT_CONFIG:
                continue
            v = self._sanitize(k, v)
            if self.data.get(k) != v:
                self.data[k] = v
                changed.add(k)
        if changed:
            self.save()
            for cb in list(self._listeners):
                try:
                    cb(changed)
                except Exception as exc:  # a broken listener must never break settings
                    print(f"[config] listener error: {exc}", file=sys.stderr)
        return changed

    def set(self, key: str, value: Any) -> bool:
        return bool(self.update(**{key: value}))

    def subscribe(self, callback: Callable[[set[str]], None]) -> None:
        self._listeners.append(callback)

    def reset(self, keys: list[str] | None = None) -> set[str]:
        keep = {"last_workspace_dir", "recent_workspaces", "last_module", "window_geometry", "last_parent_dir",
                "library_packages", "global_packages_dir"}      # a settings reset never forgets imported packages
        keys = keys or [k for k in DEFAULT_CONFIG if k not in keep]
        return self.update(**{k: copy.deepcopy(DEFAULT_CONFIG[k]) for k in keys})

    def add_recent_workspace(self, folder: str | Path) -> None:
        folder = str(Path(folder))
        recents = [r for r in self.data["recent_workspaces"] if os.path.normcase(r) != os.path.normcase(folder)]
        self.update(last_workspace_dir=folder, recent_workspaces=[folder, *recents][:10])

    # ---- derived helpers
    @property
    def scheme(self) -> dict[str, str]:
        return EDITOR_SCHEMES.get(self.data["editor_color_scheme"], EDITOR_SCHEMES[DARK_SCHEME])

    def toolchain_status(self) -> dict[str, bool]:
        return {"iverilog": Path(self.data["iverilog_path"]).is_file(), "vvp": Path(self.data["vvp_path"]).is_file(),
                "gtkwave": Path(self.data["gtkwave_path"]).is_file(), "lib": Path(self.data["lib_dir"]).is_dir(),
                "notepad_pp": Path(self.data["notepad_pp_path"]).is_file()}

    def toolchain_available(self) -> bool:
        st = self.toolchain_status()
        return st["iverilog"] and st["vvp"]

    def get_all_enabled_library_dirs(self) -> list[Path]:
        """Every enabled package folder that exists, in -y priority order: imported/linked packages first,
        the built-in course library last (the workspace itself is added before all of these by the runner)."""
        out = []
        for p in sorted(self.data["library_packages"], key=lambda q: q["kind"] == "builtin"):
            path = Path(self.data["lib_dir"]) if p["kind"] == "builtin" else Path(p["path"])
            if p["enabled"] and path.is_dir() and all(os.path.normcase(str(path)) != os.path.normcase(str(o)) for o in out):
                out.append(path)
        return out
