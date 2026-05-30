# SPRINT_FIX.md — Ghost Harvest v2.1
**Audit Date:** 2026-05-30  
**Auditor:** Senior Architect Review  
**Target:** Autonomous Agent Implementation Sprint  
**Base Ref:** `README.md` (architecture & security audit trail)

---

## HOW TO USE THIS FILE
Fix entries are tagged `[BLOCKER]`, `[HIGH]`, or `[MEDIUM]`. Apply fixes in the **Execution Order** below – each group forms a working checkpoint. Where the code diverges from `README.md`, the spec is authoritative unless a clear technical reason is stated.

---

## PASS 1 — CRITICAL BLOCKERS
No absolute stoppers found. The application runs, imports resolve, and all required Windows APIs are available via the standard library.

---

## PASS 2 — HIGH SEVERITY TEST BUGS
### BUG-001 [HIGH] — validation script assumes source code always available
**File:** `ghost_harvest/tests/validate_security.py`  
**What's wrong:** The script uses `inspect.getsource(elevate)` and similar calls. If the script is run from a different working directory or if the source files are compiled (`.pyc` only), `inspect.getsource` raises `OSError`. The test will fail, masking real validation results.  
**Fix:** Add a fallback that skips source‑inspection checks when source is unavailable, but still runs all other assertions. Replace the source‑inspection sections with a safer alternative: check `elevate`’s bytecode or simply rely on the fact that the function is defined as shown in the snapshot. For automation, we will manually verify the source in the provided snapshot.

> **Exact change:**  
> In `validate_security.py`, wrap each `inspect.getsource()` call in a try/except and print a warning instead of failing. Example:
> ```python
> try:
>     src = inspect.getsource(elevate)
> except OSError:
>     print("  ⚠  Cannot inspect elevate() source – skipping S3 checks")
>     src = ""
> ```
> Then conditionally run the checks only if `src` is non‑empty.

---

## PASS 3 — MEDIUM SEVERITY (Silent Failures & Latent Crashes)
### BUG-002 [MEDIUM] — background thread may call `self.after()` after window is destroyed
**File:** `ghost_harvest/app.py` – `_pipeline()` and `_log()`  
**What's wrong:** The pipeline thread calls `self.after(0, self._log, ...)` and `self.after(0, self._finish)`. If the user closes the window while the pipeline is running, the Tk instance is destroyed, but the daemon thread continues. `self.after()` on a destroyed `Tk` raises `TclError`. The exception is ignored because it’s in a daemon thread, but it pollutes the console.  
**Fix:** In every location where `self.after()` is called from a background thread, check `self._alive` first. Also check `self._alive` inside `_finish()` before calling `self.after(0, self._finish)`.

**Exact changes in `app.py`:**

```python
# In _pipeline(), replace every self.after(...) with:
if self._alive:
    self.after(0, ...)

# In _finish(), before the final self.after, check alive:
def _finish(self) -> None:
    if not self._alive:
        return
    self.running = False
    with self.process_lock:
        self.process = None
    self.run_btn.config(text="▶   RUN MIGRATION", style="Run.TButton")
    self.progress.stop()
    # No self.after call – _finish is already called on the main thread via after()
```

Also modify `_log()` – it already checks `self._alive`, so that part is safe.

### BUG-003 [MEDIUM] — magic scanner treats unreadable files as safe
**File:** `ghost_harvest/scanner.py` – `is_exec_by_magic()`  
**What's wrong:** When a file cannot be opened (permission error, locked file), the function catches `OSError` and returns `(False, "")`. This causes a potentially malicious locked file to be considered non‑executable, so it is not purged.  
**Fix:** Log a warning when a file cannot be read for magic scanning. Since the scanner already has a callback, we can pass a warning through it.

**Exact change in `scanner.py` – `is_exec_by_magic` does not have callback access. Instead, change `PostCopyScanner.scan_directory` to handle permission errors:**

```python
# In scan_directory, inside the file loop, replace the magic check with:
try:
    hit, label = is_exec_by_magic(path)
except PermissionError:
    cb(f"  ⚠  Permission denied – cannot scan: {fname}\n", "warn")
    continue
except OSError as e:
    cb(f"  ⚠  I/O error reading {fname}: {e}\n", "warn")
    continue
```

Also update `is_exec_by_magic` to **re‑raise** `PermissionError` instead of swallowing it:

```python
def is_exec_by_magic(path: Path) -> tuple[bool, str]:
    try:
        with open(path, "rb") as f:
            header = f.read(MAGIC_READ_SIZE)
        for offset, sig, label in EXEC_SIGS:
            if header[offset: offset + len(sig)] == sig:
                return True, label
    except PermissionError:
        raise   # re-raise so caller can warn
    except OSError:
        pass    # other I/O errors – ignore (file may be corrupt)
    return False, ""
```

