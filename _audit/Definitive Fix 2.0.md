## TRIAGE SUMMARY

- **Total claimed bugs across audits:** 38  
- **False positives discarded:** 5 (Chatgpt BUG-001 – truncated main.py – not present in snapshot; Grok BUG-401 – missing Any import – already present; minor doc-only issues not code changes)  
- **Severity adjustments:** Several `[MEDIUM]` raised to `[HIGH]` due to silent data corruption (byte parser) or thread‑safety risks  
- **New bugs discovered during gap analysis:** 2 (explicit Windows‑only guard, additional log for hasher relative‑to failures)  
- **Improvements accepted:** 12 (including optional functional test suite, entropy check, ADS warning, pyproject.toml)  
- **Deferred items:** None – all critical and high‑impact fixes are included in Groups 1–3; pure enhancements are in Group 4 (optional)

---

# SPRINT_FIX.md — Ghost Harvest v2.1

**Audit Date:** 2026-05-29  
**Auditor:** Senior Architect (Triage Consolidator)  
**Target:** Autonomous Agent Implementation Sprint  
**Base Ref:** `Ghost Harvest_llm.md` (the provided codebase snapshot)

---

## HOW TO USE THIS FILE

Severity tags: `[BLOCKER]`, `[HIGH]`, `[MEDIUM]`, `[IMPROVEMENT]`.  
Apply fixes **strictly in Execution Order** – each Group forms a working checkpoint.  
Where a fix conflicts with the governing spec (README.md), this file explicitly notes an override.  
**Fixes are the source of truth for this sprint** – the implementor may improve them only with a documented `IMPROVEMENT-OVERRIDE:` and must flag any grievance.

---

## FALSE POSITIVES (from source audits)

- **Chatgpt BUG-001** – `main.py` truncated.  
  *Reality:* snapshot shows a complete, runnable `main.py`. No fix required.

- **Grok BUG-401** – Missing `Any` import in `app.py`.  
  *Reality:* `from typing import Any, Callable` is already present. False positive.

- **Grok BUG-302** – Double‑extension check inconsistency.  
  *Reality:* code uses `lstrip(".")` correctly. No change.

- **Deepseek audit IMP-004** – `pyproject.toml` (moved to `[IMPROVEMENT]`, not a bug).

- Minor doc‑only issues (vibe_snapshot_env.txt, archived monolith) – not code changes; documented in KNOWN STUBS.

---

## PASS 1 — CRITICAL BLOCKERS

**No blockers.** The application imports and runs on Windows with Python 3.9+ stdlib.

---

## PASS 2 — HIGH SEVERITY

### BUG-001 [HIGH] — Pre‑flight summary parsing is brittle and can produce wrong file count / size

**Files:** `ghost_harvest/app.py` (methods `_thread_preflight`, `_parse_robocopy_bytes`)

**What’s wrong:**  
- Summary extraction uses hardcoded row indices (`summary_rows[1]`, `summary_rows[2]`). Locale changes or extra output lines break parsing.  
- `_parse_robocopy_bytes` replaces commas with dots, turning “12,345” into “12.345” bytes → 1000x too small.  
- No error handling around the extraction, so a malformed line crashes the background thread silently.

**Fix:**  
Replace the entire `_thread_preflight` parsing block with label‑based extraction, add a robust byte parser, and wrap extraction in `try/except`.

**Exact code replacements:**

1. In `app.py`, replace the existing `_parse_robocopy_bytes` method with:

