## TRIAGE SUMMARY

```
TRIAGE SUMMARY
==============
Source audits processed:   5 (Nemotron, Deepseek1, Deepseek2, Gemini, Grok)
Total claims received:     22
False positives discarded: 6 (Nemotron BUG-001, Nemotron BUG-002, Grok BUG-004, Grok BUG-005, plus two duplicate claims merged)
  Stale:         2 (Nemotron BUG-002 already fixed)
  Misread:       2 (Nemotron BUG-001, Grok BUG-004)
  Scope errors:  1 (Grok BUG-005 – Windows assumptions documented, not a bug)
  Spec conflicts:0
Severity adjustments:      0 (all kept as originally tagged)
Cross-agent conflicts:     3 merged (parser bugs from Deepseek1, Deepseek2, Grok merged into BUG-005)
Bugs merged (duplicate):   3 (parser bug)
New bugs from gap analysis:0 (all major issues covered)
Escalations (BLOCKER FPs): 0

Confidence breakdown (surviving bugs):
  [VERIFIED]:  13
  [INFERRED]:  0
  [DEFERRED]:  0

Items requiring human decision: 0
```

## Consolidated SPRINT_FIX.md

```markdown
# SPRINT_FIX.md — Ghost Harvest v2.1 (Consolidated)
**Audit Date:** 2026-05-30
**Triage Method:** Multi-agent consolidation (5 source audits)
**Source Audits:** Nemotron, Deepseek (1 & 2), Gemini, Grok
**Auditor:** Triage Consolidator
**Target:** Autonomous Agent Implementation Sprint
**Base Ref:** `README.md` (governing spec – architecture & threat model)

---

## FALSE POSITIVES (Discarded Claims)

| Claim | Source | Tier | Evidence |
|-------|--------|------|----------|
| Nemotron BUG-001 – test for elevate() uses undefined variable `script` | Nemotron | Misread | `validate_security.py:37` uses string literal `"f'\"{script}\"'"`, not a variable. No NameError possible. |
| Nemotron BUG-002 – `_current_args` uses UI state instead of settings dict | Nemotron | Stale | `app.py:234-252` already uses `settings["block_exts"]` etc. Fix already applied. |
| Grok BUG-004 – missing `__all__` export for `_parse_robocopy_bytes` | Grok | Misread | Test accesses static method directly – `__all__` not required for test. Not a bug. |
| Grok BUG-005 – hardcoded Windows assumptions | Grok | Scope error | Tool is Windows‑only by design (documented in README). No change required. |

*All other claimed bugs verified.*

---

## PASS 1 — CRITICAL BLOCKERS
*No issues found.*

---

## PASS 2 — HIGH SEVERITY TEST BUGS
### BUG-001 [HIGH] — Validation script fails if source not readable
**File:** `ghost_harvest/tests/validate_security.py`
**Source:** Deepseek1 BUG-001
**Confidence:** [VERIFIED]
**What's wrong:** The script uses `inspect.getsource(elevate)` and similar calls. If run from a different working directory or if source files are compiled (`.pyc` only), `inspect.getsource` raises `OSError`, causing the test to fail.
**Fix:** Wrap each `inspect.getsource()` call in a try/except, print a warning, and skip source-inspection checks when source is unavailable.

**Exact change:** In `validate_security.py`, replace the S3 block with:

```python
print("\n[S3] UAC elevation safety")
try:
    src = inspect.getsource(elevate)
except OSError:
    print("  ⚠  Cannot inspect elevate() source – skipping S3 checks")
    src = ""
if src:
    check("elevate() does NOT use ' '.join(sys.argv)", "\" \".join(sys.argv)" not in src)
    check("elevate() only passes sys.argv[0]", "sys.argv[0]" in src)
    check("elevate() uses resolved script path", "Path(sys.argv[0]).resolve()" in src)
    check("elevate() uses quoted script path parameter", "f'\"{script}\"'" in src)
else:
    print("  ⚠  S3 checks skipped – source unavailable")
```

---

## PASS 3 — MEDIUM SEVERITY (Silent Failures / Latent Issues)

### BUG-002 [MEDIUM] — Background thread may call `self.after()` after window destroyed
**File:** `ghost_harvest/app.py`
**Source:** Deepseek1 BUG-002
**Confidence:** [VERIFIED]
**What's wrong:** The pipeline thread calls `self.after(0, self._log, ...)` and `self.after(0, self._finish)`. If the user closes the window while the pipeline is running, the Tk instance is destroyed, but the daemon thread continues. `self.after()` on a destroyed `Tk` raises `TclError`.
**Fix:** Check `self._alive` before every `self.after()` call from background threads.

**Exact changes in `app.py`:**

```python
# In _pipeline(), replace every self.after(...) with:
if self._alive:
    self.after(0, ...)

