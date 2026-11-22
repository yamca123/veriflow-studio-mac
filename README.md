<a id="top"></a>

## macOS quick start

The app supports Apple silicon and Intel Macs. Install Icarus Verilog with Homebrew:

```bash
brew install icarus-verilog
# Optional waveform viewer:
brew install gtkwave
```

From a terminal in the repository:

```bash
chmod +x run_macos.sh build_macos.sh
./run_macos.sh
```

To create a standalone `VeriFlow Studio.app`:

```bash
./build_macos.sh
open "dist/VeriFlow Studio.app"
```

Settings are stored at `~/Library/Application Support/VeriFlowStudio/config.json`.
On macOS, use **Command** for editor shortcuts (`Cmd+O`, `Cmd+N`, `Cmd+S`, `Cmd+F`, and `Cmd+/`).

[🇬🇧 English](#english-documentation) | [🇮🇱 עברית (Hebrew Documentation)](#תיעוד-מלא-בעברית)

# VeriFlow Studio — VS Code-Styled Icarus Verilog IDE & One-Click Runner

![Windows](https://img.shields.io/badge/Windows-10%20%2F%2011-0078D6?logo=windows&logoColor=white)
![Latest release](https://img.shields.io/github/v/release/Nirco99/veriflow-studio?label=latest%20version&color=2EA043)
![Icarus Verilog -g2012](https://img.shields.io/badge/Icarus%20Verilog-(--g2012)-8A2BE2)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

<a id="download"></a>

## ⬇️ Download (Windows)

<p align="center">
  <a href="https://github.com/Nirco99/veriflow-studio/releases/latest/download/VeriFlowStudio.exe">
    <img src="https://img.shields.io/badge/%E2%AC%87%20Download-VeriFlowStudio.exe%20(Windows)-2EA043?style=for-the-badge&logo=windows&logoColor=white" height="60" alt="Download VeriFlowStudio.exe">
  </a>
</p>
<h3 align="center"><a href="https://github.com/Nirco99/veriflow-studio/releases/latest/download/VeriFlowStudio.exe">⬇️ Download VeriFlowStudio.exe (latest version)</a></h3>

| Step | What to do |
|:---:|---|
| **1** | Click the green **Download** button above. `VeriFlowStudio.exe` (about 32 MB, always the latest version) starts downloading. |
| **2** | Double-click the file. **Nothing to install** and no Python needed. Keep it anywhere (Desktop, Documents) and pin it to the taskbar. |
| **3** | If Windows shows *"Windows protected your PC"*, click **More info → Run anyway** (the file isn't code-signed). |
| **4** | Make sure **Icarus Verilog** is installed at `C:\iverilog`, as in the course. Without it VeriFlow still opens, in demo mode. |
| **5** | Done. New versions show up inside the app: **🔔 Update Available → Update & Restart Now**. |

Button not working? Open the **[latest release page](https://github.com/Nirco99/veriflow-studio/releases/latest)** and click **`VeriFlowStudio.exe`** under **Assets**.

🇮🇱 **הוראות הורדה בעברית: [כאן](#download-he)**

<a id="screenshots"></a>

## 📸 Screenshots

<p align="center"><img src="docs/screenshots/02-editor-run-console.png" width="100%" alt="Editor, testbench and a self-checking run"></p>
<p align="center"><sub><b>Design + testbench side by side, one-click run (F5), self-checking PASS lines</b></sub></p>

<table>
  <tr>
    <td width="50%"><img src="docs/screenshots/01-welcome.png" alt="Welcome page"><br><sub><b>Welcome page</b>: new module / assignment, open folder, recent folders</sub></td>
    <td width="50%"><img src="docs/screenshots/06-intellisense-modules.png" alt="IntelliSense module list"><br><sub><b>Live IntelliSense</b>: modules from your folder, the course library and your packages</sub></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/07-intellisense-ports.png" alt="Port completion"><br><sub><b>Port completion</b>: type <code>.</code> inside an instance to see its ports</sub></td>
    <td><img src="docs/screenshots/03-truth-table.png" alt="Truth table"><br><sub><b>Truth table</b> with radix switch, filters and PASS/FAIL status</sub></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/04-waveform.png" alt="Waveform viewer"><br><sub><b>Waveform viewer</b> (VCD) with zoom and cursor</sub></td>
    <td><img src="docs/screenshots/05-hierarchy-pinout.png" alt="Hierarchy and pinout"><br><sub><b>Hierarchy & gate count</b> plus the IC pinout diagram</sub></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/09-new-module-wizard.png" alt="New module wizard"><br><sub><b>New Module wizard</b>: folder, ports and testbench in one step</sub></td>
    <td><img src="docs/screenshots/10-package-manager.png" alt="Package manager"><br><sub><b>Packages</b>: load lecturer modules once, use them in every folder</sub></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/08-context-menu.png" alt="Context menu"><br><sub><b>Right-click menu</b>: generate a testbench, open in Notepad++</sub></td>
    <td><img src="docs/screenshots/11-light-theme.png" alt="Light theme"><br><sub><b>Light theme</b> (☀ button), with every size scaling together</sub></td>
  </tr>
</table>

---

<a id="english-documentation"></a>

## English Documentation

### Table of contents

1. [Overview & motivation](#overview--motivation)
2. [Features](#features)
3. [Download & quick start](#download--quick-start)
4. [Step-by-step usage guide](#step-by-step-usage-guide)
5. [Settings reference](#settings-reference)
6. [Keyboard shortcuts](#keyboard-shortcuts)
7. [Architecture & file structure](#architecture--file-structure)
8. [Troubleshooting](#troubleshooting)
9. [License](#license)

### Overview & motivation

In a university **Computer Structure** course, every lab and homework assignment follows the same ritual: write a
gate-level module `<Module>.v`, write a testbench `<Module>_tb.v`, then type two long commands into `cmd.exe` —
again and again, for every single change:

```bat
C:\iverilog\bin\iverilog -g2012 -oFullAdder -y "C:\iverilog\compstruct\lib" FullAdder.v FullAdder_tb.v
C:\iverilog\bin\vvp FullAdder
```

Then you scroll through raw `$monitor` text to find the one row that is wrong, guess which of your wires is floating at
`z`, and wonder why a lecturer module "cannot be found" when the file is right there.

**VeriFlow Studio** replaces that loop with a fast native desktop environment that looks and feels like VS Code:

* **One click (or `F5`)** saves, lints, compiles with `iverilog`, simulates with `vvp`, and fills four result views.
* **Live two-way Notepad++ sync** – keep coding in Notepad++; every `Ctrl+S` there re-runs the whole pipeline.
* **A course-aware linter** catches the silent bugs `iverilog` happily accepts (implicit wires, port mismatches,
  file/module name mismatches that break `-y`).
* **Automatic truth tables and waveforms** straight from your testbench output and `.vcd` dump.

### Features

#### ▶ One-click atomic pipeline (`F5` / `▶ Run`)

<p align="center"><img src="docs/screenshots/02-editor-run-console.png" width="860" alt="Editor and run"></p>

Every run performs, in order:

1. **Auto-save** of modified editor buffers (configurable).
2. **Static course linter** on both files (results go to *Problems & Linter*).
3. **Stale-binary removal** – the previous `<WorkDir>\<Module>` image is deleted first, so a failed compile can never
   silently execute an old binary.
4. **Compilation** – `iverilog -g2012 -o<Module> -y <workspace> -y <lecturer lib> -y <packages…> -Wall -Winfloop [-l <package file>…] <Module>.v <Module>_tb.v [extra files]`.
   The `-y` paths (and any `-l` library files – see the package loader below) are added automatically, so your own
   sub-modules (e.g. `HalfAdder.v`), the lecturer's modules and every loaded package are found without listing them. Success requires exit code `0`, no error lines, **and** a freshly written output file.
5. **Simulation** – `vvp -n <Module>`. The `-n` flag turns `$stop` into `$finish`, so a testbench can never hang
   waiting for interactive input. A configurable **timeout** (default 3 s) kills the whole process tree
   (`taskkill /F /T`) if the testbench has no `$finish` or contains a zero-delay infinite loop.
6. **Results** – Console, Problems & Linter, Truth Table and Waveform are all refreshed. The status bar turns **orange**
   while running, **red** on a compile error or timeout, and back to **blue** when done.

Compiler output is parsed with a Windows-safe regex that understands drive letters and column numbers
(`C:\iverilog\compstruct\lib\mux.v:14: syntax error`, `FullAdder.v:9:12: error: …`), plus fatal lines such as
`I give up.` and `No top level modules`.

#### ✍ Dual workflow — built-in editor **or** live Notepad++ sync

**Built-in editor.** Design (`.v`) and testbench (`_tb.v`) open side by side (or as tabs) with:

* VS Code **Dark+ / Light+** syntax colours for Verilog/SystemVerilog (keywords, net types, gate primitives,
  system tasks, numbers, strings, comments).
* Line-number gutter with the current line highlighted, error (red) and warning (amber) markers with hover tooltips.
* VS Code-style editor tabs with a dirty dot (`●`) and a breadcrumb bar:
  `sample_project › FullAdder.v › module FullAdder (output sum, output cout, input a, input b, input cin)`.
* Smart editing: auto-indent, auto-close `() [] {} ""`, `begin` + `Enter` inserts the matching `end`,
  Tab/Shift+Tab block indent, toggle comments, duplicate line, inline Find & Replace, Go to Line.
* Snippets (`+ Snippet ▾` or right-click → *Insert Snippet*): `module … endmodule`, `initial begin … end`,
  `always @(*)`, `$monitor`, `$display`, `$dumpfile/$dumpvars`, an exhaustive `for` loop and every gate primitive.
* Keyboard shortcuts also work with a **Hebrew keyboard layout** (they are matched by physical key).

**⚡ Live Notepad++ Sync.** Turn on the `⚡ N++ Sync` switch and VeriFlow polls the active `.v` / `_tb.v` files every
**800 ms** (configurable 500–3000 ms). When you press `Ctrl+S` in Notepad++, VeriFlow reloads the code, re-lints,
compiles, simulates and updates the truth table and waveform — no clicks needed. If you also have unsaved edits inside
VeriFlow, it refuses to overwrite them and warns you instead.

* `📝 N++` (Notepad++) opens both files of the active module in Notepad++ and switches Live Sync on automatically.
* Clicking a problem that lives in a file not open in the editors (for example a lecturer library file) opens it in
  Notepad++ **at the exact line** (`notepad++ -n<line> <file>`).

#### 📁 Workspace explorer & 📚 library inspector

* The **Explorer** pairs every `<Module>.v` with `<Module>_tb.v` automatically: a green dot + `Ready` badge when the
  testbench exists, an amber dot + `No TB` badge when it is missing.
* **Extra .v files (compile overrides)** lets you tick additional files to pass to `iverilog` explicitly (normally not
  needed thanks to `-y`).
* The **Library & Packages** view lists every module in `C:\iverilog\compstruct\lib` (44 modules in the standard course
  library) and in every loaded package (see below), with a live search box (type `mux`, `adder`, `xor`…). Selecting a module shows its parameters and exact port
  signature, and two buttons paste ready-made wiring:
  `📋 Copy Instantiation` and `⤵ Insert at Cursor`, e.g.

  ```verilog
  mux #(.SEL(1)) u1 (
      .out (out),
      .in  (in),
      .s   (s)
  );
  ```

#### 📦 Global Module & Package Loader ("Import Once, Run Anywhere")

<p align="center"><img src="docs/screenshots/10-package-manager.png" width="720" alt="Package manager"></p>

Lecturers hand out modules as loose `.v` files, as a folder, or as a Moodle `.zip` – often with **several modules in one
file** (`course_primitives.v`) or a **file name that differs from the module name** (`mux_lib.v` containing
`module Mux4`). Plain `iverilog -y <dir>` only finds a module stored in a file called exactly `<ModuleName>.v`, so
those fail with `error: Unknown module type`. VeriFlow's package manager solves this **once for the whole PC**: load the
modules one time, and every new `.v` file you create in *any* folder (`Desktop\HW4`, `Documents\Lab5`,
`Downloads\Test`…) can instantiate them with zero per-folder setup.

**Load modules once** – from the **📚 Library & Packages** side bar, the **`📦 Packages`** toolbar button, or
**⚙ Settings → Packages**:

| Button | What it does |
|---|---|
| `+ .v Files` | Pick one or more `.v` / `.sv` files anywhere on the PC. They are **copied into the global package vault** (you name the package; default `Imported_Course_Modules`). |
| `+ Folder` | **Yes** = copy the folder's `.v` files into the vault (keeps working even if the original folder is moved or deleted). **No** = **link the folder in place** – it is scanned recursively and always uses its latest files. |
| `+ .zip` | Pick a course `.zip` (e.g. from Moodle). Every `.v` / `.sv` inside is extracted into a vault package named after the archive; folder structure is flattened and other files are skipped. |

The vault lives at `%USERPROFILE%\.veriflow_studio\packages\<package>` (setting `global_packages_dir`).

**How compiling finds them – from any folder:**

1. **`-y` in a strict 3-tier priority order** – **Tier 1** the workspace folder (a student's own `<Module>.v` always
   wins), **Tier 2** enabled imported / linked packages, **Tier 3** the course library `C:\iverilog\compstruct\lib`.
   The module index uses exactly the same order, so the linter, the hierarchy view and the compiler always agree.
2. **`-l` for files `-y` cannot see.** VeriFlow indexes every module in every package (all modules of multi-module
   files included) and traces your design's instantiations **recursively** (`Top` → `Mux4` → `Mux2`…). Any needed module
   that lives in a multi-module file, a file whose name differs from the module, a `.sv` file, or a sub-folder is loaded
   with **`-l <file>`** – iverilog's *library file* mode, so only the modules you actually use are elaborated and the rest
   never become stray top-level modules. The flags are placed before the source files, as iverilog requires.
3. **Zero "already declared" clashes (`_cells`).** iverilog is never given two files that define the same module. If
   a multi-module file holds a module you need (`ModA`) *and* a module that a higher-priority definition shadows
   (`ModB`), VeriFlow extracts `ModA` – with its `` `timescale``/`` `define`` lines – into a single-module cell
   `<vault>\_cells\<workspace>\ModA.v` and resolves it through `-y`. The same happens for any package folder that still
   physically contains a skipped duplicate, so iverilog's own `-y` search can never pick the wrong copy.

**Smart partial deduplication at load time.** VeriFlow keeps one map *module name → absolute file path* over the
**enabled** packages. When you load `.v` files, a `.zip` or a folder (copied or linked), every **new** module is loaded
and every module that an enabled package already provides is **skipped** – never the whole folder. A file is only left
out when *all* of its modules are duplicates; a mixed file is kept and just its duplicate is masked (recorded per file
in the package's `excluded_modules`). You get one clear note, e.g.
*"Loaded 10 new module(s) from Lab4_Modules (skipped 1 duplicate – already provided by compstruct\lib: HalfAdder)"*,
and the Console lists where each skipped module already lives. Re-importing the *same* file into its own package simply
updates it.

**Disabled packages never block anything.** Only enabled packages count as "already provided", so you can disable an
old package and import an updated copy of the same modules. Re-enabling a package is checked first: if one of its
modules is now provided by another enabled package, VeriFlow tells you which module clashes with which package and
offers to disable the other package instead – otherwise the package stays disabled.

**`.vh` / `.svh` headers** are imported together with the modules (from files, folders and zips). They are never treated
as modules; instead every package folder that contains headers – plus the workspace – is passed with `-I`, so
`` `include "defs.vh" `` works from any folder.

**Renames in the editor are tracked live:** the linter uses the unsaved buffer, so renaming `module Top` to a name that
another workspace file or a package already uses is reported immediately (an error if both files are compiled together).

A resolved command looks like:

```bat
iverilog -g2012 -oTop -y "D:\HW4" -y "C:\iverilog\compstruct\lib" -y "%USERPROFILE%\.veriflow_studio\packages\course_modules" ^
         -Wall -Winfloop -l "...\course_modules\mux_lib.v" -l "...\course_modules\course_primitives.v" Top.v Top_tb.v
```

The console prints `📦 auto-loaded with -l: mux_lib.v, course_primitives.v`, and the panel's **Actual / Baseline** switch
still shows either this full command or the minimal command from the course instructions.

**Browsing and using packages**

* The **📚 Library & Packages** view groups modules per package (`▾ 📦 Course Built-in Library [44]`,
  `▾ 📦 course_modules [3]`…) with an on/off checkbox per package and a search box across **all** loaded modules
  (`Mux`, `Adder`, `DFF`…).
* Click a module to see its package, file, how it is resolved (`-y` or `-l`), its parameters and port signature, then
  `📋 Copy Instantiation` or `⤵ Insert at Cursor`. **Double-click** opens a read-only preview of its source.
* The **Package Manager** window (`📦 Packages`) lists every package with its type (course library / vault copy /
  linked folder), module count and location, and lets you enable or disable it, open its folder, or remove it. Removing a
  vault package deletes only the vault copy (after a confirmation); removing a linked folder only forgets it – your files
  are never touched; the built-in course library can be disabled but not removed.
* The status bar shows `📦 Packages: K active (M modules indexed)` – click it to jump to the library.
* The course linter uses the same index: port count/name/width checks also apply to package modules, and an unknown
  module is reported as *"Module 'Mux8' is not found in the workspace or any loaded package – click [📦 Packages] to
  import it"*.

#### 🧪 One-click testbench (`_tb.v`) generator

Every newly generated testbench uses a single `$display` row after each timed vector. This avoids `$monitor`
duplicates and prints only settled values after gate propagation delays.

`🧪 Gen _tb.v` parses the design (ANSI and non-ANSI ports, comma lists such as `input [3:0] a, b, c;`,
parameterised headers like `module Mux #(parameter W=16)`, multi-bit buses `[msb:lsb]`) and writes a complete
`<Module>_tb.v`:

* `reg` for every input, `wire` for every output (bus ranges preserved), `<Module> uut (.port(port), …)`.
* `$dumpfile("<Module>.vcd"); $dumpvars(0, <Module>_tb);`, a header line, and `$monitor` printing
  `a=%b | b=%b | … | y=%b`.
* **N ≤ 7 input bits:** an exhaustive loop `for (i = 0; i < (1 << N); i = i + 1) begin {in1, in2, …} = i; #10; end`.
* **N > 7 input bits:** 8 structured corner-case vectors (all zeros, all ones, `1010…`/`0101…` patterns,
  carry chain `max + 1`, MSB-only overflow, mixed, pseudo-random).
* A `clk`/`clock` input gets its own `always #5` clock instead of being enumerated.
* Designs built from **lecturer modules** (which have `#5` gate delays) automatically use a longer step (`#100`) and
  sample outputs with `$display` after each step, so the truth table shows settled values instead of glitches.
* Ends with `#… $finish;`.
* **Right-click a module** in the Explorer (or right-click inside the design editor) → **Generate Testbench (exhaustive)**
  or **Generate Skeleton Testbench (empty initial)**. The skeleton has the same declarations, `uut` wiring,
  `$dumpfile`/`$dumpvars` and `$monitor`, but an empty stimulus section for you to fill in. The Explorer menu also offers
  *Open*, *Open in Notepad++* and *Reveal in Explorer*.
* **Self-checking testbench** (right-click → *Generate Self-Checking Testbench…*): type the expected expression for each
  output (e.g. `sum = a ^ b ^ cin`, `cout = (a & b) | (cin & (a ^ b))`). After every vector the testbench compares
  (`!==`) and prints `PASS: …` or `FAIL: … <- expected …`, plus a final `SELF-CHECK` summary – FAIL rows turn red in the
  truth table.

#### 🔎 Pre-compile course linter & diagnostics

The linter runs before every compile (and while you type). It catches bugs that a plain compiler accepts silently:

| Check | Why it matters |
|---|---|
| **Implicit undeclared wires** in gate primitives and module connections | A typo such as `and g1(y, a, bb);` creates an implicit 1-bit wire that floats at `z`. |
| **Port count / port name / port width mismatches** against workspace and lecturer modules | Wrong positional order or `.q()` on a module that has no `q` port. |
| **Unknown module / wrong letter case** (`halfadder` vs `HalfAdder`) | Verilog names are case-sensitive; `iverilog -y` will report the module as missing. |
| **File name ≠ module name** | `-y` finds module `Mux4` only in a file called `Mux4.v`. |
| **Gate arity**, missing `endmodule`, ports listed but never declared | Classic structural mistakes. |
| **Testbench hygiene** – no `$finish`, no `$monitor`/`$display`, no `$dumpfile` | Prevents timeouts and empty results. |
| **Strict gate-level mode** (optional) | Warns about `always`, `initial`, `assign`, `+`, `-`, `? :` inside design files when an assignment allows only structural gates / lecturer modules. |

Every linter finding and every `iverilog`/`vvp` error appears in **Problems & Linter** (with a count badge). Clicking a
row jumps to the file and line, which is highlighted in red (error) or amber (warning) in the editor.

**⚡ Live compile check on save.** Every save starts `iverilog -tnull` in the background with the exact same flags as a
real run (`-y`, `-l`, `-I`, `-g2012`…). `-tnull` parses and elaborates the design but writes no `vvp` image, so it is fast
(≈0.1 s) and never touches a running simulation. Syntax and elaboration errors (e.g. `Unknown module type`) are marked
in the editor gutter and in *Problems*, the status bar turns red (`⊗ 2 errors (live check)`), and it clears as soon as a
save compiles cleanly. Rapid saves are coalesced into one follow-up check. Toggle it in ⚙ Settings → Linter & Sync or in
the ▶ Run & Compile view.

**🔗 Clickable error tracing in the Console.** Every `file.v:line` or `file.v:line:col` reference in the Console –
including absolute paths such as `C:\iverilog\compstruct\lib\mux.v:14` – is rendered as a link; clicking it opens the
file at that line (the editor for the current module, Notepad++ for any other file).

#### 📊 Interactive truth table & radix converter

<p align="center"><img src="docs/screenshots/03-truth-table.png" width="860" alt="Truth table"></p>

* `$monitor` / `$display` output is parsed automatically – both `key=value` style (`a=0 | b=1 | s=1`) and plain
  tabular output with a header row. `VCD info:` and `$finish called at …` lines are ignored.
* Rows whose outputs contain `x` or `z` are tagged **FLOATING/CONFLICT (x/z)** (orange); rows containing `FAIL`,
  `ERROR` or `MISMATCH` are tagged **FAIL** (red).
* Switch the radix live: **Binary / Hex / Unsigned Dec / Signed Dec** (two's complement uses each port's real width).
* `📋 Copy Markdown` / `📋 Copy CSV` – paste the table straight into a homework report.
* **Filter bar** – show `All`, only `x/z Floating` or only `FAIL` rows, plus a text search (`1010`, `sum=1`…), so
  64- or 128-row tables stay easy to inspect (the summary shows "k of n rows").

#### 〰 Built-in waveform viewer & GTKWave integration

<p align="center"><img src="docs/screenshots/04-waveform.png" width="860" alt="Waveform viewer"></p>

* Pure-Python `.vcd` reader (multi-character identifier codes, scalar and vector values, `x`/`z`).
* Canvas rendering: green high/low lines, hexagonal bus envelopes with the value printed in the current radix,
  red hatched blocks for `x`, yellow mid-lines for `z`, a time axis, zoom in/out, fit, and a click-to-place cursor that
  shows every signal's value at that time.
* Shows testbench-level signals by default; tick **Internal signals** to include signals inside `uut`.
* No `.vcd`? The waveform is synthesized from the truth-table rows instead.
* `📈 Open in GTKWave` opens the same dump in GTKWave.

#### 🌳 Hierarchy & gate-count analyzer + IC pinout (`HIERARCHY & GATES` tab)

<p align="center"><img src="docs/screenshots/05-hierarchy-pinout.png" width="860" alt="Hierarchy and pinout"></p>

* An **instance tree** of the active module across the workspace and all enabled packages – e.g.
  `FA → ha1 : HalfAdder → g1 : xor, g2 : and`. Each row shows where the module is defined (file + package);
  clicking an instance opens its `.v` file (read-only preview for package files).
* A **flattened gate count** over the whole hierarchy (`NAND`, `NOR`, `XOR`, `XNOR`, `AND`, `OR`, `NOT`, `BUF`), the number
  of sub-module instances, missing modules, and an **estimated logic depth** in gate levels (static analysis: generate
  loops and instance arrays are counted once).
* A VS Code-styled **IC block diagram**: inputs on the left, outputs/inouts on the right, buses drawn as double lines with
  their `[msb:lsb]` range, and the module name with its gate count and depth on the chip.

#### ⌨ Live IntelliSense autocomplete (as you type + `Ctrl+Space`)

<p align="center"><img src="docs/screenshots/06-intellisense-modules.png" width="860" alt="IntelliSense: modules"></p>

<p align="center"><img src="docs/screenshots/07-intellisense-ports.png" width="860" alt="IntelliSense: ports"></p>

* A VS Code style suggestion list opens **while you type**: after 2 letters of a name, on `$`, on `` ` `` and on `.`
  inside a module instance. `Ctrl+Space` opens it at any time. The popup never takes the keyboard focus, so you can
  keep typing to filter. `↑`/`↓` move, `Tab`/`Enter` insert, `Esc`, a click elsewhere, `Space` or `;` close it.
  `Enter` after a word that's already complete (`end`, `a`) just starts a new line.
* Every row has a coloured kind badge and a detail column:
  * **`M` modules**: every module from the workspace, the course library (`compstruct\lib`) and all enabled packages,
    in two variants. **Full Instantiation** inserts `Mux4 u_mux4_1 (.d(), .sel(), .y());` with an auto-numbered
    instance name and the caret inside the first `.port()`. **Module Name** inserts just the name. A bottom card shows
    the port signature and source package, e.g. `FullAdder (input a, input b, input cin -> output sum, output cout) · Workspace`.
  * **`P` ports**: type `.` inside `FullAdder fa1 ( … ` and you get that module's ports (`.cin()  [input 1-bit]`).
    Ports that aren't connected yet come first, and accepting one puts the caret inside `.cin(|)`. Parameterised
    (`#(…)`) and multi-line instances work too.
  * **`W` signals**: the `input/output/inout/wire/reg/logic/integer/parameter` names declared in the current file
    (no more typos that create implicit wires).
  * **`K` keywords and block snippets**: `module (template)`, `always @(*)`, `always @(posedge clk)`,
    `initial begin … end`, `case … endcase`, `generate`, `function`, `task`… The caret lands inside the block.
  * **`G` gate primitives** with the pin order (`nand (out, in1, in2, …)`, `bufif1 (out, in, ctrl)`): the output comes first.
  * **`S` system tasks and directives**: `$display("…")`, `$monitor`, `$finish;`, `$dumpvars(0, …)`, `$readmemb`…,
    `` `timescale 1ns/1ps``, `` `include``, `` `define``, `` `ifdef``…
* Matching is case-insensitive: prefix first, then CamelCase initials (`fa` → `FullAdder`, `ha` → `HalfAdder`), then
  substring. Ranking: ports after `.`, then modules and local signals, then gates and keywords, then system tasks.
* Turn off the as-you-type popup in Settings → Editor Behavior (`Enable Live Autocomplete (IntelliSense)`).
  `Ctrl+Space` always works.
* With the cursor on a module name, the status bar shows its port signature and package, e.g.
  `◆ HalfAdder (output s, output c, input a, input b) · Lab4`.

#### 📦 One-click homework submission (`📦 Export HW .zip`)

* The Explorer's `📦 Export HW .zip` (or `📤`) bundles every `.v` / `_tb.v` / `.vh` of the workspace into
  `<Workspace>_Submission.zip` and leaves out compiled `vvp` images, `.vcd` dumps, zips and temp/backup files.
* It checks whether your design instantiates helper modules that are **neither in the course library nor in the folder**
  (modules from your imported/linked packages) and offers to include them – one self-contained `<Module>.v` each, plus any
  `` `include``d header – so the grader can compile the zip with the normal course command.

#### 🧹 Homework submission cleaner

`🧹 Clean` deletes compiled `vvp` images from the workspace before you zip an assignment. Because they have no file
extension, they are recognized safely by their header (`#! … vvp`) – your `.v` files are never touched. `.vcd`
dumps are left in place (delete them manually if your course asks you to).

#### 🔠 Comfortable typography, global zoom & size presets

<p align="center"><img src="docs/screenshots/08-context-menu.png" width="860" alt="Dark context menu"></p>

<p align="center"><img src="docs/screenshots/11-light-theme.png" width="860" alt="Light theme"></p>

* Comfortable defaults: **15 pt** editor, **13 pt** console and **13 pt** UI text (Segoe UI for menus, tabs, sidebar and
  buttons; Consolas for code, tables and the waveform/pinout labels). Configs saved by older versions with smaller
  sizes are lifted to these defaults once, on first start.
* **Global zoom** – `A-` / `A+`, `Ctrl+MouseWheel`, `Ctrl+Plus` / `Ctrl+Minus` scale the editor, console **and** the
  whole UI together (panel tabs, menus, truth table rows/headings, waveform rows, IC pinout, status bar). `Ctrl+0`
  resets everything to the defaults.
* **UI & text size preset** (Settings → Appearance & Font): `Compact (12pt)`, `Comfortable (14-15pt)`,
  `Large / High-Visibility (17pt)`, `Extra Large (20pt)` – or set the three sizes individually (shown as `Custom`).
* Readable **dark context menus** everywhere (editor right-click, snippets submenu, module menu): borderless
  `#252526` popups with Segoe UI at the UI font size, 32 px rows with a `#04395E` hover, right-aligned shortcuts,
  side-opening submenus, keyboard navigation; they close on `Escape`, a click elsewhere or when the app loses focus.
* The toolbar is **responsive**: when the window is too narrow for the full labels, buttons collapse to their icons
  (📂 🔍 🧪 💾 ⚡ 📦 📝 🧹) and show a tooltip on hover; the labels come back as soon as there is room.

#### 🏠 Welcome / Get Started page & New Module / Project wizard

<p align="center"><img src="docs/screenshots/01-welcome.png" width="860" alt="Welcome page"></p>

<p align="center"><img src="docs/screenshots/09-new-module-wizard.png" width="720" alt="New Module wizard"></p>

* On launch VeriFlow opens a VS Code style **Welcome page** in the editor area instead of jumping into a folder:
  * **Start** – `📄 New Verilog Module / File… (Ctrl+N)`, `📁 Create New Assignment / Project Folder… (Ctrl+Shift+N)`,
    `📂 Open Existing Folder… (Ctrl+O)`, `📄 Open Single .v File…` (opens its folder and selects that module),
    `📦 Import Lecturer Modules / Package…` and `🧪 Open Built-in Sample Project (FullAdder)`.
  * **Recent** – up to 8 recent folders (name + full path, missing folders greyed out); click to open, `×` to remove,
    `Clear Recent` to empty the list.
  * `☑ Show Welcome screen on startup` at the bottom. Come back any time with `🏠 Welcome` (toolbar / activity bar) or
    `✕` **Close Folder** in the Explorer header.
* **Startup mode** (Settings → Editor Behavior → *On startup*): `Show the Welcome screen` (default), `Reopen the last
  folder`, or `Empty window`.
* **New Module / Project wizard** (`Ctrl+N` / `Ctrl+Shift+N` / Explorer `+`):
  * module name (live preview of `<Module>.v` + `<Module>_tb.v` and the target path),
  * **where to save** – defaults to the open workspace (or the last parent folder / `Documents`), `📂 Browse Folder…`,
    plus a *create subfolder* / *new folder name* field (e.g. `Documents\CompStruct` + `Lab4`),
  * optional **ports** – inputs `a, b, cin` or `[15:0] a, [15:0] b`, outputs `sum, cout` or `[15:0] y` (the width
    goes before each bus name); empty = the classic NAND starter template,
  * **testbench** – `Exhaustive Truth-Table TB`, `Empty Skeleton TB` or `No TB yet`,
  * `☐ Also open the new file(s) in Notepad++`.
  * `✨ Create & Open Module` creates the folder, writes the files, switches the workspace to it and opens both files
    in the split editor.

#### 🔔 Automatic updates from GitHub (notification + 1-click update)

* `updater.py` (standard library only) checks **two sources** ~1.5 s after start and every 30 minutes, in the background
  with a 4 s timeout (offline = silent):
  1. the latest **GitHub Release** (`api.github.com/repos/<owner>/<repo>/releases/latest`) – carries the `.exe`;
  2. **`version.json` on `main`** (`raw.githubusercontent.com/<owner>/<repo>/main/version.json`) – so a push that bumps
     it notifies everyone running from source.
* The repository is read from `git config --get remote.origin.url` (fallback: `Nirco99/veriflow-studio`). If Python's
  TLS cannot verify GitHub's certificate chain, Windows' own `curl.exe` (system certificate store) is used instead.
* A newer version shows a VS Code notification card (bottom right) and a `🔔 Update vX.Y.Z` badge in the status bar:
  `↓ Update & Restart Now` · `View Changes` · `Later`.
  * **From source**: `git pull --rebase --autostash origin main` (or `main.zip` when there is no `.git` folder), then
    VeriFlow restarts itself.
  * **`.exe`**: downloads the release `.exe` as `<name>_new.exe`, starts a small detached helper that waits for the app
    to close, swaps the file and relaunches. If `main` is newer than the latest release (no `.exe` yet), the button
    opens the download page instead.
* Turn it off or check manually in Settings → Editor Behavior (`Check GitHub for updates`, `🔔 Check for Updates Now`).
* **Publishing an update** (maintainers): bump `APP_VERSION` in `config_manager.py` and `version.json`, push to `main`;
  for `.exe` users also publish a GitHub Release `vX.Y.Z` with `VeriFlowStudio.exe` attached.

#### 🧩 Demo mode (no Icarus Verilog installed)

If `iverilog.exe` is not found, an amber banner appears and VeriFlow switches to a **built-in Python gate-level
simulator** (1-bit designs made of `and/or/nand/nor/xor/xnor/not/buf` primitives and simple `assign`s), so the editor,
linter, truth table and waveform can be explored on any machine. Lecturer modules and buses need the real toolchain.

### Download & quick start

1. **Download [VeriFlowStudio.exe](https://github.com/Nirco99/veriflow-studio/releases/latest/download/VeriFlowStudio.exe)** (the green button at the [top of this page](#download)) and double-click it.
   No installation and no Python. If Windows SmartScreen appears: **More info → Run anyway**.
2. **Icarus Verilog** installed at `C:\iverilog` (`C:\iverilog\bin\iverilog.exe`, `C:\iverilog\bin\vvp.exe`) with the
   lecturer library at `C:\iverilog\compstruct\lib`. Other locations can be set in **⚙ Settings → Compiler &
   Toolchain** (there is an **Auto-Detect Paths** button). Without Icarus Verilog the app runs in demo mode.
3. *(Optional)* **Notepad++** for Live Sync and **GTKWave** for the external waveform viewer.
4. The **Welcome page** opens: create a new assignment folder (`Ctrl+Shift+N`), open an existing one (`Ctrl+O`), or try
   the built-in sample project.
5. **Updates are automatic**: when a new version is released, a 🔔 notification offers **Update & Restart Now**.
   All versions and release notes: [Releases](https://github.com/Nirco99/veriflow-studio/releases).

### Step-by-step usage guide

1. **Open or create an assignment folder** – from the Welcome page, `📂 Open…` (`Ctrl+O`), `Recent ▾`, or
   `Ctrl+Shift+N` to create a new folder with its first module. The Explorer lists every module and whether its
   testbench exists.
2. **Select or create a module** – click it in the Explorer or use the `Module:` dropdown. `+ New .v` (`Ctrl+N`)
   opens the wizard: name, folder, optional ports and testbench (the file name always equals the module name, as `-y`
   requires).
3. **Use lecturer modules** – load them once with `📦 Packages` (`+ .v Files`, `+ Folder` or `+ .zip`), then open the
   **📚 Library & Packages** view, search, select a module and click `⤵ Insert at Cursor`.
4. **Create the testbench** – `🧪 Gen _tb.v` (also offered in the testbench tab when it is missing), then adjust it.
5. **Run** – press `F5`. Or click `📝 N++`, code there, and just press `Ctrl+S` – Live Sync runs everything.
6. **Inspect the results** –
   * **Console Output** – the exact commands, raw `iverilog`/`vvp` output, colour-coded; `file.v:line` references are
     clickable.
   * **Problems & Linter** – click a row to jump to the line.
   * **Truth Table** – change radix, copy as Markdown/CSV.
   * **Waveform** – zoom, place the cursor, or open GTKWave.
   * The panel header shows the command line; switch **Actual / Baseline** to see the exact command from the course
     instructions, and `📋 Copy CMD` to paste it into `cmd.exe`. The **▶ Run & Compile** view lists all flags.
7. **Before submitting** – `🧹 Clean` removes compiled binaries.

### Settings reference

Open **⚙** (top right, activity bar, or `Ctrl+,`). Every change applies **immediately** and is saved to
`%APPDATA%\VeriFlowStudio\config.json`.

| Tab | Setting | `config.json` key | Values / default |
|---|---|---|---|
| Appearance & Font | Appearance mode | `appearance_mode` | `Dark` (default), `Light`, `System` – also the ☀/🌙 button |
| | UI accent theme | `color_theme` | `blue`, `green`, `dark-blue` (applies after restart) |
| | Editor colour scheme | `editor_color_scheme` | `Dark Modern` (VS Code Dark+, default), `Light Modern` (VS Code Light+), `One Dark`, `Monokai`, `GitHub Light`, `High Contrast` |
| | UI scaling | `ui_scale_percent` | `80` `90` `100` `110` `125` `150` % |
| | Editor font family | `editor_font_family` | `Consolas`, `Cascadia Code`, `JetBrains Mono`, `Courier New`, `Lucida Console` |
| | Editor font size | `editor_font_size` | 10–32 pt (default 15) – also `A-` / `A+`, `Ctrl+wheel` |
| | Console font size | `console_font_size` | 10–28 pt (default 13) |
| | UI & text size preset | – | `Compact (12pt)`, `Comfortable (14-15pt)`, `Large / High-Visibility (17pt)`, `Extra Large (20pt)`, `Custom` |
| | UI font size (menus, tabs, tables, sidebar) | `ui_font_size` | 10–24 pt (default 13) |
| | Default radix | `default_radix` | `Binary`, `Hex`, `Unsigned Dec`, `Signed Dec` |
| Editor Behavior | Editor layout | `editor_split_layout` | `Side-by-Side` (.v + _tb.v, default) or `Tabbed` |
| | Tab size | `tab_size` | 2, 4 (default), 8 |
| | Insert spaces for Tab | `insert_spaces_for_tabs` | on |
| | Word wrap | `word_wrap` | off |
| | Highlight current line | `highlight_current_line` | on |
| | Auto-indent | `auto_indent` | on |
| | Auto-close brackets & `begin`/`end` | `auto_close_brackets_and_blocks` | on |
| | Auto-save before Run (F5) | `auto_save_before_run` | on |
| | Auto-save on focus loss | `auto_save_on_focus_loss` | off |
| | On startup | `startup_mode` | `welcome_screen` (default), `reopen_last`, `empty_window` |
| | Check GitHub for updates | `check_for_updates` | on (startup + every 30 min); `🔔 Check for Updates Now` button |
| | Enable Live Autocomplete (IntelliSense) as you type | `live_autocomplete` | on (`Ctrl+Space` always works) |
| Compiler & Toolchain | iverilog.exe / vvp.exe / gtkwave.exe | `iverilog_path`, `vvp_path`, `gtkwave_path` | `C:\iverilog\bin\…`, `C:\iverilog\gtkwave\bin\gtkwave.exe` |
| | Lecturer library (`-y`) | `lib_dir` | `C:\iverilog\compstruct\lib` |
| | notepad++.exe | `notepad_pp_path` | `C:\Program Files\Notepad++\notepad++.exe` |
| | Verilog generation flag | `std_flag` | `-g2012` (default), `-g2005-sv`, `-g2005`, `-g2001` |
| | Include workspace folder as `-y` library | `include_workdir_as_ylib` | on |
| | Enable `-Wall` & `-Winfloop` | `enable_wall_warnings` | on |
| | Non-interactive `vvp -n` | `vvp_non_interactive_flag` | on (prevents `$stop` hangs) |
| | Simulation timeout | `sim_timeout_sec` | 1.0–30.0 s (default 3.0) |
| Linter & Sync | Static course linter | `enable_course_linter` | on |
| | Strict gate-level mode | `strict_gate_level_mode` | off |
| | Live Notepad++ sync | `live_sync_enabled` | off (also the `⚡ N++ Sync` switch) |
| | Auto-run on external save | `auto_run_on_external_save` | on |
| | Polling interval | `external_poll_interval_ms` | 500–3000 ms (default 800) |
| | Live compile check on save (`iverilog -tnull`) | `live_check_on_save` | on |
| Packages | Auto-resolve package modules (`-y` per folder, `-l` for multi-module / renamed files) | `auto_resolve_packages_with_l_flag` | on |
| | Global package vault | `global_packages_dir` | `%USERPROFILE%\.veriflow_studio\packages` |
| | Registered packages (managed in the Package Manager) | `library_packages` | the built-in course library; imported / linked packages are added here |

`config.json` also remembers UI state (`last_workspace_dir`, `recent_workspaces`, `last_module`, `window_geometry`,
`sidebar_visible`, `sidebar_view`). **Reset to Defaults** in the dialog restores everything except workspaces and packages.

### Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `F5` | Save, lint, compile (`iverilog`) and simulate (`vvp`) |
| `Shift+F5` | Stop the running simulation |
| `F7` | Run the static course linter only |
| `Ctrl+S` | Save the active file (in the editor) / save all (elsewhere) |
| `Ctrl+B` | Toggle the side bar (Explorer / Library / Run) |
| `Ctrl+O` / `Ctrl+N` / `Ctrl+Shift+N` | Open folder / New Module wizard / New Assignment (project folder) wizard |
| `Ctrl+,` | Settings |
| `Ctrl+F` / `Ctrl+H` | Find / Find & Replace bar (`Enter`, `Shift+Enter`, `F3` = next/previous) |
| `Ctrl+G` | Go to line |
| `Ctrl+Space` | IntelliSense: modules (full instantiation / name), `.port()` connections, signals, keywords, gates, `$tasks`, directives (it also opens as you type) |
| `Ctrl+/` | Toggle `//` comment on the selected lines |
| `Ctrl+D` | Duplicate line / selection |
| `Ctrl+Z` / `Ctrl+Y` (`Ctrl+Shift+Z`) | Undo / redo |
| `Tab` / `Shift+Tab` | Indent / outdent selection |
| `Ctrl+MouseWheel`, `Ctrl+Plus`, `Ctrl+Minus`, `Ctrl+0` | Zoom editor, console and the whole UI in / out / reset |

### Architecture & file structure

```text
veriflow-studio/
├── main.py              # VS Code-style workbench: title bar, activity bar, side bar views, editor group,
│                        # bottom panel, status bar, settings dialog, Notepad++ live sync, run orchestration
├── ui_components.py     # VerilogCodeEditor (Pygments Dark+/Light+, gutter, find/replace, snippets, zoom),
│                        # TruthTableGrid, MiniWaveformViewer, ActivityBar, PanelTabs, SideSection
├── verilog_runner.py    # Threaded iverilog -> vvp pipeline, stale-binary deletion, process-tree kill on timeout,
│                        # Windows-safe diagnostics parser, truth-table parser, demo-mode gate simulator
├── verilog_parser.py    # Comment-stripping module parser (ANSI / non-ANSI / parameters), course linter,
│                        # testbench generator, VCD reader - pure functions, no GUI
├── config_manager.py    # Settings schema + validation + config.json persistence, VS Code colour tokens,
│                        # editor colour schemes, toolchain auto-detection
├── welcome.py           # Welcome / Get Started page, New Module & Project wizard, update notification card
├── intellisense.py      # IntelliSense engine (no GUI): context (word / .port / $ / `), candidates, fuzzy ranking
├── updater.py           # GitHub release + version.json update checker, git-pull / .exe self-updater (stdlib only)
├── version.json         # {"version", "notes"} on main - bump it to notify users running from source
├── package_manager.py   # Global package vault: .v / folder / .zip import, enable/remove, -y / -l resolution,
│                        # conflict-free cached copies of library files
├── build_exe.bat        # maintainers: builds the released VeriFlowStudio.exe
├── requirements.txt     # customtkinter, pygments, pyinstaller
├── sample_project/      # FullAdder.v + FullAdder_tb.v demo (gate-level, self-checking testbench)
└── docs/screenshots/     # README screenshots
```

The parser and runner have no GUI dependencies and can be imported and tested on their own, e.g.:

```python
from verilog_parser import parse_verilog_module, run_course_linter, generate_testbench_skeleton
info = parse_verilog_module("sample_project/FullAdder.v")
print(generate_testbench_skeleton(info))
```

### Troubleshooting

| Symptom | Fix |
|---|---|
| Amber "DEMO MODE" banner | Icarus Verilog was not found – install it to `C:\iverilog` or set the paths (⚙ → Compiler & Toolchain → Auto-Detect). |
| `Unknown module type: X` | Check the module name case and that `X.v` exists in the workspace or the lecturer library (the linter flags both). |
| Simulation timeout | The testbench has no `$finish`, waits forever, or contains a zero-delay loop. Raise the timeout only for genuinely long simulations. |
| Truth table empty | The testbench prints nothing – add `$monitor`/`$display` (Gen _tb.v does this). |
| Waveform empty | Add `$dumpfile`/`$dumpvars`, or rely on the waveform synthesized from the truth table. |
| `Cannot delete stale binary` | An old `vvp` process still holds the file – press Stop or close it. |

### License

Released under the [MIT License](LICENSE).

[⬆ Back to top](#top)

---

<a id="תיעוד-מלא-בעברית"></a>

<div dir="rtl" align="right">

## תיעוד מלא בעברית

[🇬🇧 English](#english-documentation) | [🇮🇱 עברית](#תיעוד-מלא-בעברית)

# VeriFlow Studio — סביבת פיתוח ל-Icarus Verilog בסגנון VS Code עם הרצה בלחיצה אחת

<a id="download-he"></a>

## ⬇️ הורדה (Windows)

<p align="center">
  <a href="https://github.com/Nirco99/veriflow-studio/releases/latest/download/VeriFlowStudio.exe">
    <img src="https://img.shields.io/badge/%E2%AC%87%20Download-VeriFlowStudio.exe%20(Windows)-2EA043?style=for-the-badge&logo=windows&logoColor=white" height="60" alt="Download VeriFlowStudio.exe">
  </a>
</p>
<h3 align="center"><a href="https://github.com/Nirco99/veriflow-studio/releases/latest/download/VeriFlowStudio.exe">⬇️ להורדת VeriFlowStudio.exe (הגרסה האחרונה)</a></h3>

| שלב | מה עושים |
|:---:|---|
| **1** | לוחצים על כפתור ה-**Download** הירוק למעלה. הקובץ `VeriFlowStudio.exe` (בערך 32MB, תמיד הגרסה האחרונה) מתחיל לרדת. |
| **2** | לוחצים על הקובץ פעמיים. **אין מה להתקין** ולא צריך Python. אפשר לשמור אותו בכל מקום (שולחן העבודה, מסמכים) ולהצמיד לשורת המשימות. |
| **3** | אם Windows מציג *"Windows protected your PC"*, לוחצים **More info ← Run anyway** (הקובץ לא חתום דיגיטלית). |
| **4** | מוודאים ש-**Icarus Verilog** מותקן ב-`C:\iverilog`, כמו בקורס. בלעדיו VeriFlow עדיין נפתח, במצב הדגמה. |
| **5** | זהו. גרסאות חדשות מופיעות בתוך התוכנה: **🔔 Update Available ← Update & Restart Now**. |

הכפתור לא עובד? פותחים את **[דף הגרסה האחרונה](https://github.com/Nirco99/veriflow-studio/releases/latest)** ולוחצים על **`VeriFlowStudio.exe`** תחת **Assets**.

צילומי מסך של כל המסכים: [📸 Screenshots](#screenshots).

### תוכן עניינים

1. [סקירה ומוטיבציה](#סקירה-ומוטיבציה)
2. [יכולות](#יכולות)
3. [הורדה והפעלה מהירה](#הורדה-והפעלה-מהירה)
4. [מדריך שימוש צעד אחר צעד](#מדריך-שימוש-צעד-אחר-צעד)
5. [טבלת הגדרות](#טבלת-הגדרות)
6. [קיצורי מקלדת](#קיצורי-מקלדת)
7. [ארכיטקטורה ומבנה קבצים](#ארכיטקטורה-ומבנה-קבצים)
8. [פתרון תקלות](#פתרון-תקלות)
9. [רישיון](#רישיון)

### סקירה ומוטיבציה

בקורס **מבנה המחשב** כל מעבדה ותרגיל בית עוברים את אותו טקס: כותבים מודול ברמת שערים `<Module>.v`, כותבים
טסטבנץ' `<Module>_tb.v`, ואז מקלידים ב-`cmd.exe` שתי פקודות ארוכות — שוב ושוב, אחרי כל שינוי קטן:

<div dir="ltr" align="left">

```bat
C:\iverilog\bin\iverilog -g2012 -oFullAdder -y "C:\iverilog\compstruct\lib" FullAdder.v FullAdder_tb.v
C:\iverilog\bin\vvp FullAdder
```

</div>

אחר כך גוללים בפלט הגולמי של `$monitor` כדי למצוא את השורה השגויה, מנחשים איזה חוט "צף" ב-`z`, ותוהים למה מודול
של המרצה "לא נמצא" כשהקובץ נמצא ממש שם.

**VeriFlow Studio** מחליף את כל הלולאה הזו בסביבת עבודה שולחנית מהירה, שנראית ומרגישה כמו VS Code:

* **לחיצה אחת (או `F5`)** – שמירה, בדיקה סטטית, קומפילציה עם `iverilog`, סימולציה עם `vvp`, ועדכון ארבע תצוגות תוצאה.
* **סנכרון חי דו-כיווני עם Notepad++** – ממשיכים לכתוב ב-Notepad++, וכל `Ctrl+S` שם מריץ מחדש את כל התהליך.
* **Linter שמכיר את הקורס** – תופס באגים שקטים ש-`iverilog` מקבל בלי להתלונן (חוטים לא מוצהרים, אי-התאמה בפורטים,
  שם קובץ ששונה משם המודול ושובר את `-y`).
* **טבלאות אמת ודיאגרמות גלים אוטומטיות** – ישירות מפלט הטסטבנץ' ומקובץ ה-`.vcd`.

### יכולות

#### ▶ תהליך הרצה אטומי בלחיצה אחת (`F5` / `▶ Run`)

<div dir="ltr">

<p align="center"><img src="docs/screenshots/02-editor-run-console.png" width="860" alt="Editor and run"></p>

</div>

כל הרצה מבצעת לפי הסדר:

1. **שמירה אוטומטית** של קבצים שהשתנו בעורך (ניתן לכיבוי).
2. **Linter סטטי של הקורס** על שני הקבצים (התוצאות בלשונית *Problems & Linter*).
3. **מחיקת קובץ בינארי ישן** – הקובץ `<WorkDir>\<Module>` מהריצה הקודמת נמחק קודם, כך שקומפילציה שנכשלה לעולם לא
   תריץ בשקט בינארי ישן.
4. **קומפילציה** – `iverilog -g2012 -o<Module> -y <תיקיית העבודה> -y <ספריית המרצה> -y <חבילות…> -Wall -Winfloop [-l <קובץ חבילה>…] <Module>.v <Module>_tb.v`.
   נתיבי ה-`-y` (וכל קובצי ספרייה עם `-l` – ראו את מנהל החבילות בהמשך) מתווספים אוטומטית, כך שגם תתי-מודולים שלכם
   (למשל `HalfAdder.v`), גם המודולים של המרצה וגם כל חבילה טעונה נמצאים בלי לרשום אותם. הצלחה מחייבת קוד יציאה `0`, היעדר שורות שגיאה, **וגם** קובץ פלט שנוצר עכשיו.
5. **סימולציה** – `vvp -n <Module>`. הדגל `-n` הופך את `$stop` ל-`$finish`, כך שטסטבנץ' לעולם לא "נתקע" ומחכה
   לקלט. **מגבלת זמן** (ברירת מחדל 3 שניות) הורגת את כל עץ התהליכים (`taskkill /F /T`) אם אין `$finish` או שיש
   לולאה אינסופית ללא השהיה.
6. **תוצאות** – הקונסולה, Problems & Linter, טבלת האמת ודיאגרמת הגלים מתעדכנות. שורת הסטטוס הופכת ל**כתומה**
   בזמן ריצה, ל**אדומה** בשגיאת קומפילציה או חריגת זמן, וחוזרת ל**כחול** בסיום.

פלט הקומפיילר מפוענח בביטוי רגולרי שמתאים ל-Windows ומבין אותיות כונן ומספרי עמודות
(`C:\iverilog\compstruct\lib\mux.v:14: syntax error`, `FullAdder.v:9:12: error: …`), וגם שורות קריטיות כמו
`I give up.` ו-`No top level modules`.

#### ✍ שתי דרכי עבודה — העורך המובנה **או** סנכרון חי עם Notepad++

**העורך המובנה.** קובץ התכן (`.v`) והטסטבנץ' (`_tb.v`) נפתחים זה לצד זה (או כלשוניות), עם:

* צבעי תחביר של VS Code **Dark+ / Light+** ל-Verilog/SystemVerilog (מילות מפתח, סוגי חוטים, שערים, משימות מערכת,
  מספרים, מחרוזות, הערות).
* מספרי שורות עם הדגשת השורה הנוכחית, וסימוני שגיאה (אדום) ואזהרה (כתום) עם הסבר בריחוף העכבר.
* לשוניות קבצים בסגנון VS Code עם נקודה (`●`) לקובץ שלא נשמר, ושורת "פירורי לחם":
  `sample_project › FullAdder.v › module FullAdder (output sum, output cout, input a, input b, input cin)`.
* עריכה חכמה: הזחה אוטומטית, סגירה אוטומטית של `() [] {} ""`, הקלדת `begin` + `Enter` מוסיפה את ה-`end` המתאים,
  הזחת בלוקים עם Tab/Shift+Tab, הוספת/הסרת הערות, שכפול שורה, חיפוש והחלפה, מעבר לשורה.
* קטעי קוד מוכנים (`+ Snippet ▾` או קליק ימני ← *Insert Snippet*): `module … endmodule`, `initial begin … end`,
  `always @(*)`, `$monitor`, `$display`, `$dumpfile/$dumpvars`, לולאת `for` ממצה וכל אחד מהשערים הבסיסיים.
* קיצורי המקלדת עובדים גם כש**פריסת המקלדת בעברית** (הם מזוהים לפי המקש הפיזי).

**⚡ סנכרון חי עם Notepad++.** מדליקים את המתג `⚡ N++ Sync`, ו-VeriFlow בודק את קבצי ה-`.v` / `_tb.v` הפעילים כל
**800 מילישניות** (ניתן לשינוי בין 500 ל-3000). כשלוחצים `Ctrl+S` ב-Notepad++, VeriFlow טוען את הקוד מחדש, מריץ
Linter, מקמפל, מסמלץ ומעדכן את טבלת האמת ואת הגלים – בלי ללחוץ על כלום. אם יש גם שינויים לא שמורים בתוך VeriFlow,
הוא לא דורס אותם אלא מציג אזהרה.

* הכפתור `📝 N++` (Notepad++) פותח את שני הקבצים של המודול הפעיל ב-Notepad++ ומדליק את הסנכרון החי אוטומטית.
* לחיצה על שגיאה שנמצאת בקובץ שלא פתוח בעורך (למשל קובץ מספריית המרצה) פותחת אותו ב-Notepad++ **בשורה המדויקת**
  (`notepad++ -n<line> <file>`).

#### 📁 סייר תיקיית העבודה ו-📚 בוחן הספרייה

* **הסייר (Explorer)** מצמיד אוטומטית כל `<Module>.v` ל-`<Module>_tb.v`: נקודה ירוקה ותג `Ready` כשהטסטבנץ' קיים,
  נקודה כתומה ותג `No TB` כשהוא חסר.
* **Extra .v files (compile overrides)** – סימון קבצים נוספים שיועברו ל-`iverilog` במפורש (בדרך כלל מיותר בזכות `-y`).
* תצוגת **Library & Packages** מציגה את כל המודולים שב-`C:\iverilog\compstruct\lib` (44 מודולים בספרייה הסטנדרטית של
  הקורס) ובכל חבילה טעונה (ראו בהמשך), עם תיבת חיפוש חיה (מקלידים `mux`, `adder`, `xor`…). בחירת מודול מציגה את הפרמטרים ואת חתימת הפורטים המדויקת, ושני
  כפתורים מדביקים חיווט מוכן: `📋 Copy Instantiation` ו-`⤵ Insert at Cursor`.

#### 📦 מנהל חבילות וטעינת מודולים גלובלית (טעינה חד-פעמית ושימוש מכל תיקייה במחשב)

<div dir="ltr">

<p align="center"><img src="docs/screenshots/10-package-manager.png" width="720" alt="Package manager"></p>

</div>

מרצים מחלקים מודולים כקבצי `.v` בודדים, כתיקייה, או כקובץ `.zip` מה-Moodle – ולעיתים קרובות עם **כמה מודולים בקובץ
אחד** (`course_primitives.v`) או עם **שם קובץ ששונה משם המודול** (`mux_lib.v` שמכיל `module Mux4`). הפקודה הרגילה
`iverilog -y <dir>` מוצאת מודול רק כשהוא שמור בקובץ ששמו בדיוק `<ModuleName>.v`, ולכן במקרים האלה מתקבלת השגיאה
`error: Unknown module type`. מנהל החבילות של VeriFlow פותר את זה **פעם אחת לכל המחשב**: טוענים את המודולים פעם אחת,
וכל קובץ `.v` חדש שתיצרו ב*כל* תיקייה (`Desktop\HW4`, `Documents\Lab5`, `Downloads\Test`…) יכול להשתמש בהם – בלי שום
הגדרה לכל תיקייה.

**טוענים מודולים פעם אחת** – מסרגל הצד **📚 Library & Packages**, מהכפתור **`📦 Packages`** בסרגל העליון, או
מ-**⚙ Settings ← Packages**:

| כפתור | מה הוא עושה |
|---|---|
| `+ .v Files` | בוחרים קובץ `.v` / `.sv` אחד או יותר מכל מקום במחשב. הם **מועתקים לכספת החבילות הגלובלית** (נותנים שם לחבילה; ברירת מחדל `Imported_Course_Modules`). |
| `+ Folder` | **Yes** = העתקת קבצי ה-`.v` של התיקייה לכספת (ממשיך לעבוד גם אם התיקייה המקורית הועברה או נמחקה). **No** = **קישור התיקייה במקומה** – היא נסרקת כולל תתי-תיקיות ותמיד משתמשים בקבצים העדכניים שלה. |
| `+ .zip` | בוחרים קובץ `.zip` של הקורס (למשל מה-Moodle). כל קובץ `.v` / `.sv` שבתוכו מחולץ לחבילה בכספת בשם הארכיון; מבנה התיקיות משוטח וקבצים אחרים מדולגים. |

הכספת נמצאת ב-`%USERPROFILE%\.veriflow_studio\packages\<package>` (ההגדרה `global_packages_dir`).

**איך הקומפילציה מוצאת אותם – מכל תיקייה:**

1. **`-y` בסדר עדיפויות קבוע של 3 שכבות** – **שכבה 1** תיקיית העבודה (קובץ `<Module>.v` של הסטודנט תמיד גובר),
   **שכבה 2** חבילות שיובאו / קושרו ופעילות, **שכבה 3** ספריית הקורס `C:\iverilog\compstruct\lib`. אינדקס המודולים
   משתמש בדיוק באותו סדר, כך שה-Linter, תצוגת ההיררכיה והקומפיילר תמיד מסכימים.
2. **`-l` לקבצים ש-`-y` לא רואה.** VeriFlow מאנדקס כל מודול בכל חבילה (כולל כל המודולים שבקבצים מרובי-מודולים) ועוקב
   **ברקורסיה** אחרי המופעים בתכנון שלכם (`Top` ← `Mux4` ← `Mux2`…). כל מודול נדרש שנמצא בקובץ מרובה מודולים, בקובץ
   ששמו שונה משם המודול, בקובץ `.sv` או בתת-תיקייה, נטען עם **`-l <file>`** – מצב *קובץ ספרייה* של iverilog, כך שרק
   המודולים שבאמת בשימוש עוברים אלבורציה והשאר לעולם לא הופכים למודולי-על מיותרים. הדגלים ממוקמים לפני קבצי המקור,
   כפי ש-iverilog דורש.
3. **אפס התנגשויות "already declared" (`_cells`).** iverilog אף פעם לא מקבל שני קבצים שמגדירים את אותו מודול. אם
   קובץ מרובה-מודולים מכיל מודול שאתם צריכים (`ModA`) *וגם* מודול שהגדרה בעדיפות גבוהה יותר מסתירה (`ModB`), VeriFlow
   מחלץ את `ModA` – יחד עם שורות ה-`` `timescale``/`` `define`` – לתא של מודול יחיד `<vault>\_cells\<workspace>\ModA.v`
   ומאתר אותו דרך `-y`. אותו דבר קורה לכל תיקיית חבילה שעדיין מכילה פיזית כפילות שדולגה, כך שחיפוש ה-`-y` של
   iverilog לעולם לא יבחר בעותק הלא נכון.

**סינון כפילויות חכם וחלקי בטעינה.** VeriFlow מחזיק מפה אחת *שם מודול ← נתיב מלא לקובץ* על החבילות **הפעילות**.
כשטוענים קבצי `.v`, קובץ `.zip` או תיקייה (מועתקת או מקושרת), כל מודול **חדש** נטען וכל מודול שחבילה פעילה כבר מספקת
**מדולג** – אף פעם לא כל התיקייה. קובץ נשאר בחוץ רק כש*כל* המודולים שבו כפולים; קובץ מעורב נשמר ורק הכפילות שבו
מוסתרת (נרשם לכל קובץ ב-`excluded_modules` של החבילה). מקבלים הודעה אחת ברורה, למשל
*"Loaded 10 new module(s) from Lab4_Modules (skipped 1 duplicate – already provided by compstruct\lib: HalfAdder)"*,
והקונסולה מציגה איפה כל מודול שדולג כבר נמצא. ייבוא מחדש של *אותו* קובץ לחבילה שלו פשוט מעדכן אותו.

**חבילות מכובות לא חוסמות שום דבר.** רק חבילות פעילות נחשבות "כבר מסופקות", כך שאפשר לכבות חבילה ישנה ולייבא עותק
מעודכן של אותם מודולים. הפעלה מחדש של חבילה נבדקת קודם: אם אחד המודולים שלה מסופק עכשיו על ידי חבילה פעילה אחרת,
VeriFlow מראה איזה מודול מתנגש עם איזו חבילה ומציע לכבות את החבילה האחרת במקום – אחרת החבילה נשארת כבויה.

**קובצי כותרת `.vh` / `.svh`** מיובאים יחד עם המודולים (מקבצים, מתיקיות ומ-zip). הם אף פעם לא נחשבים מודולים; במקום
זה כל תיקיית חבילה שיש בה כותרות – וגם תיקיית העבודה – מועברת עם `-I`, כך ש-`` `include "defs.vh" `` עובד מכל תיקייה.

**שינוי שם מודול בעורך נבדק בזמן אמת:** ה-Linter עובד על התוכן שעוד לא נשמר, כך ששינוי `module Top` לשם שכבר קיים
בקובץ אחר בתיקייה או בחבילה מדווח מיד (שגיאה אם שני הקבצים מקומפלים יחד).

<div dir="ltr" align="left">

```bat
iverilog -g2012 -oTop -y "D:\HW4" -y "C:\iverilog\compstruct\lib" -y "%USERPROFILE%\.veriflow_studio\packages\course_modules" ^
         -Wall -Winfloop -l "...\course_modules\mux_lib.v" -l "...\course_modules\course_primitives.v" Top.v Top_tb.v
```

</div>

הקונסולה מדפיסה `📦 auto-loaded with -l: mux_lib.v, course_primitives.v`, והמתג **Actual / Baseline** בפאנל עדיין מציג
או את הפקודה המלאה הזו או את הפקודה המינימלית מהנחיות הקורס.

**עיון בחבילות ושימוש בהן**

* תצוגת **📚 Library & Packages** מקבצת את המודולים לפי חבילה (`▾ 📦 Course Built-in Library [44]`,
  `▾ 📦 course_modules [3]`…), עם תיבת סימון להפעלה/כיבוי של כל חבילה ותיבת חיפוש על **כל** המודולים הטעונים
  (`Mux`, `Adder`, `DFF`…).
* לחיצה על מודול מציגה את החבילה, הקובץ, איך הוא נטען (`-y` או `-l`), הפרמטרים וחתימת הפורטים, ואז
  `📋 Copy Instantiation` או `⤵ Insert at Cursor`. **לחיצה כפולה** פותחת תצוגה מקדימה של קוד המקור לקריאה בלבד.
* חלון **Package Manager** (`📦 Packages`) מציג כל חבילה עם הסוג שלה (ספריית הקורס / עותק בכספת / תיקייה מקושרת),
  מספר המודולים והמיקום, ומאפשר להפעיל או לכבות אותה, לפתוח את התיקייה שלה או להסיר אותה. הסרת חבילת כספת מוחקת רק את
  העותק שבכספת (אחרי אישור); הסרת תיקייה מקושרת רק "שוכחת" אותה – הקבצים שלכם לעולם לא נמחקים; את ספריית הקורס המובנית
  אפשר לכבות אבל לא להסיר.
* שורת הסטטוס מציגה `📦 Packages: K active (M modules indexed)` – לחיצה עליה קופצת לספרייה.
* ה-Linter של הקורס משתמש באותו אינדקס: בדיקות מספר/שם/רוחב הפורטים חלות גם על מודולים מחבילות, ומודול לא מוכר מדווח
  כ-*"Module 'Mux8' is not found in the workspace or any loaded package – click [📦 Packages] to import it"*.

#### 🧪 מחולל טסטבנץ' (`_tb.v`) בלחיצה אחת

`🧪 Gen _tb.v` מנתח את קובץ התכן (פורטים בסגנון ANSI ובסגנון הישן, רשימות כמו `input [3:0] a, b, c;`, כותרות עם
פרמטרים כמו `module Mux #(parameter W=16)`, ואפיקים רב-סיביים `[msb:lsb]`) וכותב `<Module>_tb.v` מלא:

* `reg` לכל כניסה, `wire` לכל יציאה (כולל רוחב האפיק), ו-`<Module> uut (.port(port), …)`.
* `$dumpfile("<Module>.vcd"); $dumpvars(0, <Module>_tb);`, שורת כותרת, ו-`$monitor` שמדפיס
  `a=%b | b=%b | … | y=%b`.
* **עד 7 סיביות כניסה:** לולאה ממצה `for (i = 0; i < (1 << N); i = i + 1)` על כל הצירופים.
* **יותר מ-7 סיביות:** 8 וקטורי קצה מובנים (הכל אפסים, הכל אחדות, תבניות `1010…`/`0101…`, שרשרת נשא `max + 1`,
  גלישה ב-MSB, מעורב, פסאודו-אקראי).
* כניסת `clk`/`clock` מקבלת שעון `always #5` משלה במקום להיספר בצירופים.
* תכנון שבנוי מ**מודולים של המרצה** (שיש להם השהיית שער `#5`) מקבל אוטומטית צעד ארוך יותר (`#100`) ודגימה עם
  `$display` אחרי כל צעד – כך שטבלת האמת מציגה ערכים יציבים ולא "קפיצות" רגעיות.
* מסתיים ב-`$finish`.
* **קליק ימני על מודול** בסייר (או קליק ימני בתוך עורך התכן) ← **Generate Testbench (exhaustive)** או
  **Generate Skeleton Testbench (empty initial)**. השלד כולל את אותן הצהרות, חיווט `uut`, `$dumpfile`/`$dumpvars`
  ו-`$monitor`, אבל עם אזור גירוי ריק שתמלאו בעצמכם. בתפריט של הסייר יש גם *Open*, *Open in Notepad++* ו-*Reveal in Explorer*.
* **טסטבנץ' שבודק את עצמו** (קליק ימני ← *Generate Self-Checking Testbench…*): מקלידים את הביטוי הצפוי לכל יציאה
  (למשל `sum = a ^ b ^ cin`, `cout = (a & b) | (cin & (a ^ b))`). אחרי כל וקטור הטסטבנץ' משווה (`!==`) ומדפיס
  `PASS: …` או `FAIL: … <- expected …`, ובסוף סיכום `SELF-CHECK` – שורות FAIL נצבעות באדום בטבלת האמת.

#### 🔎 Linter של הקורס לפני קומפילציה ואבחון שגיאות

ה-Linter רץ לפני כל קומפילציה (וגם תוך כדי הקלדה), ותופס באגים שקומפיילר רגיל מקבל בשקט:

| בדיקה | למה זה חשוב |
|---|---|
| **חוטים לא מוצהרים** בחיבורי שערים ומודולים | שגיאת הקלדה כמו `and g1(y, a, bb);` יוצרת חוט מרומז של סיבית אחת שצף ב-`z`. |
| **אי-התאמה במספר / שם / רוחב הפורטים** מול מודולים בתיקייה ובספריית המרצה | סדר חיבור שגוי, או `.q()` למודול שאין לו פורט `q`. |
| **מודול לא מוכר / רישיות שגויה** (`halfadder` מול `HalfAdder`) | ב-Verilog יש הבדל בין אותיות גדולות לקטנות; `iverilog -y` ידווח שהמודול חסר. |
| **שם קובץ ≠ שם מודול** | `-y` מוצא את המודול `Mux4` רק בקובץ בשם `Mux4.v`. |
| **מספר הדקים בשער**, `endmodule` חסר, פורט שמופיע בכותרת ולא מוצהר | טעויות מבניות קלאסיות. |
| **תקינות הטסטבנץ'** – אין `$finish`, אין `$monitor`/`$display`, אין `$dumpfile` | מונע חריגות זמן ותוצאות ריקות. |
| **מצב רמת-שערים קפדני** (אופציונלי) | מזהיר על `always`, `initial`, `assign`, `+`, `-`, `? :` בקבצי תכן, כשהתרגיל מתיר רק שערים ומודולים של המרצה. |

כל ממצא של ה-Linter וכל שגיאה של `iverilog`/`vvp` מופיעים בלשונית **Problems & Linter** (עם תג מונה). לחיצה על שורה
קופצת לקובץ ולשורה, שמודגשת באדום (שגיאה) או בכתום (אזהרה).

**⚡ בדיקת קומפילציה חיה בכל שמירה.** כל שמירה מפעילה ברקע `iverilog -tnull` עם בדיוק אותם דגלים כמו בהרצה אמיתית
(`-y`, `-l`, `-I`, `-g2012`…). `-tnull` מנתח ומבצע אלבורציה לתכנון אבל לא כותב קובץ `vvp`, ולכן הוא מהיר (כ-0.1 שניות)
ולא נוגע בסימולציה שרצה. שגיאות תחביר ואלבורציה (למשל `Unknown module type`) מסומנות בשוליים של העורך וב-*Problems*,
שורת הסטטוס הופכת לאדומה (`⊗ 2 errors (live check)`), והכל מתנקה ברגע ששמירה מתקמפלת נקי. שמירות מהירות מתאחדות
לבדיקה אחת נוספת. מפעילים/מכבים ב-⚙ Settings ← Linter & Sync או בתצוגת ▶ Run & Compile.

**🔗 מעקב שגיאות בלחיצה בקונסולה.** כל הפניה מסוג `file.v:line` או `file.v:line:col` בקונסולה – כולל נתיבים מלאים כמו
`C:\iverilog\compstruct\lib\mux.v:14` – מוצגת כקישור; לחיצה עליה פותחת את הקובץ בשורה הזו (בעורך אם זה המודול
הנוכחי, ב-Notepad++ לכל קובץ אחר).

#### 📊 טבלת אמת אינטראקטיבית וממיר בסיסים

<div dir="ltr">

<p align="center"><img src="docs/screenshots/03-truth-table.png" width="860" alt="Truth table"></p>

</div>

* הפלט של `$monitor` / `$display` מפוענח אוטומטית – גם בסגנון `key=value` (`a=0 | b=1 | s=1`) וגם בטבלה רגילה עם
  שורת כותרת. שורות `VCD info:` ו-`$finish called at …` מסוננות.
* שורות שהיציאות שלהן מכילות `x` או `z` מסומנות **FLOATING/CONFLICT (x/z)** (כתום); שורות עם `FAIL`, `ERROR` או
  `MISMATCH` מסומנות **FAIL** (אדום).
* החלפת בסיס בזמן אמת: **Binary / Hex / Unsigned Dec / Signed Dec** (המשלים ל-2 לפי הרוחב האמיתי של כל פורט).
* `📋 Copy Markdown` / `📋 Copy CSV` – מדביקים את הטבלה ישירות לדוח של תרגיל הבית.
* **סרגל סינון** – הצגת `All`, רק שורות `x/z Floating` או רק `FAIL`, וגם חיפוש טקסט (`1010`, `sum=1`…), כך שטבלאות
  של 64 או 128 שורות נשארות קלות לבדיקה (הסיכום מציג "k of n rows").

#### 〰 מציג גלים מובנה ושילוב עם GTKWave

<div dir="ltr">

<p align="center"><img src="docs/screenshots/04-waveform.png" width="860" alt="Waveform viewer"></p>

</div>

* קורא `.vcd` שכתוב כולו ב-Python (מזהים מרובי תווים, ערכים סקלריים ווקטוריים, `x`/`z`).
* ציור על קנבס: קווי 0/1 ירוקים, "משושים" לאפיקים עם הערך בבסיס הנבחר, מלבן אדום מקווקו ל-`x`, קו צהוב באמצע ל-`z`,
  ציר זמן, הגדלה/הקטנה, התאמה לחלון, וסמן שמוצב בלחיצה ומציג את ערך כל אות באותו רגע.
* ברירת המחדל היא אותות רמת הטסטבנץ'; מסמנים **Internal signals** כדי לראות גם אותות פנימיים של `uut`.
* אין `.vcd`? דיאגרמת הגלים נבנית משורות טבלת האמת.
* `📈 Open in GTKWave` פותח את אותו קובץ ב-GTKWave.

#### 🌳 ניתוח היררכיה וספירת שערים + תרשים פינים (לשונית `HIERARCHY & GATES`)

<div dir="ltr">

<p align="center"><img src="docs/screenshots/05-hierarchy-pinout.png" width="860" alt="Hierarchy and pinout"></p>

</div>

* **עץ מופעים** של המודול הפעיל על פני תיקיית העבודה וכל החבילות הפעילות – למשל
  `FA ← ha1 : HalfAdder ← g1 : xor, g2 : and`. כל שורה מציגה איפה המודול מוגדר (קובץ + חבילה); לחיצה על מופע פותחת
  את קובץ ה-`.v` שלו (תצוגה לקריאה בלבד לקובצי חבילות).
* **ספירת שערים שטוחה** על כל ההיררכיה (`NAND`, `NOR`, `XOR`, `XNOR`, `AND`, `OR`, `NOT`, `BUF`), מספר מופעי תתי-המודולים,
  מודולים חסרים ו**הערכת עומק לוגי** ברמות שערים (ניתוח סטטי: לולאות generate ומערכי מופעים נספרים פעם אחת).
* **תרשים שבב (IC)** בסגנון VS Code: כניסות משמאל, יציאות/inout מימין, אפיקים מצוירים כקו כפול עם הטווח `[msb:lsb]`,
  ושם המודול עם מספר השערים והעומק על השבב.

#### ⌨ השלמה אוטומטית חיה בסגנון IntelliSense (תוך כדי הקלדה + `Ctrl+Space`)

<div dir="ltr">

<p align="center"><img src="docs/screenshots/06-intellisense-modules.png" width="860" alt="IntelliSense: modules"></p>

<p align="center"><img src="docs/screenshots/07-intellisense-ports.png" width="860" alt="IntelliSense: ports"></p>

</div>

* רשימת הצעות בסגנון VS Code נפתחת **תוך כדי הקלדה**: אחרי 2 אותיות של שם, על `$`, על `` ` `` ועל `.` בתוך מופע של
  מודול. `Ctrl+Space` פותח אותה בכל רגע. החלונית לא לוקחת את המקלדת, כך שאפשר להמשיך להקליד כדי לסנן. `↑`/`↓` לתנועה,
  `Tab`/`Enter` להכנסה, `Esc`, לחיצה במקום אחר, `Space` או `;` לסגירה. `Enter` אחרי מילה שכבר שלמה (`end`, `a`)
  פשוט יורד שורה.
* לכל שורה יש תג צבעוני של הסוג ועמודת פרטים:
  * **`M` מודולים**: כל מודול מתיקיית העבודה, מספריית הקורס (`compstruct\lib`) ומכל החבילות הפעילות, בשתי גרסאות.
    **Full Instantiation** מכניס `Mux4 u_mux4_1 (.d(), .sel(), .y());` עם שם מופע ממוספר אוטומטית והסמן בתוך
    ה-`.port()` הראשון. **Module Name** מכניס רק את השם. כרטיס בתחתית מציג את חתימת הפורטים ואת החבילה, למשל
    `FullAdder (input a, input b, input cin -> output sum, output cout) · Workspace`.
  * **`P` פורטים**: מקלידים `.` בתוך `FullAdder fa1 ( … ` ומקבלים את הפורטים של המודול הזה (`.cin()  [input 1-bit]`).
    פורטים שעדיין לא חוברו מופיעים ראשונים, ובחירה בפורט שמה את הסמן בתוך `.cin(|)`. עובד גם עם מופעים עם פרמטרים
    (`#(…)`) ועם מופעים שמתפרסים על כמה שורות.
  * **`W` אותות**: השמות שהוגדרו בקובץ הנוכחי כ-`input/output/inout/wire/reg/logic/integer/parameter` (בלי שגיאות
    הקלדה שיוצרות חוטים מרומזים).
  * **`K` מילות מפתח ותבניות בלוק**: `module (template)`, `always @(*)`, `always @(posedge clk)`,
    `initial begin … end`, `case … endcase`, `generate`, `function`, `task`… והסמן נוחת בתוך הבלוק.
  * **`G` שערים בסיסיים** עם סדר הפינים (`nand (out, in1, in2, …)`, `bufif1 (out, in, ctrl)`): היציאה תמיד ראשונה.
  * **`S` משימות מערכת והנחיות**: `$display("…")`, `$monitor`, `$finish;`, `$dumpvars(0, …)`, `$readmemb`…,
    `` `timescale 1ns/1ps``, `` `include``, `` `define``, `` `ifdef``…
* ההתאמה לא תלויה ברישיות: קודם התחלת מילה, אחר כך ראשי תיבות של CamelCase (`fa` → `FullAdder`, `ha` → `HalfAdder`),
  ואז מחרוזת חלקית. סדר הדירוג: פורטים אחרי `.`, אחר כך מודולים ואותות מקומיים, אחר כך שערים ומילות מפתח, ובסוף
  משימות מערכת.
* אפשר לכבות את הפתיחה האוטומטית בהגדרות ← Editor Behavior (`Enable Live Autocomplete (IntelliSense)`).
  `Ctrl+Space` תמיד עובד.
* כשהסמן על שם של מודול, שורת הסטטוס מציגה את חתימת הפורטים שלו ואת החבילה, למשל
  `◆ HalfAdder (output s, output c, input a, input b) · Lab4`.

#### 📦 הגשת תרגיל בלחיצה אחת (`📦 Export HW .zip`)

* הכפתור `📦 Export HW .zip` בסייר (או `📤`) אורז את כל קובצי ה-`.v` / `_tb.v` / `.vh` של תיקיית העבודה ל-
  `<Workspace>_Submission.zip`, ומשאיר בחוץ קובצי `vvp` מקומפלים, קובצי `.vcd`, קובצי zip וקבצים זמניים/גיבוי.
* הוא בודק אם התכנון שלכם משתמש במודולי עזר **שלא נמצאים בספריית הקורס וגם לא בתיקייה** (מודולים מחבילות שיובאו או
  קושרו) ומציע לצרף אותם – כל אחד כקובץ `<Module>.v` עצמאי, יחד עם קובצי כותרת שהוא עושה להם `` `include`` – כך שהבודק
  יוכל לקמפל את ה-zip עם הפקודה הרגילה של הקורס.

#### 🧹 ניקוי לפני הגשת תרגיל

`🧹 Clean` מוחק את קבצי ה-`vvp` המקומפלים מתיקיית העבודה לפני שמכווצים את התרגיל להגשה. מכיוון שאין להם סיומת, הם
מזוהים בבטחה לפי הכותרת שלהם (`#! … vvp`) – קבצי ה-`.v` שלכם לעולם לא נמחקים. קבצי `.vcd` נשארים (מחקו אותם ידנית
אם הקורס דורש).

#### 🔠 טיפוגרפיה נוחה, זום גלובלי ופריסטים של גודל טקסט

<div dir="ltr">

<p align="center"><img src="docs/screenshots/08-context-menu.png" width="860" alt="Dark context menu"></p>

<p align="center"><img src="docs/screenshots/11-light-theme.png" width="860" alt="Light theme"></p>

</div>

* ברירות מחדל נוחות לקריאה: **15** בעורך, **13** בקונסולה ו-**13** בממשק (Segoe UI לתפריטים, לשוניות, סרגל צד וכפתורים;
  Consolas לקוד, לטבלאות ולתוויות של הגלים ותרשים הפינים). הגדרות שנשמרו בגרסאות קודמות עם גדלים קטנים יותר מוגדלות
  לברירות המחדל האלה פעם אחת, בהפעלה הראשונה.
* **זום גלובלי** – `A-` / `A+`, `Ctrl+גלגלת`, `Ctrl+Plus` / `Ctrl+Minus` מגדילים את העורך, הקונסולה **וגם** את כל
  הממשק יחד (לשוניות הפאנל, תפריטים, שורות וכותרות טבלת האמת, שורות הגלים, תרשים הפינים, שורת המצב). `Ctrl+0` מאפס
  הכל לברירת המחדל.
* **פריסט גודל ממשק וטקסט** (הגדרות ← Appearance & Font): `Compact (12pt)`, `Comfortable (14-15pt)`,
  `Large / High-Visibility (17pt)`, `Extra Large (20pt)` – או הגדרה ידנית של שלושת הגדלים (מוצג כ-`Custom`).
* **תפריטי קליק-ימני כהים וקריאים** בכל מקום (עורך, תת-תפריט הסניפטים, תפריט המודול): חלונות `#252526` ללא מסגרת,
  Segoe UI בגודל הגופן של הממשק, שורות של 32 פיקסלים עם הדגשת `#04395E`, קיצורי מקלדת מיושרים לימין, תתי-תפריטים
  שנפתחים לצד וניווט במקלדת; נסגרים ב-`Escape`, בלחיצה במקום אחר או כשהחלון מאבד פוקוס.
* סרגל הכלים **רספונסיבי**: כשהחלון צר מדי לתוויות המלאות, הכפתורים מתכווצים לאייקונים (📂 🔍 🧪 💾 ⚡ 📦 📝 🧹) ומציגים
  הסבר במעבר עכבר; התוויות חוזרות ברגע שיש מקום.

#### 🏠 מסך פתיחה (Welcome) ואשף מודול / פרויקט חדש

<div dir="ltr">

<p align="center"><img src="docs/screenshots/01-welcome.png" width="860" alt="Welcome page"></p>

<p align="center"><img src="docs/screenshots/09-new-module-wizard.png" width="720" alt="New Module wizard"></p>

</div>

* בהפעלה VeriFlow פותח **מסך פתיחה** בסגנון VS Code באזור העורך, במקום לקפוץ ישר לתיקייה:
  * **Start** – `📄 New Verilog Module / File… (Ctrl+N)`, `📁 Create New Assignment / Project Folder… (Ctrl+Shift+N)`,
    `📂 Open Existing Folder… (Ctrl+O)`, `📄 Open Single .v File…` (פותח את התיקייה שלו ובוחר את המודול),
    `📦 Import Lecturer Modules / Package…` ו-`🧪 Open Built-in Sample Project (FullAdder)`.
  * **Recent** – עד 8 תיקיות אחרונות (שם + נתיב מלא, תיקייה שנמחקה מוצגת באפור); לחיצה פותחת, `×` מסיר,
    `Clear Recent` מרוקן את הרשימה.
  * בתחתית: `☑ Show Welcome screen on startup`. אפשר לחזור למסך בכל רגע עם `🏠 Welcome` (סרגל הכלים / סרגל
    הפעילות) או עם `✕` **Close Folder** בכותרת הסייר.
* **מצב הפעלה** (הגדרות ← Editor Behavior ← *On startup*): מסך פתיחה (ברירת מחדל), פתיחה מחדש של התיקייה האחרונה,
  או חלון ריק.
* **אשף מודול / פרויקט חדש** (`Ctrl+N` / `Ctrl+Shift+N` / `+` בסייר):
  * שם המודול (תצוגה מקדימה חיה של `<Module>.v` + `<Module>_tb.v` ושל נתיב היעד),
  * **איפה לשמור** – ברירת המחדל היא תיקיית העבודה הפתוחה (או תיקיית האב האחרונה / `Documents`), `📂 Browse Folder…`,
    ושדה ליצירת תת-תיקייה / שם תיקייה חדשה (למשל `Documents\CompStruct` + `Lab4`),
  * **פורטים** (רשות) – כניסות `a, b, cin` או `[15:0] a, [15:0] b`, יציאות `sum, cout` או `[15:0] y` (הרוחב נכתב לפני
    כל שם של אפיק); ריק = תבנית ה-NAND הקלאסית,
  * **טסטבנץ'** – `Exhaustive Truth-Table TB`, `Empty Skeleton TB` או `No TB yet`,
  * `☐ Also open the new file(s) in Notepad++`.
  * `✨ Create & Open Module` יוצר את התיקייה, כותב את הקבצים, עובר אליה כתיקיית עבודה ופותח את שני הקבצים בעורך המפוצל.

#### 🔔 עדכונים אוטומטיים מ-GitHub (התראה + עדכון בלחיצה אחת)

* `updater.py` (ספריית התקן בלבד) בודק **שני מקורות** כ-1.5 שניות אחרי ההפעלה ואז כל 30 דקות, ברקע ועם מגבלת זמן של
  4 שניות (בלי אינטרנט = שקט):
  1. ה-**GitHub Release** האחרון (`api.github.com/repos/<owner>/<repo>/releases/latest`) – כולל את קובץ ה-`.exe`;
  2. **`version.json` בענף `main`** (`raw.githubusercontent.com/<owner>/<repo>/main/version.json`) – כך שדחיפה שמעלה
     את הגרסה בקובץ מתריעה לכל מי שמריץ מקוד המקור.
* שם המאגר נקרא מ-`git config --get remote.origin.url` (גיבוי: `Nirco99/veriflow-studio`). אם ה-TLS של Python לא מצליח
  לאמת את שרשרת האישורים של GitHub, נעשה שימוש ב-`curl.exe` של Windows (מאגר האישורים של המערכת).
* כשיש גרסה חדשה מופיע כרטיס התראה בסגנון VS Code (פינה ימנית-תחתונה) ותג `🔔 Update vX.Y.Z` בשורת המצב:
  `↓ Update & Restart Now` · `View Changes` · `Later`.
  * **מקוד מקור**: `git pull --rebase --autostash origin main` (או `main.zip` כשאין תיקיית `.git`), ואז VeriFlow מופעל מחדש.
  * **`.exe`**: מוריד את ה-`.exe` מה-Release בשם `<name>_new.exe`, מפעיל עוזר קטן ומנותק שמחכה שהתוכנה תיסגר, מחליף
    את הקובץ ומפעיל מחדש. אם `main` חדש יותר מה-Release האחרון (אין עדיין `.exe`), הכפתור פותח את דף ההורדה.
* כיבוי או בדיקה ידנית: הגדרות ← Editor Behavior (`Check GitHub for updates`, `🔔 Check for Updates Now`).
* **פרסום עדכון** (למתחזקים): מעלים את `APP_VERSION` ב-`config_manager.py` ואת `version.json`, דוחפים ל-`main`;
  למשתמשי `.exe` מפרסמים גם GitHub Release ‏`vX.Y.Z` עם `VeriFlowStudio.exe` מצורף.

#### 🧩 מצב הדגמה (כש-Icarus Verilog לא מותקן)

אם `iverilog.exe` לא נמצא, מופיע פס כתום ו-VeriFlow עובר ל**סימולטור שערים מובנה ב-Python** (תכנונים של סיבית אחת
שבנויים מ-`and/or/nand/nor/xor/xnor/not/buf` ו-`assign` פשוטים), כך שאפשר להתנסות בעורך, ב-Linter, בטבלת האמת ובגלים
בכל מחשב. מודולים של המרצה ואפיקים דורשים את הכלים האמיתיים.

### הורדה והפעלה מהירה

1. **מורידים את [VeriFlowStudio.exe](https://github.com/Nirco99/veriflow-studio/releases/latest/download/VeriFlowStudio.exe)** (הכפתור הירוק [בראש הקטע העברי](#download-he)) ולוחצים עליו פעמיים.
   בלי התקנה ובלי Python. אם מופיע SmartScreen של Windows: **More info ← Run anyway**.
2. **Icarus Verilog** מותקן ב-`C:\iverilog` (`C:\iverilog\bin\iverilog.exe`, `C:\iverilog\bin\vvp.exe`) וספריית
   המרצה ב-`C:\iverilog\compstruct\lib`. מיקומים אחרים מוגדרים ב-**⚙ Settings → Compiler & Toolchain** (יש כפתור
   **Auto-Detect Paths**). בלי Icarus Verilog התוכנה רצה במצב הדגמה.
3. *(אופציונלי)* **Notepad++** לסנכרון החי ו-**GTKWave** להצגת גלים חיצונית.
4. נפתח **מסך הפתיחה**: יוצרים תיקיית תרגיל חדשה (`Ctrl+Shift+N`), פותחים תיקייה קיימת (`Ctrl+O`), או מנסים את
   פרויקט הדוגמה המובנה.
5. **העדכונים אוטומטיים**: כשיוצאת גרסה חדשה, מופיעה התראת 🔔 עם **Update & Restart Now**.
   כל הגרסאות והערות השחרור: [Releases](https://github.com/Nirco99/veriflow-studio/releases).

### מדריך שימוש צעד אחר צעד

1. **פתיחה או יצירה של תיקיית תרגיל** – ממסך הפתיחה, `📂 Open…` (`Ctrl+O`), `Recent ▾`, או `Ctrl+Shift+N` ליצירת
   תיקייה חדשה עם המודול הראשון שלה. הסייר מציג כל מודול והאם יש לו טסטבנץ'.
2. **בחירה או יצירה של מודול** – לחיצה בסייר או בחירה מהתפריט `Module:`. הכפתור `+ New .v` (`Ctrl+N`) פותח את האשף:
   שם, תיקייה, פורטים וטסטבנץ' לפי בחירה (שם הקובץ תמיד זהה לשם המודול, כפי ש-`-y` דורש).
3. **שימוש במודולים של המרצה** – טוענים אותם פעם אחת עם `📦 Packages` (`+ .v Files`, `+ Folder` או `+ .zip`), ואז
   פותחים את תצוגת **📚 Library & Packages**, מחפשים, בוחרים מודול ולוחצים `⤵ Insert at Cursor`.
4. **יצירת הטסטבנץ'** – `🧪 Gen _tb.v` (מוצע גם בלשונית הטסטבנץ' כשהוא חסר), ואז מתאימים אותו.
5. **הרצה** – לוחצים `F5`. או לוחצים `📝 N++`, כותבים שם ופשוט שומרים עם `Ctrl+S` – הסנכרון החי מריץ הכל.
6. **בדיקת התוצאות** –
   * **Console Output** – הפקודות המדויקות והפלט הגולמי של `iverilog`/`vvp`, בצבעים; הפניות `file.v:line` לחיצות.
   * **Problems & Linter** – לחיצה על שורה קופצת לשורה בקוד.
   * **Truth Table** – החלפת בסיס, העתקה כ-Markdown/CSV.
   * **Waveform** – הגדלה, הצבת סמן, או פתיחה ב-GTKWave.
   * בכותרת הפאנל מוצגת שורת הפקודה; המתג **Actual / Baseline** מציג את הפקודה המדויקת מהנחיות הקורס, ו-`📋 Copy CMD`
     מעתיק אותה להדבקה ב-`cmd.exe`. תצוגת **▶ Run & Compile** מציגה את כל הדגלים.
7. **לפני הגשה** – `🧹 Clean` מוחק את הקבצים המקומפלים.

### טבלת הגדרות

פותחים את **⚙** (למעלה מימין, בסרגל הפעילות, או `Ctrl+,`). כל שינוי חל **מיד** ונשמר ב-
`%APPDATA%\VeriFlowStudio\config.json`.

| לשונית | הגדרה | מפתח ב-`config.json` | ערכים / ברירת מחדל |
|---|---|---|---|
| Appearance & Font | מצב תצוגה | `appearance_mode` | `Dark` (ברירת מחדל), `Light`, `System` – גם כפתור ☀/🌙 |
| | ערכת צבע ממשק | `color_theme` | `blue`, `green`, `dark-blue` (חל אחרי הפעלה מחדש) |
| | ערכת צבעי העורך | `editor_color_scheme` | `Dark Modern` (VS Code Dark+, ברירת מחדל), `Light Modern` (VS Code Light+), `One Dark`, `Monokai`, `GitHub Light`, `High Contrast` |
| | הגדלת ממשק | `ui_scale_percent` | `80` `90` `100` `110` `125` `150` % |
| | גופן העורך | `editor_font_family` | `Consolas`, `Cascadia Code`, `JetBrains Mono`, `Courier New`, `Lucida Console` |
| | גודל גופן העורך | `editor_font_size` | 10–32 (ברירת מחדל 15) – גם `A-` / `A+` ו-`Ctrl+גלגלת` |
| | גודל גופן הקונסולה | `console_font_size` | 10–28 (ברירת מחדל 13) |
| | פריסט גודל ממשק וטקסט | – | `Compact (12pt)`, `Comfortable (14-15pt)`, `Large / High-Visibility (17pt)`, `Extra Large (20pt)`, `Custom` |
| | גודל גופן הממשק (תפריטים, לשוניות, טבלאות, סרגל צד) | `ui_font_size` | 10–24 (ברירת מחדל 13) |
| | בסיס ברירת מחדל | `default_radix` | `Binary`, `Hex`, `Unsigned Dec`, `Signed Dec` |
| Editor Behavior | פריסת העורך | `editor_split_layout` | `Side-by-Side` (‏.v + _tb.v, ברירת מחדל) או `Tabbed` |
| | גודל טאב | `tab_size` | 2, 4 (ברירת מחדל), 8 |
| | רווחים במקום טאב | `insert_spaces_for_tabs` | פעיל |
| | גלישת שורות | `word_wrap` | כבוי |
| | הדגשת השורה הנוכחית | `highlight_current_line` | פעיל |
| | הזחה אוטומטית | `auto_indent` | פעיל |
| | סגירה אוטומטית של סוגריים ו-`begin`/`end` | `auto_close_brackets_and_blocks` | פעיל |
| | שמירה לפני הרצה (F5) | `auto_save_before_run` | פעיל |
| | שמירה ביציאה מהחלון | `auto_save_on_focus_loss` | כבוי |
| | בהפעלה | `startup_mode` | `welcome_screen` (ברירת מחדל), `reopen_last`, `empty_window` |
| | בדיקת עדכונים ב-GitHub | `check_for_updates` | פעיל (בהפעלה וכל 30 דקות); כפתור `🔔 Check for Updates Now` |
| | השלמה אוטומטית חיה (IntelliSense) תוך כדי הקלדה | `live_autocomplete` | פעיל (`Ctrl+Space` תמיד עובד) |
| Compiler & Toolchain | נתיבי iverilog.exe / vvp.exe / gtkwave.exe | `iverilog_path`, `vvp_path`, `gtkwave_path` | `C:\iverilog\bin\…`, `C:\iverilog\gtkwave\bin\gtkwave.exe` |
| | ספריית המרצה (`-y`) | `lib_dir` | `C:\iverilog\compstruct\lib` |
| | notepad++.exe | `notepad_pp_path` | `C:\Program Files\Notepad++\notepad++.exe` |
| | תקן השפה | `std_flag` | `-g2012` (ברירת מחדל), `-g2005-sv`, `-g2005`, `-g2001` |
| | תיקיית העבודה כספריית `-y` | `include_workdir_as_ylib` | פעיל |
| | הפעלת `-Wall` ו-`-Winfloop` | `enable_wall_warnings` | פעיל |
| | `vvp -n` לא-אינטראקטיבי | `vvp_non_interactive_flag` | פעיל (מונע תקיעה ב-`$stop`) |
| | מגבלת זמן לסימולציה | `sim_timeout_sec` | 1.0–30.0 שניות (ברירת מחדל 3.0) |
| Linter & Sync | Linter סטטי של הקורס | `enable_course_linter` | פעיל |
| | מצב רמת-שערים קפדני | `strict_gate_level_mode` | כבוי |
| | סנכרון חי עם Notepad++ | `live_sync_enabled` | כבוי (גם המתג `⚡ N++ Sync`) |
| | הרצה אוטומטית בשמירה חיצונית | `auto_run_on_external_save` | פעיל |
| | תדירות בדיקה | `external_poll_interval_ms` | 500–3000 מילישניות (ברירת מחדל 800) |
| | בדיקת קומפילציה חיה בשמירה (`iverilog -tnull`) | `live_check_on_save` | פעיל |
| Packages | פענוח אוטומטי של מודולים מחבילות (`-y` לכל תיקייה, `-l` לקבצים מרובי-מודולים / בשם אחר) | `auto_resolve_packages_with_l_flag` | פעיל |
| | כספת החבילות הגלובלית | `global_packages_dir` | `%USERPROFILE%\.veriflow_studio\packages` |
| | החבילות הרשומות (מנוהלות בחלון Package Manager) | `library_packages` | ספריית הקורס המובנית; חבילות שיובאו / קושרו מתווספות כאן |

הקובץ `config.json` זוכר גם את מצב הממשק (`last_workspace_dir`, `recent_workspaces`, `last_module`,
`window_geometry`, `sidebar_visible`, `sidebar_view`). הכפתור **Reset to Defaults** מחזיר הכל לברירת המחדל חוץ
מרשימת התיקיות והחבילות.

### קיצורי מקלדת

| קיצור | פעולה |
|---|---|
| `F5` | שמירה, Linter, קומפילציה (`iverilog`) וסימולציה (`vvp`) |
| `Shift+F5` | עצירת הסימולציה |
| `F7` | הרצת ה-Linter בלבד |
| `Ctrl+S` | שמירת הקובץ הפעיל (בעורך) / שמירת הכל (מחוץ לעורך) |
| `Ctrl+B` | הצגה/הסתרה של סרגל הצד (Explorer / Library / Run) |
| `Ctrl+O` / `Ctrl+N` / `Ctrl+Shift+N` | פתיחת תיקייה / אשף מודול חדש / אשף תיקיית תרגיל חדשה |
| `Ctrl+,` | הגדרות |
| `Ctrl+F` / `Ctrl+H` | חיפוש / חיפוש והחלפה (`Enter`, `Shift+Enter`, `F3` = הבא/הקודם) |
| `Ctrl+G` | מעבר לשורה |
| `Ctrl+Space` | השלמה (IntelliSense): מודולים (מופע מלא / שם), חיבורי `.port()`, אותות, מילות מפתח, שערים, `$tasks`, הנחיות (נפתח גם תוך כדי הקלדה) |
| `Ctrl+/` | הוספה/הסרה של הערת `//` בשורות המסומנות |
| `Ctrl+D` | שכפול שורה / בחירה |
| `Ctrl+Z` / `Ctrl+Y` (`Ctrl+Shift+Z`) | ביטול / ביצוע מחדש |
| `Tab` / `Shift+Tab` | הזחה / ביטול הזחה של הבחירה |
| `Ctrl+גלגלת`, `Ctrl+Plus`, `Ctrl+Minus`, `Ctrl+0` | הגדלה / הקטנה / איפוס של העורך, הקונסולה וכל הממשק |

### ארכיטקטורה ומבנה קבצים

<div dir="ltr" align="left">

```text
veriflow-studio/
├── main.py              # VS Code-style workbench, settings dialog, Notepad++ live sync, run orchestration
├── ui_components.py     # Code editor, truth table, waveform viewer, activity bar, panel tabs
├── verilog_runner.py    # iverilog -> vvp pipeline, timeout/process-tree kill, diagnostics & truth-table parsers
├── verilog_parser.py    # Module parser, course linter, testbench generator, VCD reader (no GUI)
├── config_manager.py    # Settings + config.json, VS Code colour tokens, toolchain auto-detection
├── welcome.py           # Welcome page, New Module & Project wizard, update notification card
├── intellisense.py      # IntelliSense engine: completion context, candidates and ranking
├── updater.py           # GitHub update checker + 1-click self-updater (standard library only)
├── version.json         # current version + notes on main (update notifications)
├── package_manager.py   # Global package vault, .v / folder / .zip import, -y / -l resolution
├── build_exe.bat        # maintainers: builds the released VeriFlowStudio.exe
├── requirements.txt
├── sample_project/      # FullAdder.v + FullAdder_tb.v
└── docs/screenshots/     # README screenshots
```

</div>

* **`main.py`** – חלון העבודה בסגנון VS Code: סרגל כותרת ופעולות, סרגל פעילות, תצוגות הצד, קבוצת העורכים, הפאנל
  התחתון, שורת הסטטוס, חלון ההגדרות, הסנכרון החי עם Notepad++ וניהול ההרצה.
* **`ui_components.py`** – רכיבי הממשק: עורך הקוד (Pygments בצבעי Dark+/Light+, מספרי שורות, חיפוש, קטעי קוד, זום),
  טבלת האמת, מציג הגלים, סרגל הפעילות ולשוניות הפאנל.
* **`verilog_runner.py`** – תהליך `iverilog` ← `vvp` בתהליכון רקע, מחיקת בינארי ישן, הריגת עץ תהליכים בחריגת זמן,
  פענוח שגיאות שמתאים ל-Windows, פענוח טבלת אמת וסימולטור ההדגמה.
* **`verilog_parser.py`** – ניתוח מודולים (ANSI / ישן / פרמטרים), ה-Linter של הקורס, מחולל הטסטבנץ' וקורא ה-VCD –
  פונקציות טהורות ללא ממשק גרפי.
* **`config_manager.py`** – סכמת ההגדרות, אימות ושמירה ב-`config.json`, צבעי VS Code, ערכות צבעי העורך וזיהוי
  אוטומטי של הכלים.
* **`package_manager.py`** – כספת החבילות הגלובלית: ייבוא קבצי `.v`, תיקיות וארכיוני `.zip`, הפעלה/הסרה של חבילות,
  חישוב דגלי `-y` / `-l` לכל קומפילציה ועותקים שמורים ללא התנגשויות של קובצי ספרייה.
* **`sample_project/`** – הדגמה: מחבר מלא (Full Adder) ברמת שערים עם טסטבנץ' שבודק את עצמו.

### פתרון תקלות

| תסמין | פתרון |
|---|---|
| פס כתום "DEMO MODE" | Icarus Verilog לא נמצא – התקינו ב-`C:\iverilog` או הגדירו נתיבים (⚙ → Compiler & Toolchain → Auto-Detect). |
| `Unknown module type: X` | בדקו רישיות של שם המודול ושהקובץ `X.v` קיים בתיקייה או בספריית המרצה (ה-Linter מסמן את שניהם). |
| חריגת זמן בסימולציה | בטסטבנץ' אין `$finish`, הוא מחכה לנצח, או שיש לולאה ללא השהיה. הגדילו את מגבלת הזמן רק לסימולציות ארוכות באמת. |
| טבלת האמת ריקה | הטסטבנץ' לא מדפיס כלום – הוסיפו `$monitor`/`$display` (‏Gen _tb.v עושה זאת). |
| דיאגרמת הגלים ריקה | הוסיפו `$dumpfile`/`$dumpvars`, או הסתמכו על הגלים שנבנים מטבלת האמת. |
| `Cannot delete stale binary` | תהליך `vvp` ישן עדיין מחזיק את הקובץ – לחצו Stop או סגרו אותו. |

### רישיון

הפרויקט מופץ תחת [רישיון MIT](LICENSE).

[⬆ חזרה למעלה](#top)

</div>