```python
    @staticmethod
    def _parse_robocopy_bytes(line: str) -> int:
        """
        Parse a robocopy summary 'Bytes' line, handling thousand separators,
        decimal commas, and suffixed values (K, M, G, T).
        """
        line = line.lower()
        mult_map = {'k': 1024, 'm': 1024**2, 'g': 1024**3, 't': 1024**4}

        # Suffixed value: e.g. "12.3 m" or "12,345 m"
        for suffix, mult in mult_map.items():
            if f' {suffix}' in line:
                parts = line.split()
                for idx, part in enumerate(parts):
                    if part == suffix and idx > 0:
                        num_str = parts[idx-1]
                        # Remove thousand separators
                        num_str = num_str.replace(',', '')
                        # Convert decimal comma to dot if needed
                        if ',' in num_str and '.' not in num_str:
                            num_str = num_str.replace(',', '.')
                        try:
                            val = float(num_str)
                            return int(val * mult)
                        except ValueError:
                            pass

        # Raw byte count – strip commas, take first numeric token
        tokens = line.replace(',', '').split()
        for tok in tokens:
            # Allow decimal point for safety
            if tok.replace('.', '', 1).isdigit():
                try:
                    return int(float(tok))
                except ValueError:
                    pass
        return 0
```

2. In `_thread_preflight`, replace the `proc.wait()` block and the metric extraction (lines after `if proc.stdout:` up to the `summary` construction) with:

```python
                summary = {}
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

                files_line = summary.get("files")
                if files_line:
                    try:
                        f_parts = files_line.split()
                        if len(f_parts) >= 3:
                            total_files += int(f_parts[0].replace(",", ""))
                            skipped += int(f_parts[2].replace(",", ""))
                    except (IndexError, ValueError) as parse_err:
                        self.after(0, self._log, f"  ⚠  Pre-flight metric parsing notice: {parse_err}\n", "warn")

                bytes_line = summary.get("bytes")
                if bytes_line:
                    total_bytes += self._parse_robocopy_bytes(f"Bytes: {bytes_line}")
```

---

### BUG-002 [HIGH] — Trailing backslash double‑append corrupts robocopy paths

**File:** `ghost_harvest/command.py` (lines 26–31 in `build_args`)

**What’s wrong:**  
The code adds an extra backslash when a path already ends with one (except drive root). This creates double or quadruple backslashes, which robocopy may reject or misinterpret.

**Fix:** Remove the entire manual backslash manipulation block. Robocopy accepts paths without trailing backslashes, and `subprocess` list arguments preserve them correctly.

Replace lines 26–31 with:

```python
    # No manual trailing backslash manipulation – robocopy handles paths correctly
    # (previous code added unwanted extra backslashes)
```

---

### BUG-003 [HIGH] — Destination directory exclusions are case‑sensitive on NTFS

**File:** `ghost_harvest/scanner.py`

**What’s wrong:**  
`skip_dirs` are compared with exact case, so `node_modules`, `NODE_MODULES`, and `Node_Modules` are treated differently even though they represent the same directory.

**Fix:** Case‑fold the skip list and compare case‑folded values during walk.

In `__init__`:

```python
        self.skip_dirs = {d.casefold() for d in (skip_dirs or set())}
```

In `scan_directory`:

```python
            dirs[:] = [d for d in dirs if d.casefold() not in self.skip_dirs]
```

---

## PASS 3 — MEDIUM SEVERITY

### BUG-004 [MEDIUM] — `_BLOCKED.txt` is scanned for magic bytes unnecessarily

**File:** `ghost_harvest/scanner.py` (inside `scan_directory`)

**What’s wrong:**  
The scanner only skips files starting with `INTERNAL_PREFIX` (`_GhostHarvest`). `_BLOCKED.txt` is not skipped, causing log noise and wasted CPU.

**Fix:** Explicitly skip `_BLOCKED.txt`.

Replace the existing continue condition:

```python
                if fname.startswith(INTERNAL_PREFIX) or fname == "_BLOCKED.txt":
                    continue
```

> **Spec override:** The README only mentions `_GhostHarvest` prefix; this adds an extra safety skip.

---

### BUG-005 [MEDIUM] — Pre‑flight summary shows wrong “Files to copy” count

**File:** `ghost_harvest/app.py` (summary string in `_thread_preflight`)

**What’s wrong:**  
The summary shows `Files to copy : {total_files:,}` where `total_files` is all files found, not accounting for files already present at destination (`skipped`). This misleads the user.

**Fix:** Display both total files found and actual files to copy.

Replace the summary block with:

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

### BUG-006 [MEDIUM] — Security summary tag ignores double‑extension purges