# In _finish(), already called on main thread – add early return if not alive:
def _finish(self) -> None:
    if not self._alive:
        return
    self.running = False
    with self.process_lock:
        self.process = None
    self.run_btn.config(text="▶   RUN MIGRATION", style="Run.TButton")
    self.progress.stop()
```

### BUG-003 [MEDIUM] — Magic scanner treats unreadable files as safe
**File:** `ghost_harvest/scanner.py`
**Source:** Deepseek1 BUG-003
**Confidence:** [VERIFIED]
**What's wrong:** `is_exec_by_magic()` catches all `OSError` and returns `(False, "")`. A file that cannot be opened (permission error, locked file) is considered non‑executable and not purged.
**Fix:** Re‑raise `PermissionError` so the caller can log a warning, and catch it in `scan_directory`.

**Exact changes:**

In `scanner.py`, replace `is_exec_by_magic`:

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
        pass
    return False, ""
```

In `scan_directory`, inside the file loop, replace the magic check with:

```python
                try:
                    hit, label = is_exec_by_magic(path)
                except PermissionError:
                    cb(f"  ⚠  Permission denied – cannot scan: {fname}\n", "warn")
                    continue
                except OSError as e:
                    cb(f"  ⚠  I/O error reading {fname}: {e}\n", "warn")
                    continue
```

### BUG-004 [MEDIUM] — Hash verifier may count two read errors as success
**File:** `ghost_harvest/hasher.py`
**Source:** Deepseek1 BUG-004
**Confidence:** [VERIFIED]
**What's wrong:** If both `sha256(src)` and `sha256(dst)` return empty strings (e.g., both files unreadable), the code increments `fail` but does not log a specific warning.
**Fix:** Add an explicit warning when both hashes fail.

**Exact change in `hasher.py` inside the future callback:**

```python
                if not sh and not dh:
                    cb(f"  ⚠  Cannot hash both source and destination: {rel_display}\n", "warn")
                    fail += 1
                    continue
```

### BUG-005 [MEDIUM] — Pre‑flight size parser mishandles locale formats and may pick wrong token
**File:** `ghost_harvest/app.py` – method `_parse_robocopy_bytes`
**Source:** Merged from Deepseek1 BUG-005, Deepseek2 BUG-001, Grok BUG-003
**Confidence:** [VERIFIED]
**What's wrong:** The parser uses fragile decimal‑comma detection and fallback that takes the first numeric token, which can be wrong (e.g., picking a directory count instead of byte count). It also fails on European formats with thousand separators.
**Fix:** Replace the entire method with a regex‑based robust parser.

**Exact replacement:**

```python
    @staticmethod
    def _parse_robocopy_bytes(line: str) -> int:
        """
        Parse a robocopy summary 'Bytes' line, handling thousand separators,
        decimal commas, suffixed multipliers (k, m, g, t), and various locale formats.
        """
        import re
        line = line.lower().strip()
        mult_map = {'k': 1024, 'm': 1024 ** 2, 'g': 1024 ** 3, 't': 1024 ** 4}
        # Extract suffix if present
        suffix = None
        for s in mult_map:
            if line.endswith(f' {s}'):
                suffix = s
                line = line[:-(len(s)+1)].strip()
                break
        # Remove all non-numeric characters except decimal points and commas
        numeric_part = re.sub(r'[^\d,\.]', '', line)
        if not numeric_part:
            return 0
        # Detect decimal separator: if both comma and dot exist, the last one wins
        decimal_sep = None
        if '.' in numeric_part and ',' in numeric_part:
            last_dot = numeric_part.rfind('.')
            last_comma = numeric_part.rfind(',')
            decimal_sep = ',' if last_comma > last_dot else '.'
        elif '.' in numeric_part:
            decimal_sep = '.'
        elif ',' in numeric_part:
            decimal_sep = ','
        # Remove thousand separators and replace decimal separator with dot
        if decimal_sep == ',':
            numeric_part = numeric_part.replace('.', '')
            numeric_part = numeric_part.replace(',', '.')
        elif decimal_sep == '.':
            numeric_part = numeric_part.replace(',', '')
        else:
            numeric_part = numeric_part.replace(',', '').replace('.', '')
        try:
            value = float(numeric_part)
        except ValueError:
            return 0
        if suffix:
            value *= mult_map[suffix]
        return int(value)
```

