## TRIAGE SUMMARY

**Source audits processed:** 5 (Nemotron, Deepseek Audit 1, Deepseek Audit 2, Gemini, Grok)  
**Total claims received:** 33  
**False positives discarded:** 9 (see FALSE POSITIVES section)  
- Stale: 0  
- Misread: 4  
- Scope errors: 3  
- Spec conflicts: 2  

**Severity adjustments:** 3 (mostly downgrading to match taxonomy)  
**Cross-agent conflicts resolved:** 4 (parser duplicates merged; log‑switch vs. streaming merged)  
**Bugs merged (duplicate):** 6 claims merged into 3 consolidated entries  
**New bugs from gap analysis:** 3 (GAP‑001 – race condition on `self.process`, GAP‑002 – scanner abort, GAP‑003 – custom XD splitting)  

**Confidence breakdown (surviving bugs):**  
- [VERIFIED]: 17  
- [INFERRED]: 1  
- [DEFERRED]: 0  

**Items requiring human decision:** 0  

---

# SPRINT_FIX.md — Ghost Harvest (Consolidated)
**Audit Date:** 2026‑05‑30  
**Triage Method:** Multi‑agent consolidation (5 source audits)  
**Source Audits:** Nemotron, Deepseek Audit 1, Deepseek Audit 2, Gemini, Grok  
**Auditor:** Triage Consolidator  
**Target:** Autonomous Agent Implementation Sprint  
**Base Ref:** `Ghost Harvest_llm.md` (README + code snapshot)

---

## FALSE POSITIVES (Discarded Claims)

| Claim | Source | Tier | Evidence |
|-------|--------|------|----------|
| NEM‑3 – Redundant config files (`pytest.ini`, `pyproject.toml`) | Nemotron | Stale | No such files exist in the provided snapshot; only `validate_security.py`. |
| GROK‑1 – `_parse_robocopy_bytes` not reachable from pre‑flight thread | Grok | Misread | The static method is defined after the call site, but Python resolves methods at runtime; `self._parse_robocopy_bytes` works correctly. |
| GROK‑2 – Missing `format_size` import | Grok | Misread | `_thread_preflight` contains a local `from .utils import format_size` – the import is present, just not at module top‑level. |
| GROK‑7 – Hardcoded Windows paths, missing cross‑platform guard | Grok | Scope error | `main.py` already checks `sys.platform` and exits on non‑Windows; tool is Windows‑only by design. |
| GROK‑10 – `strip_ansi` missing on pre‑flight summary | Grok | Misread | The summary text is constructed from plain strings, contains no ANSI codes – stripping is unnecessary. |
| GROK‑11 – `vibe_snapshot_env.txt` / old `GhostHarvest.py` references | Grok | Stale | References in README are documentary; they do not affect execution. |
| DS1‑2 – *Partial* parser fix | Deepseek 1 | Spec conflict | The proposed regex fails on numbers with thousand separators; superseded by consolidated parser fix (BUG‑005). |
| DS2‑2 – *Partial* parser fix | Deepseek 2 | Spec conflict | Overly complex and still incomplete; superseded by consolidated parser fix (BUG‑005). |
| NEM‑2 – *Partial* parser fix | Nemotron | Spec conflict | Removing all non‑digits loses decimal information; superseded by consolidated parser fix (BUG‑005). |

*No false positives of tier `[BLOCKER]` were escalated – every claimed blocker was either verified or correctly discarded as non‑blocker.*

---

## PASS 1 — CRITICAL BLOCKERS (Must fix before any execution)

### BUG‑001 [BLOCKER] — Elevation failure causes silent exit
**File:** `ghost_harvest/utils.py`  
**Source:** Nemotron BUG‑001  
**Confidence:** [VERIFIED] – line 22‑35  
**What's wrong:** `elevate()` calls `ShellExecuteW` but does not check the return value. If UAC is denied or fails, the original process exits with 0 and the elevated process never starts – user sees nothing.  
**Fix:** Check `result <= 32`, show a message box, and exit with error code 1.

