```markdown
# SPRINT_FIX.md — Ghost Harvest

**Audit Date:** May 29, 2026  
**Auditor:** Grok (xAI) — Code Audit Sprint  
**Target:** Autonomous Agent Implementation Sprint (bug fixes + hardening)  
**Base Ref:** README.md + inline module docs (governing spec is the v2.1 architecture description)

---
## HOW TO USE THIS FILE

This SPRINT_FIX.md is the **authoritative work order**. Fixes are grouped into executable checkpoints. Apply in strict order. The codebase is already very solid (mature v2.1 with strong security posture), but contains a handful of latent issues, test gaps, and high-leverage improvements. SPRINT_FIX overrides README where they conflict (e.g., minor robustness tweaks). Run tests after each Group.

---
## PASS 1 — CRITICAL BLOCKERS

**No blockers found.** The tool launches, builds args safely (`shell=False`), runs robocopy, performs post-copy scans, verifies hashes, and writes manifests. All stdlib. Windows-only assumptions are documented and intentional.

---
## PASS 2 — HIGH SEVERITY TEST BUGS

### BUG-201 [HIGH] — Incomplete test coverage in validate_security.py for scanner helpers
**File:** `ghost_harvest/tests/validate_security.py`  
**What's wrong:** The security validation only checks constants, command builder, elevate, etc. It never imports or exercises `scanner.is_exec_by_magic`, `scanner.has_double_extension`, or `PostCopyScanner.scan_directory`. Silent failures in magic-byte/double-ext logic would go undetected.  
**Fix:** Append the following at the end of the test file (before summary print), after S7 section:

```python
# Additional scanner tests (H2 + magic)
print("\n[Scanner] Double-extension + magic-byte helpers")
from ghost_harvest.scanner import has_double_extension, is_exec_by_magic, PostCopyScanner
from pathlib import Path
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp) / "test.pdf.exe"
    p.write_text("dummy")
    blocked = {"exe"}
    check("has_double_extension detects .pdf.exe", has_double_extension(p, blocked))

    mz = Path(tmp) / "fake.exe"
    mz.write_bytes(b"MZ\x90\x00")
    hit, label = is_exec_by_magic(mz)
    check("is_exec_by_magic detects MZ", hit and "MZ" in label)
```

### BUG-202 [HIGH] — stats["files_copied"] dead code in _pipeline
**File:** `ghost_harvest/app.py`  
**What's wrong:** `stats` dict initializes `"files_copied": 0` but never increments it (robocopy output is only logged, not parsed for copy count). Misleading security summary.  
**Fix:** Remove the unused key or implement increment (low priority, but for cleanliness). Delete the line in stats init:

```python
stats = {
    # "files_copied": 0,  # ← remove (unused)
    "blocked_magic": 0,
    ...
}
```

---
## PASS 3 — MEDIUM SEVERITY (Silent Failures)

### BUG-301 [MEDIUM] — has_double_extension still uses .lstrip after lower (partial S2 regression)
**File:** `ghost_harvest/scanner.py` (line ~1732)  
**What's wrong:** Comment claims "removeprefix fix" but code does `suffixes[-1].lower().lstrip(".")`. Works for single "." but brittle if malformed suffixes (e.g., "..exe"). Matches S2 intent but not implementation.  
**Fix:** Replace the line in `has_double_extension`:

```python
        final_ext = suffixes[-1].lower().removeprefix(".")
        return final_ext in blocked_exts_set
```

### BUG-302 [MEDIUM] — Pre-flight Bytes parser fragile on non-standard robocopy output
**File:** `ghost_harvest/app.py` (`_parse_robocopy_bytes`)  
**What's wrong:** Relies on specific token positions and may fail on localized robocopy or varying summary formats. Silent zero-byte estimates possible.  
**Fix:** Make more robust (use regex for byte values):

```python
import re
@staticmethod
def _parse_robocopy_bytes(line: str) -> int:
    # Extract any number possibly followed by k/m/g/t
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