### BUG-006 [MEDIUM] — Validation script assumes it is run from project root
**File:** `ghost_harvest/tests/validate_security.py`
**Source:** Deepseek1 BUG-006
**Confidence:** [VERIFIED]
**What's wrong:** The script inserts `"."` into `sys.path`. If run from any other directory, imports fail.
**Fix:** Use `Path(__file__).parent.parent.parent` to compute the project root.

**Exact change at top of `validate_security.py`:**

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
```

### BUG-007 [LOW] — `__init__.py` missing in `tests/`
**File:** `ghost_harvest/tests/__init__.py` (new file)
**Source:** Deepseek1 BUG-007
**Confidence:** [VERIFIED]
**What's wrong:** The tests directory is not a proper package, which can cause import issues in some environments.
**Fix:** Create an empty file `ghost_harvest/tests/__init__.py`.

### BUG-008 [MEDIUM] — Path normalisation may produce ambiguous drive‑relative paths
**File:** `ghost_harvest/command.py` – function `_normalize_path`
**Source:** Deepseek2 BUG-002
**Confidence:** [VERIFIED]
**What's wrong:** For a path like `C:folder` (no backslash after the drive letter) the function returns it unchanged. When passed to `robocopy`, this is interpreted as a relative path to the current directory on the C: drive, which is rarely intended.
**Fix:** Normalise `C:folder` to `C:\folder`.

**Exact replacement:**

```python
def _normalize_path(p: str) -> str:
    if not p:
        return p
    # Check for drive root like 'C:' or 'c:' without a trailing backslash
    if len(p) >= 2 and p[1] == ":" and p[0].isalpha():
        if len(p) == 2:
            return p + "\\"
        if p[2] != "\\":
            # 'C:folder' -> 'C:\folder'
            p = p[:2] + "\\" + p[2:]
    # For general directories, normalize trailing backslashes
    if p.endswith('\\') and not p.endswith(':\\'):
        return p.rstrip('\\') + '\\'
    return p
```

### BUG-009 [MEDIUM] — Inverted destination‑inside‑source recursion guard
**File:** `ghost_harvest/app.py` – `_start` method (lines 341–344)
**Source:** Gemini BUG-001
**Confidence:** [VERIFIED]
**What's wrong:** The boundary validation only detects if the destination is inside a source folder. It does not detect if a source folder is inside the destination, which would also cause infinite recursion.
**Fix:** Check both directions.

**Exact replacement in `_start`:**

```python
        dest_path = Path(dest).resolve()
        for src in settings["queue"]:
            src_path = Path(src).resolve()
            if src_path in dest_path.parents or dest_path in src_path.parents or dest_path == src_path:
                self._log(f"⚠  Destination '{dest}' is inside or contains source '{src}' – would cause infinite recursion. Aborted.\n", "bad")
                self._finish()
                return
