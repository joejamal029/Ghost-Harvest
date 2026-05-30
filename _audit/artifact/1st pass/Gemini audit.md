```python
sprint_fix_content = """# SPRINT_FIX.md — Ghost Harvest v2.1
**Audit Date:** May 29, 2026
**Auditor:** Senior Architect Review
**Target:** Autonomous Agent Implementation Sprint
**Base Ref:** README.md

---

## HOW TO USE THIS FILE
This file serves as a strict, sequential work order for correcting critical compilation blockers, test suite vulnerabilities, and silent engineering defects in Ghost Harvest v2.1. All modifications must be applied verbatim following the specified execution groups. SPRINT_FIX.md overrides any conflicting architectural specifications.

---

## PASS 1 — CRITICAL BLOCKERS

### BUG-001 [BLOCKER] — Syntax Error (Trailing Brace) in System Utilities
**File:** `ghost_harvest/utils.py`
**What's wrong:** A trailing curly brace `}` exists on line 73 at the end of the `format_size` function block. This throws an immediate `SyntaxError: invalid syntax` upon importing or executing the module, blocking the application from booting and rendering the security validation test suite completely non-executable.
**Fix:** Remove the trailing brace from the file completely.


```

```text
SPRINT_FIX.md generated successfully.


```


python
def format_size(b: int) -> str:
"""Human-readable file size string."""
if b >= 1024  3:
return f"{b / 1024  3:.2f} GB"
if b >= 1024  2:
return f"{b / 1024  2:.1f} MB"
if b >= 1024:
return f"{b / 1024:.1f} KB"
return f"{b:,} B"

```

### BUG-002 [BLOCKER] — Trailing Backslash Argument Escaping in Robocopy CLI Spawning
**File:** `ghost_harvest/command.py`
**What's wrong:** If a user provides a source or destination path with a trailing backslash (e.g., `C:\\Infected Data\\`), Python's `subprocess.Popen` serialization escapes the trailing double quote (`\\"`). This causes Robocopy to interpret the next CLI flag as part of the directory path string, collapsing the argument sequence and causing immediate fatal parsing failures or missing directory errors inside the underlying system process.
**Fix:** Append a duplicating backslash to any paths that terminate with a single backslash before passing them to the argument builder array. This ensures Windows command line parsers interpret it as a literal trailing backslash instead of an escaped quote character.

```python
def build_args(
    source: str,
    dest: str,
    threads: int = 16,
    *,
    restartable: bool = True,
    dry_run: bool = False,
    block_exts: bool = True,
    skip_bloat: bool = True,
    custom_xd: str = "",
    save_log: bool = True,
) -> list[str]:
    # Normalize paths to prevent trailing backslash quote escaping bugs on Windows
    if source.endswith("\\\\"):
        source += "\\\\"
    if dest.endswith("\\\\"):
        dest += "\\\\"

    args: list[str] = [
        "robocopy",
        source,
        dest,
        "/E",               # recurse including empty dirs
        "/COPY:DAT",        # Data + Attributes + Timestamps (no ADS)
        f"/MT:{threads}",   # multi-threaded
    ]
    # ... remaining code remains identical

```

---

## PASS 2 — HIGH SEVERITY TEST BUGS

### BUG-003 [HIGH] — Security Regression Test Asserting Local Scoped Dummies

**File:** `ghost_harvest/tests/validate_security.py`
**What's wrong:** The extension parsing test under audit checkpoint `[S2]` assigns local variables `correct` and `broken` using standard string functions and then checks if `correct == ext[2:]`. It does *not* invoke or assert against the real codebase matching function `has_double_extension` located inside `scanner.py`. The test suite yields a false-positive success rate while masking regressions inside the production logic.
**Fix:** Rewrite the test block to import and directly challenge the production implementation inside `scanner.py`.

```python
# S2: removeprefix vs lstrip
print("\\n[S2] Extension parsing (removeprefix fix)")
from ghost_harvest.scanner import has_double_extension
blocked_set = {"wsf", "scr", "msi", "js", "exe", "ps1"}

check("Double extension detected correctly", has_double_extension(Path("report.pdf.exe"), blocked_set) == True)
check("Single dangerous extension bypassed by double-ext rule", has_double_extension(Path("report.exe"), blocked_set) == False)
check("Safe double extension bypassed", has_double_extension(Path("report.txt.pdf"), blocked_set) == False)

```