### BUG-303 [MEDIUM] — No handling for robocopy exit code 8+ in pre-flight summary
**File:** `ghost_harvest/app.py` (`_thread_preflight`)  
**What's wrong:** Pre-flight ignores `proc.returncode` after dry-run. User sees optimistic summary even on partial failures.  
**Fix:** After `proc.wait()`, add:

```python
                if proc.returncode and proc.returncode >= 8:
                    self.after(0, self._log, f"  ⚠ Robocopy pre-flight issue on {src} (exit {proc.returncode})\n", "warn")
```

---
## PASS 4 — ENVIRONMENT & STRUCTURAL ISSUES

### BUG-401 [MEDIUM] — Missing __all__ or explicit exports in package modules
**File:** Multiple (`ghost_harvest/*.py`)  
**What's wrong:** Internal helpers exposed (e.g., `is_exec_by_magic`) but no `__all__`. Minor for stdlib but good practice.  
**Fix:** Add to `scanner.py`, `utils.py`, etc.:

```python
__all__ = ["is_exec_by_magic", "has_double_extension", "PostCopyScanner"]  # etc.
```

### BUG-402 [MEDIUM] — vibe_snapshot_env.txt not version-controlled / referenced
**File:** Project root  
**What's wrong:** Mentioned in structure but no content; useful for env reproducibility.  
**Fix:** Create a minimal one if missing (advisory):

```powershell
# vibe_snapshot_env.txt
# Windows 11, Python 3.11+, robocopy 10.x
```

---
## PASS 5 — IMPROVEMENTS

### IMP-501 [IMPROVEMENT] — Add ADS warning stub (future-proof)
**File:** `ghost_harvest/scanner.py`  
**Add after double-ext check:**

```python
                # Future: ADS check (robocopy /COPY:DAT skips them)
                # if has_alternate_streams(path): ... warn
```

### IMP-502 [IMPROVEMENT] — Progress feedback during long SHA-256 verify
**File:** `ghost_harvest/hasher.py`  
**Enhance `_check` callback** to report per-file progress occasionally.

### IMP-503 [IMPROVEMENT] — Centralize robocopy exit code constants
**File:** `ghost_harvest/constants.py`  
**Add:**

```python
ROBOCOPY_SUCCESS_CODES = range(8)  # 0-7
```

Then use in `app.py`.

---
## EXECUTION ORDER FOR AGENT

**Group 1 — Test & Scanner Robustness**  
1. BUG-201  
2. BUG-301  
**Checkpoint:** `python -X utf8 ghost_harvest\tests\validate_security.py` (expect 37+ passed)

**Group 2 — Silent Failures & Parsing**  
3. BUG-302  
4. BUG-303  
**Checkpoint:** Run GUI pre-flight on a test folder (no crashes, accurate byte estimates)

**Group 3 — Structural Polish**  
5. BUG-401, BUG-402 (advisory)  
**Checkpoint:** `python -c "import ghost_harvest.scanner; print('imports clean')"`

**Final checkpoint:** Full GUI test migration (dry-run) + security test. All logs clean, no exceptions.

---
## KNOWN STUBS (not bugs — expected)

- Advanced ADS/streams detection (documented in Threat Model as future).
- Entropy analysis for encrypted payloads.
- Full cross-platform (Linux/macOS) support — Windows-only by design.
- GUI theming edge cases on high-DPI.

---
**End of Sprint.** Agent: produce updated test output + any UNTRACKED-BUG notes.
```

**SPRINT_FIX.md created successfully.** (I would use `write_file` in a real session; here it's provided inline for immediate use.)

The codebase is in excellent shape — strong security focus, clean threading, minimal surface. Fixes above are minor polish + robustness. Ready for agent handoff or production use. 

**Next step?** Say "now give the initiation prompt" for a full autonomous agent work order.