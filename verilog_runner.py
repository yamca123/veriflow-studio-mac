"""VeriFlow Studio - threaded iverilog/vvp pipeline, Windows-safe diagnostics parser, truth-table parser,
and a pure-Python gate-level fallback simulator (demo mode when Icarus Verilog is not installed)."""
from __future__ import annotations

import itertools
import locale
import os
import queue
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from verilog_parser import LINT_GATES, parse_verilog_module, strip_comments

IS_WINDOWS = os.name == "nt"
NO_WINDOW = subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0
COMPILE_TIMEOUT_SEC = 30.0

DIAG_REGEX = re.compile(
    r"^((?:[a-zA-Z]:[\\/])?[^:\r\n]+):(\d+)(?::(\d+))?:\s*(error|warning|syntax error|sorry|note)\b[:\s]*(.*)$",
    re.IGNORECASE,
)
# 'FullAdder.v:1: errors in port declarations.' - a location without a severity keyword
LOC_ONLY_REGEX = re.compile(r"^((?:[a-zA-Z]:[\\/])?[^:\r\n]+\.s?vh?):(\d+)(?::(\d+))?:\s*(.+)$", re.IGNORECASE)
VVP_DIAG_REGEX = re.compile(r"^(ERROR|WARNING|FATAL|Error|Warning)\s*:\s*((?:[a-zA-Z]:[\\/])?[^:\r\n]+):(\d+):\s*(.*)$")
STANDALONE_ERRORS = re.compile(
    r"^(I give up\.?|No top level modules.*|\d+ error\(s\).*|\*\*\* These modules were missing.*|.*: No such file or directory|"
    r"Unable to open .*|.*: Unable to open input file.*|Error: .*|.*internal error.*)$", re.IGNORECASE)
SIM_META = re.compile(r"^(VCD info:|VCD warning:|.*\$finish called at|.*\$stop called at|\*\* VVP Stop|"
                      r"\*\* Continue|Simulation (stopped|finished)|.*\(\d+\w*s\)$)", re.IGNORECASE)
FAIL_RE = re.compile(r"\b(FAIL\w*|ERROR|MISMATCH\w*)\b", re.IGNORECASE)
KV_RE = re.compile(r"([A-Za-z_][\w.\[\]:]*)\s*=\s*([^\s|,;=]+)")
VALUE_RE = re.compile(r"^[0-9a-fA-FxXzZ_?'\-]+$")
STATUS_OK, STATUS_XZ, STATUS_FAIL = "OK", "FLOATING/CONFLICT (x/z)", "FAIL"


@dataclass
class RunEvent:
    kind: str                      # STAGE_START | COMPILE_DONE | SIM_DONE | TIMEOUT | ERROR | FINISHED
    payload: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- helpers
def decode_output(raw: bytes | None) -> str:
    if not raw:
        return ""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode(locale.getpreferredencoding(False) or "cp1252", errors="replace")


def is_vvp_binary(path: Path) -> bool:
    """Extensionless compiled vvp image ('#! .../vvp' header)."""
    try:
        if not (path.is_file() and path.suffix == ""):
            return False
        with path.open("rb") as fh:
            head = fh.read(64)
        return head.startswith(b"#!") or b"vvp" in head
    except OSError:
        return False


def clean_binaries(work_dir: Path | str, include_vcd: bool = False) -> list[str]:
    removed = []
    for p in Path(work_dir).iterdir():
        if is_vvp_binary(p) or (include_vcd and p.suffix.lower() == ".vcd"):
            try:
                p.unlink()
                removed.append(p.name)
            except OSError:
                pass
    return removed


def kill_process_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if IS_WINDOWS:
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW, timeout=10)
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        proc.kill()
    except OSError:
        pass


def format_cmd(cmd: list[str], strip_exe: bool = True) -> str:
    out = []
    for i, a in enumerate(cmd):
        if i == 0 and strip_exe and a.lower().endswith(".exe"):
            a = a[:-4]
        out.append(f'"{a}"' if (" " in a or not a) and not a.startswith('"') else a)
    return " ".join(out)


