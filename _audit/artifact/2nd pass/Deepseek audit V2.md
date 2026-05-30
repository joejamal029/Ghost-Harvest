## SPRINT_FIX.md – Ghost Harvest v2.1

**Audit Date:** 2026-05-29  
**Auditor:** Senior Architect Review  
**Target:** Autonomous Agent Implementation Sprint  
**Base Ref:** `README.md` (Architecture, Threat Model, Pipeline)

---

## HOW TO USE THIS FILE

All bugs are tagged with severity (`[BLOCKER]`, `[HIGH]`, `[MEDIUM]`, `[IMPROVEMENT]`).  
Apply fixes **strictly in the Execution Order** – each Group forms a working checkpoint.  
When the code conflicts with `README.md`, the **code** is the source of truth unless this file explicitly says otherwise (spec override notes included).

---

## PASS 1 — CRITICAL BLOCKERS

**No issues found.** The codebase imports, starts, and runs without compilation or dependency blockers.

---

## PASS 2 — HIGH SEVERITY TEST BUGS

**No issues found.** The single test file `validate_security.py` passes all 37 assertions; no test failures are expected when stubs are implemented.

---

## PASS 3 — MEDIUM SEVERITY

### BUG-001 [MEDIUM] — Trailing backslash double‑append in robocopy arguments

**File:** `ghost_harvest/command.py` (lines 29–35 in `build_args`)

**What's wrong:**  
The code adds a trailing backslash to `source` and `dest` if they already end with `\\` but are not a drive root (e.g., `C:\\`). For a path like `C:\\Windows\\`, it adds another backslash, producing `C:\\Windows\\\\`. While Windows usually tolerates multiple backslashes, this is unintended and can break relative path resolution or log file naming.

**Fix:**  
Replace the current block:

```python
if source.endswith("\\") and not source.endswith(":\\"):
    source += "\\"
if dest.endswith("\\") and not dest.endswith(":\\"):
    dest += "\\"
```

with:

```python
# Ensure exactly one trailing backslash for directory arguments (robocopy works without, but this avoids double backslashes)
source = source.rstrip("\\")
if not source.endswith(":\\"):
    source += "\\"
dest = dest.rstrip("\\")
if not dest.endswith(":\\"):
    dest += "\\"
```

### BUG-002 [MEDIUM] — Pre‑flight byte parser mishandles thousands separators

**File:** `ghost_harvest/app.py` (method `_parse_robocopy_bytes`)

**What's wrong:**  
The parser replaces `,` with `.` before converting to float. If a number like `1,234` appears (thousands separator), it becomes `1.234` and is interpreted as 1.234 bytes, not 1234 bytes. Robocopy output localization may produce such formats.

**Fix:**  
Replace the `val = float(parts[j - 1].replace(",", "."))` line with a robust removal of all non‑digit characters except the decimal point:

```python
raw_num = parts[j - 1].replace(",", "")
# Remove everything except digits and dot
clean_num = "".join(ch for ch in raw_num if ch.isdigit() or ch == ".")
val = float(clean_num) if clean_num else 0.0
```

Also add a fallback for the "raw byte count" branch that strips commas:

```python
nums = [x.replace(",", "") for x in parts if x.replace(",", "").isdigit()]
```

### BUG-003 [MEDIUM] — `_BLOCKED.txt` may be scanned for magic bytes unnecessarily

**File:** `ghost_harvest/app.py` (pipeline) and `ghost_harvest/scanner.py`

**What's wrong:**  
The scanner skips files starting with `_GhostHarvest`, but the manifest is named `_BLOCKED.txt`. This file is written to the destination and may later be scanned as a normal `.txt` file (if `scan_plain` is enabled). No real harm, but it adds log noise and wastes a few CPU cycles.

**Fix:**  
Add `_BLOCKED.txt` to the internal skip list. In `scanner.py`, inside `scan_directory`, expand the skip condition:

```python
if fname.startswith(INTERNAL_PREFIX) or fname == "_BLOCKED.txt":
    continue
```

> **Spec override:** This deviates from `README.md` (which only mentions `_GhostHarvest` prefix). The manifest file should be excluded from scanning – this is a safety enhancement.

---

## PASS 4 — ENVIRONMENT & STRUCTURAL

### BUG-004 [MEDIUM] — Custom XD list splits on spaces but doesn’t quote paths with spaces

**File:** `ghost_harvest/app.py` (custom_xd handling) and `ghost_harvest/command.py`

**What's wrong:**  
The UI allows entering space‑separated folder names to exclude. If a folder name itself contains a space (e.g., `My Documents`), `split()` will break it into two separate arguments, causing robocopy to see two different exclusion patterns and likely fail to exclude the intended folder.