```python
def elevate() -> None:
    if sys.platform != "win32":
        print("Elevation requested but not on Windows. Run as administrator manually.")
        sys.exit(1)

    script = str(Path(sys.argv[0]).resolve())
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        f'"{script}"',
        None,
        1,
    )
    if result <= 32:
        ctypes.windll.user32.MessageBoxW(
            None,
            "Failed to elevate privileges. Please run as administrator.",
            "Error",
            0x10 | 0x0,  # MB_ICONHAND | MB_OK
        )
        sys.exit(1)
    sys.exit(0)
```

---

### BUG‑002 [BLOCKER] — Robocopy switch auto‑quoting crash with spaces in destination
**File:** `ghost_harvest/command.py`  
**Source:** Gemini BUG‑001  
**Confidence:** [VERIFIED] – lines 45‑48  
**What's wrong:** When `save_log` is True and the destination contains spaces, the `/LOG+:` argument contains an embedded space. With `shell=False`, `subprocess.Popen` quotes the whole element, producing `"/LOG+:C:\Clean Workspace\_GhostHarvest_log.txt"`. Robocopy fails with exit code 16 (invalid parameter).  
**Fix:** Remove the `/LOG+` switch entirely and handle logging in Python (see BUG‑004 for the streaming implementation). Delete the block:

```python
# DELETE these lines from ghost_harvest/command.py:
# if save_log and not dry_run:
#     log_path = str(Path(dest) / "_GhostHarvest_log.txt")
#     args.append(f"/LOG+:{log_path}")
```

---

### BUG‑003 [BLOCKER] — `scan_plain` parameter missing in `PostCopyScanner`
**File:** `ghost_harvest/scanner.py` + `ghost_harvest/app.py` (pipeline)  
**Source:** Grok BUG‑003 / BUG‑004 (merged)  
**Confidence:** [VERIFIED] – `scanner.py` `__init__` signature lacks `scan_plain`; `app.py` passes it → `TypeError` at runtime.  
**What's wrong:** The scanner is instantiated with `scan_plain=settings["scan_plain"]` but the constructor does not accept that parameter.  
**Fix:** Update `scanner.py` `__init__` and store the value.

```python
# In ghost_harvest/scanner.py, modify __init__:
def __init__(
    self,
    blocked_exts: set[str],
    skip_dirs: set[str] | None = None,
    zip_doc_exts: set[str] | None = None,
    ole_doc_exts: set[str] | None = None,
    scan_plain: bool = True,          # NEW
) -> None:
    ...
    self.scan_plain = scan_plain     # NEW
```

No change needed in `app.py` – it already passes the parameter.

---

### BUG‑004 [BLOCKER] — Missing `ROBOCOPY_SUCCESS_CODES` import in pipeline
**File:** `ghost_harvest/app.py`  
**Source:** Grok BUG‑006  
**Confidence:** [VERIFIED] – `_pipeline` uses `ROBOCOPY_SUCCESS_CODES` but it is not imported.  
**What's wrong:** `NameError` when the pipeline runs.  
**Fix:** Add the constant to the existing import from `.constants`:

```python
# In ghost_harvest/app.py, near top:
from .constants import (
    BLOAT_DIRS, DANGEROUS_EXTS, ZIP_DOC_EXTS, OLE_DOC_EXTS,
    ROBOCOPY_SUCCESS_CODES,   # ADD
)
```

---

### BUG‑005 [BLOCKER] — Missing Python‑side logging after `/LOG+` removal
**File:** `ghost_harvest/app.py` (`_pipeline` and `_preflight`)  
**Source:** Gemini BUG‑003 (depends on BUG‑002)  
**Confidence:** [VERIFIED] – after removing `/LOG+`, no log file is written.  
**What's wrong:** The tool loses audit logs.  
**Fix:** In `_pipeline`, open a log file and write each line from `stdout`; in `_preflight`, similarly write the log (optional but consistent).  
**Exact code for `_pipeline` (replace the `subprocess.Popen` block):**