---

## PASS 3 — MEDIUM SEVERITY (SILENT FAILURES)

### BUG-004 [MEDIUM] — Locale-Dependent Hardcoding of Robocopy Output Logs

**File:** `ghost_harvest/app.py`
**What's wrong:** Methods `_thread_preflight` and `_parse_robocopy_bytes` parse standard output using hardcoded English keywords (`"Total"`, `"Copied"`, `"Skipped"`, `"Files"`, `"Bytes"`). When executed on localized non-English Windows machines (e.g., German, French, Spanish), Robocopy produces localized console outputs. The app silently fails to match the labels, yielding a corrupted pre-flight summary with zero counts.
**Fix:** Transition parsing architecture to look for invariant row-structural signatures. The summary values can be pulled by validating lines that contain exactly 6 numeric columns following a colon delimiter, tracking the chronological table row indexes (Dirs=0, Files=1, Bytes=2).

```python
# Inside _thread_preflight parsing loop:
if ":" in line:
    parts = line.split(":")
    nums = [x.replace(",", "") for x in parts[1].split() if x.replace(",", "").isdigit()]
    if len(nums) == 6:
        # Match rows chronologically based on Robocopy standard summary structure
        label = parts[0].strip().lower()
        if "file" in label or len(nums) >= 6 and total_files == 0:  # Locale fallback tracking
            if total_files == 0:  # Assuming order: Dirs first, then Files
                # If we can't safely guess, track order or inspect positions
                pass

```

*Refined exact approach for `_thread_preflight`:*

```python
            summary_rows = []
            try:
                proc = subprocess.Popen(
                    args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                if proc.stdout:
                    for line in proc.stdout:
                        if ":" in line:
                            sub_parts = line.split(":")
                            tokens = sub_parts[1].split()
                            # A summary metrics row has 6 numeric columns
                            if len(tokens) >= 6 and all(t.replace(",", "").isdigit() or t in ("k","m","g","t") for t in tokens):
                                summary_rows.append(line)
                proc.wait()
            except OSError as e:
                self.after(0, self._log, f"  Error on {src}: {e}\\n", "bad")

            # Extract metrics from stable summary arrays sequentially
            # Row 0: Dirs, Row 1: Files, Row 2: Bytes
            if len(summary_rows) >= 3:
                f_parts = summary_rows[1].split(":")[1].split()
                total_files += int(f_parts[0].replace(",", ""))
                skipped += int(f_parts[2].replace(",", ""))
                total_bytes += self._parse_robocopy_bytes(summary_rows[2])

```

### BUG-005 [MEDIUM] — Ambiguous Logging of Identical Target Filenames

**File:** `ghost_harvest/hasher.py`
**What's wrong:** When a cryptographic hash mismatch is flagged, the logger executes `cb(f"  ❌  MISMATCH: {name}\\n", "bad")`, where `name = dst_p.name`. If identical filenames exist in nested structures (e.g., `projectA/config.json` and `projectB/config.json`), the UI panel strips directory contexts, making identification impossible.
**Fix:** Modify the log parameter to pass the relative directory path from the workspace anchor root.

```python
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                pool.submit(_check, sp, dp): (sp, dp)
                for sp, dp in pairs
            }
            for future in as_completed(futures):
                try:
                    name, sh, dh = future.result()
                    # Retrieve the mapped pair paths to calculate relative display strings
                    sp, dp = futures[future]
                    rel_display = str(dp.relative_to(dest))
                except Exception:
                    fail += 1
                    continue

                if not sh or not dh:
                    fail += 1
                    cb(f"  ⚠  Could not hash: {rel_display}\\n", "warn")
                    continue

                if sh == dh:
                    ok += 1
                else:
                    fail += 1
                    cb(f"  ❌  MISMATCH: {rel_display}\\n", "bad")

```

---

## PASS 4 — ENVIRONMENT & STRUCTURAL ISSUES

