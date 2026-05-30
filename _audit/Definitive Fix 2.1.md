## Triage Summary

**Total claimed bugs across 5 audits:** 31  
**False positives discarded:** 5  
- main.py truncation (Chatgpt BUG-001) – code is complete  
- Missing `Any` import (Grok BUG-401) – already present  
- Double‑extension inconsistency (Grok BUG-302) – no code change needed  
- vibe_snapshot_env.txt documentation (Grok BUG-402) – not a code issue  
- Bare except in tests (implied by Deepseek) – not found  

**Severity adjustments:**  
- Several `[HIGH]` claims lowered to `[MEDIUM]` (pre‑flight parsing, backslash bug) – they cause incorrect estimates or tool errors, not data loss or security bypass.  
- Gemini BUG-003 (`[LOW]`) kept as `[MEDIUM]` because it masks threat indicators.  

**New bugs discovered in gap analysis:** none – all critical blind spots were covered by the audits.

**Deferred items (out of sprint scope):**  
- Functional test suite (IMP‑006) – requires pytest and mocking  
- ADS warning (IMP‑003 from short audit) – needs `win32file` or ctypes  
- Entropy check (IMP‑501) – nice but not required  
- pyproject.toml (IMP‑004) – optional  

**Valid bugs to fix:** 12 (BUG-001 to BUG-012)  
**Improvements to implement:** 6 (IMP-001 to IMP-006, with IMP-006 deferred)

---

## SPRINT_FIX.md

```markdown
# SPRINT_FIX.md – Ghost Harvest v2.1 (Definitive)

**Audit Date:** 2026-05-29  
**Triage by:** Senior Architect (consolidated from 5 audits + gap analysis)  
**Target:** Autonomous Agent Implementation Sprint  
**Base Ref:** `Ghost Harvest_llm.md` (codebase snapshot) + README

---

## FALSE POSITIVES (from source audits)

- **BUG-001 (Chatgpt)** – `main.py` truncated  
  *Reality:* The snapshot shows a complete `if __name__ == "__main__": main()`. No change required.

- **BUG-401 (Grok)** – Missing `Any` import in `app.py`  
  *Reality:* `from typing import Any, Callable` is already present.

- **BUG-302 (Grok)** – Double‑extension inconsistency  
  *Reality:* `has_double_extension` correctly uses `lstrip(".")`. No code change needed.

- **BUG-402 (Grok)** – `vibe_snapshot_env.txt` and archived file cause confusion  
  *Reality:* Not a code bug. Ignore for this sprint.

- **Bare‑except claims (Deepseek)** – No bare `except:` found in current codebase.

---

## PASS 1 — CRITICAL BLOCKERS

None.

---

## PASS 2 — HIGH SEVERITY

No remaining `[HIGH]` issues after triage (all originally claimed high were MEDIUM).

---

## PASS 3 — MEDIUM SEVERITY (REAL BUGS)

### BUG-001 [MEDIUM] — Trailing backslash double‑append in `build_args`
**File:** `ghost_harvest/command.py`  
**What's wrong:** Manual backslash addition when path already ends with `\` produces `\\` (double backslash). Robocopy may still work but it's unintended and can break relative path resolution or log file naming.

**Fix:** Replace the block (lines 29–35) with:

```python
    # Normalize paths: ensure exactly one trailing backslash for directories,
    # but avoid double backslashes. Drive roots (C:\) keep their backslash.
    source = source.rstrip('\\')
    if not source.endswith(':\\') and source:
        source += '\\'
    dest = dest.rstrip('\\')
    if not dest.endswith(':\\') and dest:
        dest += '\\'