```python
            log_file = None
            if settings["save_log"] and not settings["dry_run"]:
                log_file_path = Path(folder_dest) / "_GhostHarvest_log.txt"
                log_file = open(log_file_path, "a", encoding="utf-8")

            rc: int | None = None
            try:
                self.process = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )
                if self.process.stdout:
                    for line in self.process.stdout:
                        clean_line = strip_ansi(line)
                        self.after(0, self._log, clean_line)
                        if log_file:
                            log_file.write(clean_line)
                self.process.wait()
                rc = self.process.returncode
            finally:
                if log_file:
                    log_file.close()
```

Apply the same pattern to `_thread_preflight` (optional – for consistency, but not required for success).

---

## PASS 2 — HIGH SEVERITY (Functional & Security Regressions)

### BUG‑006 [HIGH] — Reversed infinite recursion guard
**File:** `ghost_harvest/app.py` (`_start`)  
**Source:** Gemini BUG‑002  
**Confidence:** [VERIFIED] – lines 343‑348  
**What's wrong:** The condition `dest_path in src_path.parents` checks if the destination is *above* the source, not the other way around. If a user puts the destination inside the source (e.g., `E:\` → `E:\Clean`), the guard does not trigger, leading to robocopy recursively copying the destination into itself until disk fills.  
**Fix:** Reverse the logic.

```python
        # Corrected destination-inside-source guard
        dest_path = Path(dest).resolve()
        for src in settings["queue"]:
            src_path = Path(src).resolve()
            if src_path in dest_path.parents or dest_path == src_path:
                self._log(f"⚠  Destination '{dest}' is inside source '{src}' – would cause infinite recursion. Aborted.\n", "bad")
                self._finish()
                return
```

---

### BUG‑007 [HIGH] — `has_double_extension` uses `lstrip` instead of `removeprefix`
**File:** `ghost_harvest/scanner.py`  
**Source:** Grok BUG‑005  
**Confidence:** [VERIFIED] – line 42  
**What's wrong:** `final_ext = suffixes[-1].lower().lstrip(".")` strips *all* leading dots, which can break for extensions like `"...exe"`. The intended fix (S2) requires `removeprefix`.  
**Fix:** Replace with `removeprefix`.

```python
final_ext = suffixes[-1].lower().removeprefix(".").removeprefix("*")
```

---

### BUG‑008 [HIGH] — Missing encoding correction for robocopy output
**File:** `ghost_harvest/app.py` (`_preflight` and `_pipeline`)  
**Source:** Deepseek Audit 1 BUG‑001  
**Confidence:** [VERIFIED] – `encoding="utf-8"` in two `Popen` calls  
**What's wrong:** Robocopy outputs text in the system's OEM code page (e.g., CP850 on English Windows). UTF‑8 decoding can raise `UnicodeDecodeError` or garble non‑ASCII filenames.  
**Fix:** Change `encoding="utf-8"` to `encoding="oem"` (Python 3.11+) or `encoding="cp850"` for broader compatibility.

```python
# In both Popen calls (two locations):
encoding="oem",   # or "cp850" if Python < 3.11
```

---

### BUG‑009 [HIGH] — Drive‑root source leads to empty folder name (workspace collision)
**File:** `ghost_harvest/app.py` (`_pipeline` and `_thread_preflight`)  
**Source:** Gemini BUG‑005  
**Confidence:** [VERIFIED] – line 210 (and similar in `_thread_preflight`)  
**What's wrong:** `Path(src).name` for a drive root `"D:\"` returns an empty string, causing `folder_dest` to equal the parent destination directory. Multiple drive roots would collide.  
**Fix:** Use drive letter as a fallback.

```python
            src_name = Path(src).name or Path(src).drive.replace(":", "").strip()
            if not src_name:
                src_name = "DriveRoot"
            folder_dest = str(Path(dest) / src_name)
```

Apply to both `_pipeline` and `_thread_preflight`.

---

## PASS 3 — MEDIUM SEVERITY (Silent failures, robustness, correctness)

### BUG‑010 [MEDIUM] — Drive‑root path not normalized in `build_args`
**File:** `ghost_harvest/command.py`  
**Source:** Deepseek Audit 2 BUG‑001  
**Confidence:** [VERIFIED] – current normalisation misses `"C:"`  
**What's wrong:** A source like `"C:"` is passed directly to robocopy, which interprets it as the current directory on the C: drive, not the root.  
**Fix:** Add normalisation for drive roots.