def parse_compiler_output(text: str, work_dir: Path | str | None = None) -> list[dict]:
    """Parse iverilog / vvp output into diagnostics (handles C:\\ drive letters and :line:col)."""
    diags: list[dict] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        m = DIAG_REGEX.match(line.strip())
        if m:
            kind = m.group(4).lower()
            sev = "warning" if kind == "warning" else "info" if kind == "note" else "error"
            msg = m.group(5).strip() or ("syntax error" if kind == "syntax error" else kind)
            if kind == "syntax error":
                msg = "syntax error" + (f": {msg}" if msg != "syntax error" else "")
            elif kind == "sorry":
                msg = f"sorry (unsupported by iverilog): {msg}"
            diags.append({"file": _resolve(m.group(1).strip(), work_dir), "line": int(m.group(2)),
                          "col": int(m.group(3) or 0), "severity": sev, "code": kind.replace(" ", "-"),
                          "message": msg, "source": "iverilog", "raw": line})
            continue
        m = VVP_DIAG_REGEX.match(line.strip())
        if m:
            sev = "warning" if m.group(1).lower() == "warning" else "error"
            diags.append({"file": _resolve(m.group(2).strip(), work_dir), "line": int(m.group(3)), "col": 0,
                          "severity": sev, "code": "vvp", "message": m.group(4).strip(), "source": "vvp", "raw": line})
            continue
        m = LOC_ONLY_REGEX.match(line.strip())
        if m and not m.group(4).lstrip().startswith("$"):     # '$finish called at 90 (1s)' is a notice, not an error
            msg = m.group(4).strip()
            sev = "warning" if "warn" in msg.lower() else "error"
            diags.append({"file": _resolve(m.group(1).strip(), work_dir), "line": int(m.group(2)), "col": int(m.group(3) or 0),
                          "severity": sev, "code": "iverilog", "message": msg, "source": "iverilog", "raw": line})
            continue
        if line[:1].isspace() and diags and line.strip().startswith(":"):
            diags[-1]["message"] += " " + line.strip().lstrip(": ").strip()
            continue
        if STANDALONE_ERRORS.match(line.strip()):
            diags.append({"file": "", "line": 0, "col": 0, "severity": "error", "code": "fatal",
                          "message": line.strip(), "source": "iverilog", "raw": line})
    return diags


def _resolve(name: str, work_dir: Path | str | None) -> str:
    p = Path(name)
    if not p.is_absolute() and work_dir:
        p = Path(work_dir) / p
    return str(p)


def compile_failed(rc: int, text: str, diags: list[dict]) -> bool:
    low = text.lower()
    return (rc != 0 or any(d["severity"] == "error" for d in diags) or "error:" in low
            or "syntax error" in low or "i give up" in low)


