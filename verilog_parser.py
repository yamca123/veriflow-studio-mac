"""VeriFlow Studio - static Verilog analysis: module parser, course linter, testbench generator, VCD reader.

Pure functions only (no Tk / no subprocess) so everything here is unit-testable and fast.
Supports Verilog-2001/2005 and the SystemVerilog-2012 subset used in Computer Structure courses.
"""
from __future__ import annotations

import ast
import bisect
import os
import re
from pathlib import Path

GATE_PRIMITIVES = {"and", "nand", "or", "nor", "xor", "xnor", "not", "buf", "bufif0", "bufif1", "notif0", "notif1",
                   "pullup", "pulldown", "tran", "rtran", "tranif0", "tranif1", "nmos", "pmos", "cmos"}
LINT_GATES = {"nand", "nor", "and", "or", "xor", "xnor", "not", "buf"}
KEYWORDS = set("""
always always_comb always_ff always_latch and assert assign assume automatic begin bit break buf bufif0 bufif1 byte
case casex casez cell class cmos config const constraint continue cover deassign default defparam design disable do
edge else end endcase endclass endconfig endfunction endgenerate endinterface endmodule endpackage endprimitive
endprogram endproperty endspecify endtable endtask enum event export extern final for force foreach forever fork
function generate genvar highz0 highz1 if iff ifnone import incdir include initial inout input instance int integer
interface join join_any join_none large liblist library localparam logic longint macromodule medium modport module
nand negedge new nmos none nor noshowcancelled not notif0 notif1 null or output package packed parameter pmos posedge
primitive priority program property pull0 pull1 pulldown pullup pulsestyle_ondetect pulsestyle_onevent rcmos real
realtime ref reg release repeat return rnmos rpmos rtran rtranif0 rtranif1 scalared shortint shortreal showcancelled
signed small specify specparam static string strong0 strong1 struct super supply0 supply1 table task this time
timeprecision timeunit tran tranif0 tranif1 tri tri0 tri1 triand trior trireg type typedef union unique unsigned use
uwire var vectored virtual void wait wand weak0 weak1 while wire wor xnor xor
""".split())
NET_KINDS = ("wire", "reg", "logic", "integer", "genvar", "tri", "wand", "wor", "supply0", "supply1", "bit", "byte",
             "int", "real", "time", "shortint", "longint", "uwire", "var")
TYPE_WORDS = set(NET_KINDS) | {"signed", "unsigned", "tri0", "tri1", "triand", "trior", "trireg", "realtime"}
DIRECTIONS = ("input", "output", "inout")

_TOKEN_RE = re.compile(r'"(?:\\.|[^"\\\n])*"|//[^\n]*|/\*.*?(?:\*/|\Z)', re.S)
_IDENT = re.compile(r"[A-Za-z_]\w*")
_IDENT_FREE = re.compile(r"(?<![\w$`'.\\])[A-Za-z_]\w*")
_MODULE_RE = re.compile(r"(?<![\w$`])(?:module|macromodule)\s+(?:(?:static|automatic)\s+)?([A-Za-z_]\w*)")
_ENDMODULE_RE = re.compile(r"(?<![\w$])endmodule\b")
_FUNC_TASK_RE = re.compile(r"(?<![\w$])(function|task)\b.*?(?<![\w$])end(?:function|task)\b", re.S)
_NET_DECL_RE = re.compile(r"(?<![\w$`'.])(" + "|".join(NET_KINDS) + r")\b([^;]*);")
_PARAM_RE = re.compile(r"(?<![\w$`'.])(parameter|localparam)\b([^;]*);")
_PORT_DECL_RE = re.compile(r"(?<![\w$`'.])(input|output|inout)\b([^;]*);")
_FUNC_NAME_RE = re.compile(r"(?<![\w$])(?:function|task)\s+(?:automatic\s+|static\s+)?(?:[\w\s]*?\[[^\]]*\]\s*)?(?:\w+\s+)*?([A-Za-z_]\w*)\s*[;(]")
_NUM_LIT = re.compile(r"(\d+)?\s*'\s*([sS]?)([bBoOdDhH])\s*([0-9a-fA-F_xXzZ?]+)")
_RANGE_RE = re.compile(r"\[([^\[\]]*?):([^\[\]]*)\]")


# --------------------------------------------------------------------------- text helpers
def strip_comments(text: str, blank_strings: bool = False) -> str:
    """Replace // and /* */ comments with spaces while keeping every newline (line/col stay exact)."""
    def repl(m: re.Match) -> str:
        s = m.group(0)
        if s.startswith('"'):
            return '"' + " " * (len(s) - 2) + '"' if blank_strings else s
        return re.sub(r"[^\n]", " ", s)
    return _TOKEN_RE.sub(repl, text)


def _blank_span(s: str) -> str:
    return re.sub(r"[^\n]", " ", s)


def _line_index(text: str) -> list[int]:
    return [i for i, c in enumerate(text) if c == "\n"]


def _pos_to_linecol(nl: list[int], pos: int) -> tuple[int, int]:
    line = bisect.bisect_left(nl, pos)
    start = nl[line - 1] + 1 if line else 0
    return line + 1, pos - start + 1


def _match_close(s: str, i: int) -> int:
    """Index of the bracket closing s[i] (any of ([{), or -1."""
    depth = 0
    for j in range(i, len(s)):
        c = s[j]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                return j
    return -1


def _split_top(s: str, sep: str = ",") -> list[tuple[str, int]]:
    """Split on sep at bracket depth 0. Returns (piece, offset) pairs."""
    parts, depth, start = [], 0, 0
    for i, c in enumerate(s):
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == sep and depth == 0:
            parts.append((s[start:i], start))
            start = i + 1
    parts.append((s[start:], start))
    return parts


def _skip_ws(s: str, i: int) -> int:
    while i < len(s) and s[i].isspace():
        i += 1
    return i


# --------------------------------------------------------------------------- constant expressions
_ALLOWED_NODES = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Call, ast.Name, ast.Load, ast.Add, ast.Sub,
                  ast.Mult, ast.FloorDiv, ast.Mod, ast.Pow, ast.LShift, ast.RShift, ast.BitAnd, ast.BitOr, ast.BitXor,
                  ast.USub, ast.UAdd, ast.Invert)


def _clog2(x: int) -> int:
    return max(0, (int(x) - 1).bit_length())


def verilog_number(lit: str) -> int | None:
    m = _NUM_LIT.fullmatch(lit.strip())
    if not m:
        return int(lit.replace("_", "")) if re.fullmatch(r"\d[\d_]*", lit.strip()) else None
    digits = m.group(4).replace("_", "")
    if re.search(r"[xXzZ?]", digits):
        return None
    return int(digits, {"b": 2, "o": 8, "d": 10, "h": 16}[m.group(3).lower()])