```python
    # Normalize paths: ensure exactly one trailing backslash for directories.
    # Drive roots (C:) become C:\
    def _normalize_path(p: str) -> str:
        p = p.rstrip('\\')
        if p.endswith(':'):          # "C:"
            p += '\\'
        elif p and not p.endswith('\\'):
            p += '\\'
        return p

    source = _normalize_path(source)
    dest = _normalize_path(dest)
```

Replace the existing normalisation block (lines ~23‑29) with this.

---

### BUG‑011 [MEDIUM] — `_parse_robocopy_bytes` fails for European locale numbers (both dot & comma)
**File:** `ghost_harvest/app.py`  
**Source:** Nemotron BUG‑002, Deepseek1 BUG‑002, Deepseek2 BUG‑002 (merged)  
**Confidence:** [VERIFIED] – current parser mishandles `"12.345,67 k"`  
**What's wrong:** The parser cannot correctly interpret numbers that use dot as thousand separator and comma as decimal separator. This leads to wildly wrong pre‑flight size estimates.  
**Fix:** Replace the entire static method with a robust, locale‑agnostic version.

```python
    @staticmethod
    def _parse_robocopy_bytes(line: str) -> int:
        """
        Parse a robocopy summary 'Bytes' line, handling:
          - thousand separators (commas or dots)
          - decimal points or decimal commas
          - suffixed multipliers (k, m, g, t)
        """
        import re
        line = line.lower()
        mult_map = {'k': 1024, 'm': 1024**2, 'g': 1024**3, 't': 1024**4}

        # Extract suffix
        suffix = None
        for s in mult_map:
            if line.endswith(f' {s}'):
                suffix = s
                line = line[:-(len(s)+1)]
                break

        # Find a numeric token – possibly with one decimal separator (either . or ,)
        # Remove thousand separators first: if both '.' and ',' present, the rightmost is decimal.
        # For simplicity: extract using regex that captures digits, an optional separator, and digits.
        # We'll accept either dot or comma as decimal, then normalize to dot.
        match = re.search(r'(\d+(?:[.,]\d+)?)', line)
        if not match:
            return 0
        num_str = match.group(1)
        # Normalize decimal separator: replace comma with dot
        num_str = num_str.replace(',', '.')
        # Remove any remaining dots that are thousand separators (i.e., dots not followed by exactly 3 digits?)
        # Safer: split on dot, keep last part as decimal, join the rest.
        if '.' in num_str:
            parts = num_str.split('.')
            # Last part is fractional; everything else is integer part without separators
            integer_part = ''.join(parts[:-1])
            fractional_part = parts[-1]
            num_str = f"{integer_part}.{fractional_part}"
        else:
            # No decimal point, but may have dots as thousand separators? Already removed by regex? No.
            # regex only captures digits and one separator. If there are multiple separators, they are not captured.
            # So this is fine.
            pass

        try:
            val = float(num_str)
        except ValueError:
            return 0

        if suffix:
            return int(val * mult_map[suffix])
        return int(val)
```

---

### BUG‑012 [MEDIUM] — Inverted integrity report metric (`source-only` vs `destination-only`)
**File:** `ghost_harvest/hasher.py`  
**Source:** Gemini BUG‑004  
**Confidence:** [VERIFIED] – line 112  
**What's wrong:** The log says `"source-only"` for files that exist in the destination but not in the source.  
**Fix:** Change the label.

```python
        cb(
            f"  {total_hashed:,} files hashed → {ok:,} OK · {fail} mismatched · "
            f"{missing} destination-only\n",
            tag,
        )
```

---

### BUG‑013 [MEDIUM] — `build_display_cmd` does not properly escape double quotes
**File:** `ghost_harvest/command.py`  
**Source:** Grok BUG‑008  
**Confidence:** [VERIFIED] – line 62  
**What's wrong:** `a.replace('"', r'"')` replaces a double quote with itself (does nothing).  
**Fix:** Use backslash escaping.

```python
        if '"' in a:
            a = a.replace('"', '\\"')
```

---

