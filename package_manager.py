"""VeriFlow Studio - global Verilog package manager ("import once, resolve anywhere on the PC").

Packages are folders of .v files:
  * builtin - the course library (`lib_dir`, normally C:\\iverilog\\compstruct\\lib); can be disabled, never removed
  * vault   - copies kept by VeriFlow in the global package vault (~/.veriflow_studio/packages/<name>)
  * linked  - an existing folder registered in place (scanned recursively)

Priority (first definition of a module name wins, both in the index and in the -y search order):
  Tier 1  the active workspace folder           - a student's own <Module>.v always wins
  Tier 2  enabled imported / linked packages
  Tier 3  the built-in course library

Duplicate handling - iverilog must never see two definitions of one module:
  * Imports (files / zip / folders) are *partial*: modules already provided by an enabled package are skipped
    (recorded per file in the package's `excluded_modules`), every new module is loaded. A file is only left
    out entirely when all of its modules are duplicates.
  * Disabled packages never block an import; re-enabling one is checked for conflicts first.
  * At compile time multi-module / renamed files are loaded with `-l`; if such a file also holds a module that a
    higher-priority definition shadows, the needed modules are extracted into single-module "cells"
    (<vault>/_cells/<workspace-hash>/<Module>.v) and resolved through `-y` instead.
"""
from __future__ import annotations

import copy
import hashlib
import os
import re
import shutil
import zipfile
from pathlib import Path

from config_manager import BUILTIN_PACKAGE_NAME
from verilog_parser import (GATE_PRIMITIVES, PACKAGE_SOURCE_EXTS, build_global_module_index, extract_module_source,
                            parse_all_modules_in_file, parse_verilog_source, resolve_required_library_files)

HEADER_EXTS = (".vh", ".svh")          # `include headers: copied with packages, exposed through -I, never indexed as modules
SUBMIT_EXTS = PACKAGE_SOURCE_EXTS + HEADER_EXTS
DEFAULT_IMPORT_PACKAGE = "Imported_Course_Modules"
MAX_ZIP_BYTES = 64 * 1024 * 1024          # refuse absurd archives (zip bombs)
MAX_FILES = 3000
_INCLUDE_RE = re.compile(r'`include\s+"([^"]+)"')


def safe_name(name: str) -> str:
    name = re.sub(r"[^\w.\- ]+", "_", name.strip()).strip(" .")
    return name[:80] or DEFAULT_IMPORT_PACKAGE


def _norm(p) -> str:
    return os.path.normcase(os.path.abspath(str(p)))