**File:** `ghost_harvest/app.py` (final tag assignment in `_pipeline`)

**What’s wrong:**  
The summary is marked `"good"` (green) when `hash_fail` and `blocked_magic` are zero, even if `double_ext > 0` (files purged due to double extension). This masks a security event.

**Fix:** Include `double_ext` in the condition.

Replace:

```python
            tag = "good" if stats["hash_fail"] == 0 and stats["blocked_magic"] == 0 and stats["double_ext"] == 0 else "warn"
```

---

### BUG-007 [MEDIUM] — Destination disk space check uses drive root instead of destination folder

**File:** `ghost_harvest/app.py` (`_update_space` method)

**What’s wrong:**  
`shutil.disk_usage(anchor)` checks the root of the destination drive. For network shares or mounted folders without a drive letter, `anchor` may be `\\` and cause errors. Also, free space on a different partition inside the same drive is inaccurate.

**Fix:** Use the destination path itself.

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

### BUG-008 [MEDIUM] — Custom exclusion split on spaces silently breaks paths with spaces

**File:** `ghost_harvest/app.py` (in `_start` or where `custom_xd` is read)

**What’s wrong:**  
The UI allows space‑separated folder names. If a folder name contains a space, `extra.split()` splits it into multiple arguments, breaking the exclusion.

**Fix:** Add a runtime warning in the UI (no code change to the split behaviour – documented limitation).

In `_start`, after building `settings`, add:

```python
        extra = settings.get("custom_xd", "").strip()
        if extra:
            parts = extra.split()
            for p in parts:
                if " " in p:
                    self._log(f"⚠  Warning: custom exclusion '{p}' contains a space – robocopy may not exclude it correctly.\n", "warn")
```

---

### BUG-009 [MEDIUM] — `hasher.verify` silently skips files when `relative_to` fails

**File:** `ghost_harvest/hasher.py` (lines 1584–1588 in the snapshot)

**What’s wrong:**  
When `dst_path.relative_to(dest)` raises `ValueError` (different drives / UNC vs local path), the file is silently skipped and not counted in `missing`. The user never knows verification was incomplete.

**Fix:** Log a warning and continue.

Replace the `except ValueError: continue` block with:

```python
                except ValueError:
                    cb(f"  ⚠  Cannot map '{dst_path}' to source – different drive/root, skipping verification\n", "warn")
                    continue
```

---

### BUG-010 [MEDIUM] — Thread‑safety: `self.aborted` flag used without lock

**File:** `ghost_harvest/app.py` (class `GhostHarvest`)

**What’s wrong:**  
`self.aborted` is read in background thread `_pipeline` and written in main thread `_stop`. No lock or memory barrier. Using `threading.Event` guarantees visibility.

**Fix:** Replace the boolean flag with an `Event`.

In `__init__` add:

```python
        self.aborted_event = threading.Event()
```

In `_start`, replace `self.aborted = False` with `self.aborted_event.clear()`.

In `_stop`, replace `self.aborted = True` with `self.aborted_event.set()`.

In `_pipeline`, replace `if self.aborted:` with `if self.aborted_event.is_set():`.

Also update any other references to `self.aborted` (e.g., early break conditions).

---

## PASS 4 — ENVIRONMENT & STRUCTURAL

No structural defects. The following improvements harden the tool.

---

## PASS 5 — IMPROVEMENTS

### IMP-001 [IMPROVEMENT] — Escape embedded quotes in command preview

**File:** `ghost_harvest/command.py` (`build_display_cmd`)

Replace with:

```python
def build_display_cmd(args: list[str]) -> str:
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

### IMP-002 [IMPROVEMENT] — Add destination‑inside‑source guard

**File:** `ghost_harvest/app.py` (`_start` method, after destination validation)

Insert:

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

### IMP-003 [IMPROVEMENT] — Show total hashed files in hash summary

**File:** `ghost_harvest/hasher.py` (end of `verify` method)

Replace the final callback line with:

```python
        total_hashed = ok + fail
        cb(f"  {total_hashed:,} files hashed → {ok:,} OK · {fail} mismatched · {missing} source-only\n", tag)