def eval_const(expr: str, params: dict[str, str] | None = None, _depth: int = 0) -> int | None:
    """Safely evaluate a Verilog constant expression (widths, parameters). None if not resolvable."""
    if expr is None or _depth > 8 or len(expr) > 240:
        return None
    params = params or {}
    e = _NUM_LIT.sub(lambda m: str(verilog_number(m.group(0))) if verilog_number(m.group(0)) is not None else "@", expr)
    e = re.sub(r"\$clog2\s*\(", "_clog2(", e)

    def rep(m: re.Match) -> str:
        name = m.group(0)
        if name == "_clog2":
            return name
        if name in params:
            v = eval_const(params[name], params, _depth + 1)
            if v is not None:
                return f"({v})"
        raise ValueError(name)
    try:
        e = re.sub(r"(?<![\w$`'])[A-Za-z_]\w*", rep, e)
        if "@" in e or "?" in e or "!" in e or "`" in e:
            return None
        e = e.replace("/", "//")
        tree = ast.parse(e.strip(), mode="eval")
        for node in ast.walk(tree):
            if not isinstance(node, _ALLOWED_NODES):
                return None
            if isinstance(node, ast.Name) and node.id != "_clog2":
                return None
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
                if not (isinstance(node.right, ast.Constant) and abs(node.right.value) <= 64) and e.count("**") > 2:
                    return None
        val = eval(compile(tree, "<const>", "eval"), {"__builtins__": {}}, {"_clog2": _clog2})
        return int(val) if isinstance(val, (int, float)) else None
    except Exception:
        return None


# --------------------------------------------------------------------------- declarations
def _parse_decl(text: str) -> tuple[list[str], bool, tuple[str, str] | None, list[tuple[str, int]]]:
    """'wire logic signed [15:0] a, b = 0' -> (types, signed, (msb, lsb), [(name, offset)])."""
    i, types, signed, rng = 0, [], False, None
    while True:
        i = _skip_ws(text, i)
        m = _IDENT.match(text, i)
        if m and m.group(0) in TYPE_WORDS:
            word = m.group(0)
            signed |= word == "signed"
            if word not in ("signed", "unsigned"):
                types.append(word)
            i = m.end()
            continue
        if i < len(text) and text[i] == "[":
            j = _match_close(text, i)
            if j < 0:
                break
            if rng is None:
                inner = text[i + 1:j]
                parts = _split_top(inner, ":")
                rng = (parts[0][0].strip(), parts[1][0].strip()) if len(parts) == 2 else (f"{inner.strip()}-1", "0")
            i = j + 1
            continue
        break
    names = []
    for piece, off in _split_top(text[i:]):
        m = _IDENT.search(piece.split("=", 1)[0])
        if m and m.group(0) not in KEYWORDS:
            names.append((m.group(0), i + off + m.start()))
    return types, signed, rng, names


def _width(rng: tuple[str, str] | None, params: dict[str, str]) -> tuple[int | str | None, int | str | None, int | None]:
    if rng is None:
        return 0, 0, 1
    msb, lsb = eval_const(rng[0], params), eval_const(rng[1], params)
    if msb is None or lsb is None:
        return rng[0], rng[1], None
    return msb, lsb, abs(msb - lsb) + 1


def _parse_params(text: str, into: dict[str, str]) -> None:
    for piece, _ in _split_top(text):
        piece = re.sub(r"^\s*(parameter|localparam)\b", "", piece)
        if "=" not in piece:
            continue
        lhs, rhs = piece.split("=", 1)
        names = _IDENT.findall(re.sub(r"\[[^\]]*\]", " ", lhs))
        if names:
            into[names[-1]] = rhs.strip()


# --------------------------------------------------------------------------- instantiations
def _try_instance(code: str, pos: int, typ: str) -> tuple[list[dict], int] | None:
    n, j, params = len(code), _skip_ws(code, pos), None
    if j < n and code[j] == "#":
        j = _skip_ws(code, j + 1)
        if j < n and code[j] == "(":
            k = _match_close(code, j)
            if k < 0:
                return None
            params, j = code[j + 1:k], _skip_ws(code, k + 1)
        else:
            m = re.compile(r"[\w.']+").match(code, j)
            if not m:
                return None
            params, j = m.group(0), _skip_ws(code, m.end())
    is_prim = typ in GATE_PRIMITIVES
    found = []
    while True:
        name = None
        m = _IDENT.match(code, j)
        if m and m.group(0) not in KEYWORDS:
            name, j = m.group(0), _skip_ws(code, m.end())
            if j < n and code[j] == "[":
                k = _match_close(code, j)
                if k < 0:
                    return None
                j = _skip_ws(code, k + 1)
        if (name is None and not is_prim) or j >= n or code[j] != "(":
            return None
        k = _match_close(code, j)
        if k < 0:
            return None
        found.append({"type": typ, "name": name, "params": params, "is_primitive": is_prim,
                      "conn_text": code[j + 1:k], "conn_offset": j + 1})
        j = _skip_ws(code, k + 1)
        if j < n and code[j] == ",":
            j = _skip_ws(code, j + 1)
            continue
        if j < n and code[j] == ";":
            return found, j + 1
        return None


def _parse_connections(inst: dict) -> None:
    text = inst["conn_text"]
    items = [(p, o) for p, o in _split_top(text)]
    if len(items) == 1 and not items[0][0].strip():
        items = []
    named = any(p.strip().startswith(".") for p, _ in items)
    inst.update(named=named, wildcard=False, positional=[], connections={})
    for piece, off in items:
        s = piece.strip()
        if named:
            if s == ".*":
                inst["wildcard"] = True
                continue
            m = re.match(r"\.\s*([A-Za-z_]\w*)\s*(?:\((.*)\))?\s*$", s, re.S)
            if m:
                inst["connections"][m.group(1)] = m.group(2).strip() if m.group(2) is not None else None
        else:
            inst["positional"].append(s)


def _scan_instances(code: str) -> list[dict]:
    out, resume = [], 0
    for m in _IDENT_FREE.finditer(code):
        if m.start() < resume:
            continue
        typ = m.group(0)
        if typ in KEYWORDS and typ not in GATE_PRIMITIVES:
            continue
        res = _try_instance(code, m.end(), typ)
        if res:
            insts, resume = res
            for inst in insts:
                inst["type_offset"] = m.start()
                _parse_connections(inst)
            out.extend(insts)
    return out