# --------------------------------------------------------------------------- truth table parsing
def parse_sim_output(text: str, outputs: set[str] | None = None) -> dict:
    """Turn $monitor/$display text into a table. Supports 'a=0 b=1 | s=1' and pipe/space tabular output."""
    kv_rows: list[tuple[list[tuple[str, str]], str]] = []
    tab_lines: list[str] = []
    messages, fail_messages = [], []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or SIM_META.match(line):
            continue
        pairs = KV_RE.findall(line)
        if len(pairs) >= 2 or (len(pairs) == 1 and "|" in line):
            kv_rows.append((pairs, line))
        else:
            tab_lines.append(line)
            if FAIL_RE.search(line):
                fail_messages.append(line)
            else:
                messages.append(line)
    columns: list[str] = []
    rows: list[dict] = []
    if kv_rows:
        for pairs, _ in kv_rows:
            for k, _v in pairs:
                if k not in columns:
                    columns.append(k)
        for pairs, line in kv_rows:
            d = dict(pairs)
            rows.append({"values": [d.get(c, "") for c in columns], "line": line})
    else:
        header, width = None, 0
        for line in tab_lines:
            if re.fullmatch(r"[-=+|:\s]+", line):
                continue
            cells = [c for c in re.split(r"\s*\|\s*|\s+", line.strip("| ")) if c]
            if not cells:
                continue
            is_values = all(VALUE_RE.match(c) for c in cells)
            if header is None and not is_values and all(re.fullmatch(r"[A-Za-z_][\w\[\]:.]*", c) for c in cells):
                header, width = cells, len(cells)
                continue
            if is_values and (width == 0 or len(cells) == width):
                width = width or len(cells)
                rows.append({"values": cells, "line": line})
        columns = header or [f"c{i}" for i in range(width)]
        if header is None and rows:
            columns = [f"col{i + 1}" for i in range(width)]
        messages = [m for m in messages if not any(m == r["line"] for r in rows) and (header is None or m.split() != header)]
    out_idx = [i for i, c in enumerate(columns) if outputs and c.split("[")[0] in outputs] or list(range(len(columns)))
    counts = {STATUS_OK: 0, STATUS_XZ: 0, STATUS_FAIL: 0}
    for r in rows:
        if FAIL_RE.search(r["line"]):
            r["status"] = STATUS_FAIL
        elif any(re.search(r"[xXzZ]", r["values"][i]) for i in out_idx if i < len(r["values"]) and not r["values"][i].lower().startswith("0x")):
            r["status"] = STATUS_XZ
        else:
            r["status"] = STATUS_OK
        counts[r["status"]] += 1
    return {"columns": columns, "rows": rows, "messages": messages, "fail_messages": fail_messages,
            "counts": counts, "outputs": [columns[i] for i in out_idx] if outputs else []}


