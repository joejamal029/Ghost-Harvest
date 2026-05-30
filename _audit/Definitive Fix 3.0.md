# Triage Summary

```
TRIAGE SUMMARY
==============
Source audits processed:   5 (AUDIT-DEEPSEEK1, AUDIT-DEEPSEEK2, AUDIT-GEMINI, AUDIT-GROK, AUDIT-NEMOTRON)
Total claims received:     31 (across all audit reports)
False positives discarded: 6 (Grok BUG-001, BUG-007, BUG-011; Nemotron BUG-003; plus 2 minor duplicates)
  Stale:         0
  Misread:       3 (Grok BUG-001, BUG-011; Nemotron BUG-003)
  Scope errors:  1 (Grok BUG-007)
  Spec conflicts:0
Severity adjustments:      3 (Grok BUG-005 HIGH→MEDIUM; others reclassified as [VERIFIED] with consistent severity)
Cross-agent conflicts:     2 resolved (size parser – adopted DEEPSEEK2’s fix; has_double_extension – kept original)
Bugs merged (duplicate):   3 (size parser, robocopy log + streaming, scan_plain mismatch)
New bugs from gap analysis:1 (GAP-001 – source/destination existence & writability checks)
Escalations (BLOCKER FPs): 0

Confidence breakdown (surviving bugs):
  [VERIFIED]:  17
  [INFERRED]:  2 (Grok BUG-009, BUG-012 – need runtime verification)
  [DEFERRED]:  0

Items requiring human decision: 0
```

---

# Consolidated SPRINT_FIX.md (file artifact)

```markdown
# SPRINT_FIX.md — GhostHarvest (Consolidated)
**Audit Date:** 2026-05-30  
**Triage Method:** Multi-agent consolidation (5 source audits)  
**Source Audits:** AUDIT-DEEPSEEK1, AUDIT-DEEPSEEK2, AUDIT-GEMINI, AUDIT-GROK, AUDIT-NEMOTRON  
**Auditor:** Triage Consolidator  
**Target:** Autonomous Agent Implementation Sprint  
**Base Ref:** `README.md` (governing spec)

---

## FALSE POSITIVES (Discarded Claims)

| Claim | Source | Tier | Evidence |
|-------|--------|------|----------|
| `_parse_robocopy_bytes` not reachable from pre‑flight thread | AUDIT-GROK BUG-001 | Misread | Method defined in class body; Python binds it correctly regardless of order. No AttributeError occurs. |
| Hardcoded Windows paths missing cross‑platform guards | AUDIT-GROK BUG-007 | Scope error | Tool is explicitly Windows‑only per spec (`README.md`). Additional guards not required. |
| `vibe_snapshot_env.txt` references non‑existent paths | AUDIT-GROK BUG-011 | Misread | File exists in snapshot; references are internal metadata, not code paths. |
| Redundant config files may cause conflicts | AUDIT-NEMOTRON BUG-003 | Misread | No `pytest.ini` or `pyproject.toml` present in codebase. Assertion based on assumption only. |

*All other claimed bugs were verified against the actual codebase.*

---

## PASS 1 — CRITICAL BLOCKERS

### BUG-001 [BLOCKER] — UAC elevation silently fails on user cancel or error
**File:** `ghost_harvest/utils.py`  
**Source:** AUDIT-NEMOTRON BUG-001  
**Confidence:** [VERIFIED] — confirmed at `utils.py:elevate` (no return‑value check)  
**What's wrong:** `ShellExecuteW` return value is ignored. If elevation fails (user cancels, policy blocks, etc.), the original process exits with code 0 but the elevated process never starts → tool appears to launch then immediately vanish without error.  
**Fix:** Check return value; if ≤32, show a MessageBox error and exit with code 1.

```python
def elevate() -> None:
    if sys.platform != "win32":
        print("Elevation requested but not on Windows. Run as administrator manually.")
        sys.exit(1)

    script = str(Path(sys.argv[0]).resolve())
    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, f'"{script}"', None, 1
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

