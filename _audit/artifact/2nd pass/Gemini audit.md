# Code Audit & Sprint Plan: Ghost Harvest

I have completed a thorough, multi-pass architectural and code-level audit of the **Ghost Harvest** codebase. The layout is clean and modular, and the implementation exhibits an exceptional understanding of threading models and security boundary protection (such as mitigating command injection via `shell=False`).

However, a few critical logical flaws and reporting mismatches have been uncovered—most notably a trailing backslash handling bug that inadvertently corrupts path arguments passed to `robocopy`.

Below is the structured **SPRINT_FIX.md** work order, followed by the **Agent Initiation Prompt** to hand off these fixes seamlessly to an autonomous coding agent.

---

```markdown
# SPRINT_FIX.md — Ghost Harvest
**Audit Date:** May 29, 2026
**Auditor:** Senior Architect Review
**Target:** Autonomous Agent Implementation Sprint
**Base Ref:** Ghost Harvest_llm.md (Codebase Snapshot)

---

## HOW TO USE THIS FILE
This document contains the precise work order for the Ghost Harvest hardening sprint. All entries include exact, production-ready code replacements to remove any ambiguity for execution. The agent must process these groups sequentially and execute the associated checkpoint commands before advancing.

---

## PASS 1 — CRITICAL BLOCKERS
*Pass 1 Scan Complete: No hard compilation or import-level blockers found.*

---

## PASS 2 — HIGH SEVERITY TEST BUGS
*Pass 2 Scan Complete: No existing test failures or test suite regressions detected.*

---

## PASS 3 — SILENT FAILURES & LOGICAL CORRUPTIONS

### BUG-001 [HIGH] — Trailing Backslash Path Corruption in Command Builder
**File:** `ghost_harvest/command.py`
**What's wrong:** The command builder manually appends an extra backslash (`\\`) to source and destination paths if they already end with one. This was originally designed to prevent quote-escaping issues on Windows. However, because the application uses `subprocess.Popen(shell=False)`, Python's internal `subprocess.list2cmdline` helper **already** handles trailing backslashes perfectly when compiling arguments. By manually adding an extra backslash, paths like `C:\Source\` are converted to `C:\Source\\`. If the path contains spaces, `list2cmdline` then doubles it to four backslashes (`\\\\`), which maps to a literal trailing double-backslash (`\\`) at runtime. This causes `robocopy` to reject the parameter or fail to locate the path correctly.
**Fix:** Remove the redundant and damaging manual trailing backslash manipulation from `build_args`.

Replace lines 26–31 in `ghost_harvest/command.py`:
```python
    # Normalize paths to prevent trailing backslash quote escaping bugs on Windows
    if source.endswith("\\") and not source.endswith(":\\"):
        source += "\\"
    if dest.endswith("\\") and not dest.endswith(":\\"):
        dest += "\\"

```

With:

```python
    # Path normalization for trailing backslashes is handled automatically 
    # by subprocess.Popen(shell=False) via list2cmdline. Manual padding removed.

```

---

### BUG-002 [MEDIUM] — Pre-flight Metrics Representation Mismatch

**File:** `ghost_harvest/app.py`
**What's wrong:** In `_thread_preflight`, the UI summary panel shows a `Files to copy` metric but populates it with `total_files` (the total number of files found in the source directory). This includes all files that match the destination criteria exactly and will be skipped by `robocopy`. This creates a misleading estimation for the user prior to running the migration pipeline.
**Fix:** Update the text display block in `_thread_preflight` to break down both the absolute files found and the actual subset of files that require active copying.

Replace lines 405–417 in `ghost_harvest/app.py`:

```python
        summary = (
            f"\n{'─' * 52}\n"
            f"  PRE-FLIGHT SUMMARY\n"
            f"{'─' * 52}\n"
            f"  Folders queued   :  {len(settings['queue'])}\n"
            f"  Files to copy    :  {total_files:,}\n"
            f"  Estimated size   :  {size_str}\n"
            f"  Already at dest  :  {skipped:,}  (will be skipped)\n"
            f"{'─' * 52}\n\n"
        )

```

With:

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

### BUG-003 [LOW] — Security Summary Tag Ignores Double-Extension Purges

**File:** `ghost_harvest/app.py`
**What's wrong:** In the final step of the migration pipeline, the logging tag condition for the `SECURITY SUMMARY` box only marks the status as `"warn"` if `stats["hash_fail"] > 0` or `stats["blocked_magic"] > 0`. It completely ignores `stats["double_ext"]`. If malicious files are intercepted and purged solely due to double-extension rules (e.g., `invoice.pdf.exe`), the summary box is painted green (`"good"`) instead of amber/red (`"warn"`), masking vital threat indicators.
**Fix:** Update the summary tagging logic to account for double-extension purges.

Replace line 557 in `ghost_harvest/app.py`:

```python
            tag = "good" if stats["hash_fail"] == 0 and stats["blocked_magic"] == 0 else "warn"

```

With:

```python
            tag = "good" if stats["hash_fail"] == 0 and stats["blocked_magic"] == 0 and stats["double_ext"] == 0 else "warn"

