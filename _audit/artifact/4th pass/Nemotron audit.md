# SPRINT_FIX.md — Ghost Harvest
**Audit Date:** 2024-06-15
**Auditor:** Senior Architect Review
**Target:** Autonomous Agent Implementation Sprint
**Base Ref:** README.md (§ references below point there)

---

## HOW TO USE THIS FILE
This file contains bug fixes grouped by severity. Apply fixes in the order of the groups. 
Each group has a checkpoint command to verify the fixes. 
Fixes in later groups may depend on earlier groups, so do not reorder.

---

## PASS 1 — CRITICAL BLOCKERS
Pass 1: no issues found

---

## PASS 2 — HIGH SEVERITY TEST BUGS
### BUG-001 [HIGH] — Test for elevate() uses incorrect string to check for quoted script path
**File:** ghost_harvest/tests/validate_security.py
**What's wrong:** The test for [S3] uses an undefined variable `script` in the string it is checking for, causing a NameError when the test runs.
**Fix:** Replace the line:
    check("elevate() uses quoted script path parameter", "f'\"{script}\"'" in src)
  with:
    check("elevate() uses quoted script path parameter", 'f\'"{script}\"'" in src)
---

## PASS 3 — MEDIUM SEVERITY
### BUG-002 [MEDIUM] — _current_args uses UI state instead of settings for flags when settings is provided
**File:** ghost_harvest/app.py
**What's wrong:** In the `_current_args` method, when the `settings` argument is provided, the method uses the current UI state (via `self.block_exts.get()`, etc.) for the flags `block_exts`, `skip_bloat`, `custom_xd`, and `save_log` instead of using the values from the `settings` dictionary. This causes the preflight to potentially show an incorrect command if the user changes the UI during the preflight.
**Fix:** In the `if settings:` branch of `_current_args`, replace:
        block_exts=self.block_exts.get(),
        skip_bloat=self.skip_bloat.get(),
        custom_xd=self.custom_xd.get().strip(),
        save_log=self.save_log.get(),
  with:
        block_exts=settings["block_exts"],
        skip_bloat=settings["skip_bloat"],
        custom_xd=settings["custom_xd"],
        save_log=settings["save_log"],
---

## PASS 4 — ENVIRONMENT & STRUCTURAL
Pass 4: no issues found

---

## EXECUTION ORDER FOR AGENT
Apply fixes in this exact order. Each Group is a working checkpoint.

**Group 1 — Critical Blockers**
[none]
**Checkpoint:** `echo "No blockers to fix"`

**Group 2 — High Severity Test Bugs**
[BUG-001]
**Checkpoint:** `python -X utf8 ghost_harvest\tests\validate_security.py`

**Group 3 — Medium Severity**
[BUG-002]
**Checkpoint:** `python -X utf8 ghost_harvest\tests\validate_security.py`

**Final checkpoint:** `python -X utf8 ghost_harvest\tests\validate_security.py`
Expected result: 37 passed · 0 failed

---

## KNOWN STUBS (not bugs — expected at this stage)
None
```markdown
READ FIRST, CODE SECOND
Read SPRINT_FIX.md in full, then re-read the blockers section (which states no issues found), before making any file changes. 
Fix dependencies exist and the execution order at the bottom of the file is mandatory: complete Group 1 (no fixes) before Group 2, Group 2 before Group 3, and Group 3 before the final checkpoint.

OBJECTIVE
Run the test suite and achieve 37 passed tests with 0 failed by executing the final checkpoint command: `python -X utf8 ghost_harvest\tests\validate_security.py`.

EXECUTION RULES
1. Work file-by-file; never rewrite files not touched by a fix
2. Use provided fix code verbatim during the bug-fix sprint; don't "improve" it
3. Complete each Group's checkpoint before proceeding to the next Group
4. SPRINT_FIX.md overrides the governing spec where they conflict; call out any such conflicts explicitly in the SPRINT_FIX.md and reinforce them here (no conflicts found in this audit)
5. Any untracked bug discovered must be documented as `UNTRACKED-BUG: [file] — [desc] — [fix]` before fixing it

CHECKPOINT COMMANDS
Group 1 — Critical Blockers: `echo "No blockers to fix"`
Group 2 — High Severity Test Bugs: `python -X utf8 ghost_harvest\tests\validate_security.py`
Group 3 — Medium Severity: `python -X utf8 ghost_harvest\tests\validate_security.py`
Final checkpoint: `python -X utf8 ghost_harvest\tests\validate_security.py`

WHEN AMBIGUITY ARISES
- Test fails with NameError: name 'script' is not defined in validate_security.py → This is the test bug BUG-001 → Fix the test by changing the string in the check for [S3] to use 'f\'"{script}\"'" instead of "f'\"{script}\"'".
- Preflight shows incorrect command when UI is changed during preflight → This is the silent failure BUG-002 → In the _current_args method, when settings is provided, use the settings dictionary for the flags block_exts, skip_bloat, custom_xd, and save_log.
- Unclear whether a fix is a blocker or not → Refer to the severity tags in SPRINT_FIX.md: [BLOCKER] prevents compile, import, or test execution; [HIGH] causes test or runtime failure; [MEDIUM] is silent corruption. If in doubt, treat as [HIGH] if it causes a test failure, [MEDIUM] if it is silent.

DELIVERABLE
- Modified files: 
  ghost_harvest/tests/validate_security.py
  ghost_harvest/app.py
- Created files: None
- Deleted files: None
- UNTRACKED-BUG entries: None
- Final test result: 37 passed · 0 failed
- Deferred items: None
```