def find_vcd(work_dir: Path, tb_path: Path | None, since: float) -> Path | None:
    if tb_path and tb_path.is_file():
        try:
            m = re.search(r'\$dumpfile\s*\(\s*"([^"]+)"', strip_comments(tb_path.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            m = None
        if m:
            p = Path(m.group(1))
            p = p if p.is_absolute() else work_dir / p
            if p.is_file() and p.stat().st_mtime >= since - 1:
                return p
    fresh = [p for p in work_dir.glob("*.vcd") if p.stat().st_mtime >= since - 1]
    return max(fresh, key=lambda p: p.stat().st_mtime) if fresh else None


# --------------------------------------------------------------------------- demo-mode simulator
class _Expr:
    """Tiny 4-state evaluator for continuous-assign expressions: ~ ! & | ^ ~^ ( ) ?: and 1'b0/1'b1."""
    TOK = re.compile(r"\s*(~\^|\^~|~&|~\||[~!&|^()?:]|1'b[01xz]|[01]|[A-Za-z_]\w*)")

    def __init__(self, text: str):
        self.toks, pos = [], 0
        text = text.strip()
        while pos < len(text):
            m = self.TOK.match(text, pos)
            if not m or m.end() == pos:
                raise ValueError(f"unsupported expression: {text!r}")
            self.toks.append(m.group(1))
            pos = m.end()
        self.names = {t for t in self.toks if re.fullmatch(r"[A-Za-z_]\w*", t)}

    def eval(self, env: dict[str, str]) -> str:
        self.i = 0
        v = self._ternary(env)
        return v

    def _peek(self) -> str | None:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def _take(self) -> str:
        self.i += 1
        return self.toks[self.i - 1]

    def _ternary(self, env):
        c = self._or(env)
        if self._peek() == "?":
            self._take()
            a = self._ternary(env)
            self._take()
            b = self._ternary(env)
            return a if c == "1" else b if c == "0" else (a if a == b else "x")
        return c

    def _bin(self, env, sub, ops):
        v = sub(env)
        while self._peek() in ops:
            op = self._take()
            v = gate_eval({"|": "or", "&": "and", "^": "xor", "~^": "xnor", "^~": "xnor"}[op], [v, sub(env)])
        return v

    def _or(self, env):
        return self._bin(env, self._xor, ("|",))

    def _xor(self, env):
        return self._bin(env, self._and, ("^", "~^", "^~"))

    def _and(self, env):
        return self._bin(env, self._unary, ("&",))

    def _unary(self, env):
        t = self._take()
        if t in ("~", "!"):
            return gate_eval("not", [self._unary(env)])
        if t == "(":
            v = self._ternary(env)
            self._take()
            return v
        if t.startswith("1'b"):
            return t[-1]
        if t in ("0", "1"):
            return t
        return env.get(t, "z")


def gate_eval(kind: str, ins: list[str]) -> str:
    ins = ["x" if v == "z" else v for v in ins]
    if kind in ("and", "nand"):
        r = "0" if "0" in ins else "1" if all(v == "1" for v in ins) else "x"
    elif kind in ("or", "nor"):
        r = "1" if "1" in ins else "0" if all(v == "0" for v in ins) else "x"
    elif kind in ("xor", "xnor"):
        r = "x" if "x" in ins else str(sum(v == "1" for v in ins) % 2)
    else:                                          # buf / not
        r = ins[0]
    if kind in ("nand", "nor", "xnor", "not"):
        r = {"0": "1", "1": "0"}.get(r, "x")
    return r


def mock_simulate(design_path: Path, text: str | None = None, max_inputs: int = 10) -> tuple[bool, str]:
    """Exhaustive Python simulation of a scalar gate-level design (primitives + simple assigns)."""
    info = parse_verilog_module(design_path, text)
    if not info.get("module_name"):
        return False, f"[demo] cannot parse {design_path.name}: {info.get('error')}"
    ins = [p for p in info["ports"] if p["direction"] == "input"]
    outs = [p for p in info["ports"] if p["direction"] != "input"]
    if any(p["bits"] != 1 for p in info["ports"]):
        return False, "[demo] the built-in simulator supports 1-bit ports only - install Icarus Verilog for bus designs"
    if len(ins) > max_inputs:
        return False, f"[demo] {len(ins)} inputs is too many for exhaustive demo simulation"
    gates = []
    for inst in info["instantiations"]:
        if inst["type"] not in LINT_GATES:
            return False, (f"[demo] instance '{inst['type']}' needs the real toolchain (lecturer modules are resolved by "
                           f"iverilog -y). Install Icarus Verilog to C:\\iverilog to simulate it.")
        if any(not re.fullmatch(r"[A-Za-z_]\w*|1'b[01]", c) for c in inst["positional"]):
            return False, "[demo] bit-selects/expressions in gate terminals need the real toolchain"
        gates.append(inst)
    body = info["_code"][info["body_start"]:info["body_end"]]
    if re.search(r"(?<![\w$])(always|initial)\b", body):
        return False, "[demo] behavioral always/initial blocks need the real toolchain"
    assigns = []
    for m in re.finditer(r"(?<![\w$])assign\s+([A-Za-z_]\w*)\s*=\s*([^;]+);", body):
        try:
            assigns.append((m.group(1), _Expr(m.group(2))))
        except ValueError as exc:
            return False, f"[demo] {exc}"
    lines = [" | ".join(p["name"] for p in ins + outs), "-" * 24]
    for combo in itertools.product("01", repeat=len(ins)):
        env = {p["name"]: v for p, v in zip(ins, combo)}
        for _ in range(64):
            changed = False
            for g in gates:
                terms = [t[-1] if t.startswith("1'b") else t for t in g["positional"]]
                vals = [env.get(t, t if t in ("0", "1") else "z") for t in terms]
                if g["type"] in ("not", "buf"):
                    res = [(o, gate_eval(g["type"], [vals[-1]])) for o in terms[:-1]]
                else:
                    res = [(terms[0], gate_eval(g["type"], vals[1:]))]
                for net, v in res:
                    if env.get(net) != v:
                        env[net], changed = v, True
            for lhs, ex in assigns:
                v = ex.eval(env)
                if env.get(lhs) != v:
                    env[lhs], changed = v, True
            if not changed:
                break
        lines.append(" | ".join(f"{p['name']}={env.get(p['name'], 'z')}" for p in ins + outs))
    lines.append(f"[demo] {2 ** len(ins)} vectors evaluated by the built-in gate-level simulator (Icarus Verilog not installed)")
    return True, "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- runner
class VerilogRunner:
    """Runs the iverilog -> vvp pipeline on a worker thread, posting RunEvents to a queue."""

    def __init__(self, config, events: queue.Queue | None = None):
        self.config = config
        self.package_manager = None          # set by the app: global -y / -l package resolution
        self.last_resolution: dict | None = None
        self._check_thread: threading.Thread | None = None
        self._check_pending = None
        self._check_running = False
        self.events: queue.Queue = events or queue.Queue()
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._cancel = threading.Event()
        self._lock = threading.Lock()

    # ---- command construction
    def build_compile_cmd(self, work_dir: Path | str, module: str, extra_files: list[str] | tuple = (),
                          record: bool = True) -> list[str]:
        """iverilog command line. With a package manager attached: -y for the workspace (first, so the student's
        own modules win) and every enabled package folder, plus -l for package files -y cannot resolve."""
        c = self.config
        cmd = [c["iverilog_path"], c["std_flag"], f"-o{module}"]
        y_dirs: list[str] = []

        def add_y(d) -> None:
            if d and all(os.path.normcase(str(d)) != os.path.normcase(x) for x in y_dirs):
                y_dirs.append(str(d))
        pm, res = self.package_manager, None
        if c["include_workdir_as_ylib"]:
            add_y(work_dir)
            work_path = Path(work_dir)
            for d in sorted({p.parent for p in work_path.rglob("*") if p.suffix.lower() in (".v", ".sv")},
                            key=lambda p: str(p).lower()):
                add_y(d)
        if pm is None:
            add_y(c["lib_dir"])
        else:
            for d in pm.y_search_dirs():        # packages (tier 2) then the course library (tier 3); unsafe folders skipped
                add_y(d)
            if c["auto_resolve_packages_with_l_flag"]:
                try:
                    res = pm.resolve(work_dir, module, extra_files)
                except Exception as exc:        # resolution must never block a plain compile
                    res = {"y_dirs": [], "l_files": [], "missing": [], "notes": [f"package resolution failed: {exc}"]}
                for d in res["y_dirs"]:
                    add_y(d)
        for d in y_dirs:
            cmd += ["-y", d]
        inc_dirs = ([str(work_dir)] if c["include_workdir_as_ylib"] else []) + (pm.include_dirs() if pm is not None else [])
        for d in dict.fromkeys(inc_dirs):          # `include "x.vh" from the workspace or any package folder
            cmd += ["-I", d]
        if c["enable_wall_warnings"]:
            cmd += ["-Wall", "-Winfloop"]
        for lf in (res or {}).get("l_files", []):
            cmd += ["-l", lf]              # must precede the source files (iverilog rejects -l after them)
        work_path = Path(work_dir)
        design = next(work_path.rglob(f"{module}.v"), work_path / f"{module}.v")
        tb = next(work_path.rglob(f"{module}_tb.v"), work_path / f"{module}_tb.v")
        cmd += [str(design), str(tb), *[str(f) for f in extra_files]]
        if record:
            self.last_resolution = res
        return cmd

    # ---- live check: `iverilog -tnull` (parse + elaborate only, no vvp image)
    def start_syntax_check(self, work_dir: Path | str, module: str, extra_files=(), include_tb: bool = True) -> None:
        """Background compile check used on save. Coalesces bursts of saves; never touches the run pipeline."""
        args = (Path(work_dir), module, tuple(extra_files), include_tb)
        with self._lock:
            if self._check_running:                # a check is in flight: run once more with the newest args after it
                self._check_pending = args
                return
            self._check_running = True
            self._check_thread = threading.Thread(target=self._syntax_check_loop, args=(args,), daemon=True,
                                                  name="veriflow-live-check")
            self._check_thread.start()

    def _syntax_check_loop(self, args) -> None:
        while args is not None:
            work_dir, module, extra, include_tb = args
            t0 = time.time()
            try:
                cmd = self.build_compile_cmd(work_dir, module, extra, record=False)
                cmd = ["-tnull" if a == f"-o{module}" else a for a in cmd]
                if not include_tb:
                    cmd = [a for a in cmd if a != f"{module}_tb.v"]
                proc = subprocess.run(cmd, cwd=str(work_dir), shell=False, stdin=subprocess.DEVNULL, capture_output=True,
                                      timeout=COMPILE_TIMEOUT_SEC, creationflags=NO_WINDOW)
                text = (decode_output(proc.stderr) + "\n" + decode_output(proc.stdout)).strip()
                diags = parse_compiler_output(text, work_dir)
                for d in diags:
                    d["source"] = "iverilog -tnull"
                ok = not compile_failed(proc.returncode, text, diags)
                self._emit("LIVE_CHECK", ok=ok, diagnostics=diags, duration=time.time() - t0, module=module,
                           work_dir=str(work_dir), output=text)
            except (OSError, subprocess.SubprocessError) as exc:
                self._emit("LIVE_CHECK", ok=False, diagnostics=[], duration=time.time() - t0, module=module,
                           work_dir=str(work_dir), output="", error=str(exc))
            with self._lock:
                args, self._check_pending = self._check_pending, None
                if args is None:
                    self._check_running = False

    def build_sim_cmd(self, module: str) -> list[str]:
        return [self.config["vvp_path"], *(["-n"] if self.config["vvp_non_interactive_flag"] else []), module]

    def display_cmd(self, work_dir: Path | str, module: str, extra_files=()) -> str:
        return f"{format_cmd(self.build_compile_cmd(work_dir, module, extra_files))} && {format_cmd(self.build_sim_cmd(module))}"

    def course_baseline_cmd(self, module: str) -> str:
        iv = self.config["iverilog_path"][:-4] if self.config["iverilog_path"].lower().endswith(".exe") else self.config["iverilog_path"]
        vvp = self.config["vvp_path"][:-4] if self.config["vvp_path"].lower().endswith(".exe") else self.config["vvp_path"]
        return f'{iv} {self.config["std_flag"]} -o{module} -y "{self.config["lib_dir"]}" {module}.v {module}_tb.v && {vvp} {module}'

    # ---- lifecycle
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self, work_dir: Path | str, module: str, extra_files=(), mock: bool = False,
              outputs: set[str] | None = None) -> bool:
        if self.is_running():
            return False
        self._cancel.clear()
        self._thread = threading.Thread(target=self._guarded, args=(Path(work_dir), module, list(extra_files), mock, outputs),
                                        name="veriflow-runner", daemon=True)
        self._thread.start()
        return True

    def run_sync(self, work_dir: Path | str, module: str, extra_files=(), mock: bool = False,
                 outputs: set[str] | None = None) -> list[RunEvent]:
        self._cancel.clear()
        self._guarded(Path(work_dir), module, list(extra_files), mock, outputs)
        out = []
        while not self.events.empty():
            out.append(self.events.get_nowait())
        return out

    def stop(self) -> None:
        self._cancel.set()
        with self._lock:
            if self._proc is not None:
                kill_process_tree(self._proc)

    def _emit(self, kind: str, **payload) -> None:
        self.events.put(RunEvent(kind, payload))

    def _guarded(self, work_dir: Path, module: str, extra: list[str], mock: bool, outputs) -> None:
        t0 = time.time()
        try:
            self._pipeline(work_dir, module, extra, mock, outputs)
        except Exception as exc:   # never let the worker die silently
            self._emit("ERROR", message=f"Internal runner error: {exc!r}")
        finally:
            self._emit("FINISHED", duration=time.time() - t0)

    def _exec(self, cmd: list[str], cwd: Path, timeout: float) -> tuple[int | None, str, str, bool]:
        with self._lock:
            self._proc = subprocess.Popen(cmd, cwd=str(cwd), shell=False, stdin=subprocess.DEVNULL,
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=NO_WINDOW)
            proc = self._proc
        timed_out = False
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            kill_process_tree(proc)
            try:
                out, err = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                out, err = b"", b""
        finally:
            with self._lock:
                self._proc = None
        return proc.returncode, decode_output(out), decode_output(err), timed_out

    def _pipeline(self, work_dir: Path, module: str, extra: list[str], mock: bool, outputs) -> None:
        design_matches = list(work_dir.rglob(f"{module}.v"))
        tb_matches = list(work_dir.rglob(f"{module}_tb.v"))
        design = design_matches[0] if design_matches else work_dir / f"{module}.v"
        tb = tb_matches[0] if tb_matches else work_dir / f"{module}_tb.v"
        if mock:
            self._emit("STAGE_START", stage="compile", cmd="[demo mode] built-in Python gate-level simulator")
            ok, text = mock_simulate(design)
            self._emit("COMPILE_DONE", ok=ok, rc=0 if ok else 1, stdout="", stderr="" if ok else text,
                       diagnostics=[] if ok else [{"file": str(design), "line": 0, "col": 0, "severity": "error",
                                                  "code": "demo", "message": text, "source": "demo"}],
                       cmd="(demo)", duration=0.0, mock=True)
            if ok:
                self._emit("SIM_DONE", rc=0, stdout=text, stderr="", table=parse_sim_output(text, outputs),
                           vcd=None, duration=0.0, cmd="(demo)", mock=True)
            return
        if not design.is_file() or not tb.is_file():
            missing = [p.name for p in (design, tb) if not p.is_file()]
            self._emit("ERROR", message=f"Missing source file(s): {', '.join(missing)}")
            return
        out_bin = work_dir / module
        # Step 1 - stale-binary cleanup (a failed compile must never let an old image run)
        if out_bin.exists():
            try:
                out_bin.unlink()
            except OSError as exc:
                self._emit("ERROR", message=f"Cannot delete stale binary '{out_bin.name}' ({exc}). Is an old vvp still running?")
                return
        # Step 2 - compile
        cmd = self.build_compile_cmd(work_dir, module, extra)
        self._emit("STAGE_START", stage="compile", cmd=format_cmd(cmd), resolution=self.last_resolution)
        t0 = time.time()
        try:
            rc, out, err, to = self._exec(cmd, work_dir, COMPILE_TIMEOUT_SEC)
        except OSError as exc:
            self._emit("ERROR", message=f"Cannot start iverilog ({cmd[0]}): {exc}")
            return
        combined = (err + "\n" + out).strip()
        diags = parse_compiler_output(combined, work_dir)
        fresh = out_bin.is_file() and out_bin.stat().st_size > 0 and out_bin.stat().st_mtime >= t0 - 2
        ok = not to and not compile_failed(rc or 0, combined, diags) and rc == 0 and fresh
        if not ok and not to and rc == 0 and not fresh and not any(d["severity"] == "error" for d in diags):
            diags.append({"file": "", "line": 0, "col": 0, "severity": "error", "code": "no-output", "source": "runner",
                          "message": f"iverilog exited 0 but produced no '{module}' binary"})
        self._emit("COMPILE_DONE", ok=ok, rc=rc, stdout=out, stderr=err, diagnostics=diags, cmd=format_cmd(cmd),
                   duration=time.time() - t0, timed_out=to)
        if not ok or self._cancel.is_set():
            return
        # Step 3 - simulate
        scmd = self.build_sim_cmd(module)
        self._emit("STAGE_START", stage="simulate", cmd=format_cmd(scmd))
        t1 = time.time()
        try:
            rc, out, err, to = self._exec(scmd, work_dir, float(self.config["sim_timeout_sec"]))
        except OSError as exc:
            self._emit("ERROR", message=f"Cannot start vvp ({scmd[0]}): {exc}")
            return
        payload = dict(rc=rc, stdout=out, stderr=err, table=parse_sim_output(out, outputs),
                       diagnostics=parse_compiler_output(err + "\n" + out, work_dir),
                       vcd=str(v) if (v := find_vcd(work_dir, tb, t1)) else None, duration=time.time() - t1, cmd=format_cmd(scmd))
        if self._cancel.is_set():
            self._emit("ERROR", message="Simulation stopped by user", **payload)
        elif to:
            self._emit("TIMEOUT", timeout=float(self.config["sim_timeout_sec"]), **payload)
        else:
            self._emit("SIM_DONE", **payload)