```

---

### BUG-002 [MEDIUM] — Case‑sensitive skip directory matching in post‑copy scanner
**File:** `ghost_harvest/scanner.py`  
**What's wrong:** `os.walk` directory names are compared case‑sensitively against `self.skip_dirs`. On NTFS, `node_modules` and `Node_Modules` are the same logical directory, but only the exact‑case variant is skipped.

**Fix:** In `__init__`, convert skip dirs to case‑folded set. Then compare using `casefold()` during traversal.

**`__init__` replacement:**

```python
    def __init__(
        self,
        blocked_exts: set[str],
        skip_dirs: set[str] | None = None,
        zip_doc_exts: set[str] | None = None,
        ole_doc_exts: set[str] | None = None,
        scan_plain: bool = True,
    ) -> None:
        self.blocked_exts = blocked_exts
        self.skip_dirs = {d.casefold() for d in (skip_dirs or set())}
        self.zip_doc_exts = zip_doc_exts or ZIP_DOC_EXTS
        self.ole_doc_exts = ole_doc_exts or OLE_DOC_EXTS
        self.scan_plain = scan_plain
```

**In `scan_directory`, change the filter line to:**

```python
            dirs[:] = [d for d in dirs if d.casefold() not in self.skip_dirs]
```

---

### BUG-003 [MEDIUM] — Pre‑flight summary parsing depends on row position
**File:** `ghost_harvest/app.py` (method `_thread_preflight`)  
**What's wrong:** The code assumes `summary_rows[1]` is the `Files` row and `summary_rows[2]` is the `Bytes` row. Robocopy output can vary by locale or flags.

**Fix:** Parse by label instead of position. Replace the entire `summary_rows` collection and extraction block.

**Replace the block starting after `proc = subprocess.Popen(...)` and ending before `proc.wait()` with:**

```python
                summary: dict[str, str] = {}
                if proc.stdout:
                    for line in proc.stdout:
                        clean_line = strip_ansi(line)
                        self.after(0, self._log, clean_line)
                        if ":" not in clean_line:
                            continue
                        label, payload = clean_line.split(":", 1)
                        key = label.strip().lower()
                        if key in {"dirs", "files", "bytes"}:
                            summary[key] = payload.strip()
                proc.wait()

                # Safely extract metrics
                files_line = summary.get("files")
                if files_line:
                    parts = files_line.split()
                    if len(parts) >= 3:
                        try:
                            total_files += int(parts[0].replace(",", ""))
                            skipped += int(parts[2].replace(",", ""))
                        except (ValueError, IndexError):
                            self.after(0, self._log, "  ⚠  Could not parse file counts from robocopy output.\n", "warn")

                bytes_line = summary.get("bytes")
                if bytes_line:
                    total_bytes += self._parse_robocopy_bytes(f"Bytes: {bytes_line}")
```

---

### BUG-004 [MEDIUM] — Pre‑flight byte parser mishandles thousand separators
**File:** `ghost_harvest/app.py` (method `_parse_robocopy_bytes`)  
**What's wrong:** `replace(",", ".")` turns `"1,234"` into `"1.234"`, causing misinterpretation. Also raw comma‑separated integers fail.

**Fix:** Replace the entire method with a robust parser.

**New `_parse_robocopy_bytes`:**

```python
    @staticmethod
    def _parse_robocopy_bytes(line: str) -> int:
        """
        Parse a robocopy summary 'Bytes' line, handling thousand separators,
        decimal commas, and suffixed multipliers (k, m, g, t).
        """
        line = line.lower()
        mult_map = {'k': 1024, 'm': 1024 ** 2, 'g': 1024 ** 3, 't': 1024 ** 4}
        # Look for suffixed value
        for suffix, mult in mult_map.items():
            if f' {suffix}' in line:
                parts = line.split()
                for idx, part in enumerate(parts):
                    if part == suffix and idx > 0:
                        raw_num = parts[idx - 1].replace(',', '')
                        # Convert decimal comma to dot if needed
                        if ',' in raw_num and '.' not in raw_num:
                            raw_num = raw_num.replace(',', '.')
                        try:
                            val = float(raw_num)
                            return int(val * mult)
                        except ValueError:
                            pass
        # Fallback: raw byte count without suffix – remove all commas and take first numeric token
        tokens = line.replace(',', '').split()
        for tok in tokens:
            # Allow one dot for potential decimal (though raw bytes should be integer)
            clean_tok = ''.join(ch for ch in tok if ch.isdigit() or ch == '.')
            if clean_tok:
                try:
                    return int(float(clean_tok))
                except ValueError:
                    pass
        return 0
