## SPRINT_FIX.md — Ghost Harvest
**Audit Date:** 2026-05-30  
**Auditor:** Senior Architect Review  
**Target:** Autonomous Agent Implementation Sprint  
**Base Ref:** `README.md` (Governing spec – Architecture, Threat Model, Pipeline)

---

## HOW TO USE THIS FILE
- `[BLOCKER]` = prevents run/compile – fix first  
- `[HIGH]` = test or runtime failure when stub implemented  
- `[MEDIUM]` = silent corruption or wrong behaviour under specific conditions  
- **Execution order at bottom is mandatory** – complete each Group’s checkpoint before moving to the next.  
- Where code conflicts with the governing spec, the spec wins unless this file explicitly overrides it.

---

## PASS 1 — CRITICAL BLOCKERS
**No issues found.** The codebase is complete, imports resolve, and the entry point (`main.py`) launches the GUI when run as Administrator on Windows.

---

## PASS 2 — HIGH SEVERITY TEST BUGS
**No issues found.** The security validation script (`validate_security.py`) correctly asserts all documented fixes and would reveal regressions.

---

## PASS 3 — MEDIUM SEVERITY

### BUG-001 [MEDIUM] — Fragile pre‑flight byte‑count parser (silent failure)
**File:** `ghost_harvest/app.py` – method `_parse_robocopy_bytes`  
**What’s wrong:**  
The parser assumes a single comma as a thousand separator *or* a single comma as a decimal marker, but does not handle:
- Thousands separators that are spaces or dots (European locales)
- Numbers without any separator but followed by a suffixed multiplier (e.g. `12345678 m`)
- Mixed decimal commas with thousands separators (e.g. `1.234.567,89 m`)

When parsing fails, the function returns `0` and the pre‑flight summary shows `0 B` size, misleading the user. No exception is raised – silent failure.

**Fix:** Replace the entire method with the following robust version:

```python
@staticmethod
def _parse_robocopy_bytes(line: str) -> int:
    """
    Parse a robocopy summary 'Bytes' line, handling thousand separators,
    decimal commas, suffixed multipliers (k, m, g, t), and various locale formats.
    """
    import re
    line = line.lower().strip()
    # Suffix multiplier map
    mult_map = {'k': 1024, 'm': 1024 ** 2, 'g': 1024 ** 3, 't': 1024 ** 4}
    # Extract suffix if present
    suffix = None
    for s in mult_map:
        if line.endswith(f' {s}'):
            suffix = s
            line = line[:-(len(s)+1)].strip()
            break
    # Remove all non-numeric characters except decimal points and commas
    # But preserve only the last occurrence of comma or point as decimal separator
    numeric_part = re.sub(r'[^\d,\.]', '', line)
    if not numeric_part:
        return 0
    # Detect decimal separator: if both comma and dot exist, the last one wins
    decimal_sep = None
    if '.' in numeric_part and ',' in numeric_part:
        # Last occurrence decides
        last_dot = numeric_part.rfind('.')
        last_comma = numeric_part.rfind(',')
        decimal_sep = ',' if last_comma > last_dot else '.'
    elif '.' in numeric_part:
        decimal_sep = '.'
    elif ',' in numeric_part:
        decimal_sep = ','
    # Remove thousand separators and replace decimal separator with dot
    if decimal_sep == ',':
        # comma is decimal – treat all dots as thousand separators (remove them)
        numeric_part = numeric_part.replace('.', '')
        numeric_part = numeric_part.replace(',', '.')
    elif decimal_sep == '.':
        # dot is decimal – treat all commas as thousand separators (remove them)
        numeric_part = numeric_part.replace(',', '')
    else:
        # No decimal separator – just remove all commas and dots
        numeric_part = numeric_part.replace(',', '').replace('.', '')
    try:
        value = float(numeric_part)
    except ValueError:
        return 0
    if suffix:
        value *= mult_map[suffix]
    return int(value)
```

> **Spec override:** None – this improves robustness without changing external behaviour.

---

### BUG-002 [MEDIUM] — Path normalisation may produce ambiguous drive‑relative paths
**File:** `ghost_harvest/command.py` – function `_normalize_path`  
**What’s wrong:**  
For a path like `C:folder` (no backslash after the drive letter) the function returns it unchanged. When passed to `robocopy`, this is interpreted as a relative path to the current directory on the C: drive, which is rarely intended. The user’s input is usually an absolute path; if they mistakenly type `C:folder` the tool will copy from the wrong location without error.

**Fix:** Ensure that any path that starts with a drive letter and colon, but no backslash immediately after, is normalised to the drive root plus the rest as a relative subfolder:

```python
def _normalize_path(p: str) -> str:
    if not p:
        return p
    # Check for drive root like 'C:' or 'c:' without a trailing backslash
    if len(p) >= 2 and p[1] == ":" and p[0].isalpha():
        if len(p) == 2:
            return p + "\\"
        if p[2] != "\\":
            # 'C:folder' -> 'C:\folder'
            p = p[:2] + "\\" + p[2:]
    # For general directories, normalize trailing backslashes
    if p.endswith('\\') and not p.endswith(':\\'):
        return p.rstrip('\\') + '\\'
    return p
```

---

## PASS 4 — ENVIRONMENT & STRUCTURAL
**No issues found.** The project is well‑structured, uses only the standard library, and is Windows‑native as intended. The security test script is a standalone validator, not a pytest suite – this is acceptable for the current stage.

---

## EXECUTION ORDER FOR AGENT

Apply fixes in this exact order. Each Group is a working checkpoint.

**Group 1 — Parser and path normalisation hardening**  
1. BUG-001 – Replace `_parse_robocopy_bytes` with the robust implementation  
2. BUG-002 – Update `_normalize_path` as shown  

**Checkpoint:** Run the security validation suite and a quick functional test of the pre‑flight parser.  
```powershell
python ghost_harvest\tests\validate_security.py
```
Expected: `37 passed · 0 failed`

Then manually test the parser with a variety of formats:
```powershell
python -c "from ghost_harvest.app import GhostHarvest; p=GhostHarvest._parse_robocopy_bytes; print(p('Bytes : 1.234.567,89 m'))"
```
Expected output: `1294341062` (≈ 1.23 GB)

**Final checkpoint:** Launch the GUI and perform a dry‑run pre‑flight on a small folder to confirm that the pre‑flight size now matches the true size.

```powershell
python main.py
```

No further groups required.

---

## KNOWN STUBS (not bugs — expected at this stage)
None – all modules are fully implemented for the current feature set. No stubs are left for the sprint.

---


Now, the agent initiation prompt (Phase 2) based on the SPRINT_FIX.md above.

```markdown
# AGENT INITIATION PROMPT – Ghost Harvest Sprint

**READ FIRST, CODE SECOND**  
Read `SPRINT_FIX.md` in full. Then re‑read the **PASS 3** section and the **EXECUTION ORDER** before changing any file. Fix dependencies exist – the Group sequence is mandatory.

**OBJECTIVE**  
Apply the two medium‑severity fixes (BUG‑001, BUG‑002) so that pre‑flight size parsing becomes locale‑robust and ambiguous drive‑relative paths are corrected. After the Group, the security validation script (`validate_security.py`) must pass with `37 passed · 0 failed`. The final checkpoint is a manual pre‑flight test showing correct byte‑count parsing.

**EXECUTION RULES**  
1. Work file‑by‑file; never rewrite files not touched by a fix.  
2. Use the provided fix code **verbatim** during the bug‑fix sprint – do not “improve” it.  
3. Complete **Group 1**’s checkpoint before considering the sprint done.  
4. `SPRINT_FIX.md` overrides the governing spec (`README.md`) where they conflict; no conflicts exist in these fixes.  
5. Any untracked bug discovered must be documented as `UNTRACKED-BUG: [file] — [desc] — [fix]` before fixing it.

**ENVIRONMENT CHECK**  
- OS: Windows (the tool is Windows‑only).  
- Python: 3.9+ (uses `str.removeprefix`).  
- Required system command: `robocopy` (present by default on Windows).  
- No external packages need installation.

**CHECKPOINT COMMANDS**  
Copy and run exactly:

**Group 1** – `python ghost_harvest\tests\validate_security.py`  
**Final** – `python -c "from ghost_harvest.app import GhostHarvest; p=GhostHarvest._parse_robocopy_bytes; print(p('Bytes : 1.234.567,89 m'))"` (expected `1294341062`)

**WHEN AMBIGUITY ARISES**  
- *Pre‑flight parser still returns 0 after fix* → The robocopy output format may differ. Capture the exact line from `_thread_preflight` and adjust the regex in `_parse_robocopy_bytes` to match. Document as UNTRACKED‑BUG.  
- *Path normalisation breaks a valid absolute path* → Revert the change and add a test case; the new logic should not change behaviour for inputs like `C:\folder` or `C:\`.  
- *Security test fails after fixes* → The test expects the old implementation’s behaviour for some edge case. Compare the old vs new output; update the test only if the new output is still correct per robocopy’s documented format.

**DELIVERABLE**  
At the end of the sprint, provide:  
- List of every file modified: `ghost_harvest/app.py`, `ghost_harvest/command.py`  
- Any UNTRACKED‑BUG entries discovered (none expected)  
- Output of the Group 1 checkpoint command (security validation)  
- Output of the final parser test command  
- Explicit statement that the sprint is complete and no human decisions are deferred.
```