# --------------------------------------------------------------------------- module parsing
def parse_verilog_source(text: str, filename: str = "<memory>") -> list[dict]:
    """Parse every module in a Verilog source string."""
    clean = strip_comments(text)
    code = strip_comments(text, blank_strings=True)
    nl = _line_index(text)
    modules = []
    for mm in _MODULE_RE.finditer(code):
        name, i = mm.group(1), _skip_ws(code, mm.end())
        params: dict[str, str] = {}
        header_params = ""
        # SV package imports in header: module m import pkg::*; #(...) (...)
        while code.startswith("import", i):
            semi = code.find(";", i)
            i = _skip_ws(code, semi + 1) if semi > 0 else i
            break
        if i < len(code) and code[i] == "#":
            p = _skip_ws(code, i + 1)
            if p < len(code) and code[p] == "(":
                q = _match_close(code, p)
                if q > 0:
                    header_params = code[p + 1:q]
                    _parse_params(header_params, params)
                    i = _skip_ws(code, q + 1)
        port_text, port_off = "", i
        if i < len(code) and code[i] == "(":
            q = _match_close(code, i)
            if q > 0:
                port_text, port_off = code[i + 1:q], i + 1
                i = q + 1
        semi = code.find(";", i)
        body_start = semi + 1 if semi >= 0 else i
        em = _ENDMODULE_RE.search(code, body_start)
        body_end = em.start() if em else len(code)
        body = code[body_start:body_end]
        body_nf = _FUNC_TASK_RE.sub(lambda m: _blank_span(m.group(0)), body)
        for pm in _PARAM_RE.finditer(body_nf):
            _parse_params(pm.group(2), params)

        ports, nonansi, ansi, cur = [], [], False, None
        for piece, off in _split_top(port_text):
            s = piece.strip()
            if not s:
                continue
            dm = re.match(r"(input|output|inout|ref)\b(.*)", s, re.S)
            if dm:
                ansi = True
                types, signed, rng, names = _parse_decl(dm.group(2))
                cur = {"direction": dm.group(1), "net_type": " ".join(types) or ("wire" if dm.group(1) != "output" or "reg" not in types else "reg"),
                       "signed": signed, "rng": rng}
            elif ansi and cur is not None:
                types, signed, rng, names = _parse_decl(s)
                if rng is not None or types:
                    cur = {**cur, "rng": rng if rng is not None else cur["rng"], "net_type": " ".join(types) or cur["net_type"]}
            else:
                idm = _IDENT.search(s)
                if idm:
                    nonansi.append((idm.group(0), port_off + off + (len(piece) - len(piece.lstrip())) + idm.start()))
                continue
            for pname, poff in names:
                ports.append({"name": pname, "direction": cur["direction"], "net_type": cur["net_type"],
                              "signed": cur["signed"], "rng": cur["rng"],
                              "line": _pos_to_linecol(nl, port_off + off + (len(piece) - len(piece.lstrip())) + len(dm.group(1) if dm else "") + poff)[0] if dm else _pos_to_linecol(nl, port_off + off)[0]})
        if nonansi:
            decls: dict[str, dict] = {}
            for dm2 in _PORT_DECL_RE.finditer(body_nf):
                types, signed, rng, names = _parse_decl(dm2.group(2))
                for pname, poff in names:
                    decls[pname] = {"direction": dm2.group(1), "net_type": " ".join(types) or "wire", "signed": signed,
                                    "rng": rng, "line": _pos_to_linecol(nl, body_start + dm2.start(2) + poff)[0]}
            for pname, poff in nonansi:
                d = decls.get(pname, {"direction": "inout", "net_type": "wire", "signed": False, "rng": None,
                                      "line": _pos_to_linecol(nl, poff)[0], "undeclared": True})
                ports.append({"name": pname, **d})
        for p in ports:
            p["width_msb"], p["width_lsb"], p["bits"] = _width(p["rng"], params)
            p["range_text"] = f"[{p['rng'][0]}:{p['rng'][1]}]" if p["rng"] else ""

        nets = []
        for nm in _NET_DECL_RE.finditer(body):   # 'output reg q;' also lands here -> q counts as declared
            types, signed, rng, names = _parse_decl(nm.group(1) + " " + nm.group(2))
            msb, lsb, bits = _width(rng, params)
            if nm.group(1) == "integer" and rng is None:
                msb, lsb, bits = 31, 0, 32
            for nname, noff in names:
                nets.append({"kind": nm.group(1), "name": nname, "width_msb": msb, "width_lsb": lsb, "bits": bits,
                             "line": _pos_to_linecol(nl, body_start + nm.start(1) + max(0, noff - 1))[0]})
        for pname in params:
            nets.append({"kind": "parameter", "name": pname, "width_msb": None, "width_lsb": None, "bits": None, "line": 0})
        functions = set(_FUNC_NAME_RE.findall(body))

        instances = []
        for inst in _scan_instances(body_nf):
            inst["line"] = _pos_to_linecol(nl, body_start + inst["type_offset"])[0]
            inst["conn_offset"] += body_start
            instances.append(inst)
        modules.append({
            "module_name": name, "file": filename, "line": _pos_to_linecol(nl, mm.start())[0],
            "params": params, "ports": ports, "declared_nets": nets, "functions": sorted(functions),
            "instantiations": instances, "ansi": ansi, "has_endmodule": em is not None,
            "body_start": body_start, "body_end": body_end,
            "end_line": _pos_to_linecol(nl, body_end)[0],
            "span": (mm.start(), em.end() if em else len(code)),
            "_clean": clean, "_code": code,
        })
    return modules


def parse_verilog_module(filepath: Path | str, text: str | None = None) -> dict:
    """Parse a .v file and return the module matching the file stem (or the first one).

    Result keys: module_name, ports, declared_nets, instantiations, params, file, all_modules, error.
    """
    path = Path(filepath)
    if text is None:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return {"module_name": None, "ports": [], "declared_nets": [], "instantiations": [], "params": {},
                    "file": str(path), "all_modules": [], "error": str(exc)}
    mods = parse_verilog_source(text, str(path))
    if not mods:
        return {"module_name": None, "ports": [], "declared_nets": [], "instantiations": [], "params": {},
                "file": str(path), "all_modules": [], "error": "no module declaration found"}
    best = next((m for m in mods if m["module_name"] == path.stem), None) \
        or next((m for m in mods if m["module_name"].lower() == path.stem.lower()), mods[0])
    return {**best, "all_modules": mods, "error": None}


def public_module_info(info: dict) -> dict:
    """Drop the private text caches (handy for printing / JSON)."""
    return {k: v for k, v in info.items() if not k.startswith("_") and k != "all_modules"}


def scan_module_dir(folder: Path | str, cache: dict | None = None) -> dict[str, dict]:
    """Parse every *.v file recursively -> {module_name: module_info}. Optional mtime cache dict."""
    out: dict[str, dict] = {}
    folder = Path(folder)
    if not folder.is_dir():
        return out
    for f in sorted(folder.rglob("*.v"), key=lambda p: str(p).lower()):
        try:
            mtime = f.stat().st_mtime
        except OSError:
            continue
        key = str(f)
        if cache is not None and key in cache and cache[key][0] == mtime:
            mods = cache[key][1]
        else:
            mods = parse_verilog_module(f).get("all_modules", [])
            if cache is not None:
                cache[key] = (mtime, mods)
        for m in mods:
            out.setdefault(m["module_name"], m)
    return out