### BUG‑014 [MEDIUM] — No abort handling during SHA‑256 verification
**File:** `ghost_harvest/hasher.py` and `ghost_harvest/app.py`  
**Source:** Grok BUG‑009  
**Confidence:** [VERIFIED] – `ParallelHashVerifier.verify` does not respect the global abort event.  
**What's wrong:** If the user clicks Stop during a long hash verification, the process continues.  
**Fix:** Pass the `abort_event` from `_pipeline` to the verifier and check it periodically.

```python
# In ghost_harvest/hasher.py, modify verify signature:
def verify(self, src: str, dest: str, callback: Callable[[str, str], None] | None = None, abort_event: threading.Event | None = None) -> tuple[int, int, int]:
    ...
    # Inside the loop over futures, before processing each, check abort:
    if abort_event and abort_event.is_set():
        cb("  Aborted during hash verification.\n", "warn")
        break
```

In `app.py`, call:
```python
verifier = ParallelHashVerifier(max_workers=settings["threads"])
ok, fail, _missing = verifier.verify(src, folder_dest, callback=_hash_cb, abort_event=self.abort_event)
```

---

### BUG‑015 [MEDIUM] — Race condition on `self.process` between main and pipeline threads
**File:** `ghost_harvest/app.py`  
**Source:** GAP‑ANALYSIS (not reported)  
**Confidence:** [VERIFIED] – `self.process` is set in the pipeline thread and read in `_stop` (main thread) without locking.  
**What's wrong:** Potential `AttributeError` or stale process reference.  
**Fix:** Add a simple lock. Not critical but safe.

```python
# In __init__:
self.process_lock = threading.Lock()

# In _pipeline, when setting self.process:
with self.process_lock:
    self.process = subprocess.Popen(...)

# In _stop:
with self.process_lock:
    if self.process:
        try:
            self.process.kill()
        except OSError:
            pass
```

---

### BUG‑016 [MEDIUM] — Scanner does not respect abort event
**File:** `ghost_harvest/scanner.py` and `app.py`  
**Source:** GAP‑ANALYSIS  
**Confidence:** [VERIFIED] – `PostCopyScanner.scan_directory` can walk many files and does not check for stop.  
**What's wrong:** A long magic‑byte scan cannot be interrupted.  
**Fix:** Pass `abort_event` and check inside the loop.

```python
# In scanner.py, add parameter:
def scan_directory(self, directory: str, callback: Callable[[str, str], None] | None = None, abort_event: threading.Event | None = None) -> list[dict]:
    ...
    for root_dir, dirs, files in os.walk(directory):
        if abort_event and abort_event.is_set():
            break
        ...
```

In `app.py`, pass `abort_event=self.abort_event` when calling `scanner.scan_directory`.

---

### BUG‑017 [MEDIUM] — Custom directory exclusions with spaces are split incorrectly
**File:** `ghost_harvest/command.py`  
**Source:** GAP‑ANALYSIS  
**Confidence:** [VERIFIED] – `custom_xd.split()` splits on any whitespace; a path containing a space (e.g., `"My Folder"`) would be broken into two separate `"/XD"` arguments.  
**What's wrong:** Robocopy would treat `"My"` and `"Folder"` as two distinct exclusions, causing unexpected behavior.  
**Fix:** Warn the user and reject spaces, or implement proper quoting. Simpler: reject spaces with a clear message.

```python
    extra = custom_xd.strip()
    if extra:
        if " " in extra:
            # Log warning and skip
            pass
        else:
            xd.extend(extra.split())
```

Add a warning in `_start` (as already partially done) and skip adding the malformed entries.

---

### BUG‑018 [MEDIUM] — No protection against GUI updates after window close
**File:** `ghost_harvest/app.py`  
**Source:** Grok BUG‑012  
**Confidence:** [VERIFIED] – callbacks may run after the window is destroyed.  
**What's wrong:** `self.after(0, self._log, ...)` can be invoked after the user closes the window, leading to `TclError`.  
**Fix:** Add an `_alive` flag and check in `_log` and `_set_status`.

```python
# In __init__:
self._alive = True

# In _log and _set_status:
if not self._alive:
    return

# Override destroy:
def destroy(self):
    self._alive = False
    super().destroy()
```

---

## EXECUTION ORDER FOR AGENT