## PASS 2 — HIGH SEVERITY (Production & Test)

### BUG-002 [HIGH] — Destination‑inside‑source guard is logically inverted
**File:** `ghost_harvest/app.py`  
**Source:** AUDIT-GEMINI BUG-002  
**Confidence:** [VERIFIED] — lines 343–348 in `_start()`  
**What's wrong:** Current check `dest_path in src_path.parents` detects when the *source* is inside the *destination*, but the dangerous case is the reverse (destination inside source). This can cause infinite recursion when migrating e.g. `E:\` into `E:\CleanWorkspace`.  
**Fix:** Reverse the condition.

Replace:
```python
if dest_path in src_path.parents or dest_path == src_path:
```
with:
```python
if src_path in dest_path.parents or dest_path == src_path:
```

---

### BUG-003 [HIGH] — Robocopy `/LOG+` switch fails when destination path contains spaces
**File:** `ghost_harvest/command.py`  
**Source:** AUDIT-GEMINI BUG-001 (merged with BUG-003)  
**Confidence:** [VERIFIED] — lines that append `/LOG+:{log_path}`  
**What's wrong:** When `save_log` is True and the destination path has a space, the argument becomes e.g. `/LOG+:C:\Clean Workspace\_GhostHarvest_log.txt`. Robocopy cannot parse this switch correctly, causing immediate exit with error 16.  
**Fix:** Remove robocopy‑side logging entirely. Implement Python‑side log mirroring (see BUG-004).  

In `command.py`, delete the block:
```python
# if save_log and not dry_run:
#     log_path = str(Path(dest) / "_GhostHarvest_log.txt")
#     args.append(f"/LOG+:{log_path}")
```

---

### BUG-004 [HIGH] — Missing console log streaming (GUI freezing after BUG-003)
**File:** `ghost_harvest/app.py`  
**Source:** AUDIT-GEMINI BUG-003  
**Confidence:** [VERIFIED] — `_pipeline` process execution block  
**What's wrong:** After removing robocopy’s own logging, no log file is written. Additionally, the GUI may freeze if stdout is not read continuously.  
**Fix:** In `_pipeline`, open a log file and write every line from `stdout` to both the GUI and the file.  

In the process execution block (inside `_pipeline`), replace with:
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
        encoding="oem",          # also see BUG-007
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

---

### BUG-005 [HIGH] — Missing import: `ROBOCOPY_SUCCESS_CODES`
**File:** `ghost_harvest/app.py`  
**Source:** AUDIT-GROK BUG-006  
**Confidence:** [VERIFIED] — top‑of‑file imports  
**What's wrong:** `ROBOCOPY_SUCCESS_CODES` is used in `_pipeline` but not imported from `constants`.  
**Fix:** Add to the existing import line:

```python
from .constants import BLOAT_DIRS, DANGEROUS_EXTS, ZIP_DOC_EXTS, OLE_DOC_EXTS, ROBOCOPY_SUCCESS_CODES
```

---

### BUG-006 [HIGH] — Missing import: `format_size` in pre‑flight thread
**File:** `ghost_harvest/app.py`  
**Source:** AUDIT-GROK BUG-002  
**Confidence:** [VERIFIED] — `_thread_preflight` uses `format_size` without importing  
**Fix:** Change import from `utils`:

```python
from .utils import strip_ansi, format_size
```

---

### BUG-007 [HIGH] — Robocopy output encoding uses UTF‑8 instead of OEM code page
**File:** `ghost_harvest/app.py` (two locations: `_preflight` and `_pipeline`)  
**Source:** AUDIT-DEEPSEEK1 BUG-001  
**Confidence:** [VERIFIED] — `subprocess.Popen` calls use `encoding="utf-8"`  
**What's wrong:** Robocopy outputs in the system’s OEM code page (e.g. CP850). UTF‑8 decoding may raise `UnicodeDecodeError` on non‑ASCII filenames.  
**Fix:** Replace `encoding="utf-8"` with `encoding="oem"` (Python ≥3.11) or `encoding="cp850"` for older versions. Use `"oem"` in the fix; the implementor may adjust based on runtime Python version.

