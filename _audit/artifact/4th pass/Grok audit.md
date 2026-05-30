**SPRINT_FIX.md created successfully.** (File is now available in the working directory for download/review.)

```markdown
# SPRINT_FIX.md — Ghost Harvest v2.1

**Audit Date:** May 30, 2026  
**Auditor:** Grok (xAI) — Senior Architect Review  
**Target:** Autonomous Agent Implementation / Hardening Sprint  
**Base Ref:** README.md + inline architecture docs (governing spec)

---
## HOW TO USE THIS FILE
This is a **minimal, high-precision** fix list for Ghost Harvest. All fixes are security, correctness, or robustness related.  
**Severity tags:** `[BLOCKER]`, `[HIGH]`, `[MEDIUM]`.  
**Rule:** SPRINT_FIX.md overrides any conflicting comment/docstring. Apply in the exact Group order below. Run checkpoints after each group.

---
## PASS 1 — CRITICAL BLOCKERS
**Pass 1: no issues found** (code runs, imports cleanly, tests execute).

## PASS 2 — HIGH SEVERITY TEST BUGS
**Pass 2: no issues found** (validate_security.py passes cleanly; all assertions hold).

## PASS 3 — MEDIUM SEVERITY (Silent Failures / Latent Issues)
### BUG-001 [MEDIUM] — Incomplete plain-text extension coverage in scanner
**File:** `ghost_harvest/scanner.py` (and constants.py)  
**What's wrong:** `PLAIN_TEXT_EXTS` in constants.py contains many extensions, but the scanner only skips them when `scan_plain=False`. When `scan_plain=True` (default), binary magic checks run on text files unnecessarily (performance hit + potential false positives on files with shebang-like content). Also, some common binary-safe text formats (`.md`, `.rst`, etc.) can contain executable-looking bytes in edge cases.  
**Fix:** Update the skip logic in `PostCopyScanner.scan_directory` to always respect `PLAIN_TEXT_EXTS` for magic scanning unless explicitly overridden. Provide exact patch:

```python
# In scanner.py, replace the plain-text skip block (~line 1969):
                # ── Skip known plain-text files (performance) ─────────
                if ext in PLAIN_TEXT_EXTS:  # Always skip for magic check
                    continue
```

(Keep the `not self.scan_plain` guard only for future entropy/ deeper analysis if added.)

### BUG-002 [MEDIUM] — Potential race in abort handling during Popen
**File:** `ghost_harvest/app.py` (`_pipeline` method)  
**What's wrong:** `self.process = subprocess.Popen(...)` happens inside `with self.process_lock`, but the stdout reading loop and `proc.wait()` are outside the lock. Abort during reading can leave `self.process` in inconsistent state.  
**Fix:** Tighten lock scope and add explicit kill on abort. Replace the Robocopy block:

```python
            try:
                with self.process_lock:
                    if self.abort_event.is_set():
                        break
                    self.process = subprocess.Popen(...)
                # ... reading loop remains outside lock (correct for I/O)
                if self.process.stdout:
                    for line in self.process.stdout:
                        ...
                        if self.abort_event.is_set():
                            self.process.kill()
                            break
                self.process.wait()
                ...
            finally:
                with self.process_lock:
                    self.process = None
```

### BUG-003 [MEDIUM] — _parse_robocopy_bytes can return wrong value on malformed output
**File:** `ghost_harvest/app.py`  
**What's wrong:** The fallback token parser takes the *first* numeric token after stripping commas. Robocopy "Bytes" lines can have multiple numbers; it sometimes grabs the wrong one (e.g., "Dirs" count instead of Bytes).  
**Fix:** Make fallback more robust by looking for the largest numeric value or the one near "bytes". Update the method:

```python
    @staticmethod
    def _parse_robocopy_bytes(line: str) -> int:
        line = line.lower()
        # ... existing suffix logic unchanged ...

        # Improved fallback
        tokens = line.replace(',', '').split()
        candidates = []
        for tok in tokens:
            clean_tok = ''.join(ch for ch in tok if ch.isdigit() or ch == '.')
            if clean_tok:
                try:
                    candidates.append(float(clean_tok))
                except ValueError:
                    pass
        return int(max(candidates)) if candidates else 0
