# SPRINT_FIX.md — Ghost Harvest v2.1
**Audit Date:** 2026-05-29  
**Auditor:** Consensus Review (Deepseek, Gemini, Grok, Nemotron)  
**Target:** Autonomous Agent Implementation Sprint  
**Base Ref:** README.md + Ghost Harvest_llm.md  

---  

## HOW TO USE THIS FILE  
This file contains the definitive, prioritized work order for fixing critical bugs in Ghost Harvest v2.1.  
Severity tags indicate fix order: [BLOCKER] must be fixed first, then [HIGH], [MEDIUM], and [IMPROVEMENT] last.  
Fixes within a group can be applied in any order unless dependencies are noted.  
The governing spec is the README.md; where code diverges from the README without explicit override, the spec wins.  
> **Spec override notes** are included where fixes intentionally deviate from README for security/correctness.  

---  

## PASS 1 — CRITICAL BLOCKERS  

### BUG-001 [BLOCKER] — Syntax Error (Trailing Brace) in System Utilities  
**File:** `ghost_harvest/utils.py`  
**What's wrong:** A trailing curly brace `}` exists at the end of the `format_size` function block (line 73 in Gemini audit). This throws an immediate `SyntaxError: invalid syntax` upon importing or executing the module, blocking the application from booting and rendering the security validation test suite completely non-executable.  
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
**What's wrong:** If a user provides a source or destination path with a trailing backslash (e.g., `C:\Infected Data\`), Python's `subprocess.Popen` serialization escapes the trailing double quote (`\"`). This causes Robocopy to interpret the next CLI flag as part of the directory path string, collapsing the argument sequence and causing immediate fatal parsing failures or missing directory errors.  
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

## PASS 2 — HIGH SEVERITY  

### BUG-003 [HIGH] — Magic-Byte Scanner Skips Plain-Text Extensions (Security Regression)  
**File:** `ghost_harvest/scanner.py` (lines 120-123)  
**What's wrong:** The scanner bypasses any file whose extension is in `PLAIN_TEXT_EXTS` without checking its magic bytes. A malicious executable renamed to `.txt`, `.py`, `.md`, or any other plain-text extension will be copied to the destination and never flagged. This directly contradicts the threat model’s “magic-byte scan” defence and represents a critical security regression.  
> **Spec override:** This changes README.md § “Efficiency improvements”. The new behaviour is “scan every file” – required for security.  
**Fix:** Remove the plain-text extension skip entirely. The performance impact of reading the first 16 bytes of every file is negligible, and security must take precedence.  

Replace these lines in `scanner.py` (inside `scan_directory`):  

```python  
                # ── Skip known plain-text files (performance) ─────────  
                if ext in PLAIN_TEXT_EXTS:  
                    continue  
```  

with:  

```python  
                # NOTE: we do NOT skip any extension – magic‑byte scan runs on every file.  
                # (Plain‑text file reading is cheap, and skipping would allow renamed malware.)  
```  

### BUG-004 [HIGH] — UAC Elevation Fails with Relative Script Paths  
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

### BUG-005 [HIGH] — Pipeline Continues After Robocopy Fatal Errors  
**File:** `ghost_harvest/app.py` (lines 475-480)  
**What's wrong:** When `robocopy` returns exit code ≥8 (fatal error or copy errors), the pipeline still proceeds to the post‑copy scanner and hash verifier. If the copy failed (e.g., disk full, permission denied), the destination may contain a partial file or be empty. Scanning/hashing a partial file could produce false negatives (malware not detected) or false mismatches.  
**Fix:** Skip the magic scan and hash verify steps when `rc` is not in the success range (0‑7).  

Inside `_pipeline`, after `rc = self.process.returncode`, change the condition for steps 2 and 3 from:  

```python  
            if settings["magic_scan"] and not settings["dry_run"] and not self.aborted:  
```  

to:  

```python  
            if rc is not None and rc <= 7 and settings["magic_scan"] and not settings["dry_run"] and not self.aborted:  
```  

And similarly for the hash verify step.  

### BUG-006 [HIGH] — Test Suite False Positives for Bare Except Checks  
**File:** `ghost_harvest/tests/validate_security.py`  
**What's wrong:** The test suite contains logically flawed assertions for checking bare `except:` clauses that will always pass regardless of actual code quality, providing false confidence in exception handling safety.  
**Fix:** Remove the bogus check and keep only the proper line‑scan validation.  

Replace the flawed check (lines ~30-33 in Deepseek audit) with proper validation:  

