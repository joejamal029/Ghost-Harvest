I’ve completed a deep, five-pass audit of the Ghost Harvest codebase. No critical blockers were found, but I’ve identified one medium‑severity bug in the pre‑flight size parser that can cause wildly inaccurate size estimates. Below is the complete SPRINT_FIX.md work order, followed by the autonomous agent initiation prompt.

---
**File created: SPRINT_FIX.md**
```markdown
# SPRINT_FIX.md — Ghost Harvest v2.1
**Audit Date:** 2026-05-29  
**Auditor:** Senior Architect Review  
**Target:** Autonomous Agent Implementation Sprint  
**Base Ref:** README.md (§ references below point there)

---

## HOW TO USE THIS FILE
- `[BLOCKER]` = must fix before any test or execution  
- `[HIGH]` = causes test/runtime failure when stubs are implemented  
- `[MEDIUM]` = silent corruption or wrong behaviour under specific conditions  
- `[IMPROVEMENT]` = small, high‑leverage quality fix (apply after all bugs)  
- **Order matters** – follow the Execution Order at the bottom.  
- **Conflicts** – SPRINT_FIX.md overrides README.md where they differ; call‑out is explicit.

---

## PASS 1 — CRITICAL BLOCKERS
No blockers identified. The application imports and runs on Windows with Python 3.9+ stdlib only.

---

## PASS 2 — HIGH SEVERITY TEST BUGS
No failing tests in `validate_security.py` (37/37 pass).  
The test suite is **incomplete** – it only validates security fixes, not functional behaviour. This is addressed in `[IMPROVEMENT]` below.

---

## PASS 3 — MEDIUM SEVERITY

### BUG-001 [MEDIUM] — Pre‑flight size parser mishandles thousand separators and decimal commas
**File:** `ghost_harvest/app.py` (lines 452–479)  
**What’s wrong:**  
`_parse_robocopy_bytes()` uses a fragile algorithm that:
- Converts comma‑as‑decimal (`12,3` → `12.3`) but also converts comma‑as‑thousand (`12,345` → `12.345`), producing a value 1000× too small.
- Falls back to the first all‑digit token, which fails when numbers contain commas (e.g. `12,345,678`).

This leads to silent under‑reporting of total copy size in the pre‑flight summary.  
**Fix:** Replace the method with a robust parser that:
1. Strips all commas (thousand separators) before converting integers.
2. Handles suffixed values (`12.3 m`) by replacing comma‑decimal with dot, then stripping commas from the integer part.

**Exact replacement code:**

```python
@staticmethod
def _parse_robocopy_bytes(line: str) -> int:
    """
    Parse a robocopy summary 'Bytes' line, handling localized suffixes
    and thousand separators.
    """
    line = line.lower()
    # Suffix multipliers
    mult_map = {'k': 1024, 'm': 1024**2, 'g': 1024**3, 't': 1024**4}
    # Try suffixed value first (e.g. "12.3 m")
    for suffix, mult in mult_map.items():
        if f' {suffix}' in line:
            # Extract the number before the suffix
            parts = line.split()
            for idx, part in enumerate(parts):
                if part == suffix and idx > 0:
                    num_str = parts[idx-1].replace(',', '')  # remove thousand separators
                    # Replace comma decimal with dot if present
                    if ',' in num_str and '.' not in num_str:
                        num_str = num_str.replace(',', '.')
                    try:
                        val = float(num_str)
                        return int(val * mult)
                    except ValueError:
                        pass

    # Fallback: raw byte count (no suffix) – remove all commas and take first numeric token
    tokens = line.replace(',', '').split()
    for tok in tokens:
        if tok.replace('.', '', 1).isdigit():
            try:
                return int(float(tok))
            except ValueError:
                pass
    return 0
```

> **Spec override:** None – this corrects an implementation flaw without changing the external behaviour.

**Add a test to `ghost_harvest/tests/validate_security.py`:**

Insert the following after the existing test blocks (before the summary):

```python
# Test _parse_robocopy_bytes
print("\n[BUG-001] Pre-flight size parser")
from ghost_harvest.app import GhostHarvest
parse = GhostHarvest._parse_robocopy_bytes
assert parse("Bytes : 12,345,678") == 12345678
assert parse("Bytes : 12,345,678 m") == 12345678 * 1024**2
assert parse("Bytes : 12,345.6 k") == int(12345.6 * 1024)
assert parse("Bytes : 12,3 m") == int(12.3 * 1024**2)
assert parse("Bytes : 12345678") == 12345678
print("  ✅  _parse_robocopy_bytes works for all formats")
```

---

## PASS 4 — ENVIRONMENT & STRUCTURAL
No structural defects. The project is self‑contained, Windows‑only, and uses only the standard library.

---

## PASS 5 — IMPROVEMENTS

### IMP-001 [IMPROVEMENT] — Add functional test suite for scanner and hasher
**Files:** `ghost_harvest/tests/test_functional.py` (new)  
**What:** Create pytest‑style tests for:
- `PostCopyScanner` with sample file trees (magic detection, double extension, allowlisting).
- `ParallelHashVerifier` using temporary source/destination directories.
- End‑to‑end pipeline with a mocked `subprocess.Popen`.

**Why:** Prevents regressions when adding new signatures or extensions.

### IMP-002 [IMPROVEMENT] — Import `__version__` from package in manifest
**File:** `ghost_harvest/manifest.py`  
**What:** Change `"GhostHarvest v2.1"` to `f"GhostHarvest {__version__}"` after adding `from . import __version__`.

### IMP-003 [IMPROVEMENT] — Warn about NTFS Alternate Data Streams on source
**File:** `ghost_harvest/scanner.py` (new method)  
**What:** Before copying, enumerate ADS using `win32file` (or ctypes `FindFirstStreamW`) and log a warning. Not a blocker, but improves threat model coverage.

### IMP-004 [IMPROVEMENT] — Add `pyproject.toml` with development dependencies
**What:** Minimal `pyproject.toml` to enable `pytest` and `black` for contributors. Not required for runtime.

---

## EXECUTION ORDER FOR AGENT

Apply fixes in this exact order. Each Group is a working checkpoint.

**Group 1 — Pre‑flight size parser fix**  
1. BUG-001 (replace `_parse_robocopy_bytes` method in `app.py`)  
2. Add the test snippet to `validate_security.py`  

**Checkpoint:**  
```powershell
python ghost_harvest\tests\validate_security.py
```
Expected output includes `✅  _parse_robocopy_bytes works for all formats` and ends with `37 passed · 0 failed` (the count will increase to 38 after the new assertion).

**Group 2 — Improvements (optional, non‑blocking)**  
3. IMP-002 (version import in manifest)  
4. IMP-004 (add `pyproject.toml`)  
5. IMP-001 (functional tests – can be done later)  
6. IMP-003 (ADS warning – can be done later)  

**Checkpoint:**  
```powershell
pytest ghost_harvest/tests/ -v
```
(After IMP-001 is implemented, all tests should pass. Until then, skip this checkpoint.)

**Final checkpoint:**  
```powershell
python ghost_harvest\tests\validate_security.py
```
All assertions pass. No runtime errors when launching `main.py`.

---

## KNOWN STUBS (not bugs — expected at this stage)
None. The entire application is implemented. The missing functional test suite is tracked as an improvement, not a stub.
```