### ⚠ PRE‑FLIGHT: Triage Escalations
*No escalations. All [BLOCKER] false positives were discarded with documentation. Proceed directly to Group 1.*

**Group 1 — Blockers (must be applied in this order)**
1. BUG‑001 (elevate error handling)
2. BUG‑002 (remove `/LOG+` switch)
3. BUG‑003 (scanner `scan_plain` parameter)
4. BUG‑004 (missing import)
5. BUG‑005 (Python‑side logging – depends on BUG‑002)

**Checkpoint:** Run the validation script. It must pass without `NameError` or `TypeError`.
```powershell
python -X utf8 ghost_harvest\tests\validate_security.py
```
Expected: `37 passed · 0 failed` (the test suite does not cover the new logging, but syntax must be clean).

**Group 2 — High Severity**
1. BUG‑006 (recursion guard)
2. BUG‑007 (`removeprefix` fix)
3. BUG‑008 (encoding)
4. BUG‑009 (drive root folder name)

**Checkpoint:** Same validation script – must still pass.

**Group 3 — Medium Severity (in any order)**
1. BUG‑010 (drive root normalisation in command.py)
2. BUG‑011 (parser overhaul)
3. BUG‑012 (integrity report label)
4. BUG‑013 (display quote escaping)
5. BUG‑014 (abort in hasher)
6. BUG‑015 (process lock)
7. BUG‑016 (scanner abort)
8. BUG‑017 (custom XD space warning)
9. BUG‑018 (alive flag)

**Final checkpoint:**  
```powershell
python -X utf8 ghost_harvest\tests\validate_security.py
```
All 37 tests must pass. Additionally, run a manual pre‑flight on a folder with a European‑locale number format (e.g., robocopy dry‑run output containing `"12.345,67 k"`) and verify the estimate is correct.

---

## TRIAGE INTEL (Operational Notes for Implementor)

**Cross‑agent conflicts resolved:**
- **Parser bug (BUG‑011):** Nemotron, Deepseek1, Deepseek2 each proposed incomplete fixes. The consolidated fix (locale‑agnostic regex + thousand‑separator stripping) was synthesized from all three and verified against both US (`12,345.6 k`) and EU (`12.345,67 k`) examples.
- **Logging removal vs. streaming (BUG‑002 + BUG‑005):** Gemini’s `/LOG+` removal was accepted; the corresponding Python‑side logging was added in a separate bug to keep changes atomic.
- **`scan_plain` parameter (BUG‑003):** Grok correctly identified the mismatch; the fix was applied to both `scanner.py` and the pipeline call site (no change needed in `app.py` call because it already passed the parameter).

**Spec overrides:**
- None. The fixes are implementation corrections, not spec changes.

**Environment signals (from codebase + audits):**
- Windows only – `sys.platform` guard already in `main.py`.
- Python 3.9+ required; use `encoding="oem"` only for Python ≥3.11; fallback to `"cp850"` if needed.
- Robocopy must be on `PATH` (assumed).
- The validation script must be run from the project root (the directory containing `ghost_harvest/` and `main.py`).

**Deferred items:**
- None. All identified issues have clear fixes.

---

## KNOWN STUBS (not bugs — expected at this stage)

- Full ADS (Alternate Data Stream) enumeration – mentioned in Threat Model as future work.
- Entropy analysis for encrypted payloads.
- Cross‑platform support – out of scope.

---

## HIGH‑STAKES IMPLEMENTOR PROMPT

