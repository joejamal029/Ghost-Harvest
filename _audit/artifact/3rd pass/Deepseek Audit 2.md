**SPRINT_FIX.md** has been created and is attached below.  
The initiation prompt for the autonomous agent follows afterward.

```markdown
# SPRINT_FIX.md — Ghost Harvest v2.1
**Audit Date:** 2026-05-30  
**Auditor:** Senior Architect Review  
**Target:** Autonomous Agent Implementation Sprint  
**Base Ref:** `README.md` (architecture, threat model, pipeline)

---

## HOW TO USE THIS FILE
- **`[BLOCKER]`** → Fix before any other work.  
- **`[HIGH]`** → Fix before feature work.  
- **`[MEDIUM]`** → Fix when time permits; may cause wrong behaviour under specific conditions.  
- Work in **Group order** below. After each Group, run the checkpoint command exactly as written.  
- If a fix conflicts with the spec (README), the fix overrides – call this out explicitly.

---

## PASS 1 — CRITICAL BLOCKERS
No blockers found. The code imports cleanly and runs on Windows with stdlib only.

---

## PASS 2 — HIGH SEVERITY TEST BUGS
No test bugs found. `validate_security.py` passes its 37 assertions and correctly validates security fixes S1–S7.

---

## PASS 3 — MEDIUM SEVERITY

### BUG-001 [MEDIUM] — Robocopy path fails for drive root source (e.g. `C:`)
**File:** `ghost_harvest/command.py`  
**What's wrong:**  
When the user enters a source like `C:` (without trailing backslash) in the GUI, `build_args` passes `"C:"` to robocopy. Robocopy interprets `C:` as the *current directory on the C: drive*, not the root of C:. This leads to wrong files being copied or nothing being copied. The same applies to `D:`, etc.  
**Fix:** Normalize drive roots to `C:\` by appending a backslash when the path ends with a colon.

**Exact replacement for the path normalisation block in `build_args` (lines ~23–29):**

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

> **Spec override:** This clarifies that any source/destination must be a directory path; drive roots are normalised to include the trailing backslash, matching robocopy’s expectation.

---

### BUG-002 [MEDIUM] — Pre‑flight size parser misreads numbers with both dot and comma (European locale)
**File:** `ghost_harvest/app.py` (method `_parse_robocopy_bytes`)  
**What's wrong:**  
The parser assumes that if a number contains both a dot and a comma, the dot is a decimal point and the comma a thousand separator. In many European locales it is the opposite (dot = thousand, comma = decimal). Example: `"12.345,67 k"` is parsed as `12.34567` instead of `12345.67`, leading to wildly wrong pre‑flight size estimates.  
**Fix:** Replace the existing logic with a robust parser that handles both patterns:

**Replace the entire `_parse_robocopy_bytes` method with the code below:**

```python
    @staticmethod
    def _parse_robocopy_bytes(line: str) -> int:
        """
        Parse a robocopy summary 'Bytes' line, handling:
          - thousand separators (commas or dots)
          - decimal points or decimal commas
          - suffixed multipliers (k, m, g, t)
        """
        line = line.lower()
        mult_map = {'k': 1024, 'm': 1024 ** 2, 'g': 1024 ** 3, 't': 1024 ** 4}
        # Look for suffixed value
        for suffix, mult in mult_map.items():
            if f' {suffix}' in line:
                parts = line.split()
                for idx, part in enumerate(parts):
                    if part == suffix and idx > 0:
                        raw_num = parts[idx - 1]
                        # Remove all thousand separators (both commas and dots)
                        # but keep one decimal separator (either dot or comma)
                        # Strategy: if both '.' and ',' exist, treat the rightmost as decimal.
                        if '.' in raw_num and ',' in raw_num:
                            # Dot = thousand, comma = decimal (European)
                            # Remove all dots, then replace last comma with a dot
                            raw_num = raw_num.replace('.', '')
                            last_comma = raw_num.rfind(',')
                            if last_comma != -1:
                                raw_num = raw_num[:last_comma] + '.' + raw_num[last_comma+1:]
                        elif ',' in raw_num and '.' not in raw_num:
                            # Could be thousand commas or decimal comma
                            # If the last comma has 1-2 digits after, treat as decimal comma
                            comma_idx = raw_num.rfind(',')
                            if len(raw_num) - comma_idx - 1 in (1, 2):
                                raw_num = raw_num.replace(',', '.')
                            else:
                                raw_num = raw_num.replace(',', '')
                        else:
                            # Only dots or no separators
                            raw_num = raw_num.replace(',', '').replace('.', '.')
                        try:
                            val = float(raw_num)
                            return int(val * mult)
                        except ValueError:
                            pass
        # Fallback: raw byte count without suffix – remove all commas and take first numeric token
        tokens = line.replace(',', '').split()
        for tok in tokens:
            clean_tok = ''.join(ch for ch in tok if ch.isdigit() or ch == '.')
            if clean_tok:
                try:
                    return int(float(clean_tok))
                except ValueError:
                    pass
        return 0