```python  
# S5: No bare except in codebase  
print("\n[S5] Exception handling")  
for mod_name, mod in [("utils", u_mod), ("scanner", s_mod), ("hasher", h_mod)]:  
    src_lines = inspect.getsource(mod).split("\n")  
    bare_excepts = [ln.strip() for ln in src_lines if ln.strip() == "except:"]  
    check(f"No bare 'except:' in {mod_name}.py", len(bare_excepts) == 0)  
```  

---  

## PASS 3 — MEDIUM SEVERITY  

### BUG-007 [MEDIUM] — Locale‑Dependent Robocopy Output Parsing  
**File:** `ghost_harvest/app.py` (`_thread_preflight` and `_parse_robocopy_bytes`)  
**What's hard:** Methods parse standard output using hardcoded English keywords (`"Total"`, `"Copied"`, `"Skipped"`, `"Files"`, `"Bytes"`). When executed on localized non‑English Windows machines, Robocopy produces localized console outputs. The app silently fails to match the labels, yielding a corrupted pre‑flight summary with zero counts.  
**Fix:** Transition parsing architecture to look for invariant row‑structural signatures. Extract metrics from stable summary arrays sequentially (Row 0: Directories, Row 1: Files, Row 2: Bytes) based on the 6‑numeric‑column footprint.  

In `_thread_preflight`, replace the parsing loop with:  

```python  
            summary_rows = []  
            try:  
                proc = subprocess.Popen(  
                    args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,  
                    text=True, encoding="utf-8", errors="replace",  
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0  
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
            if len(summary_rows) >= 3:  
                f_parts = summary_rows[1].split(":")[1].split()  
                total_files += int(f_parts[0].replace(",", ""))  
                skipped += int(f_parts[2].replace(",", ""))  
                total_bytes += self._parse_robocopy_bytes(summary_rows[2])  
```  

Also update `_parse_robocopy_bytes` to handle localized suffixes:  

```python  
    @staticmethod  
    def _parse_robocopy_bytes(line: str) -> int:  
        """Parse a robocopy summary 'Bytes' line, handling localized suffixes."""  
        parts = line.split()  
        # Try suffixed value first (e.g. "12.3 m")  
        for j, p in enumerate(parts):  
            p_lower = p.lower()  
            if p_lower in ("k", "m", "g", "t") and j > 0:  
                try:  
                    val = float(parts[j - 1].replace(",", "."))  
                    mult = {"k": 1024, "m": 1024 ** 2, "g": 1024 ** 3, "t": 1024 ** 4}[p_lower]  
                    return int(val * mult)  
                except (ValueError, IndexError):  
                    pass  

        # Fallback: raw byte count (no suffix)  
        nums = [x.replace(",", "") for x in parts if x.replace(",", "").isdigit()]  
        if nums:  
            try:  
                return int(nums[0])  
            except ValueError:  
                pass  
        return 0  
```  

### BUG-008 [MEDIUM] — Ambiguous Logging of Identical Target Filenames  
**File:** `ghost_harvest/hasher.py`  
**What's wrong:** When a cryptographic hash mismatch is flagged, the logger executes `cb(f"  ❌  MISMATCH: {name}\\n", "bad")`, where `name = dst_p.name`. If identical filenames exist in nested structures (e.g., `projectA/config.json` and `projectB/config.json`), the UI panel strips directory contexts, making identification impossible.  
**Fix:** Modify the log parameter to pass the relative directory path from the workspace anchor root.  

In the `_check` callback within `ParallelHashVerifier.verify()`:  

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
                    cb(f"  ⚠  Could not hash: {rel_display}\\n", "warn")  
                    continue  

                if sh == dh:  
                    ok += 1  
                else:  
                    fail += 1  
                    cb(f"  ❌  MISMATCH: {rel_display}\\n", "bad")  
```  

### BUG-009 [MEDIUM] — Manifest Write Failures Silently Ignored  
**File:** `ghost_harvest/app.py` (`_pipeline` method)  
**What's wrong:** If the manifest cannot be written (e.g., due to permissions), the function `write_manifest` returns `None`, but the app does not log an error, leaving the user unaware.  
**Fix:** Log an error when manifest writing fails.  

After the `write_manifest` call in `_pipeline`:  

```python  
            mpath = write_manifest(manifest, dest)  
            if mpath:  
                self.after(  
                    0, self._log,  
                    f"\\n📄  Blocked manifest → {mpath}\\n", "dim",  
                )  
            else:  
                self.after(  
                    0, self._log,  
                    f"\\n⚠  Failed to write blocked manifest.\\n", "warn",  
                )  