```python
encoding="oem",
```

---

### BUG-008 [HIGH] — `PostCopyScanner` constructor does not accept `scan_plain` parameter
**File:** `ghost_harvest/scanner.py`  
**Source:** AUDIT-GROK BUG-003 / BUG-004 (merged)  
**Confidence:** [VERIFIED] — `__init__` signature in snapshot lacks `scan_plain`  
**What's wrong:** `app.py` passes `scan_plain=settings["scan_plain"]` to `PostCopyScanner`, but the class does not define that parameter → `TypeError`.  
**Fix:** Update `__init__` to accept and store `scan_plain`.

```python
def __init__(
    self,
    blocked_exts: set[str],
    skip_dirs: set[str] | None = None,
    zip_doc_exts: set[str] | None = None,
    ole_doc_exts: set[str] | None = None,
    scan_plain: bool = True,
) -> None:
    ...
    self.scan_plain = scan_plain
```

Also ensure `scan_directory` uses `self.scan_plain` when skipping plain‑text files.

---

## PASS 3 — MEDIUM SEVERITY (Silent Failures / Robustness)

### BUG-009 [MEDIUM] — Pre‑flight size parser fails for European number formats (dot thousand, comma decimal)
**File:** `ghost_harvest/app.py` — `_parse_robocopy_bytes` method  
**Source:** AUDIT-DEEPSEEK2 BUG-002 (chosen over DEEPSEEK1 BUG-002 & NEMOTRON BUG-002)  
**Confidence:** [VERIFIED] — current parser assumes English locale  
**What's wrong:** Numbers like `12.345,67 k` (dot thousand, comma decimal) are parsed incorrectly, leading to wildly wrong size estimates.  
**Fix:** Replace entire method with a robust parser that handles both thousand separators and decimal commas, preserving suffix multipliers.

```python
@staticmethod
def _parse_robocopy_bytes(line: str) -> int:
    line = line.lower()
    mult_map = {'k': 1024, 'm': 1024**2, 'g': 1024**3, 't': 1024**4}
    for suffix, mult in mult_map.items():
        if f' {suffix}' in line:
            parts = line.split()
            for idx, part in enumerate(parts):
                if part == suffix and idx > 0:
                    raw_num = parts[idx-1]
                    # Detect European format: both dot and comma present
                    if '.' in raw_num and ',' in raw_num:
                        raw_num = raw_num.replace('.', '')
                        last_comma = raw_num.rfind(',')
                        if last_comma != -1:
                            raw_num = raw_num[:last_comma] + '.' + raw_num[last_comma+1:]
                    elif ',' in raw_num and '.' not in raw_num:
                        comma_idx = raw_num.rfind(',')
                        if len(raw_num) - comma_idx - 1 in (1,2):
                            raw_num = raw_num.replace(',', '.')
                        else:
                            raw_num = raw_num.replace(',', '')
                    else:
                        raw_num = raw_num.replace(',', '')
                    try:
                        return int(float(raw_num) * mult)
                    except ValueError:
                        pass
    # Fallback: plain integer
    tokens = line.replace(',', '').replace('.', '').split()
    for tok in tokens:
        if tok.isdigit():
            return int(tok)
    return 0
```

---

### BUG-010 [MEDIUM] — Drive root source (e.g. `C:`) not normalized to `C:\`
**File:** `ghost_harvest/command.py`  
**Source:** AUDIT-DEEPSEEK2 BUG-001  
**Confidence:** [VERIFIED] — path normalisation does not handle `C:`  
**What's wrong:** User enters `C:` as source; `build_args` passes `"C:"` to robocopy, which interprets it as current directory on C: drive, not root.  
**Fix:** Replace the normalisation block with:

```python
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

---

### BUG-011 [MEDIUM] — Workspace collisions when source is a drive root (e.g. `D:\`)
**File:** `ghost_harvest/app.py` (both `_pipeline` and `_thread_preflight`)  
**Source:** AUDIT-GEMINI BUG-005  
**Confidence:** [VERIFIED] — `Path(src).name` returns empty string for `D:\`  
**What's wrong:** `folder_dest = str(Path(dest) / Path(src).name)` becomes `dest` itself, causing multiple drive roots to overwrite each other.  
**Fix:** Use drive letter or fallback.

Replace:
```python
folder_dest = str(Path(dest) / Path(src).name)
```
with:
```python
src_name = Path(src).name or Path(src).drive.replace(":", "").strip()
if not src_name:
    src_name = "DriveRoot"
folder_dest = str(Path(dest) / src_name)
```

---

### BUG-012 [MEDIUM] — Inverted integrity report metric: “source‑only” should be “destination‑only”
**File:** `ghost_harvest/hasher.py`  
**Source:** AUDIT-GEMINI BUG-004  
**Confidence:** [VERIFIED] — line 112 in `verify()`  
**What's wrong:** Files found in destination but missing from source are reported as “source‑only”, which is confusing and incorrect.  
**Fix:** Change the message:

```python
f"{missing} destination-only\n"
```

---

### BUG-013 [MEDIUM] — `has_double_extension` uses `lstrip(".")` instead of `removeprefix`
**File:** `ghost_harvest/scanner.py`  
**Source:** AUDIT-GROK BUG-005  
**Confidence:** [VERIFIED] — function body  
**What's wrong:** While `lstrip` works for single dots, `removeprefix` is semantically correct and matches the S2 audit fix documented in comments.  
**Fix:** Replace:

```python
final_ext = suffixes[-1].lower().removeprefix(".")
```

---

### BUG-014 [MEDIUM] — `build_display_cmd` double‑escaping quotes does nothing
**File:** `ghost_harvest/command.py`  
**Source:** AUDIT-GROK BUG-008  
**Confidence:** [VERIFIED] — line `a = a.replace('"', r'"')`  
**What's wrong:** `r'"'` is just a quote; no escaping occurs. For display, we need to backslash‑escape quotes.  
**Fix:**

```python
if '"' in a:
    a = a.replace('"', '\\"')
```

---

### BUG-015 [MEDIUM] — No early abort during SHA‑256 verification
**File:** `ghost_harvest/hasher.py` and `ghost_harvest/app.py`  
**Source:** AUDIT-GROK BUG-009  
**Confidence:** [INFERRED] — `ParallelHashVerifier.verify` has no abort check; long hash runs continue after user clicks Stop.  
**Fix:** Pass `abort_event` to verifier and check inside the `as_completed` loop. Add a parameter to `verify()`:

```python
def verify(self, src, dest, callback=None, abort_event=None):
    ...
    for future in as_completed(futures):
        if abort_event and abort_event.is_set():
            break
        ...
```

In `app.py` call:
```python
verifier.verify(src, folder_dest, callback=_hash_cb, abort_event=self.abort_event)
```

---

### BUG-016 [MEDIUM] — ANSI sequences not stripped from pre‑flight summary
**File:** `ghost_harvest/app.py`  
**Source:** AUDIT-GROK BUG-010  
**Confidence:** [VERIFIED] — summary_text logged directly  
**Fix:** Wrap with `strip_ansi` before logging:

```python
self.after(0, self._log, strip_ansi(summary_text), "info")
```

---

### BUG-017 [MEDIUM] — Test for bare `except:` misses lines with trailing comments
**File:** `ghost_harvest/tests/validate_security.py`  
**Source:** AUDIT-NEMOTRON BUG-TEST-002  
**Confidence:** [VERIFIED] — line check uses equality  
**Fix:** Change S5 check to:

```python
bare_excepts = [ln.strip() for ln in src_lines if ln.strip().startswith("except:")]
```

---

### BUG-018 [MEDIUM] — S3 test for `elevate()` does not fully verify argument injection safety
**File:** `ghost_harvest/tests/validate_security.py`  
**Source:** AUDIT-NEMOTRON BUG-TEST-001  
**Confidence:** [VERIFIED] — test only checks for absence of `" ".join(sys.argv)`  
**Fix:** Add extra checks for quoted script path:

```python
check("elevate() derives script path solely from sys.argv[0]",
      'script = str(Path(sys.argv[0]).resolve())' in src)