PACKAGE_SOURCE_EXTS = (".v", ".sv")


def parse_all_modules_in_file(filepath: Path | str) -> list[dict]:
    """Every `module ... endmodule` in a file (a lecturer file may hold many helper modules)."""
    return parse_verilog_module(filepath).get("all_modules", [])


def _iter_source_files(root: Path, recursive: bool, limit: int = 3000) -> list[Path]:
    it = root.rglob("*") if recursive else root.iterdir()
    out = []
    for p in it:
        if p.suffix.lower() in PACKAGE_SOURCE_EXTS and p.is_file() and not any(part.startswith(".") for part in p.relative_to(root).parts):
            out.append(p)
            if len(out) >= limit:
                break
    return sorted(out, key=lambda p: str(p).lower())


def build_global_module_index(library_dirs: list, work_dir: Path | str | None = None,
                              cache: dict | None = None, exclude_files: list | None = None) -> dict[str, dict]:
    """Index every module of the workspace and all package folders: name -> entry.

    `library_dirs` items: Path | (Path, package_name) | {"path", "name", "recursive", "exclude_modules"}.
    Modules listed in a package's `exclude_modules` (duplicates skipped at import) are never indexed for it.
    Precedence (first definition wins): workspace, then packages in the given order.
    Entry = module info + filepath, package_name, file_modules, needs_l_flag (file stem != module name,
    several modules in the file, a non-.v file, or a file in a sub-folder that `-y` cannot see).
    """
    sources: list[tuple[Path, str, bool, frozenset]] = []
    if work_dir:
        sources.append((Path(work_dir), "Workspace", True, frozenset()))
    for item in library_dirs:
        if isinstance(item, dict):
            sources.append((Path(item["path"]), item.get("name") or Path(item["path"]).name, bool(item.get("recursive")),
                            frozenset(item.get("exclude_modules") or ())))
        elif isinstance(item, (tuple, list)):
            sources.append((Path(item[0]), item[1], bool(item[2]) if len(item) > 2 else False, frozenset()))
        else:
            sources.append((Path(item), Path(item).name, False, frozenset()))
    skip = {os.path.normcase(os.path.abspath(f)) for f in (exclude_files or [])}
    index: dict[str, dict] = {}
    seen_dirs: set[str] = set()
    for root, pkg_name, recursive, excluded in sources:
        key = os.path.normcase(os.path.abspath(root))
        if key in seen_dirs or not root.is_dir():
            continue
        seen_dirs.add(key)
        for f in _iter_source_files(root, recursive):
            fkey = os.path.normcase(os.path.abspath(f))
            if fkey in skip:
                continue
            try:
                st = f.stat()
            except OSError:
                continue
            if cache is not None and fkey in cache and cache[fkey][0] == (st.st_mtime, st.st_size):
                mods = cache[fkey][1]
            else:
                mods = parse_all_modules_in_file(f)
                if cache is not None:
                    cache[fkey] = ((st.st_mtime, st.st_size), mods)
            names = [m["module_name"] for m in mods]
            rel = f.relative_to(root).as_posix() if excluded else ""
            for m in mods:
                if excluded and (f"{rel}|{m['module_name']}" in excluded or m["module_name"] in excluded):
                    continue                      # duplicate skipped at import ("<file>|<module>" or a bare name)
                entry = {**m, "filepath": f, "package_name": pkg_name, "package_root": root, "file_modules": names,
                         "needs_l_flag": (f.stem != m["module_name"] or len(mods) > 1 or f.suffix.lower() != ".v"
                                          or os.path.normcase(str(f.parent)) != os.path.normcase(str(root)))}
                if m["module_name"] in index:
                    index[m["module_name"]].setdefault("shadows", []).append(f)
                else:
                    index[m["module_name"]] = entry
    return index


def resolve_required_library_files(root_files: list, known_modules: dict[str, dict],
                                   shadowed: dict | None = None, needed: list | None = None) -> tuple[list[str], list[str], list[str]]:
    """Trace instantiations from the explicit sources and work out what iverilog needs.

    Returns (y_dirs, l_files, missing_modules):
      * y_dirs  - folders whose `<Module>.v` files resolve the rest through `-y`
      * l_files - package files that must be loaded with `-l` (multi-module / name-mismatched files)
      * missing - instantiated modules found nowhere (not primitives, not in workspace or packages)
    If `shadowed` is a dict it is filled with {l_file: {module names that a higher-precedence definition
    overrides}} - loading those unfiltered would make iverilog fail with "already declared".
    """
    roots = [Path(f) for f in root_files]
    root_mods: dict[str, dict] = {}
    for f in roots:
        if f.is_file():
            for m in parse_all_modules_in_file(f):
                root_mods.setdefault(m["module_name"], m)
    y_dirs: list[str] = []
    l_files: list[str] = []
    missing: list[str] = []
    queue = [i["type"] for m in root_mods.values() for i in m["instantiations"]]
    seen: set[str] = set()
    while queue:
        name = queue.pop(0)
        if name in seen or name in GATE_PRIMITIVES:
            continue
        seen.add(name)
        if name in root_mods:
            queue.extend(i["type"] for i in root_mods[name]["instantiations"])
            continue
        entry = known_modules.get(name)
        if entry is None:
            missing.append(name)
            continue
        if needed is not None:
            needed.append(name)            # every module resolved from outside the explicit sources
        target = str(entry["filepath"]) if entry["needs_l_flag"] else str(entry["filepath"].parent)
        bucket = l_files if entry["needs_l_flag"] else y_dirs
        if all(os.path.normcase(target) != os.path.normcase(t) for t in bucket):
            bucket.append(target)
        queue.extend(i["type"] for i in entry["instantiations"])
    if shadowed is not None:
        for lf in l_files:
            lkey = os.path.normcase(lf)
            for m in parse_all_modules_in_file(lf):
                name = m["module_name"]
                owner = known_modules.get(name)
                if name in root_mods or (owner is not None and os.path.normcase(str(owner["filepath"])) != lkey):
                    shadowed.setdefault(lf, set()).add(name)
    return y_dirs, l_files, missing


def strip_modules_from_source(text: str, names: set[str] | list[str]) -> str:
    """Blank out the given modules (keeping every newline, so line numbers stay valid)."""
    names = set(names)
    spans = [m["span"] for m in parse_verilog_source(text) if m["module_name"] in names]
    for start, end in sorted(spans, reverse=True):
        text = text[:start] + _blank_span(text[start:end]) + text[end:]
    return text


_DIRECTIVE_LINE = re.compile(r"^[ \t]*`(timescale|define|undef|include|default_nettype|resetall)\b[^\n]*", re.M)