class PackageManager:
    def __init__(self, config):
        self.cfg = config
        self._cache: dict = {}

    # ------------------------------------------------------------------ registry
    @property
    def vault(self) -> Path:
        return Path(os.path.expanduser(self.cfg["global_packages_dir"]))

    def packages(self) -> list[dict]:
        """Registered packages with resolved paths (built-in path follows lib_dir)."""
        out = []
        for p in self.cfg["library_packages"]:
            path = Path(self.cfg["lib_dir"]) if p["kind"] == "builtin" else Path(p["path"])
            out.append({**p, "path": str(path), "exists": path.is_dir(), "excluded_modules": list(p.get("excluded_modules", []))})
        return out

    def _save(self, pkgs: list[dict]) -> None:
        self.cfg.update(library_packages=copy.deepcopy(pkgs))

    def _find(self, name_or_path: str) -> int:
        key = os.path.normcase(str(name_or_path))
        for i, p in enumerate(self.cfg["library_packages"]):
            if p["name"] == name_or_path or os.path.normcase(p["path"]) == key:
                return i
        return -1

    def _register(self, name: str, path: Path, kind: str, excluded: set[str] | None = None) -> dict:
        pkgs = copy.deepcopy(self.cfg["library_packages"])
        i = self._find(str(path))
        if i >= 0:
            pkgs[i]["enabled"] = True
            pkgs[i]["excluded_modules"] = sorted(set(pkgs[i].get("excluded_modules", [])) | (excluded or set()))
            entry = pkgs[i]
        else:
            base, k = name, 2
            while any(p["name"] == name for p in pkgs):
                name, k = f"{base} ({k})", k + 1
            entry = {"name": name, "path": str(path), "enabled": True, "builtin": False, "kind": kind,
                     "excluded_modules": sorted(excluded or set())}
            pkgs.append(entry)
        self._save(pkgs)
        return entry

    def _spec(self, p: dict) -> dict:
        return {"path": p["path"], "name": p["name"], "recursive": p["kind"] == "linked",
                "exclude_modules": p.get("excluded_modules", [])}

    def _lib_specs(self, enabled_only: bool = True) -> list[dict]:
        """Package specs in priority order: imported/linked packages (tier 2) before the built-in library (tier 3)."""
        pkgs = [p for p in self.packages() if p["exists"] and (p["enabled"] or not enabled_only)]
        return [self._spec(p) for p in sorted(pkgs, key=lambda q: q["kind"] == "builtin")]

    def enable_conflicts(self, package_name_or_path: str) -> list[dict]:
        """Modules of a (disabled) package that an enabled package already provides."""
        i = self._find(package_name_or_path)
        if i < 0:
            return []
        target = next(p for p in self.packages() if p["name"] == self.cfg["library_packages"][i]["name"])
        if not target["exists"]:
            return []
        own = build_global_module_index([self._spec(target)], None, self._cache)
        others = build_global_module_index([s for s in self._lib_specs() if s["name"] != target["name"]], None, self._cache)
        return [{"module": n, "existing": str(others[n]["filepath"]), "package": others[n]["package_name"]}
                for n in sorted(own) if n in others]

    def toggle_package_enabled(self, package_name_or_path: str, enabled: bool, force: bool = False) -> dict:
        """Enable/disable a package. Re-enabling is refused when one of its modules is already provided by an
        enabled package (iverilog would see two definitions); with force=True those packages are disabled instead."""
        i = self._find(package_name_or_path)
        if i < 0:
            return {"ok": False, "message": "package not found", "conflicts": [], "disabled": []}
        pkgs = copy.deepcopy(self.cfg["library_packages"])
        disabled: list[str] = []
        conflicts = self.enable_conflicts(pkgs[i]["name"]) if enabled and not pkgs[i]["enabled"] else []
        if conflicts and not force:
            names = ", ".join(sorted({c["module"] for c in conflicts}))
            return {"ok": False, "conflicts": conflicts, "disabled": [],
                    "message": f"'{pkgs[i]['name']}' defines {names}, already provided by "
                               f"{', '.join(sorted({c['package'] for c in conflicts}))}"}
        if conflicts:
            for c in conflicts:
                j = next((k for k, p in enumerate(pkgs) if p["name"] == c["package"]), -1)
                if j >= 0 and pkgs[j]["enabled"]:
                    pkgs[j]["enabled"] = False
                    disabled.append(pkgs[j]["name"])
        pkgs[i]["enabled"] = bool(enabled)
        self._save(pkgs)
        return {"ok": True, "conflicts": conflicts, "disabled": disabled, "message": ""}

    def remove_package(self, package_name_or_path: str, delete_vault_files: bool = True) -> dict:
        """Unregister a package. Vault copies are deleted; linked folders are only forgotten, never deleted."""
        pkgs = copy.deepcopy(self.cfg["library_packages"])
        i = self._find(package_name_or_path)
        if i < 0:
            return {"ok": False, "message": "package not found"}
        p = pkgs[i]
        if p["kind"] == "builtin":
            return {"ok": False, "message": "the built-in course library can be disabled but not removed"}
        deleted = False
        if p["kind"] == "vault" and delete_vault_files:
            path = Path(p["path"])
            if path.is_dir() and self._inside_vault(path):
                shutil.rmtree(path, ignore_errors=True)
                deleted = True
        del pkgs[i]
        self._save(pkgs)
        return {"ok": True, "message": f"removed '{p['name']}'" + (" and deleted its vault folder" if deleted else ""),
                "deleted_files": deleted}

    def _inside_vault(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self.vault.resolve())
            return path.resolve() != self.vault.resolve()
        except ValueError:
            return False

    # ------------------------------------------------------------------ global module registry
    def module_map(self, include_disabled: bool = False) -> dict[str, str]:
        """Map<ModuleName, AbsoluteFilePath> over the *enabled* packages (disabled ones never block anything)."""
        idx = build_global_module_index(self._lib_specs(enabled_only=not include_disabled), None, self._cache)
        return {n: str(Path(e["filepath"]).resolve()) for n, e in idx.items()}

    @staticmethod
    def _read(path: Path) -> str:
        return path.read_text(encoding="utf-8", errors="replace")

    def _vet(self, label: str, text: str, target: Path, rel: str, registry: dict[str, str], report: dict) -> bool:
        """Partial dedup of one source file. New modules are reserved in `registry`; duplicates are recorded as
        excluded ("<rel>|<module>"). Returns False only when every module of the file is a duplicate."""
        names = [m["module_name"] for m in parse_verilog_source(text)]
        tkey = os.path.normcase(str(target.resolve()))
        dups = [n for n in names if n in registry and os.path.normcase(registry[n]) != tkey]
        for n in dups:
            report["duplicates"].append({"file": label, "module": n, "existing": registry[n]})
        report["excluded"].update(f"{rel}|{n}" for n in dups)   # also for fully-duplicate files (a linked folder keeps them)
        if names and len(dups) == len(names):
            report["blocked"].append({"file": label, "conflicts": [{"module": n, "existing": registry[n]} for n in dups]})
            return False
        for n in names:
            if n not in dups:
                registry.setdefault(n, str(target.resolve()))
        return True

    def _summarize(self, entry: dict | None, files: list[Path], skipped: list[str], report: dict) -> dict:
        loaded: list[str] = []
        if entry is not None:                    # what the package index really serves from these files (per-file excludes)
            pkg = next((p for p in self.packages() if p["name"] == entry["name"]), None)
            if pkg is not None and pkg["exists"]:
                keys = {_norm(f) for f in files}
                idx = build_global_module_index([self._spec(pkg)], None, self._cache)
                loaded = sorted(n for n, e in idx.items() if _norm(e["filepath"]) in keys)
        return {"package": entry["name"] if entry else None, "path": entry["path"] if entry else None,
                "files": [f.name for f in files], "modules": loaded, "skipped": skipped,
                "blocked": report["blocked"], "duplicates": report["duplicates"]}

    def _finish(self, name: str, dest: Path, kind: str, copied: list[Path], skipped: list[str], report: dict) -> dict:
        known = self._find(str(dest)) >= 0
        if not copied and not known:                     # everything duplicated -> no empty package
            try:
                dest.rmdir()
            except OSError:
                pass
            return self._summarize(None, [], skipped, report)
        return self._summarize(self._register(name, dest, kind, report["excluded"]), copied, skipped, report)

    @staticmethod
    def _new_report() -> dict:
        return {"duplicates": [], "blocked": [], "excluded": set()}

    # ------------------------------------------------------------------ imports (partial deduplication)
    def import_files_to_package(self, file_paths: list, package_name: str = DEFAULT_IMPORT_PACKAGE) -> dict:
        """Copy .v/.sv modules (and .vh headers) into the vault package `package_name`, skipping duplicates."""
        registry = self.module_map()
        dest = self.vault / safe_name(package_name)
        dest.mkdir(parents=True, exist_ok=True)
        copied, skipped, report = [], [], self._new_report()
        for src in map(Path, file_paths):
            ext = src.suffix.lower()
            if ext not in SUBMIT_EXTS or not src.is_file():
                skipped.append(src.name)
                continue
            target = dest / src.name
            if ext in PACKAGE_SOURCE_EXTS and not self._vet(src.name, self._read(src), target, src.name, registry, report):
                continue
            if os.path.normcase(str(src.resolve())) != os.path.normcase(str(target.resolve())):
                shutil.copy2(src, target)
            copied.append(target)
        return self._finish(safe_name(package_name), dest, "vault", copied, skipped, report)

    def import_zip_package(self, zip_path, package_name: str | None = None) -> dict:
        """Extract every .v/.sv/.vh from a course .zip (flattened, path-traversal safe), skipping duplicates."""
        zip_path = Path(zip_path)
        name = safe_name(package_name or zip_path.stem)
        dest = self.vault / name
        dest.mkdir(parents=True, exist_ok=True)
        registry = self.module_map()
        copied, skipped, report, total = [], [], self._new_report(), 0
        with zipfile.ZipFile(zip_path) as zf:
            for info in zf.infolist():
                parts = [p for p in re.split(r"[\\/]+", info.filename) if p]
                if info.is_dir() or not parts or "__MACOSX" in parts or parts[-1].startswith("."):
                    continue
                ext = Path(parts[-1]).suffix.lower()
                if ext not in SUBMIT_EXTS:
                    skipped.append(info.filename)
                    continue
                total += info.file_size
                if total > MAX_ZIP_BYTES or len(copied) >= MAX_FILES:
                    raise ValueError("archive too large for a Verilog package")
                data = zf.read(info)
                target = self._unique_target(dest, safe_name(parts[-1]), parts[-2] if len(parts) > 1 else "")
                if ext in PACKAGE_SOURCE_EXTS and not self._vet(info.filename, data.decode("utf-8", "replace"),
                                                                target, target.name, registry, report):
                    continue
                target.write_bytes(data)
                copied.append(target)
        return self._finish(name, dest, "vault", copied, skipped, report)

    def add_external_library_folder(self, folder_path, name: str | None = None, copy_to_vault: bool = False) -> dict:
        """Register a folder in place (linked, scanned recursively) or copy its .v/.vh files into the vault.
        Never refused as a whole: duplicate modules are skipped, every new module is loaded."""
        folder = Path(folder_path)
        if not folder.is_dir():
            raise ValueError(f"not a folder: {folder}")
        display = (name or folder.name).strip() or folder.name
        name = safe_name(display)                 # folder-safe name only matters for vault copies
        registry = self.module_map()
        files = sorted((p for p in folder.rglob("*") if p.suffix.lower() in SUBMIT_EXTS and p.is_file()),
                       key=lambda p: str(p).lower())[:MAX_FILES]
        report = self._new_report()
        if not copy_to_vault:
            kept = []
            already = self._find(str(folder)) >= 0
            for f in files:
                rel = f.relative_to(folder).as_posix()
                if f.suffix.lower() not in PACKAGE_SOURCE_EXTS or already or self._vet(rel, self._read(f), f, rel, registry, report):
                    kept.append(f)
            if not kept:
                return self._summarize(None, [], [], report)
            return self._summarize(self._register(display, folder, "linked", report["excluded"]), kept, [], report)
        dest = self.vault / name
        dest.mkdir(parents=True, exist_ok=True)
        copied = []
        for src in files:
            target = self._unique_target(dest, src.name, src.parent.name if src.parent != folder else "")
            if src.suffix.lower() in PACKAGE_SOURCE_EXTS and not self._vet(str(src.relative_to(folder)), self._read(src),
                                                                           target, target.name, registry, report):
                continue
            shutil.copy2(src, target)
            copied.append(target)
        return self._finish(name, dest, "vault", copied, [], report)

    def _unique_target(self, dest: Path, name: str, hint: str = "") -> Path:
        target = dest / name
        if target.exists() and hint:
            target = dest / f"{safe_name(hint)}_{name}"
        return target

    # ------------------------------------------------------------------ indexing & resolution
    def build_index(self, work_dir=None, exclude_files: list | None = None) -> dict[str, dict]:
        """Tier 1 workspace, tier 2 imported/linked packages, tier 3 built-in library (first definition wins)."""
        return build_global_module_index(self._lib_specs(), work_dir, self._cache, exclude_files)

    def modules_by_package(self) -> list[tuple[dict, list[dict]]]:
        """[(package, [module entries defined in it])] for every registered package (enabled or not)."""
        out = []
        for p in self.packages():
            idx = build_global_module_index([self._spec(p)], None, self._cache) if p["exists"] else {}
            out.append((p, sorted(idx.values(), key=lambda m: m["module_name"].lower())))
        return out

    def stats(self) -> tuple[int, int]:
        active = [p for p in self.packages() if p["enabled"] and p["exists"]]
        return len(active), len(self.build_index())

    def include_dirs(self) -> list[str]:
        """Folders of enabled packages that hold `include headers (.vh/.svh) -> passed to iverilog with -I."""
        out: list[str] = []
        for p in self.packages():
            if not (p["enabled"] and p["exists"]):
                continue
            root = Path(p["path"])
            for f in (root.rglob("*") if p["kind"] == "linked" else root.iterdir()):
                if f.suffix.lower() in HEADER_EXTS and f.is_file() and str(f.parent) not in out:
                    out.append(str(f.parent))
        return out

    def _unsafe_roots(self) -> set[str]:
        """Package folders that physically contain an excluded duplicate `<Name>.v` which iverilog's -y search would
        find. These folders are never passed with -y; their needed modules are served from _cells instead."""
        out = set()
        for p in self.packages():
            for e in p.get("excluded_modules", []):
                rel, _, mod = e.rpartition("|")
                if rel and "/" not in rel and Path(rel).stem == mod and Path(rel).suffix.lower() == ".v":
                    out.add(_norm(p["path"]))
        return out

    def y_search_dirs(self) -> list[str]:
        """Enabled package folders that are safe to pass with -y, in priority order (packages, then course lib)."""
        unsafe = self._unsafe_roots()
        return [str(d) for d in self.cfg.get_all_enabled_library_dirs() if _norm(d) not in unsafe]

    def cells_dir(self, work_dir) -> Path:
        return self.vault / "_cells" / hashlib.sha1(_norm(work_dir).encode()).hexdigest()[:10]

    def resolve(self, work_dir, module: str, extra_files: list | tuple = ()) -> dict:
        """Everything the compiler needs for <module>.v + <module>_tb.v compiled from work_dir."""
        work_dir = Path(work_dir)
        design_matches = list(work_dir.rglob(f"{module}.v"))
        tb_matches = list(work_dir.rglob(f"{module}_tb.v"))
        roots = ([design_matches[0]] if design_matches else [work_dir / f"{module}.v"])
        roots += ([tb_matches[0]] if tb_matches else [work_dir / f"{module}_tb.v"])
        roots += [work_dir / f for f in extra_files]
        index = self.build_index(work_dir, exclude_files=roots)
        shadowed: dict = {}
        needed: list[str] = []
        y_dirs, l_files, missing = resolve_required_library_files(roots, index, shadowed, needed)
        final_l, cells, notes = [], {}, []
        unsafe = self._unsafe_roots()
        if unsafe:                                   # modules from folders that also hold a skipped duplicate -> cells
            moved = [n for n in needed if n in index and _norm(index[n]["package_root"]) in unsafe]
            for n in moved:
                src = extract_module_source(self._read(Path(index[n]["filepath"])), n)
                if src:
                    cells[n] = src
            gone = {_norm(index[n]["filepath"]) for n in moved} | {_norm(Path(index[n]["filepath"]).parent) for n in moved}
            y_dirs = [d for d in y_dirs if _norm(d) not in unsafe]
            l_files = [f for f in l_files if _norm(f) not in gone]
            if moved:
                notes.append(f"{', '.join(moved)} via _cells (their package folder also holds a skipped duplicate)")
        for lf in l_files:
            if lf not in shadowed:
                final_l.append(lf)
                continue
            owned = [m["module_name"] for m in parse_all_modules_in_file(lf)
                     if m["module_name"] in index and _norm(index[m["module_name"]]["filepath"]) == _norm(lf)]
            text = self._read(Path(lf))
            for n in owned:
                src = extract_module_source(text, n)
                if src:
                    cells[n] = src
            notes.append(f"{Path(lf).name}: {', '.join(owned) or 'nothing'} via _cells "
                         f"(skipped duplicate {', '.join(sorted(shadowed[lf]))} - a higher-priority definition wins)")
        if cells:
            y_dirs.append(str(self._write_cells(work_dir, cells)))
        return {"y_dirs": y_dirs, "l_files": final_l, "missing": missing, "notes": notes, "cells": sorted(cells),
                "enabled_dirs": [str(p) for p in self.cfg.get_all_enabled_library_dirs()]}

    def _write_cells(self, work_dir, cells: dict[str, str]) -> Path:
        cdir = self.cells_dir(work_dir)
        cdir.mkdir(parents=True, exist_ok=True)
        for old in cdir.glob("*.v"):
            if old.stem not in cells:
                old.unlink(missing_ok=True)          # a stale cell must never shadow a newer definition
        for name, src in cells.items():
            f = cdir / f"{name}.v"
            if not f.is_file() or self._read(f) != src:
                f.write_text(src, encoding="utf-8")
        return cdir

    def open_vault_folder(self) -> Path:
        self.vault.mkdir(parents=True, exist_ok=True)
        return self.vault

    # ------------------------------------------------------------------ live duplicate check for editor buffers
    def editor_collisions(self, path, text: str, work_dir, extra_files: list | tuple = ()) -> list[dict]:
        """Catches a module renamed in the editor to a name another workspace file or a package already uses."""
        path = Path(path)
        diags: list[dict] = []
        if not work_dir:
            return diags
        ws = build_global_module_index([], work_dir, self._cache, exclude_files=[path])
        pk = self.build_index(None)
        extras = {os.path.normcase(str(Path(work_dir) / f)) for f in extra_files}
        for m in parse_verilog_source(text):
            n = m["module_name"]
            if n in ws:
                other = Path(ws[n]["filepath"])
                compiled = os.path.normcase(str(other)) in extras
                diags.append({"file": str(path), "line": m["line"], "col": 0, "source": "registry", "code": "duplicate-module",
                              "severity": "error" if compiled else "warning",
                              "message": f"Module '{n}' is also defined in {other.name} - "
                                         + ("both are compiled, iverilog will fail with 'already declared'; rename one"
                                            if compiled else "rename one of them (iverilog fails with 'already declared' "
                                                             "if both files are ever compiled together)")})
            elif n in pk:
                diags.append({"file": str(path), "line": m["line"], "col": 0, "source": "registry", "code": "shadows-package",
                              "severity": "info",
                              "message": f"Module '{n}' also exists in package '{pk[n]['package_name']}' "
                                         f"({Path(pk[n]['filepath']).name}) - your definition is used, the package copy is masked"})
        return diags

    # ------------------------------------------------------------------ homework submission packager
    def submission_plan(self, work_dir) -> dict:
        """Which workspace files go into the submission zip, which are left out, and which helper modules from
        imported/linked packages (not the course library) the design instantiates."""
        wd = Path(work_dir)
        files, excluded = [], []
        for f in sorted(wd.iterdir(), key=lambda p: p.name.lower()):
            if not f.is_file():
                continue
            n = f.name
            temp = n.endswith("~") or n.startswith(("~$", ".")) or f.suffix.lower() in (".bak", ".tmp", ".swp", ".orig")
            if f.suffix.lower() in SUBMIT_EXTS and not temp:
                files.append(f)
            else:
                excluded.append(n)          # vvp images (no extension), .vcd dumps, zips, temp/backup files
        builtin = next((p["name"] for p in self.packages() if p["kind"] == "builtin"), BUILTIN_PACKAGE_NAME)
        index = self.build_index(wd)
        own = {m["module_name"] for f in files if f.suffix.lower() in PACKAGE_SOURCE_EXTS for m in parse_all_modules_in_file(f)}
        queue = [i["type"] for f in files if f.suffix.lower() in PACKAGE_SOURCE_EXTS
                 for m in parse_all_modules_in_file(f) for i in m["instantiations"]]
        helpers, seen = {}, set()
        while queue:
            n = queue.pop(0)
            if n in seen or n in GATE_PRIMITIVES or n in own:
                continue
            seen.add(n)
            e = index.get(n)
            if e is None or e["package_name"] in ("Workspace", builtin):
                continue
            helpers[n] = {"module": n, "file": str(e["filepath"]), "package": e["package_name"]}
            queue.extend(i["type"] for i in e["instantiations"])
        return {"files": files, "excluded": excluded, "helpers": sorted(helpers.values(), key=lambda h: h["module"])}

    def build_submission_zip(self, work_dir, out_path, include_helpers: bool = True, plan: dict | None = None) -> dict:
        plan = plan or self.submission_plan(work_dir)
        out_path = Path(out_path)
        added: list[str] = []
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
            names = set()
            for f in plan["files"]:
                if _norm(f) != _norm(out_path):
                    z.write(f, f.name)
                    names.add(f.name.lower())
            if include_helpers:
                for h in plan["helpers"]:
                    arc = f"{h['module']}.v"
                    if arc.lower() in names:
                        continue
                    src = extract_module_source(self._read(Path(h["file"])), h["module"])
                    if not src:
                        continue
                    z.writestr(arc, src)
                    names.add(arc.lower())
                    added.append(arc)
                    for inc in _INCLUDE_RE.findall(src):          # headers the helper `includes travel with it
                        hdr = Path(h["file"]).parent / inc
                        if hdr.is_file() and hdr.name.lower() not in names:
                            z.write(hdr, hdr.name)
                            names.add(hdr.name.lower())
                            added.append(hdr.name)
        return {"zip": str(out_path), "files": [f.name for f in plan["files"]], "helpers": added,
                "excluded": plan["excluded"]}


__all__ = ["PackageManager", "DEFAULT_IMPORT_PACKAGE", "BUILTIN_PACKAGE_NAME", "HEADER_EXTS", "safe_name"]