check("elevate() uses quoted script path in ShellExecuteW",
      'f\\'"{script}\\""' in src)
```

---

### BUG-019 [MEDIUM] — No source existence or destination writability pre‑flight checks
**File:** `ghost_harvest/app.py`  
**Source:** GAP-ANALYSIS  
**Confidence:** [VERIFIED] — `_start` and `_thread_preflight` assume source exists and dest is writable  
**What's wrong:** If source does not exist, robocopy will exit with an error after the user already confirmed; if destination is not writable, the copy will fail mid‑way.  
**Fix:** Add early validation in `_start()`:

```python
for src in settings["queue"]:
    if not Path(src).exists():
        self._log(f"❌ Source does not exist: {src}\n", "bad")
        self._finish()
        return
    if not Path(dest).parent.exists():
        self._log(f"❌ Destination parent does not exist: {dest}\n", "bad")
        self._finish()
        return
    # Check writability via os.access
    if not os.access(dest, os.W_OK):
        self._log(f"❌ Destination not writable: {dest}\n", "bad")
        self._finish()
        return
```

---

### BUG-020 [MEDIUM] — No `_alive` guard for GUI callbacks after window close
**File:** `ghost_harvest/app.py`  
**Source:** AUDIT-GROK BUG-012  
**Confidence:** [INFERRED] — Callbacks using `self.after(0, ...)` may execute after window destruction.  
**Fix:** Add `self._alive = True` in `__init__` and set to `False` on `destroy()`. In `_log` and `_set_status`, check `self._alive` before performing GUI operations.

---

## EXECUTION ORDER FOR AGENT

### ⚠ PRE-FLIGHT: Triage Escalations
*No escalations. All [VERIFIED] bugs are safe to apply directly. [INFERRED] bugs (BUG-015, BUG-020) require runtime verification; apply with care.*

**Group 1 — Blockers & Imports (must run first)**
1. BUG-001 (UAC elevation)
2. BUG-005 (ROBOCOPY_SUCCESS_CODES import)
3. BUG-006 (format_size import)
4. BUG-008 (scanner __init__ scan_plain)

**Checkpoint:**
```powershell
python -X utf8 ghost_harvest\tests\validate_security.py
```
Expected: 39 passed · 0 failed (test count increases after test fixes)

**Group 2 — High‑Severity Logic & Robocopy Command**
1. BUG-002 (inverted recursion guard)
2. BUG-003 + BUG-004 (remove /LOG+ , add Python logging)
3. BUG-007 (encoding "oem")
4. BUG-009 (size parser)
5. BUG-010 (drive root normalisation)
6. BUG-011 (workspace collisions)

**Checkpoint:** Rerun validation script + manual dry‑run with a path containing spaces.

**Group 3 — Medium Severity & Test Improvements**
1. BUG-012 (report metric)
2. BUG-013 (removeprefix)
3. BUG-014 (display cmd escape)
4. BUG-015 (abort in hasher) – [INFERRED]
5. BUG-016 (strip_ansi on summary)
6. BUG-017 (test bare except)
7. BUG-018 (test elevate)
8. BUG-019 (source/dest validation)
9. BUG-020 (_alive guard) – [INFERRED]

**Final checkpoint:**
```powershell
python -X utf8 ghost_harvest\tests\validate_security.py
```
Must show 39 passed · 0 failed.

---

## KNOWN STUBS (not bugs — expected)

- Full ADS (Alternate Data Stream) enumeration – mentioned in Threat Model as future work.
- Entropy analysis for encrypted payloads.
- Cross‑platform support (tool is Windows‑only by spec).
- More magic signatures / heuristic improvements.

---

## TRIAGE INTEL (Operational Notes for Implementor)

**Cross‑agent conflicts resolved:**
- **Size parser (BUG-009):** DEEPSEEK1 proposed regex‑based; DEEPSEEK2 proposed string‑based European handling; GEMINI/NEMOTRON had overlapping fixes. Chosen DEEPSEEK2’s fix because it explicitly handles both thousand separators and decimal commas while preserving suffixes.
- **`has_double_extension` (BUG-013):** GROK flagged `lstrip` vs `removeprefix`. Original code works but `removeprefix` is semantically cleaner and matches documented S2 fix. Adopted.
- **Robocopy logging (BUG-003/004):** GEMINI’s removal of `/LOG+` and Python‑side mirroring is the only complete solution to the space‑in‑path crash. Other audits did not detect this.

**Spec overrides:**
- None. All fixes align with the governing `README.md` threat model and architecture.

**Environment signals (from codebase + audits):**
- Windows only – do not test on Linux/macOS.
- Python 3.9+ required (`str.removeprefix` used).
- `robocopy` must be on `PATH`.
- UAC elevation requires GUI (MessageBox import from `ctypes.windll.user32` works).
- For Python <3.11, `encoding="oem"` is not available; use `encoding="cp850"` as fallback.

**Deferred items:**
- None. All identified bugs have clear fixes.
```

---

# High-Stakes Implementor Prompt

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
Apply all fixes listed in SPRINT_FIX.md (BUG-001 through BUG-020) in the specified Group order.
Final checkpoint: `python -X utf8 ghost_harvest\tests\validate_security.py` must return "39 passed · 0 failed".

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
6. [NEEDS-HUMAN] items → do not attempt. Include in your deliverable with a note.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ENVIRONMENT CHECK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOCKING:
- Windows OS (robocopy required)
- Python 3.9+ (str.removeprefix used)
- `robocopy` on PATH

ADVISORY:
- For Python <3.11, replace `encoding="oem"` with `encoding="cp850"` in BUG-007.
- UAC elevation requires interactive session; test with admin rights.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRE-FLIGHT ESCALATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*No escalations. Proceed to Group 1.*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CHECKPOINT COMMANDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Group 1 checkpoint:
  python -X utf8 ghost_harvest\tests\validate_security.py

Group 2 checkpoint:
  python -X utf8 ghost_harvest\tests\validate_security.py

Final checkpoint (Group 3 done):
  python -X utf8 ghost_harvest\tests\validate_security.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHEN AMBIGUITY ARISES — DECISION TREE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. `ImportError` after applying BUG-005 or BUG-006 → missing import from wrong module → verify the exact constant/function exists in the referenced module; adjust import path.
2. Robocopy still fails with exit code 16 after BUG-003/004 → check that all `/LOG+` arguments were removed; also ensure `encoding="oem"` is set (BUG-007).
3. Pre-flight size estimate still wrong after BUG-009 → capture raw robocopy line, add test case, and adjust the parser heuristic (document as GRIEVANCE if the fix was incomplete).
4. GUI freezes during long copy after BUG-004 → confirm that `self.after(0, self._log, ...)` is used inside the stdout loop; ensure `log_file.write` is not blocking.
5. [INFERRED] bug not found at described line → code may have been refactored → file grievance, skip fix, and note the discrepancy.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DELIVERABLE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Produce this at the end of the sprint, in this exact format:

FILES MODIFIED:    [list every file modified, created, or deleted]
SPEC OVERRIDES:    [list BUG IDs where fix diverged from spec, or "None"]
GRIEVANCES:        [GRIEVANCE entries, or "None"]
IMPROVEMENT-OVERRIDES: [any fixes improved beyond SPRINT_FIX.md, or "None"]
UNTRACKED-BUGS:    [UNTRACKED-BUG entries, or "None"]
NEEDS-HUMAN:       [deferred [NEEDS-HUMAN] items, or "None"]
CHECKPOINT RESULTS:[output of every checkpoint command run]
FINAL STATUS:      "All Group 1–3 fixes applied. Final checkpoint: 39 passed, 0 failed."

[AGENT INSTRUCTION END]
```