```

---

### BUG-005 [MEDIUM] — `_BLOCKED.txt` is scanned for magic bytes unnecessarily
**File:** `ghost_harvest/scanner.py`  
**What's wrong:** The scanner skips only files starting with `_GhostHarvest`. `_BLOCKED.txt` is written by the tool and may be scanned, adding log noise.

**Fix:** Add `_BLOCKED.txt` to the skip condition.

In `scan_directory`, replace:

```python
                if fname.startswith(INTERNAL_PREFIX):
                    continue
```

with:

```python
                if fname.startswith(INTERNAL_PREFIX) or fname == "_BLOCKED.txt":
                    continue
```

> **Spec override:** The README only mentions `_GhostHarvest`. This change is a safety enhancement.

---

### BUG-006 [MEDIUM] — Custom XD split on spaces breaks folders with spaces (warning)
**File:** `ghost_harvest/app.py` (pipeline and pre‑flight)  
**What's wrong:** `custom_xd.get().strip().split()` splits on spaces, so a folder named `My Documents` becomes two separate exclusion patterns. Robocopy will not exclude the intended folder.

**Fix (warning only – full fix would require quoting changes not feasible with robocopy’s `/XD`):** Add a runtime warning when any custom exclusion contains a space.

In `_current_args` and `_thread_preflight` (where `custom_xd` is used), add after splitting:

```python
extra = custom_xd.strip()
if extra:
    parts = extra.split()
    for p in parts:
        if " " in p:
            self._log(f"⚠  Warning: custom exclusion '{p}' contains a space – robocopy may not exclude it correctly.\n", "warn")
    xd.extend(parts)
```

Apply this in both `_current_args` and `_thread_preflight` where `build_args` is called.

---

### BUG-007 [MEDIUM] — Disk space check uses root anchor, not destination folder
**File:** `ghost_harvest/app.py` (method `_update_space`)  
**What's wrong:** `shutil.disk_usage(anchor)` uses the drive root. For network shares or mounted volumes without a drive letter, this fails or shows wrong info.

**Fix:** Use the destination path directly.

Replace the `try` block with:

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

### BUG-008 [MEDIUM] — Pre‑flight “Files to copy” includes files that will be skipped
**File:** `ghost_harvest/app.py` (method `_thread_preflight`, summary output)  
**What's wrong:** The summary shows `Files to copy : {total_files:,}` but `total_files` includes files already present at destination (will be skipped by robocopy).

**Fix:** Change the summary labels to clarify.

Replace the summary string block with:

```python
        summary = (
            f"\n{'─' * 52}\n"
            f"  PRE-FLIGHT SUMMARY\n"
            f"{'─' * 52}\n"
            f"  Folders queued   :  {len(settings['queue'])}\n"
            f"  Total files found:  {total_files:,}\n"
            f"  Files to copy    :  {max(0, total_files - skipped):,}\n"
            f"  Estimated size   :  {size_str}\n"
            f"  Already at dest  :  {skipped:,}  (will be skipped)\n"
            f"{'─' * 52}\n\n"
        )
```

---

### BUG-009 [MEDIUM] — Security summary tag ignores double‑extension purges
**File:** `ghost_harvest/app.py` (pipeline, final summary)  
**What's wrong:** The summary tag is `"good"` if `hash_fail == 0` and `blocked_magic == 0`, even when `double_ext > 0` (malicious files were purged).

**Fix:** Include `double_ext` in the condition.

Replace:

```python
            tag = "good" if stats["hash_fail"] == 0 and stats["blocked_magic"] == 0 else "warn"
```

with:

```python
            tag = "good" if stats["hash_fail"] == 0 and stats["blocked_magic"] == 0 and stats["double_ext"] == 0 else "warn"
```

---

### BUG-010 [MEDIUM] — Thread safety: `aborted` flag accessed without lock
**File:** `ghost_harvest/app.py`  
**What's wrong:** `self.aborted` is written by main thread and read by background pipeline thread with no synchronisation. Rare race may cause missed stop.

**Fix:** Use `threading.Event`.

In `__init__`:
```python
        self.abort_event = threading.Event()
        # remove self.aborted = False