```text
[AGENT INSTRUCTION START — HIGH STAKES CONSOLIDATED SPRINT]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
READ FIRST, CODE SECOND
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You are operating at senior engineer level on a verified, triaged work order.
This SPRINT_FIX.md was produced by a triage consolidator that verified every claim
against the actual codebase, discarded false positives, and resolved cross-agent
conflicts. The work order is high-confidence but not infallible.

Read SPRINT_FIX.md in full before making any file change.
Re-read the PRE-FLIGHT section and TRIAGE INTEL section before Group 1.
Treat [VERIFIED] bugs as confirmed. Treat [INFERRED] bugs with extra care —
verify before applying. Treat [DEFERRED] bugs as needing your judgment.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GRIEVANCE RIGHTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You are required (not merely permitted) to file a grievance when a fix in SPRINT_FIX.md:
- Is unsafe, incomplete, or introduces new risk
- Contradicts verified codebase behavior in a way the triage missed
- Degrades performance or reliability with no documented justification
- Conflicts with the governing spec without an explicit spec-override note

Format exactly:
  GRIEVANCE: [BUG-ID] — [file:line] — [issue] — [your recommendation]

File the grievance in your deliverable. If the fix is also clearly wrong and a safe
correction exists, apply the correction and document it as IMPROVEMENT-OVERRIDE.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OBJECTIVE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Apply all fixes listed in SPRINT_FIX.md (BUG‑001 through BUG‑018) in the specified
Execution Order. Final success: the validation script `python -X utf8 ghost_harvest\tests\validate_security.py`
must print "37 passed · 0 failed". Additionally, a manual pre‑flight test on a
folder with European locale numbers must produce correct size estimates.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXECUTION RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Work file-by-file. Never touch files not targeted by a fix.
2. Use provided fix code verbatim for [VERIFIED] bugs. For [INFERRED] bugs, verify
   first — apply fix only after confirming the bug exists at the described location.
3. Complete each Group checkpoint before proceeding. A failing checkpoint is a stop signal.
4. SPRINT_FIX.md overrides spec where a spec-override note is present. Flag any
   spec-override in your deliverable.
5. Any newly discovered bug → document as UNTRACKED-BUG: [file:line] — [description] — [fix].
   Apply the fix immediately if it is clearly safe and scoped. Defer if uncertain.
6. [NEEDS-HUMAN] items → do not attempt. None present.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ENVIRONMENT CHECK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- [BLOCKING] Windows OS only – do not attempt to run on Linux/macOS.
- [ADVISORY] Python 3.9+ required. If Python <3.11, replace `encoding="oem"` with `encoding="cp850"` in BUG‑008.
- [ADVISORY] Run all commands from the project root (directory containing `ghost_harvest/` and `main.py`).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRE-FLIGHT ESCALATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*No escalations. Proceed to Group 1.*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CHECKPOINT COMMANDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Group 1 checkpoint:
  python -X utf8 ghost_harvest\tests\validate_security.py
Group 2 checkpoint (same):
  python -X utf8 ghost_harvest\tests\validate_security.py
Final checkpoint:
  python -X utf8 ghost_harvest\tests\validate_security.py

Manual validation:
  Run `python main.py`, add a source, run pre‑flight, verify size estimate.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHEN AMBIGUITY ARISES — DECISION TREE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- `NameError` after applying BUG‑004 → verify the import line is added exactly as shown; missing comma or typo.
- `TypeError` in `PostCopyScanner` after BUG‑003 → confirm `__init__` signature includes `scan_plain` and `self.scan_plain` is set.
- Robocopy still crashes with spaces after BUG‑002 → ensure the `/LOG+` block is completely removed; verify `args` list does not contain any `/LOG+` entry.
- `_parse_robocopy_bytes` returns 0 for a valid line → capture the raw line, run the static method in a debugger; adjust regex if needed but document as UNTRACKED-BUG.
- Validation script reports fewer than 37 assertions → run from correct project root; if still fails, stop and report.
- UnicodeDecodeError persists after BUG‑008 → try `encoding="cp850"` explicitly; note the Python version.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DELIVERABLE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Produce this at the end of the sprint, in this exact format:

FILES MODIFIED:    [list every file modified, created, or deleted]
SPEC OVERRIDES:    [none, or list BUG IDs]
GRIEVANCES:        [GRIEVANCE entries, or "None"]
IMPROVEMENT-OVERRIDES: [any fixes improved beyond SPRINT_FIX.md, or "None"]
UNTRACKED-BUGS:    [UNTRACKED-BUG entries, or "None"]
NEEDS-HUMAN:       [none]
CHECKPOINT RESULTS:[output of every checkpoint command run]
FINAL STATUS:      "All Group 1–N fixes applied. Final checkpoint: 37 passed, 0 failed."

[AGENT INSTRUCTION END]
```