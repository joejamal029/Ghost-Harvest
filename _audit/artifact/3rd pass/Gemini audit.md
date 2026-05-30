# Multi-Pass Codebase Audit & Sprint Plan

A comprehensive, four-pass architectural and security audit has been performed on the **GhostHarvest v2.1** codebase. Below is the structured `SPRINT_FIX.md` work order followed by the autonomous agent initiation prompt.

---

# SPRINT_FIX.md — GhostHarvest v2.1

**Audit Date:** May 30, 2026
**Auditor:** Senior AI Architect Review
**Target:** Autonomous Agent Implementation Sprint
**Base Ref:** `Ghost Harvest_llm.md`

---

## HOW TO USE THIS FILE

This document contains highly specific, actionable bug fixes categorized by severity. All fixes must be implemented verbatim without changing non-impacted files. SPRINT_FIX.md acts as the definitive authority; where these instructions diverge from previous implementation notes, this file wins.

---

## PASS 1 — CRITICAL BLOCKERS

### BUG-001 [BLOCKER] — Robocopy Switch Auto-Quoting Crash via Paths with Spaces

**File:** `ghost_harvest/command.py`
**What's wrong:** When log saving is enabled and the destination path contains a space (e.g., `C:\Clean Workspace`), `args.append(f"/LOG+:{log_path}")` creates an argument with an embedded space. Because `shell=False`, `subprocess.Popen` automatically wraps the entire list element in double quotes, resulting in `"/LOG+:C:\Clean Workspace\_GhostHarvest_log.txt"`. Robocopy’s command-line parser fails to recognize this as a valid switch because the quote precedes the forward slash, causing Robocopy to crash instantly with an invalid parameter error.
**Fix:** Remove Robocopy-side logging switches entirely and move logging responsibility directly to the Python runtime. This completely eliminates the switch-quoting problem and solves the GUI log freezing issue simultaneously.

Modify `build_args` in `ghost_harvest/command.py` to remove the log switch block:

```python
# REMOVE THIS BLOCK FROM ghost_harvest/command.py:
# if save_log and not dry_run:
#     log_path = str(Path(dest) / "_GhostHarvest_log.txt")
#     args.append(f"/LOG+:{log_path}")

```

---

## PASS 2 — HIGH SEVERITY TEST BUGS

### BUG-002 [HIGH] — Reversed Infinite Recursion Guard

**File:** `ghost_harvest/app.py`
**What's wrong:** The destination-inside-source loop check in `_start()` is logically inverted. It checks `if dest_path in src_path.parents or dest_path == src_path:`. This evaluates whether the *source* directory is inside the *destination* folder. If a user sets a destination folder inside an infected source directory (e.g., migrating `E:\` into `E:\CleanWorkspace`), the guard fails to trigger, causing Robocopy to recursively copy the destination folder into itself until disk space is fully exhausted.
**Fix:** Reverse the parent directory lookup logic to accurately check if the destination resides inside the source folder.

Replace lines 343–348 in `ghost_harvest/app.py` with:

```python
        # Corrected destination-inside-source guard (BUG-002)
        dest_path = Path(dest).resolve()
        for src in settings["queue"]:
            src_path = Path(src).resolve()
            if src_path in dest_path.parents or dest_path == src_path:
                self._log(f"⚠  Destination '{dest}' is inside source '{src}' – would cause infinite recursion. Aborted.\n", "bad")
                self._finish()
                return

```

---

## PASS 3 — SILENT FAILURES

### BUG-003 [MEDIUM] — Missing Console Log Streaming (GUI Freezing)

**File:** `ghost_harvest/app.py`
**What's wrong:** Because Robocopy was capturing log outputs via `/LOG+`, standard output streaming was suppressed. Now that BUG-001 removes the native switch, we must implement Python-side asynchronous log file mirroring inside the background worker pipeline thread to ensure the UI window updates smoothly in real time while archiving data.
**Fix:** Update `_pipeline` and `_thread_preflight` to handle file logging explicitly as lines stream from `stdout`.

In `ghost_harvest/app.py`, update the process execution block inside `_pipeline` to mirror output to the log file:

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

### BUG-004 [MEDIUM] — Inverted Integrity Report Metrics