```

In `_start`: replace `self.aborted = False` with `self.abort_event.clear()`

In `_stop`: replace `self.aborted = True` with `self.abort_event.set()`

In `_pipeline`: replace `if self.aborted:` with `if self.abort_event.is_set():`

Also add `import threading` at top of `app.py` if not already present (it is already imported).

---

### BUG-011 [MEDIUM] — Hash verifier silently skips files when `relative_to` fails
**File:** `ghost_harvest/hasher.py` (method `verify`)  
**What's wrong:** When `dst_path.relative_to(dest)` raises `ValueError` (e.g., cross‑drive copies), the file is skipped without any log entry, leading to incomplete verification without indication.

**Fix:** Add a callback log for each skipped file.

Replace the `try/except` block inside the `os.walk` loop with:

```python
                try:
                    rel = dst_path.relative_to(dest)
                    src_path = Path(src) / rel
                except ValueError:
                    if callback:
                        callback(f"  ⚠  Cannot map destination file to source (different root): {dst_path}\n", "warn")
                    missing += 1
                    continue
```

---

### BUG-012 [IMPROVEMENT] — Escape embedded quotes in GUI command preview
**File:** `ghost_harvest/command.py` (function `build_display_cmd`)  
**What's wrong:** Arguments containing `"` are not escaped, breaking the preview display (actual subprocess call remains safe because it uses list arguments).

**Fix:** Escape double quotes before wrapping.

Replace `build_display_cmd` with:

```python
def build_display_cmd(args: list[str]) -> str:
    """
    Convert an argument list into a human-readable command string
    for the GUI preview text box.

    Quotes any argument containing spaces or double quotes,
    and escapes embedded double quotes.
    """
    parts: list[str] = []
    for a in args:
        if '"' in a:
            a = a.replace('"', r'"')
        if " " in a or '"' in a:
            parts.append(f'"{a}"')
        else:
            parts.append(a)
    return "  ".join(parts)
```

---

## PASS 4 — ENVIRONMENT & STRUCTURAL

No structural issues.

---

## PASS 5 — IMPROVEMENTS (apply after all bugs)

### IMP-001 [IMPROVEMENT] — Destination‑inside‑source guard
**File:** `ghost_harvest/app.py` (method `_start`)  
**Fix:** After validating destination, before starting pipeline:

```python
        dest_path = Path(dest).resolve()
        for src in settings["queue"]:
            src_path = Path(src).resolve()
            if dest_path in src_path.parents or dest_path == src_path:
                self._log(f"⚠  Destination '{dest}' is inside source '{src}' – would cause infinite recursion. Aborted.\n", "bad")
                self._finish()
                return
```

---

### IMP-002 [IMPROVEMENT] — Hash verifier reports total files hashed
**File:** `ghost_harvest/hasher.py` (end of `verify` method)  
**Fix:** Change the final callback to:

```python
        total_hashed = ok + fail
        cb(
            f"  {total_hashed:,} files hashed → {ok:,} OK · {fail} mismatched · "
            f"{missing} source-only\n",
            tag,
        )
```

---

### IMP-003 [IMPROVEMENT] — `elevate()` fallback for non‑Windows
**File:** `ghost_harvest/utils.py`  
**Fix:** Add platform guard at the start of `elevate()`:

```python
def elevate() -> None:
    if sys.platform != "win32":
        print("Elevation requested but not on Windows. Run as administrator manually.")
        sys.exit(1)
    # … existing code …
```

---

### IMP-004 [IMPROVEMENT] — Import `__version__` in manifest (optional)
**File:** `ghost_harvest/manifest.py`  
**Fix:** At top add `from . import __version__`. Then change `"GhostHarvest v2.1"` to `f"GhostHarvest {__version__}"`.

---

### IMP-005 [IMPROVEMENT] — Functional test suite (deferred)
Out of sprint scope. Requires `pytest` and mocking.

---

## EXECUTION ORDER FOR AGENT

