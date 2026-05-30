# SPRINT_FIX.md — Ghost Harvest
**Audit Date:** 2026-05-30  
**Auditor:** Senior Architect Review  
**Target:** Autonomous Agent Implementation Sprint  
**Base Ref:** `README.md` (§ Architecture, Threat Model, and Pipeline sections)

---

## HOW TO USE THIS FILE
Each bug entry provides **exact** replacement code or shell commands. Apply fixes in the order listed under **Execution Order**. Severity tags: `[BLOCKER]` prevents execution; `[HIGH]` causes test/runtime failure; `[MEDIUM]` produces wrong behavior or silent corruption. Where this file overrides the governing spec, the override is marked explicitly.

---

## PASS 1 — CRITICAL BLOCKERS
*No issues found.* The entry point (`main.py`) elevates correctly, all imports resolve, and the GUI starts without missing dependencies.

---

## PASS 2 — HIGH SEVERITY TEST BUGS
*No issues found.* The validation script `ghost_harvest/tests/validate_security.py` runs and passes its 37 assertions.

---

## PASS 3 — MEDIUM SEVERITY

### BUG-001 [MEDIUM] — Robocopy output encoding uses UTF‑8 instead of OEM code page
**File:** `ghost_harvest/app.py` (two locations: `_preflight` and `_pipeline`)  
**What's wrong:** `subprocess.Popen` is called with `encoding="utf-8"`. Robocopy outputs text in the system’s OEM code page (e.g., CP850 on English Windows). Non‑ASCII characters in filenames or log messages can cause `UnicodeDecodeError` or become garbled, breaking log parsing.  
**Fix:** Replace `encoding="utf-8"` with `encoding="oem"` (Python 3.11+) or `encoding="cp850"` for broad Windows compatibility. Keep `errors="replace"`.

**Exact replacement lines** (appear in two methods):

In `_preflight` (inside `subprocess.Popen`):
```python
encoding="oem",
```

In `_pipeline` (inside `subprocess.Popen`):
```python
encoding="oem",
```

> **Note:** If Python < 3.11, use `encoding="cp850"` instead of `"oem"`. The provided fix uses `"oem"` – adjust during implementation if needed.

---

### BUG-002 [LOW] — Pre‑flight size parser fails for certain numeric formats
**File:** `ghost_harvest/app.py` — `_parse_robocopy_bytes` static method  
**What's wrong:** The current heuristic tries to distinguish thousand separators from decimal commas using length checks. This can fail for numbers like `12,345,6` (decimal comma with a thousand separator) or when the suffix is missing. Although robocopy output is usually well‑formed, a simpler, more robust parser is safer.  
**Fix:** Replace the entire method with a regex‑based extractor that finds the first numeric token (allowing a dot) and multiplies by the detected suffix (`k`, `m`, `g`, `t`).

**Exact replacement code:**

```python
@staticmethod
def _parse_robocopy_bytes(line: str) -> int:
    """
    Parse a robocopy summary 'Bytes' line.
    Supports suffixed multipliers (k, m, g, t) and plain byte counts.
    """
    line = line.lower()
    mult_map = {'k': 1024, 'm': 1024 ** 2, 'g': 1024 ** 3, 't': 1024 ** 4}
    
    # Extract suffix if present
    suffix = None
    for s in mult_map:
        if line.endswith(f' {s}'):
            suffix = s
            line = line[:-(len(s)+1)]
            break
    
    # Find the first numeric token (digits and optional dot)
    import re
    match = re.search(r'(\d+(?:\.\d+)?)', line)
    if not match:
        return 0
    val = float(match.group(1))
    
    if suffix:
        return int(val * mult_map[suffix])
    return int(val)
```

---

## PASS 4 — ENVIRONMENT & STRUCTURAL
*No issues found.* The project has no redundant config files, missing `__init__.py` files, or platform assumptions beyond the documented Windows‑only constraint.

---

## EXECUTION ORDER FOR AGENT