def extract_module_source(text: str, name: str) -> str | None:
    """Source of one module plus the compiler directives (`timescale, `define, `include...) that precede it -
    a self-contained single-module "cell" that `-y` can find by name."""
    mod = next((m for m in parse_verilog_source(text) if m["module_name"] == name), None)
    if mod is None:
        return None
    start, end = mod["span"]
    code = strip_comments(text)
    head = [d.group(0).strip() for d in _DIRECTIVE_LINE.finditer(code, 0, start)]
    return ("\n".join(head) + "\n\n" if head else "") + text[start:end].rstrip() + "\n"


_PRIM_COUNTED = ("nand", "nor", "xor", "xnor", "and", "or", "not", "buf")


def _terms(expr: str) -> list[str]:
    return [t for t in _IDENT_FREE.findall(expr or "") if t not in KEYWORDS]


def _instance_io(inst: dict, known: dict) -> tuple[list[str], list[str]]:
    """(driven nets, read nets) of one instance - nets reduced to identifiers (buses as a whole)."""
    if inst["is_primitive"]:
        terms = inst["positional"]
        n_out = len(terms) - 1 if inst["type"] in ("not", "buf") else 1
        return ([t for e in terms[:n_out] for t in _terms(e)], [t for e in terms[n_out:] for t in _terms(e)])
    sub = known.get(inst["type"])
    if sub is None:
        return [], [t for e in (inst["positional"] or inst["connections"].values()) for t in _terms(e or "")]
    pairs = (list(zip(sub["ports"], inst["positional"])) if not inst["named"] else
             [(p, inst["connections"][p["name"]]) for p in sub["ports"] if inst["connections"].get(p["name"])])
    outs = [t for p, e in pairs if p["direction"] != "input" for t in _terms(e)]
    ins = [t for p, e in pairs if p["direction"] == "input" for t in _terms(e)]
    return outs, ins


def module_logic_depth(name: str, known: dict, _memo: dict | None = None, _stack: set | None = None) -> int:
    """Estimated combinational depth in gate levels (inputs -> outputs, sub-modules expanded recursively)."""
    memo = {} if _memo is None else _memo
    stack = set() if _stack is None else _stack
    if name in memo:
        return memo[name]
    info = known.get(name)
    if info is None or name in stack:
        return 0
    stack.add(name)
    drivers = []
    for inst in info.get("instantiations", []):
        if inst["is_primitive"]:
            d = 1
        else:
            d = max(1, module_logic_depth(inst["type"], known, memo, stack)) if inst["type"] in known else 1
        outs, ins = _instance_io(inst, known)
        ins = [i for i in ins if i not in outs]      # bus treated as one net: c[i] <- c[i-1] is not a real loop
        drivers.append((outs, ins, d))
    depth = {p["name"]: 0 for p in info["ports"] if p["direction"] == "input"}
    for _ in range(len(drivers) + 2):          # relaxation; bounded so feedback loops cannot spin forever
        changed = False
        for outs, ins, d in drivers:
            v = d + max((depth.get(i, 0) for i in ins), default=0)
            for o in outs:
                if depth.get(o, -1) < v:
                    depth[o], changed = v, True
        if not changed:
            break
    stack.discard(name)
    memo[name] = max((depth.get(p["name"], 0) for p in info["ports"] if p["direction"] != "input"), default=0)
    return memo[name]


def analyze_hierarchy(root: str, known: dict, max_nodes: int = 4000) -> dict:
    """Instance tree + flattened primitive gate counts + estimated logic depth for module `root`.

    Counts are static: an instance array or a generate loop body is counted once."""
    gates = {g: 0 for g in _PRIM_COUNTED}
    other_prims: dict[str, int] = {}
    totals = {"instances": 0, "nodes": 0}
    missing: set[str] = set()

    def build(inst_name: str, type_name: str, path: tuple, file=None, line=0) -> dict:
        info = known.get(type_name)
        node = {"name": inst_name, "type": type_name, "file": str(info["filepath"]) if info and info.get("filepath") else file,
                "line": info.get("line", 0) if info else line, "children": [], "primitive": False,
                "missing": info is None, "package": info.get("package_name") if info else None}
        if info is None:
            missing.add(type_name)
            return node
        if type_name in path or totals["nodes"] > max_nodes:
            node["recursive"] = True
            return node
        for inst in info.get("instantiations", []):
            totals["nodes"] += 1
            src = str(info["filepath"]) if info.get("filepath") else None
            if inst["is_primitive"]:
                if inst["type"] in gates:
                    gates[inst["type"]] += 1
                else:
                    other_prims[inst["type"]] = other_prims.get(inst["type"], 0) + 1
                node["children"].append({"name": inst["name"] or "", "type": inst["type"], "file": src, "line": inst["line"],
                                         "children": [], "primitive": True, "missing": False, "package": None})
            else:
                totals["instances"] += 1
                child = build(inst["name"] or "?", inst["type"], path + (type_name,), src, inst["line"])
                child["inst_file"], child["inst_line"] = src, inst["line"]
                node["children"].append(child)
        return node
    tree = build(root, root, ())
    return {"tree": tree, "gates": gates, "other_primitives": other_prims, "total_gates": sum(gates.values()) + sum(other_prims.values()),
            "instances": totals["instances"], "depth": module_logic_depth(root, known), "missing": sorted(missing)}


def instantiation_template(info: dict, instance_name: str = "u0") -> str:
    ports = info.get("ports", [])
    params = info.get("params", {})
    head = info["module_name"]
    if params:
        head += " #(" + ", ".join(f".{k}({v})" for k, v in params.items()) + ")"
    if not ports:
        return f"{head} {instance_name} ();\n"
    w = max(len(p["name"]) for p in ports)
    lines = [f"    .{p['name'].ljust(w)} ({p['name']})" for p in ports]
    return f"{head} {instance_name} (\n" + ",\n".join(lines) + "\n);\n"


def describe_ports(info: dict) -> str:
    rows = [f"module {info['module_name']}" + (" #(" + ", ".join(f"{k}={v}" for k, v in info.get("params", {}).items()) + ")" if info.get("params") else "")]
    for p in info.get("ports", []):
        rows.append(f"  {p['direction']:<6} {p['range_text']:<14} {p['name']}" + (f"   ({p['bits']} bit)" if p["bits"] and p["bits"] > 1 else ""))
    return "\n".join(rows)


# --------------------------------------------------------------------------- course linter
def _diag(path: Path, line: int, sev: str, code: str, msg: str, col: int = 0) -> dict:
    return {"file": str(path), "line": line, "col": col, "severity": sev, "code": code, "message": msg, "source": "linter"}


