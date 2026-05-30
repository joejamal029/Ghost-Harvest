# Ghost Harvest v2.1 — Definitive Audit & Sprint Work Order

After reviewing all five audit reports against the actual codebase snapshot, I have consolidated the **real bugs** (false positives removed) and produced a single authoritative `SPRINT_FIX.md`. The codebase is already robust, but several security‑critical issues, silent failures, and test gaps must be fixed.

---

## SPRINT_FIX.md — Ghost Harvest v2.1 (Definitive)

**Audit Date:** 2026-05-29  
**Auditor:** Senior Architect (Consolidated)  
**Base Ref:** README.md + codebase snapshot  

---

### HOW TO USE THIS FILE

- Fixes are grouped into **execution Groups** with mandatory checkpoints.
- Apply **in strict order**. Do not skip or reorder.
- Use the exact replacement code provided. Do not “improve” beyond the fix.
- After each Group, run the checkpoint command. Success = move to next Group.
- SPRINT_FIX.md overrides any conflicting spec (no conflicts exist).

---

## PASS 1 — CRITICAL BLOCKERS (Security & Correctness)

### BUG‑001 [CRITICAL] — Magic‑byte scanner bypasses all plain‑text extensions
**File:** `ghost_harvest/scanner.py` (lines 120–123 in snapshot)  
**What’s wrong:**  
The scanner skips every file whose extension is in `PLAIN_TEXT_EXTS` without reading its magic bytes. A malicious executable renamed to `.txt`, `.py`, `.md`, etc., will be copied and never flagged, breaking the threat model’s “magic‑byte scan” defence.  

**Fix:** Remove the plain‑text extension skip entirely.  

```python
                # ── Skip known plain-text files (performance) ─────────
                if ext in PLAIN_TEXT_EXTS:
                    continue
```
Replace with:
```python
                # NOTE: we do NOT skip any extension – magic‑byte scan runs on every file.
```

---

### BUG‑002 [CRITICAL] — `CREATE_NO_WINDOW` breaks on non‑Windows
**File:** `ghost_harvest/app.py` (lines 312, 455, 465)  
**What’s wrong:**  
`subprocess.Popen` uses `creationflags=subprocess.CREATE_NO_WINDOW` unconditionally. On Linux/macOS this attribute does not exist, causing `AttributeError`.  

**Fix:** Guard the flag with `sys.platform`. Also add `import sys` at the top of `app.py` (missing).  

```python
creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
```
Apply in three places: `_thread_preflight` (line ~312) and twice inside `_pipeline` (lines ~455 and ~465).

---

### BUG‑003 [CRITICAL] — Pipeline continues after robocopy fatal error (exit ≥8)
**File:** `ghost_harvest/app.py` (lines 475–480, then steps 2 and 3)  
**What’s wrong:**  
If robocopy returns exit code ≥8 (fatal error / copy errors), the post‑copy scanner and hash verifier still run. The destination may contain partial or zero files → false negatives / mismatches.  

**Fix:** Only run magic scan and hash verify when `rc` is in success range (0‑7).  

Change the condition from:
```python
            if settings["magic_scan"] and not settings["dry_run"] and not self.aborted:
```
to:
```python
            if rc is not None and rc <= 7 and settings["magic_scan"] and not settings["dry_run"] and not self.aborted:
```
Do the same for the hash verify block.

---

**Group 1 Checkpoint:**
```powershell
python -c "import ghost_harvest.scanner, ghost_harvest.app; print('Imports OK')"
```

---

## PASS 2 — HIGH SEVERITY TEST & ENVIRONMENT BUGS

### BUG‑004 [HIGH] — Test suite: flawed bare‑except check (false pass)
**File:** `ghost_harvest/tests/validate_security.py` (lines 55–63 in snapshot)  
**What’s wrong:**  
The first loop for S5 uses a broken condition (`... and False`) that always passes. The later loop is correct.  

**Fix:** Remove the flawed loop entirely. Keep only the per‑module line scan.  