```

---

## PASS 4 — ENVIRONMENT & STRUCTURAL

*Pass 4 Scan Complete: Package architecture and dependency constraints conform to specification layout rules.*

---

## PASS 5 — CRITICAL IMPROVEMENTS

### IMP-001 [IMPROVEMENT] — Pre-flight Summary Parsing Safe Guard

**File:** `ghost_harvest/app.py`
**What's wrong:** While the log scraping logic in `_thread_preflight` effectively extracts metrics from `robocopy`'s summary matrix using text token verification, any unforeseen platform localization shift or formatting truncation could cause an unhandled `IndexError` or `ValueError` during integer casting.
**Fix:** Wrap the token value extraction step in a local `try...except` block to log a degradation notice without crashing the background pre-flight thread.

Replace lines 397–402 in `ghost_harvest/app.py`:

```python
                # Extract metrics from stable summary arrays sequentially
                if len(summary_rows) >= 3:
                    f_parts = summary_rows[1].split(":")[1].split()
                    total_files += int(f_parts[0].replace(",", ""))
                    skipped += int(f_parts[2].replace(",", ""))
                    total_bytes += self._parse_robocopy_bytes(summary_rows[2])

```

With:

```python
                # Extract metrics from stable summary arrays sequentially
                if len(summary_rows) >= 3:
                    try:
                        f_parts = summary_rows[1].split(":")[1].split()
                        total_files += int(f_parts[0].replace(",", ""))
                        skipped += int(f_parts[2].replace(",", ""))
                        total_bytes += self._parse_robocopy_bytes(summary_rows[2])
                    except (IndexError, ValueError) as parse_err:
                        self.after(0, self._log, f"  ⚠  Pre-flight metric parsing notice: {parse_err}\n", "warn")

```

---

## EXECUTION ORDER FOR AGENT

Apply fixes in this exact sequence to manage verification integrity.

**Group 1 — Command Argument Engine Resolution**

* Apply: `BUG-001`
* **Checkpoint:** Run the diagnostic test suite to ensure no structural formatting break occurs:
`python -X utf8 ghost_harvest\tests\validate_security.py`

**Group 2 — User Interface Presentation Hardening**

* Apply: `BUG-002`, `BUG-003`, `IMP-001`
* **Checkpoint:** Validate successful compilation and script startup:
`python main.py` (Verify GUI renders successfully without syntax/runtime configuration issues)

**Final Checkpoint:** `python -X utf8 ghost_harvest\tests\validate_security.py`

---

## KNOWN STUBS (Not Bugs)

* No functional components are currently subbed out; the core feature ecosystem is fully implemented as written.

```

---

## Phase 2: Agent Initiation Prompt

Paste the block below directly into your autonomous coding agent's initialization context to begin executing the sprint immediately.

```text
### READ FIRST, CODE SECOND
Read through SPRINT_FIX.md entirely before making modifications to any system files. Pay strict attention to the structural dependencies outlined in the Execution Order. You must execute all adjustments on a file-by-file basis without rewriting unrelated components.

### OBJECTIVE
Eliminate the path corruption bug introduced by manual trailing backslash handling in the command builder, resolve metrics layout discrepancies during pre-flight executions, and fix visual log summary vulnerabilities. The sprint concludes successfully when the full validation script passes with zero exceptions.

### EXECUTION RULES
1. Modify files incrementally. Never rewrite whole blocks or entire files that are unaffected by a fix order.
2. Use the provided replacement code segments verbatim. Do not alter naming variables, styles, or logic streams unless an explicit bug is identified.
3. Complete each individual group's checkpoint verification check before proceeding to modifications in subsequent groups.
4. If an unmonitored bug is observed during execution, document it strictly using this format: `UNTRACKED-BUG: [file] — [desc] — [fix]` before applying adjustments.

### CHECKPOINT COMMANDS
- **Group 1 Checkpoint:** `python -X utf8 ghost_harvest\tests\validate_security.py`
- **Group 2 Checkpoint:** `python main.py`
- **Final Integration Checkpoint:** `python -X utf8 ghost_harvest\tests\validate_security.py`

### WHEN AMBIGUITY ARISES
- Robocopy outputs non-zero exit codes (1–7) → This indicates operational copy variances (e.g., extra files or matching skips), not an application failure. Do not modify `ROBOCOPY_SUCCESS_CODES` mapping ranges.
- `Path.relative_to` throws `ValueError` during verification loops → This arises if target paths mismatch root scopes. The verifier safely catches this and skips; allow this mechanism to execute without altering standard path rules.
- Pre-flight text scraper receives less than 3 filtered summary rows → This indicates an unpopulated or missing folder root. The system defaults to safe zero-metrics and continues execution gracefully via structural bounds guards.

### DELIVERABLES
Produce an implementation summary containing:
1. A clear list of every file modified during the execution sprint.
2. The exact command lines executed for verification checks.
3. Any `UNTRACKED-BUG` entries caught and resolved out-of-scope.
4. Final diagnostic reports showing validation execution success status.

```