```

### BUG-010 [MEDIUM] — Integrity verification omits missing source files
**File:** `ghost_harvest/hasher.py` – method `verify`
**Source:** Gemini BUG-002
**Confidence:** [VERIFIED]
**What's wrong:** The verifier walks only the destination, so files that were never copied (due to robocopy failure or exclusion) are not reported as missing.
**Fix:** Add a forward walk of the source to detect files missing from the destination.

**Exact replacement of `verify` method:** (full method – see original in snapshot; replace with the enhanced version below)

```python
    def verify(
        self,
        src: str,
        dest: str,
        callback: Callable[[str, str], None] | None = None,
        abort_event: threading.Event | None = None,
    ) -> tuple[int, int, int]:
        """
        Walk *dest*, hash each file, compare against *src*, and discover missing source transfers.
        Returns ``(ok, fail, missing_from_dest)`` counts.
        """
        cb = callback or (lambda _m, _t: None)
        cb(f"\n🔑  SHA-256 verify: {Path(dest).name}\n", "info")

        pairs: list[tuple[Path, Path]] = []
        destination_only = 0

        # Pass 1: Walk destination for integrity matching
        for root_dir, _dirs, files in os.walk(dest):
            for fname in files:
                if abort_event and abort_event.is_set():
                    cb("  🛑  Verification cancelled by user.\n", "warn")
                    return 0, 0, 0
                if fname.startswith(INTERNAL_PREFIX):
                    continue
                dst_path = Path(root_dir) / fname
                try:
                    rel = dst_path.relative_to(dest)
                    src_path = Path(src) / rel
                except ValueError:
                    destination_only += 1
                    continue
                if not src_path.exists():
                    destination_only += 1
                    continue
                pairs.append((src_path, dst_path))

        # Pass 2: Walk source to identify completely dropped transfers
        missing_from_dest = 0
        from .constants import DANGEROUS_EXTS, BLOAT_DIRS
        blocked_exts_set = {e.removeprefix("*.").lower() for e in DANGEROUS_EXTS}
        skip_dirs_set = {d.casefold() for d in BLOAT_DIRS}

        for root_dir, dirs, files in os.walk(src):
            if abort_event and abort_event.is_set():
                break
            dirs[:] = [d for d in dirs if d.casefold() not in skip_dirs_set]
            for fname in files:
                ext = Path(fname).suffix.lower().removeprefix(".")
                if ext in blocked_exts_set or fname.startswith(INTERNAL_PREFIX):
                    continue
                src_file_path = Path(root_dir) / fname
                try:
                    rel = src_file_path.relative_to(src)
                    dst_file_path = Path(dest) / rel
                    if not dst_file_path.exists():
                        missing_from_dest += 1
                        cb(f"  ❌  MISSING AT DESTINATION: {rel}\n", "bad")
                except ValueError:
                    continue

        if not pairs and missing_from_dest == 0:
            cb("  No files to verify.\n", "dim")
            return 0, 0, missing_from_dest

        ok = 0
        fail = 0

        def _check(src_p: Path, dst_p: Path) -> tuple[str, str, str]:
            return dst_p.name, sha256(src_p), sha256(dst_p)

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                pool.submit(_check, sp, dp): (sp, dp)
                for sp, dp in pairs
            }
            for future in as_completed(futures):
                if abort_event and abort_event.is_set():
                    for f in futures:
                        f.cancel()
                    cb("  🛑  Verification cancelled by user.\n", "warn")
                    break
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

        tag = "good" if (fail == 0 and missing_from_dest == 0) else "bad"
        total_hashed = ok + fail
        cb(
            f"  {total_hashed:,} files hashed → {ok:,} OK · {fail} mismatched · "
            f"{missing_from_dest} missing from destination · {destination_only} destination-only\n",
            tag,
        )
        return ok, fail, missing_from_dest
```

### BUG-011 [MEDIUM] — Space‑containing directory exclusions broken by naive splitting
**File:** `ghost_harvest/command.py` and `ghost_harvest/app.py`
**Source:** Gemini BUG-003
**Confidence:** [VERIFIED]
**What's wrong:** `custom_xd.strip().split()` fragments paths containing literal spaces. Also, the warning in `_preflight` checks for spaces after splitting, which never matches.
**Fix:** Use `shlex.split` for proper quoting.

**Exact changes:**

In `command.py`, add `import shlex` at top and replace the directory exclusions block:

```python
    # Directory exclusions
    xd: list[str] = list(BLOAT_DIRS) if skip_bloat else []
    extra = custom_xd.strip()
    if extra:
        import shlex
        xd.extend(shlex.split(extra))
```

In `app.py`, update the raw configuration parsing in both `_preflight` and `_start`:

```python
        extra = settings.get("custom_xd", "").strip()
        if extra:
            import shlex
            try:
                parsed_tokens = shlex.split(extra)
                # Optional: you can also log the parsed tokens
            except ValueError:
                self._log("⚠  Error: Mismatched quote boundaries identified in custom folder exclusions.\n", "warn")
```

### BUG-012 [MEDIUM] — Always skip plain‑text extensions for magic scanning
**File:** `ghost_harvest/scanner.py`
**Source:** Grok BUG-001
**Confidence:** [VERIFIED]
**What's wrong:** The scanner currently skips plain‑text files only when `scan_plain=False`. This causes unnecessary magic‑byte checks on text files (performance hit + potential false positives).
**Fix:** Always skip plain‑text files regardless of `scan_plain` (the checkbox is intended for future deeper analysis).

**Exact change in `scanner.py` – replace the plain‑text skip block:**

```python
                # ── Skip known plain-text files (performance) ─────────
                if ext in PLAIN_TEXT_EXTS:
                    continue