def _strict_scan(code: str, nl: list[int], start: int, end: int, path: Path) -> list[dict]:
    diags = []
    seg = code[start:end]
    seg = _FUNC_TASK_RE.sub(lambda m: _blank_span(m.group(0)), seg)
    for kw, why in (("always", "behavioral 'always' block"), ("initial", "behavioral 'initial' block"),
                    ("assign", "continuous 'assign' statement")):
        for m in re.finditer(rf"(?<![\w$`]){kw}\w*\b", seg):
            diags.append(_diag(path, _pos_to_linecol(nl, start + m.start())[0], "warning", "strict-gate",
                               f"Strict gate-level mode: {why} - use gate primitives / lecturer modules only"))
    masked = re.sub(r"\[[^\[\]]*\]", lambda m: _blank_span(m.group(0)), seg)
    masked = re.sub(r"#\s*\((?:[^()]|\([^()]*\))*\)|#\s*[\w.]+", lambda m: _blank_span(m.group(0)), masked)
    masked = re.sub(r"(?<![\w$])for\s*\((?:[^()]|\([^()]*\))*\)", lambda m: _blank_span(m.group(0)), masked)
    masked = re.sub(r"(?<![\w$`])(parameter|localparam|genvar)\b[^;]*;", lambda m: _blank_span(m.group(0)), masked)
    masked = re.sub(r"`\w+[^\n]*", lambda m: _blank_span(m.group(0)), masked)
    masked = re.sub(r'"[^"\n]*"', lambda m: _blank_span(m.group(0)), masked)
    seen = set()
    for m in re.finditer(r"(?<![+\-])([+\-?])(?![+\-:=])", masked):
        line = _pos_to_linecol(nl, start + m.start())[0]
        if (line, m.group(1)) in seen:
            continue
        seen.add((line, m.group(1)))
        what = "conditional operator '? :'" if m.group(1) == "?" else f"arithmetic operator '{m.group(1)}'"
        diags.append(_diag(path, line, "warning", "strict-gate", f"Strict gate-level mode: behavioral {what} is not allowed"))
    return diags


_PRIM_ARITY = {"not": 2, "buf": 2, "bufif0": 3, "bufif1": 3, "notif0": 3, "notif1": 3}


def run_course_linter(filepath: Path | str, known_modules: dict[str, dict] | None = None,
                      strict_gate_mode: bool = False, text: str | None = None) -> list[dict]:
    """Course-specific static checks. Returns diagnostics {file,line,col,severity,code,message,source}."""
    path = Path(filepath)
    known = dict(known_modules or {})
    if text is None:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return [_diag(path, 0, "error", "io", f"Cannot read file: {exc}")]
    mods = parse_verilog_source(text, str(path))
    is_tb = path.stem.lower().endswith("_tb") or path.stem.lower().startswith("tb_")
    diags: list[dict] = []
    if not mods:
        return [_diag(path, 1, "error", "no-module", "No 'module ... endmodule' declaration found in this file")]
    for m in mods:
        known[m["module_name"]] = m       # the (possibly unsaved) editor text wins over the disk scan
    known_ci = {k.lower(): k for k in known}
    nl = _line_index(text)

    # 1. filename vs module name (-y lookup)
    names = [m["module_name"] for m in mods]
    if path.stem not in names:
        first = mods[0]
        if is_tb:
            diags.append(_diag(path, first["line"], "info", "name-mismatch",
                               f"Testbench module '{first['module_name']}' differs from file name '{path.stem}' (fine for a top-level testbench)"))
        elif first["module_name"].lower() == path.stem.lower():
            diags.append(_diag(path, first["line"], "warning", "name-case",
                               f"Module '{first['module_name']}' and file '{path.name}' differ only in letter case - "
                               f"iverilog -y looks for '<ModuleName>.v' exactly, so other modules instantiating '{first['module_name']}' may fail to resolve it"))
        else:
            diags.append(_diag(path, first["line"], "warning", "name-mismatch",
                               f"Module '{first['module_name']}' does not match file name '{path.stem}' - iverilog -y can only find a module whose name equals its file name"))
    if len(mods) > 1 and not is_tb:
        diags.append(_diag(path, mods[1]["line"], "info", "multi-module",
                           f"File defines {len(mods)} modules; -y library lookup only finds '{path.stem}', the others are visible only when this file is compiled explicitly"))

    for m in mods:
        if not m["has_endmodule"]:
            diags.append(_diag(path, m["end_line"], "error", "endmodule", f"Module '{m['module_name']}' is missing 'endmodule'"))
        declared = {p["name"] for p in m["ports"]} | {n["name"] for n in m["declared_nets"]} | set(m["functions"])
        widths = {p["name"]: p["bits"] for p in m["ports"]}
        widths.update({n["name"]: n["bits"] for n in m["declared_nets"] if n["bits"]})
        for p in m["ports"]:
            if p.get("undeclared"):
                diags.append(_diag(path, p["line"], "error", "port-decl", f"Port '{p['name']}' is listed in the header but never declared as input/output"))
        reported: set[str] = set()

        # 2. implicit / undeclared wires
        for inst in m["instantiations"]:
            if inst["is_primitive"] and inst["type"] not in LINT_GATES and inst["type"] not in _PRIM_ARITY:
                continue
            for im in _IDENT_FREE.finditer(inst["conn_text"]):
                ident = im.group(0)
                if ident in declared or ident in KEYWORDS or ident in reported:
                    continue
                reported.add(ident)
                line, col = _pos_to_linecol(nl, inst["conn_offset"] + im.start())
                diags.append(_diag(path, line, "warning", "implicit-wire",
                                   f"Undeclared wire '{ident}' (creates implicit 1-bit wire that may float at 'z')", col))
            if inst["named"]:
                for pname, expr in inst["connections"].items():
                    if expr is None and pname not in declared and pname not in reported:
                        reported.add(pname)
                        diags.append(_diag(path, inst["line"], "warning", "implicit-wire",
                                           f"'.{pname}' shorthand needs a local net named '{pname}', which is not declared"))

            # 3. port count / names / widths
            tname = inst["type"]
            label = f"{tname} {inst['name'] or ''}".strip()
            if inst["is_primitive"]:
                need = _PRIM_ARITY.get(tname, 3)
                cnt = len(inst["positional"])
                if tname in LINT_GATES | set(_PRIM_ARITY) and (cnt < need or (tname in _PRIM_ARITY and tname.startswith(("bufif", "notif")) and cnt != 3)):
                    diags.append(_diag(path, inst["line"], "error", "gate-arity",
                                       f"Gate '{label}' has {cnt} terminal(s); '{tname}' needs " + ("exactly 3 (out, in, ctrl)" if need == 3 and tname in _PRIM_ARITY else f"at least {need} (output first, then inputs)")))
                continue
            target = known.get(tname)
            if target is None:
                alt = known_ci.get(tname.lower())
                if alt:
                    diags.append(_diag(path, inst["line"], "error", "unknown-module-case",
                                       f"Module '{tname}' not found - did you mean '{alt}'? (Verilog names are case-sensitive)"))
                else:
                    diags.append(_diag(path, inst["line"], "warning", "unknown-module",
                                       f"Module '{tname}' is not found in the workspace or any loaded package - "
                                       f"click [📦 Packages] to import it (iverilog will report it missing)"))
                continue
            tports = target["ports"]
            tnames = [p["name"] for p in tports]
            if inst["named"]:
                for pname in inst["connections"]:
                    if pname not in tnames:
                        diags.append(_diag(path, inst["line"], "error", "port-name",
                                           f"Instance '{label}': module '{tname}' has no port '.{pname}' (ports: {', '.join(tnames)})"))
                missing = [p for p in tnames if p not in inst["connections"]]
                if missing and not inst["wildcard"]:
                    diags.append(_diag(path, inst["line"], "warning", "port-unconnected",
                                       f"Instance '{label}': port(s) {', '.join(missing)} left unconnected"))
                pairs = [(next(p for p in tports if p["name"] == k), v) for k, v in inst["connections"].items() if k in tnames]
            else:
                if len(inst["positional"]) != len(tports):
                    diags.append(_diag(path, inst["line"], "error" if len(inst["positional"]) > len(tports) else "warning", "port-count",
                                       f"Instance '{label}' connects {len(inst['positional'])} port(s) but '{tname}' has {len(tports)}: "
                                       f"({', '.join(p['direction'][:3] + ' ' + p['name'] for p in tports)})"))
                pairs = list(zip(tports, inst["positional"]))
            if inst["params"] is None:
                for tp, expr in pairs:
                    if expr and re.fullmatch(r"[A-Za-z_]\w*", expr) and tp["bits"] and widths.get(expr) and widths[expr] != tp["bits"]:
                        diags.append(_diag(path, inst["line"], "warning", "port-width",
                                           f"Instance '{label}': '{expr}' is {widths[expr]} bit(s) but port '{tp['name']}' is {tp['bits']} bit(s)"))

        # 4. strict gate-level course mode
        if strict_gate_mode and not is_tb:
            diags.extend(_strict_scan(m["_code"], nl, m["body_start"], m["body_end"], path))

    # 5. testbench hygiene
    if is_tb:
        code = mods[0]["_code"]
        clean = mods[0]["_clean"]
        if not re.search(r"\$finish\b", code):
            stop = re.search(r"\$stop\b", code)
            line = _pos_to_linecol(nl, stop.start())[0] if stop else mods[0]["end_line"]
            diags.append(_diag(path, line, "warning", "no-finish",
                               "Testbench never calls $finish - " + ("$stop is handled by 'vvp -n', but $finish is the course convention"
                                                                      if stop else "the simulation will run until the timeout kills it")))
        if not re.search(r"\$(monitor|display|strobe|write)\b", code):
            diags.append(_diag(path, mods[0]["line"], "info", "no-output", "Testbench prints nothing ($monitor/$display) - the Truth Table tab will stay empty"))
        if not re.search(r"\$dumpfile\b", clean):
            diags.append(_diag(path, mods[0]["line"], "info", "no-vcd", "No $dumpfile/$dumpvars - the waveform will be synthesized from the printed truth table"))
    diags.sort(key=lambda d: (d["line"], {"error": 0, "warning": 1, "info": 2}[d["severity"]]))
    return diags