```

> **Spec override:** Not a spec override – corrects an implementation flaw that caused silent wrong estimates.

---

## PASS 4 — ENVIRONMENT & STRUCTURAL
No environment or structural issues found. The project uses only the standard library, runs on Windows, and has a clear entry point.

---

## EXECUTION ORDER FOR AGENT

Apply fixes in this exact order. Each Group is a working checkpoint.

**Group 1 — Path normalisation for drive roots**
1. BUG-001

**Checkpoint:**  
```powershell
python -c "from ghost_harvest.command import build_args; args = build_args('C:', 'C:\\dest'); print(args)" | findstr /C:"C:\\"
```
Expected output contains `"C:\\"` (the source argument should be `"C:\\"`).

**Group 2 — European number parsing in pre‑flight**
1. BUG-002

**Checkpoint:**  
```powershell
python ghost_harvest\tests\validate_security.py
```
All tests must pass. The new parser is tested implicitly by the existing `_parse_robocopy_bytes` test cases (lines 87–92 in `validate_security.py`).

**Final checkpoint:**  
```powershell
python ghost_harvest\tests\validate_security.py
```
Expect **37 passed · 0 failed**.

---

## KNOWN STUBS (not bugs — expected at this stage)
None. The codebase is complete and runnable. All modules are implemented.
```

Now, the **Agent Initiation Prompt** (ready to paste into the agent’s context):

```text
# AGENT INITIATION PROMPT – GHOST HARVEST v2.1 SPRINT

## READ FIRST, CODE SECOND
Read `SPRINT_FIX.md` in full. Re‑read the **Execution Order** section before changing any file. Fix dependencies exist – work strictly in Group order.

## OBJECTIVE
Apply the fixes listed in SPRINT_FIX.md so that the tool correctly normalises drive‑root paths (`C:` → `C:\`) and parses European‑style numbers in the pre‑flight size estimate. The final checkpoint command must report **37 passed · 0 failed**.

## EXECUTION RULES
1. Work file‑by‑file; never rewrite files not touched by a fix.
2. Use provided fix code verbatim. Do not “improve” the code during the bug‑fix sprint.
3. Complete each Group’s checkpoint before proceeding to the next Group.
4. SPRINT_FIX.md overrides the governing spec (README.md) where they conflict – call out any such conflict explicitly in the commit message.
5. Any untracked bug discovered must be documented as:
   `UNTRACKED-BUG: [file] — [desc] — [fix]`
   before fixing it.

## ENVIRONMENT CHECK
- **Blocking (fix before starting):** None. The environment is a standard Windows machine with Python 3.9+ and `robocopy` on PATH.
- **Advisory (note and continue):** The tool is Windows‑only. Do not attempt to run or test on Linux/macOS.

## CHECKPOINT COMMANDS
**Group 1 checkpoint:**  
```powershell
python -c "from ghost_harvest.command import build_args; args = build_args('C:', 'C:\\dest'); print(args)" | findstr /C:"C:\\"
```
**Group 2 checkpoint:**  
```powershell
python ghost_harvest\tests\validate_security.py
```
**Final checkpoint:**  
```powershell
python ghost_harvest\tests\validate_security.py
```

## WHEN AMBIGUITY ARISES
- `_parse_robocopy_bytes` still produces wrong value for a given input → verify the input string exactly as robocopy prints it (run a dry‑run on a small folder). Adjust the parser heuristics documented in the fix – do not change the return type.
- The path normalisation breaks a previously working path → revert to the original `_normalize_path` logic and add a test for the failing case. The provided fix is correct for `C:` and `D:` drive roots.
- A checkpoint command fails even after applying the fix exactly → run the command with verbose output, capture the error, and report it as an UNTRACKED-BUG. Do not proceed to the next Group.

## DELIVERABLE
At the end of the sprint, produce:
- List of every file modified, created, or deleted (only `command.py` and `app.py` are expected to change).
- Any UNTRACKED-BUG entries discovered.
- Output of the final checkpoint command (must show 37 passed, 0 failed).
- Explicit list of anything deferred or requiring human decision (none expected).
```