Delete lines:
```python
for mod_name, mod in [("utils", u_mod), ("scanner", s_mod), ("hasher", h_mod)]:
    src = inspect.getsource(mod)
    has_bare = "\nexcept:" in src or " except:" in src.replace("\n", " ")
    check(f"No bare 'except:' in {mod_name}.py", "except:" not in src or "except:" in "except: pass" and False)
```

---

### BUG‑005 [HIGH] — Test suite: S2 only tests string ops, not production code
**File:** `ghost_harvest/tests/validate_security.py` (S2 section)  
**What’s wrong:**  
The test checks `removeprefix` vs `lstrip` on hardcoded strings, but never calls `has_double_extension` or any real scanner logic.  

**Fix:** Replace the S2 block with a real test of `has_double_extension`.  

```python
# S2: Extension parsing (removeprefix fix)
print("\n[S2] Extension parsing (removeprefix fix)")
from ghost_harvest.scanner import has_double_extension
from pathlib import Path
blocked_set = {"wsf", "scr", "msi", "js", "exe", "ps1", "dll", "sys"}
check("Double extension detected (.pdf.exe)", has_double_extension(Path("report.pdf.exe"), blocked_set))
check("Single dangerous extension not flagged", not has_double_extension(Path("report.exe"), blocked_set))
check("Safe double extension not flagged", not has_double_extension(Path("report.txt.pdf"), blocked_set))
```

---

### BUG‑006 [HIGH] — UAC elevation fails when script launched with relative path
**File:** `ghost_harvest/utils.py` (`elevate` function)  
**What’s wrong:**  
`sys.argv[0]` may be relative (e.g., `python main.py`). After elevation, the new process’s working directory is often `C:\Windows\System32`, causing “file not found”.  

**Fix:** Resolve to absolute path before passing to `ShellExecuteW`.  

```python
def elevate() -> None:
    script = str(Path(sys.argv[0]).resolve())
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}"', None, 1)
    sys.exit(0)
```
(Add `from pathlib import Path` at top of `utils.py` if missing – it already imports Path.)

---

**Group 2 Checkpoint:**
```powershell
python -X utf8 ghost_harvest\tests\validate_security.py
```
Expect **37 passed, 0 failed** (after applying later fixes; may be fewer until Group 3).

---

## PASS 3 — MEDIUM SEVERITY SILENT FAILURES

### BUG‑007 [MEDIUM] — Manifest write failure not logged
**File:** `ghost_harvest/app.py` (pipeline after `write_manifest`)  
**What’s wrong:**  
`write_manifest` returns `None` on failure, but the app does nothing. User never knows.  

**Fix:** After `mpath = write_manifest(manifest, dest)`, add:
```python
            if mpath is None:
                self.after(0, self._log, "\n⚠  Failed to write blocked manifest.\n", "warn")
```

---

### BUG‑008 [MEDIUM] — Disk usage label fails silently on error
**File:** `ghost_harvest/app.py` (`_update_space` method)  
**What’s wrong:**  
The `except` block catches `OSError` and `ValueError` and does nothing, leaving the label blank.  

**Fix:** In the `except` block, set an error message:
```python
        except (OSError, ValueError):
            self.space_lbl.config(text="Unable to check disk space", style="Warn.TLabel")
```

---

### BUG‑009 [MEDIUM] — Robocopy byte parser fails on uppercase suffixes (M, G, T)
**File:** `ghost_harvest/app.py` (`_parse_robocopy_bytes`)  
**What’s wrong:**  
The parser checks for `"m"` but not `"M"`. Robocopy may output `"12.3 M"`.  

**Fix:** Convert suffix to lowercase. Replace the loop:
```python
        for j, p in enumerate(parts):
            if p in ("k", "m", "g", "t") and j > 0:
```
with:
```python
        for j, p in enumerate(parts):
            p_lower = p.lower()
            if p_lower in ("k", "m", "g", "t") and j > 0:
                mult = {"k": 1024, "m": 1024**2, "g": 1024**3, "t": 1024**4}[p_lower]
                # ... (rest of logic unchanged)
```

---