# --------------------------------------------------------------------------- testbench generator
def _lit(bits: int, value: int) -> str:
    return f"{bits}'b{value & ((1 << bits) - 1):0{bits}b}"


def generate_testbench_skeleton(module_info: dict, include_vcd: bool = True, step: int | None = None,
                                empty_stimulus: bool = False, checks: dict[str, str] | None = None) -> str:
    """Build a complete <Module>_tb.v for the given parsed module.

    empty_stimulus=True gives a skeleton: declarations, DUT wiring, dump/monitor and an empty stimulus section.
    checks={"sum": "a ^ b ^ cin", ...} makes it self-checking: after every vector each listed output is compared
    with its expected expression and a PASS / FAIL line is printed (FAIL rows show up red in the truth table)."""
    checks = {k: v.strip().rstrip(";").split("=", 1)[-1].strip() if v.strip().startswith(k) and "=" in v and "==" not in v
              else v.strip().rstrip(";") for k, v in (checks or {}).items() if v and v.strip()}
    name = module_info["module_name"]
    tb = f"{name}_tb"
    ports = module_info.get("ports", [])

    def bits(p: dict) -> int:
        return p["bits"] if isinstance(p.get("bits"), int) and p["bits"] > 0 else 1

    def decl_range(p: dict) -> str:
        if isinstance(p.get("width_msb"), int) and isinstance(p.get("width_lsb"), int) and bits(p) > 1:
            return f"[{p['width_msb']}:{p['width_lsb']}] "
        return ""
    clocks = [p for p in ports if p["direction"] == "input" and p["name"].lower() in ("clk", "clock") and bits(p) == 1]
    ins = [p for p in ports if p["direction"] == "input" and p not in clocks]
    outs = [p for p in ports if p["direction"] in ("output", "inout")]
    checked = [p for p in outs if p["name"] in checks]
    if checked:
        empty_stimulus = False                 # self-checking needs real stimulus vectors
    if step is None:
        step = 100
    total = sum(bits(p) for p in ins)
    unresolved = [p["name"] for p in ports if p.get("bits") is None]

    L = ["`timescale 1ns/1ns", "", f"// Auto-generated by VeriFlow Studio for module '{name}'"]
    if unresolved:
        L.append(f"// note: width of {', '.join(unresolved)} could not be resolved statically - declared as 1 bit, adjust if needed")
    L.append(f"// step = {step} time units; every vector is applied and sampled in a loop")
    L += [f"module {tb};", ""]
    for p in clocks + ins:
        L.append(f"    reg  {decl_range(p)}{p['name']};")
    for p in outs:
        L.append(f"    wire {decl_range(p)}{p['name']};")
    if 0 < total <= 7 and not empty_stimulus:
        L.append("    integer i;")
    if checked:
        L.append("    integer errors;")
        for p in checked:
            L.append(f"    reg  {decl_range(p)}exp_{p['name']};      // expected: {checks[p['name']]}")
    L.append("")
    if ports:
        w = max(len(p["name"]) for p in ports)
        conns = ",\n".join(f"        .{p['name'].ljust(w)} ({p['name']})" for p in ports)
        L += [f"    {name} uut (", conns, "    );", ""]
    else:
        L += [f"    {name} uut ();", ""]
    for c in clocks:
        L += [f"    initial {c['name']} = 1'b0;", f"    always #5 {c['name']} = ~{c['name']};", ""]
    shown = ins + outs
    L.append("    initial begin")
    if include_vcd:
        L += [f'        $dumpfile("{name}.vcd");', f"        $dumpvars(0, {tb});"]
    if shown:
        header = " | ".join(p["name"] for p in shown)
        L += [f'        $display("{header}");', f'        $display("{"-" * max(len(header), 8)}");']
    fmt = " | ".join(f"{p['name']}=%b" for p in shown)
    sample = f'$display("{fmt}", {", ".join(p["name"] for p in shown)});' if shown else ""
    if checked:
        L += ["        errors = 0;", "        // self-checking: every vector prints PASS or FAIL (FAIL rows turn red in the truth table)"]
    elif shown:
        L.append("        // sample once per vector, after the delay (settled values only)")
    L.append("")
    after = f" {sample}" if shown and not checked else ""
    vec_args = ", ".join(p["name"] for p in shown)

    def check_block(indent: str) -> list[str]:
        if not checked:
            return []
        cond = " || ".join(f"({p['name']} !== exp_{p['name']})" for p in checked)
        exp_txt = ", ".join(f"{p['name']} %b" for p in checked)
        exp_args = ", ".join(f"exp_{p['name']}" for p in checked)
        return ([f"{indent}exp_{p['name']} = {checks[p['name']]};" for p in checked] +
                [f"{indent}if ({cond}) begin",
                 f'{indent}    $display("FAIL: {fmt}   <- expected {exp_txt}", {vec_args}, {exp_args});',
                 f"{indent}    errors = errors + 1;",
                 f"{indent}end else",
                 f'{indent}    $display("PASS: {fmt}", {vec_args});'])
    if empty_stimulus:
        example = " ".join(f"{p['name']} = {_lit(bits(p), 0)};" for p in ins[:3]) or "// (no inputs)"
        L += ["        // ---- apply your stimulus here, for example:", f"        // {example} #{step};", ""]
    elif total == 0:
        L.append(f"        #{step};{after}")
        L += check_block("        ")
    elif total <= 7:
        concat = "{" + ", ".join(p["name"] for p in ins) + "}"
        L += [f"        for (i = 0; i < (1 << {total}); i = i + 1) begin",
              f"            {concat} = i;", f"            #{step};{after}"] + check_block("            ") + ["        end"]
    else:
        seed = 0x2545F491
        vectors = []
        for k in range(8):
            row = []
            for idx, p in enumerate(ins):
                b = bits(p)
                full = (1 << b) - 1
                alt_a = int(("10" * b)[:b], 2)
                alt_5 = int(("01" * b)[:b], 2)
                seed = (seed * 1103515245 + 12345) & 0xFFFFFFFF
                v = [0, full, alt_a, alt_5, full if idx == 0 else (1 if idx == 1 else 0),
                     1 << (b - 1), alt_a if idx % 2 == 0 else alt_5, (seed >> 7) & full][k]
                row.append(f"{p['name']} = {_lit(b, v)};")
            vectors.append(row)
        labels = ["all zeros", "all ones", "alternating 1010 (A)", "alternating 0101 (5)", "carry chain: max + 1",
                  "MSB only (overflow)", "mixed A/5", "pseudo-random"]
        for lab, row in zip(labels, vectors):
            L.append(f"        // {lab}")
            L.append("        " + " ".join(row) + f" #{step};{after}")
            L += check_block("        ")
    if checked:
        L += ['        if (errors == 0) $display("SELF-CHECK: all vectors PASSED");',
              '        else             $display("SELF-CHECK: %0d vector(s) FAILED", errors);']
    L += [f"        #{step} $finish;", "    end", "", "endmodule", ""]
    return "\n".join(L)