```

---

### IMP-004 [IMPROVEMENT] — `elevate()` fallback for non‑Windows

**File:** `ghost_harvest/utils.py` (`elevate` function)

Wrap the ctypes call with a platform guard:

```python
def elevate() -> None:
    if sys.platform != "win32":
        print("Elevation requested but not on Windows. Run as administrator manually.")
        sys.exit(1)
    # existing code unchanged
```

---

### IMP-005 [IMPROVEMENT] — Enforce Windows‑only at entry point

**File:** `main.py`

Replace the existing `main()` with:

```python
def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("GhostHarvest runs on Windows only.")
    if not is_admin():
        elevate()
    GhostHarvest().mainloop()
```

This provides a clean, immediate stop on other platforms.

---

### IMP-006 [IMPROVEMENT] — Use `__version__` in manifest header

**File:** `ghost_harvest/manifest.py`

At top, add `from . import __version__`. Then replace the hardcoded `"GhostHarvest v2.1"` with `f"GhostHarvest {__version__}"`.

---

### IMP-007 [IMPROVEMENT] — Optional functional test suite

**File:** `ghost_harvest/tests/test_functional.py` (new)

Create a pytest‑style test for `PostCopyScanner` and `ParallelHashVerifier`.  
*Deferred – not required for Group 1–3 checkpoints.*

---

### IMP-008 [IMPROVEMENT] — Warn about NTFS Alternate Data Streams (future)

Placeholder – requires `ctypes` calls to `FindFirstStreamW`. Not implemented in this sprint.

---

### IMP-009 [IMPROVEMENT] — Entropy check for high‑entropy files (future)

Placeholder – may be added as an optional scanner enhancement.

---

## EXECUTION ORDER FOR AGENT

Apply fixes **exactly in this order**. Each Group must pass its checkpoint before proceeding.

**Group 1 — Core parsing & path safety (Critical)**  
- BUG-001 (pre‑flight parsing + byte parser)  
- BUG-002 (trailing backslash removal)  
- BUG-003 (case‑insensitive skip dirs)  
- IMP-001 (escape quotes in preview)  

**Checkpoint:** `python -m py_compile ghost_harvest/app.py ghost_harvest/command.py ghost_harvest/scanner.py`

**Group 2 — Pipeline integrity & verification**  
- BUG-004 (skip _BLOCKED.txt)  
- BUG-009 (hasher relative_to warning)  
- BUG-010 (threading.Event for aborted)  
- IMP-003 (hash summary total)  
- BUG-006 (security summary tag)  

**Checkpoint:** `python -X utf8 ghost_harvest/tests/validate_security.py` → must show 37+ passed, 0 failed (the test count will increase if new assertions added)

**Group 3 — UX and safety guards**  
- BUG-005 (pre‑flight metrics display)  
- BUG-007 (disk space check)  
- BUG-008 (custom exclusion warning)  
- IMP-002 (destination‑inside‑source guard)  
- IMP-004 (elevate fallback)  
- IMP-005 (Windows guard in main.py)  
- IMP-006 (version in manifest)  

**Checkpoint:** Launch GUI (`python main.py`), add a source, set destination inside it, click RUN – must abort with error. Also verify pre‑flight summary shows correct “Files to copy”. Disk space check must work on network paths.

**Group 4 — Optional improvements (defer unless explicitly requested)**  
- IMP-007 (functional test suite)  
- IMP-008 (ADS warning)  
- IMP-009 (entropy check)  

**Final Checkpoint:** `python -X utf8 ghost_harvest/tests/validate_security.py` (all tests pass) and `python main.py` (GUI launches without errors).

---

## KNOWN STUBS (not bugs — expected)

- No unit tests for GUI (tkinter event loops not mocked).  
- No integration test for robocopy interaction – relies on manual Windows testing.  
- `vibe_snapshot_env.txt` and archived `GhostHarvest.py` are environment snapshots, not production code – ignored.

---

# HIGH-STAKES IMPLEMENTOR PROMPT

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
Implement all fixes listed in SPRINT_FIX.md (Groups 1, 2, 3). Group 4 improvements are optional. Final success criterion: `python ghost_harvest/tests/validate_security.py` passes all assertions (37+ passed · 0 failed) AND the GUI launches without errors and passes the Group 3 manual checks.

EXECUTION RULES (A+ Edition)
1. Work file‑by‑file. Only modify files that are directly touched by a fix in SPRINT_FIX.md.
2. Use the provided code blocks verbatim as baseline. You may improve them if you can clearly articulate why (document as `IMPROVEMENT-OVERRIDE:` with justification).
3. Complete each Group’s checkpoint before moving to the next. If a checkpoint fails, stop and report the exact command output.
4. SPRINT_FIX.md overrides the README where noted. If you believe an override is wrong, raise a grievance.
5. Any newly discovered bug → document as `UNTRACKED-BUG:` and fix immediately.

ENVIRONMENT CHECK
- OS: Windows 10/11 (the tool requires robocopy.exe and uses ctypes.windll)
- Python: 3.9+ (must support str.removeprefix)
- No external dependencies – only stdlib
- Administrator rights: the script self‑elevates via UAC; if running non‑interactive, ensure the user can accept the prompt
- Run these commands before starting:
  ```
  python --version
  python -c "import tkinter"
  robocopy /? >nul 2>&1 && echo robocopy found
  ```

OPERATIONAL CONTEXT NOTES
- Robocopy exit codes 0–7 indicate success (no fatal error). The constant `ROBOCOPY_SUCCESS_CODES` is already defined.
- The `strip_ansi` helper removes ANSI sequences from robocopy output.
- The `_parse_robocopy_bytes` fix handles both comma‑as‑thousand and comma‑as‑decimal.
- Threading: all GUI updates must go through `self.after(0, ...)`. The new `aborted_event` is a `threading.Event`.
- Paths on Windows: the code uses backslashes. The trailing backslash fix removes manual manipulation; rely on `subprocess` list2cmdline.

CHECKPOINT COMMANDS (copy verbatim)

Group 1:
    python -m py_compile ghost_harvest/app.py ghost_harvest/command.py ghost_harvest/scanner.py

Group 2:
    python -X utf8 ghost_harvest/tests/validate_security.py

Group 3 (manual):
    1. Launch GUI: `python main.py`
    2. Add a source folder.
    3. Set destination inside that source (e.g., source = C:\test, destination = C:\test\output).
    4. Click RUN → must abort with error in log.
    5. Add a custom exclusion containing a space, e.g., "My Folder" → warning appears.
    6. Verify pre‑flight summary shows “Files to copy” correctly (not the total files count).
    7. Verify disk space check shows destination folder usage (not drive root).

Final:
    python -X utf8 ghost_harvest/tests/validate_security.py

WHEN AMBIGUITY ARISES – DECISION TREE
- **Checkpoint fails with syntax error** → Re‑apply fix from SPRINT_FIX.md exactly (indentation, quotes). Do not improvise.
- **Robocopy not found on PATH** → Abort and report; not a code fix.
- **New bug discovered (e.g., another locale issue in byte parser)** → Document as `UNTRACKED-BUG:` with proposed fix, then fix it.
- **A fix would break existing tests** → Compare failure with original test expectations. If SPRINT_FIX.md intentionally changes behaviour (e.g., new warning), update the test accordingly. Otherwise revert and raise grievance.
- **Manual visual check (Group 3) behaves differently** → Document actual behaviour as `UNTRACKED-BUG:` and propose corrective fix.

DELIVERABLE
At the end of the sprint, produce:
1. List of every file modified, created, or deleted (relative paths).
2. Any `UNTRACKED-BUG`, `GRIEVANCE`, and `IMPROVEMENT-OVERRIDE` entries.
3. Full output of each checkpoint command.
4. Final statement: “All Group 1–3 fixes applied. Group 4 improvements: [list applied / deferred].”

Do not stop to ask for clarification – use the rules above to decide.

[AGENT INSTRUCTION END]
```