### BUG‑010 [MEDIUM] — Pre‑flight byte parser fragile on non‑English robocopy output
**File:** `ghost_harvest/app.py` (`_thread_preflight` + `_parse_robocopy_bytes`)  
**What’s wrong:**  
Relies on English keywords (“Files”, “Bytes”). Localised robocopy (German, French, etc.) will cause zero counts.  

**Fix:** Use structural parsing – the summary table always has rows with 6 numeric columns. Replace the parsing logic in `_thread_preflight`:

```python
            summary_rows = []
            try:
                proc = subprocess.Popen(..., stdout=subprocess.PIPE, text=True, ...)
                if proc.stdout:
                    for line in proc.stdout:
                        if ":" in line:
                            parts = line.split(":")
                            tokens = parts[1].split()
                            if len(tokens) >= 6 and all(t.replace(",", "").isdigit() or t.lower() in ("k","m","g","t") for t in tokens):
                                summary_rows.append(line)
                proc.wait()
            except OSError as e:
                self.after(0, self._log, f"  Error on {src}: {e}\n", "bad")

            if len(summary_rows) >= 3:
                # Row 0: Dirs, Row 1: Files, Row 2: Bytes
                file_tokens = summary_rows[1].split(":")[1].split()
                total_files += int(file_tokens[0].replace(",", ""))
                skipped += int(file_tokens[2].replace(",", ""))
                total_bytes += self._parse_robocopy_bytes(summary_rows[2])
```

Also update `_parse_robocopy_bytes` with the case‑insensitive fix (BUG‑009). For even more robustness, replace the entire method with a regex‑based parser (recommended):

```python
@staticmethod
def _parse_robocopy_bytes(line: str) -> int:
    import re
    matches = re.findall(r'([\d.,]+)\s*([kmgt]?)', line.lower())
    for val_str, unit in matches:
        try:
            val = float(val_str.replace(",", ""))
            if unit:
                mult = {"k": 1024, "m": 1024**2, "g": 1024**3, "t": 1024**4}[unit]
                return int(val * mult)
            return int(val)
        except (ValueError, KeyError):
            continue
    return 0
```

---

### BUG‑011 [MEDIUM] — Pre‑flight ignores robocopy exit code ≥8
**File:** `ghost_harvest/app.py` (`_thread_preflight`)  
**What’s wrong:**  
Even if robocopy dry‑run fails (exit ≥8), the summary still shows optimistic numbers.  

**Fix:** After `proc.wait()`, add:
```python
                if proc.returncode and proc.returncode >= 8:
                    self.after(0, self._log, f"  ⚠ Robocopy pre-flight issue on {src} (exit {proc.returncode})\n", "warn")
```

---

### BUG‑012 [MEDIUM] — Hash verifier logs only filename, not relative path
**File:** `ghost_harvest/hasher.py` (inside `verify` method)  
**What’s wrong:**  
Mismatch messages show only `dst_p.name`. Duplicate filenames in different folders become indistinguishable.  

**Fix:** Log relative path from destination root.  

In the `_check` submission and result handling, retrieve the relative path. Replace the relevant section:

```python
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                pool.submit(_check, sp, dp): (sp, dp)
                for sp, dp in pairs
            }
            for future in as_completed(futures):
                sp, dp = futures[future]
                try:
                    name, sh, dh = future.result()
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

**Group 3 Checkpoint:**
```powershell
python -X utf8 ghost_harvest\tests\validate_security.py
```
Should now show **37 passed, 0 failed** (or all tests pass after we also update the test file to include new checks).

---

## PASS 4 — IMPROVEMENTS (optional but recommended)

### IMP‑001 [IMPROVEMENT] — Strip ANSI escape codes from subprocess output
**File:** `ghost_harvest/utils.py` (new function) + `app.py` (log lines)  
Add to `utils.py`:
```python
import re
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[mK]')
def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub('', text)
```
Then in `app.py`, inside `_pipeline` where we log each line from robocopy:
```python
                    for line in self.process.stdout:
                        self.after(0, self._log, strip_ansi(line))