### BUG-006 [MEDIUM] — Unresolved Execution Context of Relative Script Paths on UAC Elevation

**File:** `ghost_harvest/utils.py`
**What's wrong:** The function `elevate()` directly passes `sys.argv[0]` inside parameters to `ShellExecuteW`. If the script was initialized via a relative invocation path (e.g., `python main.py`), Windows handles the elevated token redirection by defaulting the new CWD environment to `C:\\Windows\\System32`. The program crashes instantly on relaunch due to the missing file lookup framework under system scopes.
**Fix:** Force absolute resolution of the target execution file string prior to wrapping parameters.

```python
def elevate() -> None:
    # Ensure execution targets resolve cleanly to absolute locations before breaking scope
    script = str(Path(sys.argv[0]).resolve())
    ctypes.windll.shell32.ShellExecuteW(
        None,                    # parent window handle
        "runas",                 # verb — request elevation
        sys.executable,          # program — python.exe / pythonw.exe
        f'"{script}"',           # parameters — properly quoted script path
        None,                    # working directory
        1,                       # show-window flag (SW_SHOWNORMAL)
    )
    sys.exit(0)

```

---

## PASS 5 — CRITICAL IMPROVEMENTS

### IMP-001 [IMPROVEMENT] — Lowercase String Coercion Guard on Extension Bypasses

**File:** `ghost_harvest/scanner.py`
**What's wrong:** `has_double_extension` uses `.lstrip(".")` on the final suffix block. If anomalous edge-case patterns match mixed metadata entries, matching bounds decay.
**Fix:** Refactor `has_double_extension` to explicitly resolve lower-cased text filters uniformly using `.replace(".", "")`.

```python
def has_double_extension(path: Path, blocked_exts_set: set[str]) -> bool:
    suffixes = path.suffixes
    if len(suffixes) >= 2:
        final_ext = suffixes[-1].lower().replace(".", "")
        return final_ext in blocked_exts_set
    return False

```

---

## EXECUTION ORDER FOR AGENT

Apply fixes in this exact order. Each Group is an autonomous working checkpoint.

**Group 1 — Resolve Syntax and Execution Launch Vectors**

* BUG-001
* BUG-006
**Checkpoint:** `python -c "import ghost_harvest.utils; print('Utils Loaded Cleanly')"`

**Group 2 — Harden Arguments and Test Architectures**

* BUG-002
* BUG-003
* IMP-001
**Checkpoint:** `python ghost_harvest\\tests\\validate_security.py`

**Group 3 — Fix Application Pipeline Integrity and Tracking**

* BUG-004
* BUG-005
**Final Checkpoint:** Run security test suite and confirm real cross-checks complete error-free.

---

## KNOWN STUBS (Not bugs)

