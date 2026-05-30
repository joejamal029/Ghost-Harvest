```text
READ FIRST, CODE SECOND
Read SPRINT_FIX.md in full, then re-read the blockers section (though there are none), before making any file changes.
Understand that fix dependencies exist and the execution order at the bottom of the file is mandatory: 
  Group 1 must be completed and pass its checkpoint before Group 2, and so on.

OBJECTIVE
Successfully apply all fixes and improvements in SPRINT_FIX.md, culminating in the final checkpoint command:
  `python -X utf8 ghost_harvest\tests\validate_security.py`
  resulting in 37 passed tests and 0 failed tests.

EXECUTION RULES
1. Work file-by-file; never rewrite files not touched by a fix.
2. Use the exact fix code provided in SPRINT_FIX.md; do not "improve" or refactor beyond the specified changes.
3. Complete each Group's checkpoint before proceeding to the next Group.
4. SPRINT_FIX.md overrides the governing spec (README.md) where they conflict; no such conflicts exist in this audit.
5. If you discover an untracked bug during the sprint, document it as `UNTRACKED-BUG: [file] — [desc] — [fix]` in your notes before fixing it.

CHECKPOINT COMMANDS
Group 1 — Fix test bug
  Checkpoint: `python -X utf8 ghost_harvest\tests\validate_security.py`
Group 2 — Fix silent failures and environment issues
  Checkpoint: `python -X utf8 ghost_harvest\tests\validate_security.py`
Group 3 — Apply improvement
  Checkpoint: `python -X utf8 ghost_harvest\tests\validate_security.py`
Final checkpoint: `python -X utf8 ghost_harvest\tests\validate_security.py`

WHEN AMBIGUITY ARISES
- The test suite fails after applying a fix → Revert the fix and re-examine the SPRINT_FIX.md instructions for that bug.
- The pre-flight scan shows incorrect size estimates after applying BUG-005 → Verify that the ANSI escape stripping is working correctly by checking a sample robocopy output line.
- The disk usage label shows "Unable to check disk space" unexpectedly → Verify that the destination path is valid and accessible.

DELIVERABLE
- List of every file modified, created, or deleted:
  * Modified: ghost_harvest/tests/validate_security.py (BUG-002)
  * Modified: ghost_harvest/app.py (BUG-003, BUG-004, BUG-005, IMPROVEMENT-001)
- Any UNTRACKED-BUG entries discovered: None
- Final pytest/test result: 37 passed, 0 failed
- Explicit list of anything deferred or requiring human decision: None
```

--- 
# SPRINT_FIX.md — Ghost Harvest
**Audit Date:** 2024-06-15
**Auditor:** Senior Architect Review
**Target:** Autonomous Agent Implementation Sprint
**Base Ref:** README.md (§ references below point there)

---
 
## HOW TO USE THIS FILE
This file contains a prioritized work order for fixing bugs and implementing improvements.
Severity tags indicate the order of fixes: [BLOCKER] must be fixed first, then [HIGH], [MEDIUM], and [IMPROVEMENT] last.
Fixes within a group can be applied in any order unless dependencies are noted.
The governing spec is the README.md; where code diverges from the README, the README wins unless a spec override is noted.
 
---
 
## PASS 1 — CRITICAL BLOCKERS
Pass 1: no issues found
 
---
 
## PASS 2 — HIGH SEVERITY TEST BUGS
### BUG-002 [HIGH] — Test bug in validate_security.py: flawed check for bare excepts
**File:** ghost_harvest/tests/validate_security.py
**What's wrong:** The first loop for S5 uses an incorrect condition to check for bare excepts, which will fail even if there are no bare excepts.
**Fix:** Remove the flawed loop (lines 55-63 in the provided snapshot) and keep the second loop (lines 66-72) that correctly checks for bare excepts by scanning for lines containing exactly "except:".
 
---
 
## PASS 3 — MEDIUM SEVERITY
### BUG-003 [MEDIUM] — Silent failure: manifest write failure not logged
**File:** ghost_harvest/app.py
**What's wrong:** If the manifest cannot be written (e.g., due to permissions), the function `write_manifest` returns `None`, but the app does not log an error, leaving the user unaware.
**Fix:** In the `_pipeline` method, after calling `write_manifest`, if `mpath` is `None`, log an error message: `\n⚠  Failed to write blocked manifest.\n` with the "warn" tag.
 
---
 
### BUG-004 [MEDIUM] — Environment issue: disk usage check fails silently
**File:** ghost_harvest/app.py
**What's wrong:** The `_update_space` function catches `OSError` and `ValueError` and does nothing, leaving the space label blank if there is an error (e.g., invalid path, inaccessible drive). The user is not informed of the issue.
**Fix:** In the `_update_space` method, in the `except` block, set the label to an error message (e.g., `"Unable to check disk space"`) and use the "Warn.TLabel" style.
 
---
 
### BUG-005 [MEDIUM] — Silent failure: ANSI escape codes in robocopy output break pre-flight byte count
**File:** ghost_harvest/app.py
**What's wrong:** The robocopy output may contain ANSI escape codes, which are not stripped before being passed to `_parse_robocopy_bytes`. This can cause the byte count parsing to fail silently (returning 0) and lead to incorrect size estimates in the pre-flight.
**Fix:** Strip ANSI escape codes from each line of robocopy output in the `_thread_preflight` method before logging and before parsing. Add a helper function `strip_ansi` using a regular expression to remove ANSI escape sequences.
 
---
 
## PASS 4 — ENVIRONMENT & STRUCTURAL
Pass 4: no issues found
 
---
 
## PASS 5 — IMPROVEMENTS
### IMPROVEMENT-001 [IMPROVEMENT] — Force dry-run in pre-flight by settings, not by appending "/L"
**File:** ghost_harvest/app.py
**What's improvement:** The pre-flight currently forces dry-run by appending "/L" to the robocopy args if not present. This is a workaround that might break if the args already contain "/L" in an unexpected way. Instead, we should set the dry_run setting to True in the settings dictionary passed to `_current_args`.
**Fix:** In the `_preflight` method, when building the settings dictionary, set `"dry_run": True`.
 
---
 
## EXECUTION ORDER FOR AGENT
 
Apply fixes in this exact order. Each Group is a working checkpoint.
 
**Group 1 — Fix test bug**
[1] BUG-002
Checkpoint: `python -X utf8 ghost_harvest\tests\validate_security.py`
 
**Group 2 — Fix silent failures and environment issues**
[2] BUG-003
[3] BUG-004
[4] BUG-005
Checkpoint: `python -X utf8 ghost_harvest\tests\validate_security.py`
 
**Group 3 — Apply improvement**
[5] IMPROVEMENT-001
Checkpoint: `python -X utf8 ghost_harvest\tests\validate_security.py`
 
**Final checkpoint:** `python -X utf8 ghost_harvest\tests\validate_security.py`
 
---
 
## KNOWN STUBS (not bugs — expected at this stage)
There are no known stubs in this codebase; all functionality is implemented.
```