Apply **Groups in order**. Each checkpoint must pass before moving to next.

**Group 1 – Core path & scanner fixes**  
- BUG-001 (trailing backslash)  
- BUG-002 (case‑fold skip_dirs)  
- BUG-005 (skip _BLOCKED.txt)  
- BUG-007 (disk space check)  

**Checkpoint:** `python -c "from ghost_harvest.command import build_args; print(build_args('C:\\Windows\\', 'D:\\dest\\'))"`  
Expected output: arguments with single backslashes (no double).

---

**Group 2 – Pre‑flight & summary correctness**  
- BUG-003 (label‑based parsing)  
- BUG-004 (byte parser)  
- BUG-008 (summary labels)  
- BUG-009 (tag includes double_ext)  

**Checkpoint:** Run `python -X utf8 ghost_harvest\tests\validate_security.py` – must pass all tests (original 37 + new assertions from BUG-004 if added). We will add a test for `_parse_robocopy_bytes` inside `validate_security.py` (see below).

---

**Group 3 – Thread safety, logging, UI warnings**  
- BUG-006 (custom XD space warning)  
- BUG-010 (abort_event)  
- BUG-011 (hasher skip logging)  
- BUG-012 (escape quotes preview)  

**Checkpoint:** `python main.py` – GUI launches without errors. Manually test: add a source, set destination, add a custom exclusion containing a space, click Refresh – warning appears in log.

---

**Group 4 – Improvements**  
- IMP-001 (destination‑inside‑source guard)  
- IMP-002 (hash total reported)  
- IMP-003 (elevate fallback)  
- IMP-004 (manifest version)  

**Final checkpoint:** `python ghost_harvest/tests/validate_security.py` – all tests pass (including new test for byte parser). Then `python main.py` – GUI works, and pipeline runs without crashes.

---

## ADDITIONAL TEST FOR `validate_security.py`

Insert this block after existing tests and before the summary:

```python
# Test _parse_robocopy_bytes (BUG-004)
print("\n[BUG-004] Pre-flight size parser")
from ghost_harvest.app import GhostHarvest
parse = GhostHarvest._parse_robocopy_bytes
assert parse("Bytes : 12,345,678") == 12345678
assert parse("Bytes : 12,345,678 m") == 12345678 * 1024**2
assert parse("Bytes : 12,345.6 k") == int(12345.6 * 1024)
assert parse("Bytes : 12,3 m") == int(12.3 * 1024**2)
assert parse("Bytes : 12345678") == 12345678
print("  ✅  _parse_robocopy_bytes works for all formats")
```

After adding, the expected final count becomes **38 passed**.

---

## KNOWN STUBS (not bugs)

- No functional test suite (IMP-005 deferred)
- ADS warning not implemented
- Entropy check not implemented
- `pyproject.toml` not added

All core functionality is present and will be fixed per above.
```

---

## High‑Stakes Implementor Prompt

```text
[AGENT INSTRUCTION START – HIGH STAKES]

READ FIRST, CODE SECOND
You are expected to operate at A+ senior-engineer level. This is not routine work. You have deep operational context — use it. Be proactive, skeptical, and intelligent. If a fix would cause real-world problems (platform differences, environment quirks, performance regression, security degradation), you must raise a grievance before applying it.

GRIEVANCE RIGHTS
You are not only permitted but required to voice grievances when a fix in SPRINT_FIX.md is:
- Unsafe, incomplete, or introduces new risks
- Violates the governing spec without explicit override
- Degrades performance or reliability significantly
- Contradicts known operational reality

Format: `GRIEVANCE: [BUG-ID] — [file] — [issue] — [recommendation]`

OBJECTIVE
Apply all fixes and improvements listed in SPRINT_FIX.md (Groups 1–4). The sprint succeeds when:
- `python ghost_harvest/tests/validate_security.py` shows `38 passed · 0 failed`
- `python main.py` launches the GUI and a dry‑run migration completes without crashes or incorrect robocopy arguments.