### BUG-004 [MEDIUM] — hash verifier may count two read errors as success
**File:** `ghost_harvest/hasher.py` – `ParallelHashVerifier.verify()`  
**What's wrong:** If both `sha256(src)` and `sha256(dst)` return empty strings (e.g., both files unreadable due to permissions), the condition `if not sh or not dh` catches it and increments `fail`. However, if **both** are empty and the files actually exist, the code treats it as a failure (good). But if the source file is missing (already handled earlier by `src_path.exists()` check), we never reach the hash step. So the only risk is a rare edge case where both files exist but both cannot be read. That still increments `fail`. This is acceptable, but to be precise, we add an explicit error log.

**Fix:** Already handled, but add a warning message when both hashes fail.

**Exact change in `hasher.py` inside the future callback:**

```python
if not sh and not dh:
    cb(f"  ⚠  Cannot hash both source and destination: {rel_display}\n", "warn")
    fail += 1
    continue
```

### BUG-005 [MEDIUM] — pre‑flight size parser mishandles some locale formats
**File:** `ghost_harvest/app.py` – `_parse_robocopy_bytes()`  
**What's wrong:** The parser tries to handle decimal commas (e.g., "12,3 m") but the logic for detecting a decimal comma is fragile. It looks for a comma and then checks if the part after the comma is 1‑2 digits. This may incorrectly interpret thousands separators in some European locales where a dot is the thousand separator.  
**Fix:** Simplify: trust robocopy’s English output (the tool runs on English Windows only, as documented). Remove the complex decimal‑comma detection and rely on standard thousand‑separator removal.

**Exact replacement for `_parse_robocopy_bytes`:**

```python
@staticmethod
def _parse_robocopy_bytes(line: str) -> int:
    line = line.lower()
    mult_map = {'k': 1024, 'm': 1024**2, 'g': 1024**3, 't': 1024**4}
    # Look for suffixed value
    for suffix, mult in mult_map.items():
        if f' {suffix}' in line:
            parts = line.split()
            for idx, part in enumerate(parts):
                if part == suffix and idx > 0:
                    raw_num = parts[idx-1].replace(',', '')
                    try:
                        val = float(raw_num)
                        return int(val * mult)
                    except ValueError:
                        pass
    # Fallback: raw bytes without suffix
    tokens = line.replace(',', '').split()
    for tok in tokens:
        if tok.replace('.', '', 1).isdigit():
            try:
                return int(float(tok))
            except ValueError:
                pass
    return 0
```

---

## PASS 4 — ENVIRONMENT & STRUCTURAL
### BUG-006 [MEDIUM] — validation script assumes it is run from project root
**File:** `ghost_harvest/tests/validate_security.py`  
**What's wrong:** The script inserts `"."` into `sys.path`. If run from any other directory, imports will fail. The README instructs running from the project root, but a robust script should compute its own location.  
**Fix:** Use `Path(__file__).parent.parent.parent` to add the project root.

**Exact change at top of `validate_security.py`:**

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
```

### BUG-007 [LOW] — `__init__.py` missing in `tests/` (not a package)
**File:** `ghost_harvest/tests/`  
**What's wrong:** There is no `__init__.py` in the tests directory. This is not required for running the validation script as a standalone, but it prevents the directory from being treated as a package. For consistency, add an empty `__init__.py`.  
**Fix:** Create an empty file `ghost_harvest/tests/__init__.py`.

---

## EXECUTION ORDER FOR AGENT

Apply fixes in this exact order. Each Group is a working checkpoint.

**Group 1 — Environment & Test Harness**  
1. BUG-006 (fix path in validation script)  
2. BUG-007 (add empty `__init__.py` in tests)  
**Checkpoint:** `python ghost_harvest/tests/validate_security.py` – should run without import errors (source‑inspection warnings may appear but are non‑fatal).

**Group 2 — Crash Prevention & I/O Robustness**  
3. BUG-002 (window‑close race condition)  
4. BUG-003 (permission errors in magic scanner)  
5. BUG-004 (hash verifier double‑error logging)  
**Checkpoint:** Run the GUI manually: `python main.py`. Start a migration, then close the window mid‑operation – no exception should be printed to console.

**Group 3 — Parsing & Validation**  
6. BUG-005 (robocopy size parser)  
7. BUG-001 (fallback for source inspection in test)  
**Checkpoint:** `python ghost_harvest/tests/validate_security.py` – all 37 assertions pass, no `OSError` from `inspect.getsource`.

**Final checkpoint:** `python ghost_harvest/tests/validate_security.py` and a manual smoke test (copy a small folder with a renamed `.exe` to confirm purging).

---

## KNOWN STUBS (not bugs — expected at this stage)
- No unit test framework (pytest, unittest) – only the security validation script. This is by design for v2.1.
- No support for NTFS Alternate Data Streams (ADS) detection – explicitly deferred in README.
- No entropy analysis for encrypted payloads – deferred.
- The `_preflight` size parser does not handle all possible robocopy locale variations – the tool assumes English Windows.

---

Now generate the agent initiation prompt.```markdown
**AGENT INITIATION PROMPT — Ghost Harvest v2.1 SPRINT**