**File:** `ghost_harvest/hasher.py`
**What's wrong:** In `ParallelHashVerifier.verify`, the filesystem walker iterates across the destination folder. If a file exists in the destination workspace but is absent from the source drive, the metric `missing` is incremented. At completion, the logger outputs: `f"... {missing} source-only\n"`. This is incorrect: files found in the destination but missing from the source are **destination-only** artifacts. True source-only items are completely omitted from the scan.
**Fix:** Update the console reporting message to reflect the precise state of the filesystem.

Replace line 112 in `ghost_harvest/hasher.py` with:

```python
        cb(
            f"  {total_hashed:,} files hashed → {ok:,} OK · {fail} mismatched · "
            f"{missing} destination-only\n",
            tag,
        )

```

---

## PASS 4 — ENVIRONMENT & STRUCTURAL

### BUG-005 [MEDIUM] — Workspace Collisions on Source Drive Roots

**File:** `ghost_harvest/app.py`
**What's wrong:** In `_pipeline` and `_thread_preflight`, subdirectories are matched using `Path(src).name`. When a user chooses a drive root (e.g., `D:\`), `Path("D:\\").name` evaluates to an empty string `""`. This maps `folder_dest` straight to the parent workspace directory, causing overlapping drive migrations to mingle messy contents into a single workspace root.
**Fix:** Add a fallback parameter checking for empty path name variables, using the root drive letter as a clean identifier.

Replace line 210 in `ghost_harvest/app.py` (and the corresponding line in `_thread_preflight` line 109) with:

```python
            src_name = Path(src).name or Path(src).drive.replace(":", "").strip()
            if not src_name:
                src_name = "DriveRoot"
            folder_dest = str(Path(dest) / src_name)

```

---

## EXECUTION ORDER FOR AGENT

Apply all fixes in sequential phases. Do not move to the next group until the current group's validation checkpoint passes completely.

**Group 1 — Execution Safety & Command Hardening**

* Apply: `BUG-001`, `BUG-002`, `BUG-003`
**Checkpoint:** Open a terminal and run the local regression test suite to ensure syntax validity:

```powershell
python -X utf8 ghost_harvest\tests\validate_security.py

```

**Group 2 — Structural Data Matching & Reports**

* Apply: `BUG-004`, `BUG-005`
**Checkpoint:** Launch the main entry point to ensure the application frame handles dry runs correctly:

```powershell
python main.py

```

---

## KNOWN STUBS

* `ghost_harvest/theme.py`: Standard layout style configurations (Catppuccin dark mode skin). No functionality additions required here.

---

# AGENT INITIATION PROMPT

```markdown
READ FIRST, CODE SECOND:
Read the repository file SPRINT_FIX.md entirely before making any structural changes to the code. You must execute fixes according to the precise order outlined in the "EXECUTION ORDER FOR AGENT" block.

OBJECTIVE:
Resolve path-handling logic bugs, correct the inverted thread boundary conditions, and fix command parameter quoting errors across the codebase. The task is complete when `validate_security.py` runs successfully and `main.py` opens without raising runtime script errors.

EXECUTION RULES:
1. Make targeted adjustments file-by-file. Avoid large-scale rewrites of clean modules.
2. Inject fix blocks precisely as written inside SPRINT_FIX.md.
3. Verify changes at each Group Checkpoint using the provided commands before processing downstream steps.
4. SPRINT_FIX.md holds absolute authority over generic documentation rules or architectural assumptions.
5. If an undocumented bug appears during compilation, log it inside the final summary using the format: `UNTRACKED-BUG: [file] — [desc] — [fix]` before applying corrections.

CHECKPOINT COMMANDS:
* Group 1: `python -X utf8 ghost_harvest\tests\validate_security.py`
* Group 2: `python main.py`

WHEN AMBIGUITY ARISES:
- Symptom: Robocopy errors out with exit code 16 → Diagnosis: Parameter parsing failure due to string quoting issues → Resolution: Verify that BUG-001 has been applied and all Robocopy-side `/LOG` parameters have been cleared.
- Symptom: Main GUI windows freeze or become unresponsive during a deep file copy → Diagnosis: Standard I/O block over the master loop → Resolution: Ensure log stream loops use the `self.after(0, ...)` wrapper correctly as configured in BUG-003.
- Symptom: Flash drive paths dump contents haphazardly into folder parents → Diagnosis: Empty folder name matching on drive letters → Resolution: Verify the fallback drive letter substitution rules applied via BUG-005.

DELIVERABLE:
Provide a clear list of altered file paths, a copy of the diagnostic execution output string, and confirm that all 5 key bugs have been resolved.

```