def new_module_template(name: str) -> str:
    return (f"`timescale 1ns/1ns\n\nmodule {name} (\n    output y,\n    input  a,\n    input  b\n);\n\n"
            f"    nand g1 (y, a, b);\n\nendmodule\n")


# --------------------------------------------------------------------------- VCD reader
def parse_vcd_file(vcd_path: Path | str, max_steps: int = 64) -> dict:
    """Minimal, fast VCD reader. Returns signals + per-signal (time, value) change lists."""
    text = Path(vcd_path).read_text(encoding="utf-8", errors="replace")
    toks = text.split()
    n, i = len(toks), 0
    scope: list[str] = []
    by_code: dict[str, list[dict]] = {}
    signals: list[dict] = []
    timescale = ""

    def skip_end(k: int) -> int:
        while k < n and toks[k] != "$end":
            k += 1
        return k + 1
    while i < n:
        t = toks[i]
        if t == "$timescale":
            j = skip_end(i)
            timescale = " ".join(toks[i + 1:j - 1])
            i = j
        elif t == "$scope":
            scope.append(toks[i + 2] if i + 2 < n else "?")
            i = skip_end(i)
        elif t == "$upscope":
            if scope:
                scope.pop()
            i = skip_end(i)
        elif t == "$var":
            j = skip_end(i)
            parts = toks[i + 1:j - 1]
            if len(parts) >= 4:
                kind, width, code, ref = parts[0], int(parts[1]) if parts[1].isdigit() else 1, parts[2], parts[3]
                if len(parts) > 4 and parts[4].startswith("["):
                    ref += parts[4]
                sig = {"name": ref, "scope": ".".join(scope), "full_name": ".".join(scope + [ref]), "width": width,
                       "code": code, "kind": kind, "depth": len(scope)}
                signals.append(sig)
                by_code.setdefault(code, []).append(sig)
            i = j
        elif t == "$enddefinitions":
            i = skip_end(i)
            break
        elif t.startswith("$"):
            i = skip_end(i)
        else:
            i += 1
    values: dict[str, list[tuple[int, str]]] = {s["full_name"]: [] for s in signals}
    times: list[int] = []
    cur_t, pending, truncated = 0, None, False

    def record(code: str, val: str) -> None:
        for s in by_code.get(code, ()):
            w = s["width"]
            if s["kind"] != "real" and len(val) < w:
                val = (val[0] if val[0] in "xz" else "0") * (w - len(val)) + val
            seq = values[s["full_name"]]
            if seq and seq[-1][0] == cur_t:
                seq[-1] = (cur_t, val)
            elif not seq or seq[-1][1] != val:
                seq.append((cur_t, val))
    while i < n:
        t = toks[i]
        i += 1
        if pending is not None:
            record(t, pending)
            pending = None
        elif t[0] == "#" and t[1:].isdigit():
            cur_t = int(t[1:])
            if not times or times[-1] != cur_t:
                times.append(cur_t)
                if len(times) > max_steps:
                    truncated = True
                    times.pop()
                    break
        elif t in ("$dumpvars", "$dumpall", "$dumpon", "$dumpoff", "$end"):
            continue
        elif t.startswith("$comment"):
            while i < n and toks[i] != "$end":
                i += 1
            i += 1
        elif t[0] in "bBrR":
            pending = t[1:].lower()
        elif t[0] in "01xXzZ":
            record(t[1:], t[0].lower())
    return {"timescale": timescale, "signals": signals, "values": values, "times": times,
            "end_time": times[-1] if times else 0, "truncated": truncated}