* `GhostHarvest.py` — Legacy monolith (retained for reference archives only; bypassed during execution).
"""

with open("SPRINT_FIX.md", "w", encoding="utf-8") as f:
f.write(sprint_fix_content)

print("SPRINT_FIX.md generated successfully.")

```
I have conducted a deep, multi-pass codebase audit of **Ghost Harvest v2.1** following the structured audit framework. 

The primary structural, compilation, and programmatic bugs have been triaged, categorized, and written into a clean workspace work order file. 

---

# SPRINT_FIX.md — Ghost Harvest v2.1
**Audit Date:** May 29, 2026
**Auditor:** Senior Architect Review
**Target:** Autonomous Agent Implementation Sprint
**Base Ref:** `README.md`

---

## HOW TO USE THIS FILE
This file serves as an explicit, sequential work order for correcting critical compilation blockers, test suite vulnerabilities, and silent engineering defects in Ghost Harvest v2.1. All modifications must be applied verbatim following the specified execution groups. SPRINT_FIX.md overrides any conflicting architectural specifications.

---

## PASS 1 — CRITICAL BLOCKERS

### BUG-001 [BLOCKER] — Syntax Error (Trailing Brace) in System Utilities
**File:** `ghost_harvest/utils.py`
**What's wrong:** A trailing curly brace `}` exists on line 73 at the end of the `format_size` function block. This throws an immediate `SyntaxError: invalid syntax` upon importing or executing the module, blocking the application from booting and rendering the security validation test suite completely non-executable.
**Fix:** Remove the trailing brace from the file completely.

```python
def format_size(b: int) -> str:
    """Human-readable file size string."""
    if b >= 1024 ** 3:
        return f"{b / 1024 ** 3:.2f} GB"
    if b >= 1024 ** 2:
        return f"{b / 1024 ** 2:.1f} MB"
    if b >= 1024:
        return f"{b / 1024:.1f} KB"
    return f"{b:,} B"

```

### BUG-002 [BLOCKER] — Trailing Backslash Argument Escaping in Robocopy CLI Spawning

**File:** `ghost_harvest/command.py`
**What's wrong:** If a user provides a source or destination path with a trailing backslash (e.g., `C:\Infected Data\`), Python's `subprocess.Popen` serialization escapes the trailing double quote (`\"`). This causes Robocopy to interpret the next CLI flag as part of the directory path string, collapsing the argument sequence and causing immediate fatal parsing failures or missing directory errors inside the underlying system process.
**Fix:** Append a duplicating backslash to any paths that terminate with a single backslash before passing them to the argument builder array. This ensures Windows command line parsers interpret it as a literal trailing backslash instead of an escaped quote character.

```python
def build_args(
    source: str,
    dest: str,
    threads: int = 16,
    *,
    restartable: bool = True,
    dry_run: bool = False,
    block_exts: bool = True,
    skip_bloat: bool = True,
    custom_xd: str = "",
    save_log: bool = True,
) -> list[str]:
    # Normalize paths to prevent trailing backslash quote escaping bugs on Windows
    if source.endswith("\\") and not source.endswith(":\\"):
        source += "\\"
    if dest.endswith("\\") and not dest.endswith(":\\"):
        dest += "\\"

    args: list[str] = [
        "robocopy",
        source,
        dest,
        "/E",               # recurse including empty dirs
        "/COPY:DAT",        # Data + Attributes + Timestamps (no ADS)
        f"/MT:{threads}",   # multi-threaded
    ]
    # ... remaining code remains identical

```

---

## PASS 2 — HIGH SEVERITY TEST BUGS

### BUG-003 [HIGH] — Security Regression Test Asserting Local Scoped Dummies

**File:** `ghost_harvest/tests/validate_security.py`
**What's wrong:** The extension parsing test under audit checkpoint `[S2]` assigns local variables `correct` and `broken` using standard string functions and then checks if `correct == ext[2:]`. It does *not* invoke or assert against the real codebase matching function `has_double_extension` located inside `scanner.py`. The test suite yields a false-positive success rate while masking regressions inside the production logic.
**Fix:** Rewrite the test block to import and directly challenge the production implementation inside `scanner.py`.

```python
# S2: removeprefix vs lstrip
print("\n[S2] Extension parsing (removeprefix fix)")
from ghost_harvest.scanner import has_double_extension
blocked_set = {"wsf", "scr", "msi", "js", "exe", "ps1"}

check("Double extension detected correctly", has_double_extension(Path("report.pdf.exe"), blocked_set) == True)
check("Single dangerous extension bypassed by double-ext rule", has_double_extension(Path("report.exe"), blocked_set) == False)
check("Safe double extension bypassed", has_double_extension(Path("report.txt.pdf"), blocked_set) == False)

```

---

## PASS 3 — MEDIUM SEVERITY (SILENT FAILURES)

### BUG-004 [MEDIUM] — Locale-Dependent Hardcoding of Robocopy Output Logs

**File:** `ghost_harvest/app.py`
**What's wrong:** Methods `_thread_preflight` and `_parse_robocopy_bytes` parse standard output using hardcoded English keywords (`"Total"`, `"Copied"`, `"Skipped"`, `"Files"`, `"Bytes"`). When executed on localized non-English Windows machines (e.g., German, French, Spanish), Robocopy produces localized console outputs. The app silently fails to match the labels, yielding a corrupted pre-flight summary with zero counts.
**Fix:** Transition parsing architecture to look for invariant row-structural signatures. Extract metrics from stable summary arrays sequentially (Row 0: Directories, Row 1: Files, Row 2: Bytes) based on the 6 numeric column footprint.

```python
            summary_rows = []
            try:
                proc = subprocess.Popen(
                    args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                if proc.stdout:
                    for line in proc.stdout:
                        if ":" in line:
                            sub_parts = line.split(":")
                            tokens = sub_parts[1].split()
                            # A summary metrics row has 6 numeric columns
                            if len(tokens) >= 6 and all(t.replace(",", "").isdigit() or t in ("k","m","g","t") for t in tokens):
                                summary_rows.append(line)
                proc.wait()
            except OSError as e:
                self.after(0, self._log, f"  Error on {src}: {e}\n", "bad")

            # Extract metrics from stable summary arrays sequentially
            if len(summary_rows) >= 3:
                f_parts = summary_rows[1].split(":")[1].split()
                total_files += int(f_parts[0].replace(",", ""))
                skipped += int(f_parts[2].replace(",", ""))
                total_bytes += self._parse_robocopy_bytes(summary_rows[2])

```

### BUG-005 [MEDIUM] — Ambiguous Logging of Identical Target Filenames

**File:** `ghost_harvest/hasher.py`
**What's wrong:** When a cryptographic hash mismatch is flagged, the logger executes `cb(f"  ❌  MISMATCH: {name}\n", "bad")`, where `name = dst_p.name`. If identical filenames exist in nested structures (e.g., `projectA/config.json` and `projectB/config.json`), the UI panel strips directory contexts, making identification impossible.
**Fix:** Modify the log parameter to pass the relative directory path from the workspace anchor root.

```python
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                pool.submit(_check, sp, dp): (sp, dp)
                for sp, dp in pairs
            }
            for future in as_completed(futures):
                try:
                    name, sh, dh = future.result()
                    sp, dp = futures[future]
                    rel_display = str(dp.relative_to(dest))
                except Exception:
                    fail += 1
                    continue

                if not sh or not dh:
                    fail += 1
                    cb(f"  ⚠  Could not hash: {rel_display}\n", "warn")
                    continue

                if sh == dh:
                    ok += 1
                else:
                    fail += 1
                    cb(f"  ❌  MISMATCH: {rel_display}\n", "bad")

```

---

## PASS 4 — ENVIRONMENT & STRUCTURAL ISSUES

### BUG-006 [MEDIUM] — Unresolved Execution Context of Relative Script Paths on UAC Elevation

**File:** `ghost_harvest/utils.py`
**What's wrong:** The function `elevate()` directly passes `sys.argv[0]` inside parameters to `ShellExecuteW`. If the script was initialized via a relative invocation path (e.g., `python main.py`), Windows handles the elevated token redirection by defaulting the new CWD environment to `C:\Windows\System32`. The program crashes instantly on relaunch due to the missing file lookup framework under system scopes.
**Fix:** Force absolute resolution of the target execution file string prior to wrapping parameters.

```python
def elevate() -> None:
    # Ensure execution targets resolve cleanly to absolute locations before breaking scope
    script = str(Path(sys.argv[0]).resolve())
    ctypes.windll.shell32.ShellExecuteW(
        None,                    # parent window handle
        "runas",                 # verb — request elevation
        sys.executable,          # program — python.exe / pythonw.exe
        f'"{script}"',           # parameters — properly quoted script path
        None,                    # working directory
        1,                       # show-window flag (SW_SHOWNORMAL)
    )
    sys.exit(0)

```

---

## PASS 5 — CRITICAL IMPROVEMENTS

### IMP-001 [IMPROVEMENT] — Lowercase String Coercion Guard on Extension Bypasses

**File:** `ghost_harvest/scanner.py`
**What's wrong:** `has_double_extension` uses `.lstrip(".")` on the final suffix block. If anomalous edge-case patterns match mixed metadata entries, matching bounds decay.
**Fix:** Refactor `has_double_extension` to explicitly resolve lower-cased text filters uniformly using `.replace(".", "")`.

```python
def has_double_extension(path: Path, blocked_exts_set: set[str]) -> bool:
    suffixes = path.suffixes
    if len(suffixes) >= 2:
        final_ext = suffixes[-1].lower().replace(".", "")
        return final_ext in blocked_exts_set
    return False

```

---

## EXECUTION ORDER FOR AGENT

Apply fixes in this exact order. Each Group is an autonomous working checkpoint.

**Group 1 — Resolve Syntax and Execution Launch Vectors**

* BUG-001
* BUG-006
**Checkpoint:** `python -c "import ghost_harvest.utils; print('Utils Loaded Cleanly')"`

**Group 2 — Harden Arguments and Test Architectures**

* BUG-002
* BUG-003
* IMP-001
**Checkpoint:** `python ghost_harvest\tests\validate_security.py`

**Group 3 — Fix Application Pipeline Integrity and Tracking**

* BUG-004
* BUG-005
**Final Checkpoint:** Run security test suite and confirm real cross-checks complete error-free.

---

## KNOWN STUBS (Not bugs)

* `GhostHarvest.py` — Legacy monolith (retained for reference archives only; bypassed during execution).

---

## PHASE 2: AGENT INITIATION PROMPT

You can copy and paste the raw work order configuration below directly into your autonomous programming agent workspace context:

```markdown
### READ FIRST, CODE SECOND
Read SPRINT_FIX.md in full and review the documented codebase patterns prior to making edits. Execution must proceed file-by-file following the chronological Group checkpoints located at the bottom of the work order. Fix dependencies are rigid; do not alter the sequence.

### OBJECTIVE
Execute all structural bug fixes and quality improvements outlined in SPRINT_FIX.md verbatim to stabilize the application context. Success is achieved when the security test validation engine executes error-free, imports execute cleanly, and path evaluation logic bypasses all standard quote-escaping hazards on Windows.
Final Checkpoint Target: `python ghost_harvest\tests\validate_security.py` returns passing metrics with 0 failures.

### EXECUTION RULES
1. Work surgically file-by-file; do not touch, rewrite, or modify files not specified by an active fix entry.
2. Use the provided fix replacement blocks exactly as written. Do not add undocumented design abstractions.
3. Validate each Group's standalone checkpoint command successfully before attempting work on a subsequent block.
4. SPRINT_FIX.md represents a system override on top of the original specifications; prioritize its architecture patterns over any conflicting code styles in legacy snapshots.
5. If an untracked bug is encountered during the sprint, log it exactly as: `UNTRACKED-BUG: [file] — [desc] — [fix]` in your final status update before patching.

### ENVIRONMENT CHECK
Prior to executing changes, verify the core platform footprint:
- Confirm OS target: Windows target simulation framework (`win32` libraries are standard).
- Validate core Python engine version is 3.9+ without third-party `pip` overheads.

### CHECKPOINT COMMANDS
- Group 1 Checkpoint: `python -c "import ghost_harvest.utils; print('Utils Loaded Cleanly')"`
- Group 2 Checkpoint: `python ghost_harvest\tests\validate_security.py`
- Group 3 / Final Target: Validate UI logging output pipeline manually or ensure all regression checkpoints run clean.

### WHEN AMBIGUITY ARISES
- Symptom: `SyntaxError` on workspace import loops.
  -> Diagnosis: Residual trailing curly brace markers corrupting function terminations.
  -> Resolution: Apply BUG-001 directly and remove the terminal curly bracket from the bottom of `utils.py`.
- Symptom: Robocopy process syntax errors or directory not found errors when testing paths with spaces or slashes.
  -> Diagnosis: Single trailing backslashes escaping closing string quotes inside `subprocess.Popen`.
  -> Resolution: Apply BUG-002 to catch and duplicate trailing slashes before arguments pass to array construction blocks.
- Symptom: Pre-flight calculations display 0 metrics or blank values during non-English system simulation tests.
  -> Diagnosis: Locale-dependent parsing failures due to localized system headers.
  -> Resolution: Apply BUG-004 to replace word tracking with the structural 6-column numeric row index signature array.

### DELIVERABLE
Provide a clean summary detailing:
1. List of files modified during the sprint.
2. Concrete test logging assertions validating the removal of the false-positive local validation variables.
3. Final console print confirmations from `validate_security.py`.
4. Any `UNTRACKED-BUG` entries identified or handled during operations.

```