```  

### BUG-010 [MEDIUM] — Disk Usage Check Failures Silently Ignored  
**File:** `ghost_harvest/app.py` (`_update_space` method)  
**What's wrong:** The function catches `OSError` and `ValueError` and does nothing, leaving the space label blank if there is an error (e.g., invalid path, inaccessible drive). The user is not informed of the issue.  
**Fix:** Update the label to show an error message when disk usage cannot be checked.  

In `_update_space`:  

```python  
    def _update_space(self) -> None:  
        try:  
            anchor = str(Path(self.dest_var.get().strip()).anchor)  
            if anchor and os.path.exists(anchor):  
                _, used, free = shutil.disk_usage(anchor)  
                style = "Good.TLabel" if free / 1024 ** 3 > 50 else "Warn.TLabel"  
                self.space_lbl.config(  
                    text=(  
                        f"Destination drive — {used / 1024 ** 3:.1f} GB used"  
                        f" · {free / 1024 ** 3:.1f} GB free"  
                    ),  
                    style=style,  
                )  
        except (OSError, ValueError):  
            self.space_lbl.config(  
                text="Unable to check disk space",  
                style="Warn.TLabel",  
            )  
```  

### BUG-011 [MEDIUM] — ANSI Escape Codes Break Pre‑Flight Parsing  
**File:** `ghost_harvest/app.py` (`_thread_preflight` method)  
**What's wrong:** The robocopy output may contain ANSI escape codes, which are not stripped before being passed to `_parse_robocopy_bytes`. This can cause the byte count parsing to fail silently (returning 0) and lead to incorrect size estimates in the pre‑flight.  
**Fix:** Strip ANSI escape codes from each line of robocopy output before logging and parsing.  

Add to `utils.py`:  

```python  
import re  
_ANSI_RE = re.compile(r'\\x1b\\[[0-9;]*[mK]')  

def strip_ansi(text: str) -> str:  
    return _ANSI_RE.sub('', text)  
```  

Then in `_thread_preflight`, before logging and parsing each line:  

```python  
                if proc.stdout:  
                    for line in proc.stdout:  
                        clean_line = strip_ansi(line)  
                        self.after(0, self._log, clean_line)  
                        # ... rest of parsing logic uses clean_line  
```  

---  

## PASS 4 — IMPROVEMENTS  

### IMP-001 [IMPROVEMENT] — Centralize Robocopy Exit Code Constants  
**File:** `ghost_harvest/constants.py`  
**Why:** Magic numbers reduce readability and increase risk of inconsistency.  
**Fix:** Add named constants for robocopy exit codes.  

```python  
# Robocopy exit code ranges  
ROBOCOPY_SUCCESS_CODES = range(8)  # 0‑7 = success  
ROBOCOPY_ERROR_CODES = range(8, 16)  # 8‑15 = errors  
```  

Then use in `app.py`:  

```python  
from .constants import ROBOCOPY_SUCCESS_CODES  
# ...  
if rc is not None and rc in ROBOCOPY_SUCCESS_CODES:  
```  

### IMP-002 [IMPROVEMENT] — Force Dry‑Run in Pre‑Flight via Settings  
**File:** `ghost_harvest/app.py` (`_preflight` method)  
**Why:** The current workaround of appending `"/L"` to args is fragile if args already contain `"/L"` unexpectedly.  
**Fix:** Set the dry_run setting to True in the settings dictionary passed to `_current_args`.  

In `_preflight`:  

```python  
        settings: dict[str, Any] = {  
            "queue": list(self.queue),  
            "dest": self.dest_var.get().strip(),  
            "threads": int(self.threads_var.get()),  
            "restartable": self.restartable.get(),  
            "dry_run": True,  # ← Force dry‑run via settings, not arg mutation  
            "block_exts": self.block_exts.get(),  
            "skip_bloat": self.skip_bloat.get(),  
            "custom_xd": self.custom_xd.get().strip(),  
            "save_log": self.save_log.get(),  
        }  