EXECUTION RULES (A+ Edition)
1. Work file-by-file. Never touch files unrelated to fixes.
2. Use SPRINT_FIX.md fixes as baseline. You may improve them if you can clearly articulate why (document as `IMPROVEMENT-OVERRIDE:`).
3. Complete each Group’s checkpoint before moving to the next.
4. SPRINT_FIX.md overrides spec where noted. If you believe an override is wrong, raise grievance.
5. Any newly discovered bug → document as `UNTRACKED-BUG:` and fix immediately.

ENVIRONMENT CHECK
- OS: Windows 10/11 (the tool uses `robocopy` and `ctypes.windll`).  
- Python: 3.9+ (code uses `str.removeprefix`).  
- No external dependencies – do not install any packages.  
- `robocopy` must be on PATH (Windows built‑in).  
- Administrator rights are auto‑requested via UAC.  

Run these commands before starting:
```
python --version
python -c "import tkinter; print('tkinter OK')"
robocopy /? >nul 2>&1 && echo robocopy OK
```

OPERATIONAL CONTEXT NOTES
- The test suite `validate_security.py` must run from the project root directory (where `main.py` resides). It adds `"."` to `sys.path`.
- `_parse_robocopy_bytes` is a static method; tests that instantiate `GhostHarvest` to call it will work because the class exists.
- When applying BUG-003, ensure the new `summary` dictionary parsing does not break the existing logic for `_parse_robocopy_bytes` call (the line `total_bytes += self._parse_robocopy_bytes(f"Bytes: {bytes_line}")` is safe).
- For BUG-006 (custom XD space warning), you must add the warning logic in both `_current_args` (used for preview and pre‑flight) AND in `_pipeline` (where `custom_xd` is read again). The fix description says “in `_current_args` and `_thread_preflight`” – but `_thread_preflight` calls `_current_args`, so adding it once inside `_current_args` is sufficient. However, the pipeline also reads `custom_xd` directly. Add the warning in `_pipeline` right before calling `build_args`.
- BUG-010 (abort_event): Make sure to remove the old `self.aborted` attribute entirely to avoid confusion.
- BUG-011 (hasher logging): The callback may be `None`; check `if callback:` before calling.

CHECKPOINT COMMANDS
- **Group 1 checkpoint:** `python -c "from ghost_harvest.command import build_args; print(build_args('C:\\Windows\\', 'D:\\dest\\'))"`
- **Group 2 checkpoint:** `python -X utf8 ghost_harvest\tests\validate_security.py`
- **Group 3 checkpoint:** `python main.py` (manual visual verification)
- **Group 4 (final):** `python ghost_harvest/tests/validate_security.py` and then `python main.py`

WHEN AMBIGUITY ARISES – DECISION TREE
1. **`_parse_robocopy_bytes` test fails after replacement** → The regex/parsing may not cover a locale variation. Add a new test case and adjust parser accordingly, documenting the change as `IMPROVEMENT-OVERRIDE`.
2. **`build_args` still produces double backslashes** → Ensure the `rstrip` logic correctly handles drive roots (e.g., `C:\\`). The condition `if not source.endswith(':\\') and source:` prevents adding a backslash to `C:` alone.
3. **Robocopy fails with “invalid parameter” after BUG-001** → The fix might have removed a necessary trailing backslash. Revert and raise grievance.
4. **`threading.Event` causes `AttributeError`** → Forgot to import `threading`. Add import.
5. **Custom XD warning appears multiple times per run** → Acceptable; it’s a warning, not an error.
6. **Test suite fails with `ModuleNotFoundError: No module named 'ghost_harvest'`** → Run from project root, or set `PYTHONPATH=.`.
7. **Destination‑inside‑source guard falsely triggers on UNC paths** → Use `resolve()` which normalises UNC; if still wrong, raise grievance.

DELIVERABLE
- List of every file modified, created, or deleted (with paths).
- All `UNTRACKED-BUG`, `GRIEVANCE`, and `IMPROVEMENT-OVERRIDE` entries.
- The exact output of every checkpoint command.
- Final statement: “All Group 1–4 fixes applied. Group 5 improvements (IMP-005) deferred.”

[AGENT INSTRUCTION END]
```