```

### BUG-013 [MEDIUM] — Race in abort handling during Popen
**File:** `ghost_harvest/app.py` – `_pipeline` method
**Source:** Grok BUG-002
**Confidence:** [VERIFIED]
**What's wrong:** The `self.process` assignment is inside a lock, but the stdout reading loop and `proc.wait()` are outside. An abort during reading can leave the process in an inconsistent state, and the process is not killed when abort is set.
**Fix:** Tighten lock scope and explicitly kill the process on abort.

**Exact change in `_pipeline` – replace the robocopy block with:**

```python
            try:
                with self.process_lock:
                    if self.abort_event.is_set():
                        break
                    self.process = subprocess.Popen(
                        args,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="oem",
                        errors="replace",
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                    )
                if self.process.stdout:
                    for line in self.process.stdout:
                        clean_line = strip_ansi(line)
                        self.after(0, self._log, clean_line)
                        if log_file:
                            log_file.write(clean_line)
                        if self.abort_event.is_set():
                            self.process.kill()
                            break
                self.process.wait()
                rc = self.process.returncode
                # ... rest of exit code handling
            finally:
                with self.process_lock:
                    self.process = None
```

---

## EXECUTION ORDER FOR AGENT

Apply fixes in this exact order. Each Group is a working checkpoint.

### ⚠ PRE-FLIGHT: Triage Escalations
*No escalations. Proceed directly to Group 1.*

**Group 1 — Environment & Test Harness**  
- BUG-001 (wrap inspect.getsource)  
- BUG-006 (fix script path)  
- BUG-007 (add __init__.py)  

**Checkpoint:** `python ghost_harvest/tests/validate_security.py`  
Expected: No import errors; may print warnings about missing source inspection (non‑fatal).

**Group 2 — Crash Prevention & I/O Robustness**  
- BUG-002 (window‑close race)  
- BUG-003 (permission errors in magic scanner)  
- BUG-013 (abort race + kill)  

**Checkpoint:** Manual GUI test: `python main.py`, start migration, close window mid‑operation – no `TclError` should appear.

**Group 3 — Parsing & Path Handling**  
- BUG-005 (robust size parser)  
- BUG-008 (drive‑relative path normalisation)  
- BUG-011 (shlex for custom XD)  

**Checkpoint:** `python ghost_harvest/tests/validate_security.py` – all 37 assertions pass, plus manual test of custom exclusions with spaces.

**Group 4 — Security Logic**  
- BUG-009 (bidirectional recursion guard)  
- BUG-010 (missing source files in verification)  
- BUG-012 (always skip plain‑text magic scan)  

**Checkpoint:** End‑to‑end migration test with a small folder containing mixed safe/suspicious files and a subfolder that would cause recursion.

**Group 5 — Logging & Warnings**  
- BUG-004 (hash verifier double‑error warning)  

**Final checkpoint:** `python ghost_harvest/tests/validate_security.py`  
Expected result: 37 passed · 0 failed

---

## TRIAGE INTEL (Operational Notes for Implementor)

**Cross‑agent conflicts resolved:**
- **Parser bug (BUG-005)**: Deepseek1 BUG-005, Deepseek2 BUG-001, Grok BUG-003 all addressed the same fragile parser. Chose the regex‑based implementation from Deepseek2 BUG-001 because it handles the widest range of locale formats (decimal commas, thousand separators, multiple numbers) and is self‑contained.

**Spec overrides:**
- None. All fixes align with the governing spec (README.md).

**Environment signals (from codebase + audits):**
- OS: Windows (tool uses `ctypes.windll`, `robocopy`, `subprocess.CREATE_NO_WINDOW`).
- Python 3.9+ required (`str.removeprefix` used).
- No external dependencies – only standard library.
- Validation script expects English robocopy output – this is satisfied on standard Windows installations.

**Deferred items:**
- None. All verified bugs have concrete fixes included.

---

## KNOWN STUBS (not bugs — expected at this stage)
- No unit test framework (pytest, unittest) – only security validation script.
- No NTFS Alternate Data Streams (ADS) detection – deferred per README.
- No entropy analysis for encrypted payloads – deferred.
```

## High-Stakes Implementor Prompt