```
(Add `from .utils import strip_ansi` at the top.)

---

### IMP‑002 [IMPROVEMENT] — Add `__all__` to core modules
**Files:** `scanner.py`, `utils.py`, `hasher.py`  
Add at the end of each (after imports, before code):
```python
__all__ = ["PostCopyScanner", "is_exec_by_magic", "has_double_extension"]  # scanner
__all__ = ["is_admin", "elevate", "sha256", "format_size", "strip_ansi"]   # utils
__all__ = ["ParallelHashVerifier"]                                          # hasher
```

---

### IMP‑003 [IMPROVEMENT] — Remove dead `files_copied` stat
**File:** `ghost_harvest/app.py` (stats dict in `_pipeline`)  
Delete the line `"files_copied": 0,` – it is never incremented.

---

**Final Checkpoint:**
```powershell
python main.py
```
Perform a dry‑run migration on a small test folder. Verify:
- No exceptions or crashes.
- Pre‑flight estimates are reasonable (non‑zero).
- Security summary appears.
- Test suite passes 100%.

---

## EXECUTION ORDER (SUMMARY)

| Group | Fixes | Checkpoint |
|-------|-------|-------------|
| **1** | BUG‑001, BUG‑002, BUG‑003 | `python -c "import ghost_harvest.scanner, ghost_harvest.app; print('OK')"` |
| **2** | BUG‑004, BUG‑005, BUG‑006 | `python -X utf8 ghost_harvest\tests\validate_security.py` |
| **3** | BUG‑007 through BUG‑012 | Same test – all pass |
| **4** | IMP‑001, IMP‑002, IMP‑003 | `python main.py` (dry‑run) |

---

## DELIVERABLE (for the agent)

After applying all fixes, provide:

1. **List of modified files** with line/block descriptions.
2. **Final test output** (all 37 passed, 0 failed).
3. **Any `UNTRACKED-BUG` entries** (none expected).
4. **Confirmation** that Groups 1–3 are complete, and Group 4 was (or was not) applied.

---

## AGENT INITIATION PROMPT

Copy and paste the following into your autonomous agent:

```text
[AGENT INSTRUCTION START]

READ FIRST, CODE SECOND
Read the entire SPRINT_FIX.md above before making any changes. The execution order is mandatory.

OBJECTIVE
Apply all BUG‑001 through BUG‑012 fixes in the specified Groups. After Group 2, `validate_security.py` must show 37 passed, 0 failed. After Group 3, the GUI must run a dry‑run without errors.

EXECUTION RULES
1. Work file‑by‑file. Never rewrite files not touched by a fix.
2. Use the exact replacement code provided. Do not refactor.
3. Complete each Group’s checkpoint before moving to the next.
4. SPRINT_FIX.md overrides README.md where they conflict.
5. If you discover an untracked bug, document it as `UNTRACKED-BUG: [file] — [desc] — [fix]` and then fix it.

ENVIRONMENT
- Python 3.9+ on Windows (the tool uses robocopy).
- If testing on Linux/macOS, BUG‑002 prevents crashes, but robocopy won’t run.

CHECKPOINT COMMANDS
- Group 1: `python -c "import ghost_harvest.scanner, ghost_harvest.app; print('Imports OK')"`
- Group 2 & 3: `python -X utf8 ghost_harvest\tests\validate_security.py`
- Final: `python main.py` (dry‑run on a small folder)

WHEN AMBIGUITY ARISES
- “Scanner still skips .txt files” → Did you remove the plain‑text block? Re‑check BUG‑001.
- “CREATE_NO_WINDOW AttributeError” → Did you add `import sys` and the conditional flag?
- “Pre‑flight shows zero bytes” → Verify BUG‑009 and BUG‑010 applied correctly.

DELIVERABLE
- List of modified files.
- Final test output (all passing).
- Any UNTRACKED-BUG entries.
- Statement: “All Group 1–3 fixes applied. Group 4 (improvements) applied/not applied.”

[AGENT INSTRUCTION END]
```

---

**This definitive audit supersedes all previous audit files. Apply strictly in order.**