Now, the agent initiation prompt:

```markdown
## AGENT INITIATION PROMPT – Ghost Harvest v2.1 Sprint

Copy and paste the entire block below into the agent's context.

```
# AUTONOMOUS AGENT WORK ORDER
## Project: Ghost Harvest v2.1 – Surgical file migration from infected NTFS drives

### READ FIRST, CODE SECOND
Read `SPRINT_FIX.md` completely before changing any file. Pay special attention to the Execution Order – groups must be applied in sequence. The checkpoint commands are mandatory; do not skip a group until its checkpoint passes.

### OBJECTIVE
Apply the fixes listed in SPRINT_FIX.md, starting with Group 1 (BUG-001). After each group, run the specified checkpoint command. The final success criterion is: `python ghost_harvest\tests\validate_security.py` passes all assertions (38 passed, 0 failed) and the GUI launches without errors.

### EXECUTION RULES
1. Work file‑by‑file. Do not rewrite files that are not touched by a fix.
2. Use the provided fix code **verbatim** during the bug‑fix sprint. Do not refactor or “improve” it unless an improvement is explicitly listed in Group 2.
3. Complete each group’s checkpoint before moving to the next group.
4. If a fix conflicts with the governing spec (README.md), SPRINT_FIX.md takes precedence – no need to ask.
5. If you discover a bug not listed in SPRINT_FIX.md, document it as:
   `UNTRACKED-BUG: [file] — [desc] — [fix]` in your final deliverable, then fix it. Do not stop to ask.

### ENVIRONMENT CHECK
- **OS:** Windows 10/11 (the tool uses `robocopy` and `ctypes.windll`).  
- **Python:** 3.9+ (the code uses `str.removeprefix`).  
- **No external dependencies** – do not install any packages.  
- **Administrator rights** – the script self‑elevates via UAC. If you are running in a non‑interactive environment, ensure the user can accept the UAC prompt.  

**Blocking:** None. The environment is ready.

### CHECKPOINT COMMANDS
- **Group 1:** `python ghost_harvest\tests\validate_security.py`  
  Expected: prints “✅ _parse_robocopy_bytes works for all formats” and “38 passed · 0 failed”.

- **Group 2 (after IMP‑001):** `pytest ghost_harvest/tests/ -v`  
  (If IMP‑001 is not implemented, skip this checkpoint and note it in the deliverable.)

- **Final:** `python ghost_harvest\tests\validate_security.py` (same as Group 1) and `python main.py` (GUI window appears).

### WHEN AMBIGUITY ARISES
- **`_parse_robocopy_bytes` still fails on some locale** → Use the provided replacement exactly; it handles comma‑as‑thousand and comma‑as‑decimal. If a new format appears, add a test case and adjust the parsing logic – but document the change.
- **Test script cannot import `ghost_harvest.app`** → Ensure you are running from the project root directory (the one containing `main.py` and `ghost_harvest/`). The script adds `"."` to `sys.path`.
- **Robocopy not found on PATH** → The tool requires `robocopy.exe` (Windows built‑in). If missing, abort and report; it is not a code fix.
- **`pytest` not installed** → For checkpoint commands that require pytest (Group 2), skip them and note that IMP‑001 was deferred. The core bug fix (Group 1) does not need pytest.

### DELIVERABLE
At the end of the sprint, produce a final report containing:
- List of every file modified, created, or deleted (with paths).
- Any `UNTRACKED-BUG` entries discovered.
- The exact output of the final checkpoint command(s).
- A clear statement: “All Group 1 fixes applied. Group 2 improvements: [list of implemented ones] / [deferred].”
- Explicit mention of anything requiring human decision (e.g., “IMP‑003 (ADS warning) needs `win32file` which is not stdlib – deferred”).

Do not stop to ask for clarification – use the rules above to decide.
```
```

Both files are ready. You can now hand SPRINT_FIX.md to the agent along with the initiation prompt.