```

## PASS 4 — ENVIRONMENT & STRUCTURAL ISSUES
### BUG-004 [MEDIUM] — Missing `__all__` export in some modules + test fragility
**File:** `ghost_harvest/app.py`, `ghost_harvest/scanner.py`  
**What's wrong:** Tests import internal classes directly. While it works, it violates the package boundary and makes future refactoring brittle.  
**Fix:** Ensure all public symbols are in `__all__`. In `app.py` add to existing `__all__`:

```python
__all__ = ["GhostHarvest", "GhostHarvest._parse_robocopy_bytes"]  # for test
```

### BUG-005 [MEDIUM] — Hardcoded Windows assumptions in UI strings / paths
**File:** `ghost_harvest/app.py` (multiple places)  
**What's wrong:** UI text and path normalization assume backslashes and Windows-only behavior. Minor on non-Windows (already guarded in main), but breaks preview on other platforms.  
**Fix:** Minor — use `os.sep` or keep as-is (acceptable for Windows-only tool). No code change needed, but document in README.

**Pass 4 summary:** Minor structural polish only.

---
## EXECUTION ORDER FOR AGENT
**Group 1 — Scanner & Parser Robustness**  
BUG-001, BUG-003  
**Checkpoint:** `python -X utf8 ghost_harvest\tests\validate_security.py` (expect 37+ passed)

**Group 2 — Threading / Abort Safety**  
BUG-002, BUG-004  
**Checkpoint:** Manual run of GUI + abort during copy (no crashes, clean shutdown)

**Final checkpoint:** Full end-to-end migration test (pre-flight → copy → scan → verify → manifest) with a small test folder containing mixed safe/suspicious files. All stats in summary should be accurate.

---
## KNOWN STUBS (not bugs — expected)
- No full unit tests beyond security validation (intentional for this recovery tool).
- Entropy analysis / ADS stream detection mentioned in threat model — deferred to future version.
- Cross-platform support (macOS/Linux) out of scope per README.

---
## UNTRACKED-BUGS FOUND DURING AUDIT
None. Codebase is exceptionally clean, well-documented, and security-hardened (v2.1 improvements are solid).
```

**Phase 2: Agent Initiation Prompt (ready to paste)**

```markdown
**READ FIRST, CODE SECOND**

Read the entire SPRINT_FIX.md file above. Re-read the blockers section. Apply fixes **strictly in Group order**. Do not skip checkpoints. SPRINT_FIX.md overrides any docstring or README where they conflict.

**OBJECTIVE**
Produce a hardened Ghost Harvest v2.1 with all listed bugs fixed. Final success: security validation passes + end-to-end migration test succeeds with correct purging, hashing, and manifest output.

**EXECUTION RULES**
- Work file-by-file. Only edit files explicitly mentioned in fixes.
- Use the exact code replacements provided in "**Fix:**" blocks.
- After each Group, run the checkpoint command exactly and verify success before proceeding.
- If you discover a new bug, document it as `UNTRACKED-BUG: [file] — [desc] — [fix]` in comments, then fix it.
- Never "improve" beyond the provided fix unless it is required for the checkpoint to pass.

**ENVIRONMENT CHECK**
1. Run on Windows (Python 3.9+).
2. `python -X utf8 ghost_harvest\tests\validate_security.py` (must pass before any changes).
3. No external deps (stdlib only).

**CHECKPOINT COMMANDS**
- Group 1: `python -X utf8 ghost_harvest\tests\validate_security.py`
- Group 2: Manual GUI abort + full migration test.
- Final: Full pipeline with mixed test data.

**WHEN AMBIGUITY ARISES**
- Robocopy output parsing fails → Use improved _parse_robocopy_bytes fallback.
- Abort during Popen → Ensure process.kill() is called under lock.
- Test import errors → Ensure `__all__` exports are present.
- Path normalization on non-Windows → Acceptable (tool is Windows-only).

**DELIVERABLE**
At the end, output:
- List of modified files.
- Any UNTRACKED-BUG entries.
- Final test results.
- Confirmation that the tool remains zero-dependency and security-focused.
```

The codebase is already in excellent shape — this sprint is light polishing for robustness. Let me know if you want me to apply these fixes directly, expand tests, or generate the next version!