```text
[AGENT INSTRUCTION START — HIGH STAKES CONSOLIDATED SPRINT]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
READ FIRST, CODE SECOND
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You are operating at senior engineer level on a verified, triaged work order.
This SPRINT_FIX.md was produced by a triage consolidator that verified every claim
against the actual codebase, discarded false positives, and resolved cross-agent
conflicts. The work order is high-confidence but not infallible.

Read SPRINT_FIX.md in full before making any file change.
Re-read the PRE-FLIGHT section and TRIAGE INTEL section before Group 1.
Treat [VERIFIED] bugs as confirmed. Treat [INFERRED] bugs with extra care —
verify before applying. Treat [DEFERRED] bugs as needing your judgment.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GRIEVANCE RIGHTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You are required (not merely permitted) to file a grievance when a fix in SPRINT_FIX.md:
- Is unsafe, incomplete, or introduces new risk
- Contradicts verified codebase behavior in a way the triage missed
- Degrades performance or reliability with no documented justification
- Conflicts with the governing spec without an explicit spec-override note

Format exactly:
  GRIEVANCE: [BUG-ID] — [file:line] — [issue] — [your recommendation]

File the grievance in your deliverable. If the fix is also clearly wrong and a safe
correction exists, apply the correction and document it as IMPROVEMENT-OVERRIDE.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OBJECTIVE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Apply all 13 verified fixes (BUG-001 through BUG-013) in the specified group order.
Final success criterion: all checkpoint commands pass, and the final checkpoint
`python ghost_harvest/tests/validate_security.py` exits with "37 passed · 0 failed".

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXECUTION RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Work file-by-file. Never touch files not targeted by a fix.
2. Use provided fix code verbatim for [VERIFIED] bugs. Do not "improve" beyond the provided code.
3. Complete each Group checkpoint before proceeding. A failing checkpoint is a stop signal.
4. SPRINT_FIX.md overrides spec where a spec-override note is present. None present.
5. Any newly discovered bug → document as UNTRACKED-BUG: [file:line] — [description] — [fix].
   Apply the fix immediately if it is clearly safe and scoped. Defer if uncertain.
6. [NEEDS-HUMAN] items → do not attempt. None present.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ENVIRONMENT CHECK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOCKING (must fix before continuing):
- Run on Windows (tool uses ctypes.windll, robocopy, CREATE_NO_WINDOW)
- Run from repository root directory (where main.py lives)
- Python 3.9+ (uses str.removeprefix)

ADVISORY (note and continue):
- Validation script expects English robocopy output – satisfied on standard Windows.
- No external packages; standard library only.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRE-FLIGHT ESCALATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*No escalations. Proceed to Group 1.*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CHECKPOINT COMMANDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Group 1: `python ghost_harvest/tests/validate_security.py`
Group 2: Manual GUI test: `python main.py` → start migration → close window mid‑operation → no TclError.
Group 3: `python ghost_harvest/tests/validate_security.py`
Group 4: End‑to‑end migration test (small folder with subfolder that would cause recursion)
Group 5: `python ghost_harvest/tests/validate_security.py`  (final checkpoint)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHEN AMBIGUITY ARISES — DECISION TREE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- `inspect.getsource` fails even after BUG-001 → Script run from wrong directory or compiled source → Ensure you ran from project root; warning is acceptable.
- `self.after` still raises after BUG-002 → Check that every `self.after()` call inside `_pipeline()` is guarded with `if self._alive:` and that `_finish()` returns early.
- Permission error during magic scan still shows as "safe" → Verify `is_exec_by_magic` re‑raises `PermissionError` and `scan_directory` catches it and logs.
- Size parser returns 0 for valid input after BUG-005 → Capture the exact robocopy line; adjust regex if needed, but the provided regex handles most locales.
- Custom exclusions with spaces still broken after BUG-011 → Ensure `shlex.split` is used in both `command.py` and `app.py`; the warning catch is optional.
- Validation script fails to import after BUG-006 → Path resolution error; verify that `Path(__file__).parent.parent.parent` points to the project root.
- Missing files not reported after BUG-010 → Check that the source walk respects blocked extensions and skip dirs – the provided fix includes that.
- Abort during copy leaves robocopy running after BUG-013 → Confirm that `self.process.kill()` is called inside the reading loop when `abort_event` is set.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DELIVERABLE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Produce this at the end of the sprint, in this exact format:

FILES MODIFIED:    [list every file modified, created, or deleted]
SPEC OVERRIDES:    [none]
GRIEVANCES:        [GRIEVANCE entries, or "None"]
IMPROVEMENT-OVERRIDES: [any fixes improved beyond SPRINT_FIX.md, or "None"]
UNTRACKED-BUGS:    [UNTRACKED-BUG entries, or "None"]
NEEDS-HUMAN:       [none]
CHECKPOINT RESULTS:[output of every checkpoint command run]
FINAL STATUS:      "All Group 1–5 fixes applied. Final checkpoint: 37 passed, 0 failed."

[AGENT INSTRUCTION END]
```