```  

### IMP-003 [IMPROVEMENT] — Add Missing `__all__` Exports  
**File:** Multiple (`ghost_harvest/*.py`)  
**Why:** Internal helpers are exposed but no `__all__` limits clarity of public interface.  
**Fix:** Add `__all__` to key modules.  

In `scanner.py`:  

```python  
__all__ = ["is_exec_by_magic", "has_double_extension", "PostCopyScanner"]  
```  

In `utils.py`:  

```python  
__all__ = ["is_admin", "elevate", "sha256", "format_size", "strip_ansi"]  
```  

In `hasher.py`:  

```python  
__all__ = ["ParallelHashVerifier"]  
```  

---  

## EXECUTION ORDER FOR AGENT  

Apply fixes in this exact order. Each Group is a working checkpoint.  

**Group 1 — Resolve Syntax and Execution Launch Vectors**  
1. BUG-001  
2. BUG-002  
3. BUG-004  
**Checkpoint:** `python -c "import ghost_harvest.utils; import ghost_harvest.command; print('Core modules loaded cleanly')"`  

**Group 2 — Harden Security Core and Test Integrity**  
1. BUG-003  
2. BUG-005  
3. BUG-006  
**Checkpoint:** `python ghost_harvest\\tests\\validate_security.py`  

**Group 3 — Fix Application Pipeline Robustness**  
1. BUG-007  
2. BUG-008  
3. BUG-009  
4. BUG-010  
5. BUG-011  
**Checkpoint:** Run GUI pre‑flight on a test folder (verify accurate byte estimates and error handling)  

**Group 4 — Apply Polish and Improvements**  
1. IMP-001  
2. IMP-002  
3. IMP-003  
**Final Checkpoint:** `python ghost_harvest\\tests\\validate_security.py` (expect 37+ passed, 0 failed)  

---  

## KNOWN STUBS (not bugs — expected at this stage)  

* `GhostHarvest.py` — Legacy monolith (retained for reference archives only; bypassed during execution).  
* Advanced ADS/streams detection — Documented in Threat Model as future work.  
* Entropy analysis for encrypted payloads — Considered out of scope for v2.1.  
* Full cross‑platform (Linux/macOS) support — Windows‑only by design (artifact of `robocopy` dependency).  

--- End of SPRINT_FIX.md ---  

[AGENT INSTRUCTION START]  

READ FIRST, CODE SECOND  
Read the entire SPRINT_FIX.md file attached above before making any changes.  
Re‑read the PASS 1, 2, and 3 sections carefully – fix dependencies exist.  
The execution order at the bottom of SPRINT_FIX.md is mandatory.  

OBJECTIVE  
Apply all BUG-001 through BUG-011 and IMP-001 through IMP-003 fixes in the specified groups,  
verify each checkpoint passes, and produce a working Ghost Harvest v2.1  
with the security gaps closed and critical reliability issues resolved.  
Final success: `python ghost_harvest/tests/validate_security.py` shows 37 passed, 0 failed.  

EXECUTION RULES  
1. Work file‑by‑file. Never rewrite files not touched by a fix.  
2. Use the exact fix code provided in SPRINT_FIX.md. Do not “improve” it during the bug‑fix sprint.  
3. Complete each Group's checkpoint before moving to the next Group.  
4. SPRINT_FIX.md overrides the README.md where they conflict – call out any such conflict in a comment when you apply the change.  
5. If you discover any untracked bug, document it as:  
   `UNTRACKED-BUG: [file] — [description] — [fix suggestion]`  
   then fix it (the fix becomes part of the sprint).  

ENVIRONMENT CHECK  
- Python 3.9+ required (removeprefix works).  
- Run on Windows unless you are only verifying code changes (the tool uses robocopy).  
- If you are on Linux/macOS, you can still apply the code fixes – the guard added in BUG-002 and BUG-007 will prevent crashes.  

CHECKPOINT COMMANDS  
- Group 1: `python -c "import ghost_harvest.utils; import ghost_harvest.command; print('Core modules loaded cleanly')"`  
- Group 2: `python ghost_harvest\\tests\\validate_security.py`  
- Group 3: Run GUI pre‑flight on a test folder (verify accurate byte estimates and error handling)  
- Group 4: `python ghost_harvest\\tests\\validate_security.py`  
- Final: `python ghost_harvest\\tests\\validate_security.py`  

WHEN AMBIGUITY ARISES  
- `The scanner still seems to skip .txt files` → Did you remove the plain‑text block and not re‑introduce a similar skip? → Fix applied only lines 120‑123; confirm no other `if ext in PLAIN_TEXT_EXTS` remains.  
- `Robocopy still runs on non‑Windows` → Did you import `sys` in `app.py` and use the conditional? → Add `import sys` and wrap `creationflags`.  
- `After BUG-005 the pipeline stops on error, but I need to log the error` → The fix only skips scan/hash when rc ≥8; the error is still logged. No further action needed.  
- `Pre‑flight size estimates are still wrong on non‑English Windows` → Did you apply BUG-007 and BUG-011? → Verify both locale‑robust parsing and ANSI stripping are active.  
- `Hash mismatch logs still show only filenames, not paths` → Did you apply BUG-008? → Confirm relative path logging is active in hasher.py.  
- `Manifest write failures still silent` → Did you apply BUG-009? → Check for warning log when write_manifest returns None.  

DELIVERABLE  
- List of every file modified (with line numbers/changed blocks).  
- Any UNTRACKED-BUG entries discovered (none expected).  
- Final output of `validate_security.py` – all tests passing.  
- Explicit note: “All Group 1‑3 fixes applied. Group 4 (improvements) was/was not applied.”  

[AGENT INSTRUCTION END]