```
## READ FIRST, CODE SECOND

You are an autonomous agent tasked with applying the fixes documented in `SPRINT_FIX.md` (attached to this conversation). Read that file in full before making any changes. Pay special attention to the **EXECUTION ORDER FOR AGENT** – you must apply fixes in the exact group order shown. Do not skip groups, do not reorder fixes within a group. Each group has a **Checkpoint** command – run that command after completing the group and verify success before moving to the next group.

## OBJECTIVE

Make the Ghost Harvest codebase robust against window‑close crashes, improve error handling for unreadable files, fix the pre‑flight size parser, and make the security validation script runnable from any directory. The final success criterion is: **all checkpoint commands pass, and `python ghost_harvest/tests/validate_security.py` exits with “37 passed · 0 failed”.**

## EXECUTION RULES

1. **Work file‑by‑file** – never rewrite a file that is not touched by a fix.
2. **Use provided fix code verbatim** – do not “improve” or refactor beyond the exact changes shown in `SPRINT_FIX.md`. The sprint is for fixing, not for redesign.
3. **Complete each Group’s checkpoint** before proceeding to the next Group. If a checkpoint fails, stop and report the failure with the exact error output.
4. **Spec override** – `SPRINT_FIX.md` is authoritative for this sprint. Where it contradicts `README.md` (e.g., error handling behaviour), follow the fix file.
5. **Untracked bugs** – if you discover a new bug not listed in `SPRINT_FIX.md`, document it as `UNTRACKED-BUG: [file] — [description] — [proposed fix]` before fixing it. Do not fix it without this documentation.

## ENVIRONMENT CHECK

The codebase uses only the Python standard library. No `pip install` is required.  
**Blocking (must fix before continuing):**  
- Ensure you are running on **Windows** (the tool uses `ctypes.windll` and `robocopy`).  
- Run from the repository root directory.  
- Verify that `python main.py` launches the GUI. If it fails with “No module named ghost_harvest”, the working directory is wrong – set it to the folder containing `main.py`.  

**Advisory (note and continue):**  
- The validation script expects English robocopy output – this is satisfied on standard Windows installations.

## CHECKPOINT COMMANDS

Copy and run these exactly as shown:

**Group 1**  
`python ghost_harvest/tests/validate_security.py`  
*Expected:* No import errors; may print warnings about missing source inspection (that is expected until Group 3).

**Group 2**  
Manual GUI test: `python main.py`, add a source folder, start migration, then close the window before it finishes. No `TclError` exception should be printed.

**Group 3**  
`python ghost_harvest/tests/validate_security.py`  
*Expected:* 37 passed, 0 failed, no `OSError` from `inspect.getsource`.

## WHEN AMBIGUITY ARISES

- **`inspect.getsource` fails even after fix** → The script is being run from a directory where the source `.py` files are not readable (e.g., zipped). Workaround: skip the failing check and report which check was skipped. The fix already adds a try/except – verify that the warning is printed and the test continues.
- **`self.after` still raises after applying BUG-002** → Ensure you added the `if self._alive:` guard to **every** `self.after()` call inside `_pipeline()`. Also check that `_finish()` returns early if `not self._alive`.
- **Permission error during magic scan still shows as “safe”** → Verify that you replaced the call to `is_exec_by_magic` with a try/except block that catches `PermissionError` and calls `cb()` with a warning, then `continue`. Also ensure `is_exec_by_magic` re‑raises `PermissionError` instead of swallowing it.
- **Size parser returns 0 for valid input** → Compare your implementation against the exact replacement code in BUG-005. The simplified parser expects English numeric format (commas as thousand separators). If the input contains a decimal comma, the parser will fallback to raw digits – that’s acceptable.

## DELIVERABLE

When you have completed all groups and all checkpoints pass, produce a final report containing:

1. A list of every file **modified**, **created**, or **deleted** (absolute or relative paths).
2. Any `UNTRACKED-BUG` entries you created (if none, state “No untracked bugs found”).
3. The output of the final validation script (the “37 passed · 0 failed” line).
4. An explicit statement: “All fixes applied, ready for merge.”

Do not include conversational commentary. The report must be concise and machine‑parseable.
```