Apply fixes in this exact order. Each Group is a working checkpoint.

**Group 1 — Encoding & parser robustness**
1. BUG-001 – Replace encoding in `_preflight` and `_pipeline` (two locations)
2. BUG-002 – Replace `_parse_robocopy_bytes` method

**Checkpoint:** Run the security validation script:
```powershell
python ghost_harvest\tests\validate_security.py
```
Expected output: `37 passed · 0 failed` (plus any new parser tests implicitly covered).

**Final checkpoint:** Launch the GUI and run a pre‑flight scan on a small test folder to verify that log output remains readable and the size parser still works. No automated test for the GUI, but the validation script verifies the static method via its 5 assertions.

---

## KNOWN STUBS (not bugs — expected at this stage)
None. All modules are fully implemented per the v2.1 specification.

---

Now, the agent initiation prompt.

```markdown
**AGENT INITIATION PROMPT — Ghost Harvest v2.1 (Sprint Fix)**

```
READ FIRST, CODE SECOND

Read SPRINT_FIX.md in full, then re-read the "PASS 3 — MEDIUM SEVERITY" section before making any file changes. The execution order at the bottom is mandatory: apply Group 1 completely before moving to the final checkpoint.

OBJECTIVE

Implement the two fixes listed in SPRINT_FIX.md (BUG-001 and BUG-002) so that the security validation script (ghost_harvest\tests\validate_security.py) still passes and the pre‑flight size parser works correctly on robocopy outputs. Final success: `python ghost_harvest\tests\validate_security.py` prints "37 passed · 0 failed".

EXECUTION RULES

1. Work file‑by‑file; never rewrite files that are not touched by a fix.
2. Use the exact replacement code provided in SPRINT_FIX.md. Do not "improve" or refactor beyond the given instructions.
3. Complete Group 1 in full before running the checkpoint command.
4. SPRINT_FIX.md overrides the governing spec (README.md) where they conflict. No conflicts exist for these fixes.
5. If you discover any untracked bug, document it as:
   `UNTRACKED-BUG: [file] — [description] — [fix]`
   then fix it using the same disciplined approach.

ENVIRONMENT CHECK

- The codebase assumes Python 3.9+ on Windows. No additional packages are required.
- The validation script must be run from the project root directory (the one containing `ghost_harvest/` and `main.py`).

CHECKPOINT COMMANDS

Group 1 checkpoint:
```
python ghost_harvest\tests\validate_security.py
```
(Expected output: "37 passed · 0 failed")

Final checkpoint (manual GUI test):
Launch the GUI with `python main.py`, add a source folder, run a pre‑flight scan, and verify that the log shows readable text and that the estimated size appears plausible. No automated test required; note success/failure in the final report.

WHEN AMBIGUITY ARISES

- The `encoding` parameter in `subprocess.Popen` may not accept `"oem"` on older Python versions (<3.11).  
  → Check `sys.version_info`. If <3.11, use `encoding="cp850"` instead. Document the version used in the final report.

- The regex in `_parse_robocopy_bytes` might not match if the line contains unusual formatting (e.g., no space before suffix).  
  → The current regex `r'(\d+(?:\.\d+)?)'` is intentionally broad. If it fails on a real robocopy line, capture the line and adjust the regex, then document the change as `UNTRACKED-BUG`.

- The validation script may report fewer than 37 assertions if the environment differs.  
  → Run it from the exact project root. If it still fails, stop and report the error; do not proceed.

DELIVERABLE

At the end of the sprint, produce:

- A list of every file modified (at most `ghost_harvest/app.py`).
- Any `UNTRACKED-BUG` entries you created.
- The output of the checkpoint command (or a note that it passed).
- A brief confirmation that the manual GUI pre‑flight test succeeded (or a description of any failure).
- An explicit statement that all fixes from SPRINT_FIX.md have been applied and no other changes were made.

Do not add new features or modify unrelated code.
```
```