**Fix:**  
No code change – this is a documented limitation. Add a **runtime warning** to the UI. In `app.py`, when building `custom_xd`, check if any component contains a space and show a warning in the log:

```python
extra = custom_xd.strip()
if extra:
    parts = extra.split()
    for p in parts:
        if " " in p:
            self._log(f"⚠  Warning: custom exclusion '{p}' contains a space – robocopy may not exclude it correctly.\n", "warn")
```

### BUG-005 [MEDIUM] — Destination disk space check uses root anchor, not destination folder

**File:** `ghost_harvest/app.py` (`_update_space` method)

**What's wrong:**  
`shutil.disk_usage(anchor)` uses the root of the destination drive (e.g., `C:\`). If the destination is on a network share or a mounted volume without a drive letter, `Path(anchor).anchor` returns `\\` (UNC root) and `os.path.exists(anchor)` may fail or produce wrong usage. The error is caught silently, but the user sees "Unable to check disk space" even when space is available.

**Fix:**  
Use the destination path itself and catch more specific errors. Replace the `try` block:

```python
try:
    target = Path(self.dest_var.get().strip())
    if target.exists():
        _, used, free = shutil.disk_usage(target)
        style = "Good.TLabel" if free / 1024**3 > 50 else "Warn.TLabel"
        self.space_lbl.config(
            text=f"Destination folder — {used / 1024**3:.1f} GB used · {free / 1024**3:.1f} GB free",
            style=style,
        )
    else:
        self.space_lbl.config(text="Destination folder does not exist yet", style="Warn.TLabel")
except (OSError, ValueError, PermissionError):
    self.space_lbl.config(text="Unable to check disk space", style="Warn.TLabel")
```

---

## PASS 5 — IMPROVEMENTS

### IMP-001 [IMPROVEMENT] — Add destination‑inside‑source guard

**File:** `ghost_harvest/app.py` (inside `_start` before running pipeline)

**Fix:**  
After validating destination, check that no source folder is a parent of the destination (would cause recursive copy). Insert:

```python
dest_path = Path(dest).resolve()
for src in settings["queue"]:
    src_path = Path(src).resolve()
    if dest_path in src_path.parents or dest_path == src_path:
        self._log(f"⚠  Destination '{dest}' is inside source '{src}' – would cause infinite recursion. Aborted.\n", "bad")
        self._finish()
        return
```

### IMP-002 [IMPROVEMENT] — Parallel hash verifier should report total files hashed

**File:** `ghost_harvest/hasher.py` (end of `verify` method)

**Fix:**  
Add a final summary line showing `ok+fail` total hashed files. Change:

```python
cb(
    f"  {ok:,} verified OK · {fail} mismatched · "
    f"{missing} source-only\n",
    tag,
)
```

to:

```python
total_hashed = ok + fail
cb(
    f"  {total_hashed:,} files hashed → {ok:,} OK · {fail} mismatched · "
    f"{missing} source-only\n",
    tag,
)
```

### IMP-003 [IMPROVEMENT] — Make `elevate()` fallback for non‑Windows

**File:** `ghost_harvest/utils.py` (`elevate` function)

**What's wrong:**  
The function uses `ctypes.windll` unconditionally. On non‑Windows (e.g., WSL, Linux), this crashes. The tool is Windows‑only per README, but a graceful fallback improves developer experience.

**Fix:**  
Add a guard:

```python
def elevate() -> None:
    if sys.platform != "win32":
        print("Elevation requested but not on Windows. Run as administrator manually.")
        sys.exit(1)
    # … existing code …
```

---

## EXECUTION ORDER FOR AGENT

Apply fixes in this exact order. Each Group is a working checkpoint.

**Group 1 — Backslash & manifest scanner fixes**  
1. BUG-001 (trailing backslash)  
2. BUG-003 (skip `_BLOCKED.txt`)  

**Checkpoint:** `python -c "from ghost_harvest.command import build_args; print(build_args('C:\\Windows', 'D:\\dest'))"` – should output a list without double backslashes.

**Group 2 — Pre‑flight parser & disk space**  
1. BUG-002 (byte parser)  
2. BUG-005 (disk space check)  

**Checkpoint:** Run a pre‑flight on a folder with large files – verify that byte parsing works correctly and disk space shows destination folder usage (not just drive root).

**Group 3 — Custom XD warning & destination guard**  
1. BUG-004 (space warning)  
2. IMP-001 (destination‑inside‑source guard)  

**Checkpoint:** Launch GUI, enter a custom exclusion with a space, click Refresh – warning appears in log. Try to set destination inside a queued source – migration should abort with error.

**Group 4 — Improvements (optional, but apply)**  
1. IMP-002 (hash summary)  
2. IMP-003 (elevate fallback)  

**Final checkpoint:** `python ghost_harvest/tests/validate_security.py` – expected output: `37 passed · 0 failed` (all existing tests must still pass).

---

## KNOWN STUBS (not bugs – expected at this stage)

- No unit tests for GUI components (tkinter event loops are not mocked). The only test is the security regression suite.
- No integration test for robocopy interaction – relies on manual execution in Windows environment.
- `validate_security.py` does not test pre‑flight parsing or disk space checks – those are covered by manual checkpoint commands.

---

Now, the agent initiation prompt follows.

```text
================================================================================
AGENT INITIATION PROMPT – GHOST HARVEST v2.1 SPRINT
================================================================================

READ FIRST, CODE SECOND

Read SPRINT_FIX.md (the file above) in full. Then re‑read the "EXECUTION ORDER
FOR AGENT" section. Fix dependencies exist: Group 1 must be applied before
Group 2, etc. Do not skip groups or reorder fixes.

OBJECTIVE

Implement all bug fixes (BUG-001 through BUG-005) and improvements (IMP-001
through IMP-003) exactly as described in SPRINT_FIX.md. After completing each
group, run the associated checkpoint command. The final success criterion is:

    python ghost_harvest/tests/validate_security.py
    → Output: "37 passed · 0 failed"

and the application must still launch and perform a dry‑run migration without
crashing or producing incorrect robocopy arguments.

EXECUTION RULES

1. Work file‑by‑file. Only modify files that are directly touched by a fix in
   SPRINT_FIX.md. Do not rewrite any other files.

2. Use the provided code blocks verbatim. Do not "improve" them during the
   bug‑fix sprint – any improvement beyond the given fix must be documented as
   an UNTRACKED‑BUG and justified.

3. Complete each group's checkpoint before moving to the next group. If a
   checkpoint fails, stop and report the failure with the exact command output.

4. SPRINT_FIX.md overrides the governing spec (README.md) where they conflict.
   This is explicitly noted in BUG-003 – follow the fix, not the README.

5. If you discover any new bug not listed in SPRINT_FIX.md, document it as:

       UNTRACKED-BUG: [file] — [description] — [proposed fix]

   before fixing it. Do not fix it silently.

ENVIRONMENT CHECK

- Python 3.9+ required (Windows environment mandatory for full testing, but
  code changes must be syntax‑compatible with Python 3.9+).
- No external dependencies – the project uses only the standard library.
- To verify the environment:

    python --version          # must be 3.9 or higher
    python -c "import tkinter"   # must succeed (GUI toolkit present)
    robocopy /? >nul 2>&1    # must succeed (robocopy exists on PATH)

All three checks are blocking – if any fails, abort and report.

CHECKPOINT COMMANDS (copy verbatim)

Group 1 checkpoint:
    python -c "from ghost_harvest.command import build_args; print(build_args('C:\\Windows', 'D:\\dest'))"

Group 2 checkpoint:
    (Manual visual verification) Launch GUI with `python main.py`, add a source
    folder with at least 1 GB of data, click "Pre‑flight". Confirm that byte
    parsing works and disk space shows destination folder usage (not just drive
    root). Also confirm no "Unable to check disk space" warning appears for a
    valid network path.

Group 3 checkpoint:
    Launch GUI, add a source folder, set destination inside that source (e.g.,
    source = C:\test, destination = C:\test\output). Click RUN – must abort
    with error in log. Also add a custom exclusion containing a space, e.g.,
    "My Folder" – warning must appear in log.

Final checkpoint:
    python ghost_harvest/tests/validate_security.py

WHEN AMBIGUITY ARISES

- The checkpoint command fails with a syntax error → Verify that the fix code
  was copied exactly (indentation, quotes). Re‑apply the fix from SPRINT_FIX.md
  without modification.

- The GUI shows an unexpected error after applying a fix → Check if the fix
  introduced a new import or changed a function signature. Roll back that fix
  and report the conflict.

- A checkpoint requires manual visual verification (Group 2, Group 3) → Run the
  described steps. If any step behaves differently than described, document the
  actual behaviour as an UNTRACKED‑BUG and propose a corrective fix.

- The test suite (final checkpoint) fails after applying all fixes → Compare the
  failure output with the original test expectations. If the failure is due to a
  change in behaviour that was not documented in SPRINT_FIX.md, revert the last
  change and report.

DELIVERABLE

At the end of the sprint, produce:

1. A list of every file modified, created, or deleted (relative to the original
   snapshot).

2. Any UNTRACKED‑BUG entries (if you discovered and fixed additional issues).

3. The output of the final checkpoint command (`python ghost_harvest/tests/validate_security.py`).
   It must show "37 passed · 0 failed".

4. An explicit statement of anything deferred (e.g., a fix that could not be
   applied due to a dependency on an unimplemented stub) – none should remain.

Do not produce any other commentary or analysis. The deliverable is the working
codebase and the required verification output.

================================================================================
```