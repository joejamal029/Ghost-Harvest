SPRINT_FIX.md — Ghost Harvest
Audit Date: 2026-05-29
Auditor: Senior Architect Review
Target: Autonomous Agent Implementation Sprint
Base Ref: Ghost Harvest_llm.md (§ references below point there)
---
HOW TO USE THIS FILE
Severity tags are ordered by blast radius: [BLOCKER] first, then [HIGH], [MEDIUM], and finally [IMPROVEMENT]. Apply the groups in the execution order exactly as written. If any fix appears to conflict with the governing snapshot, the snapshot wins unless the fix explicitly states a spec override.
---
PASS 1 — CRITICAL BLOCKERS
BUG-001 [BLOCKER] — `main.py` is truncated and cannot execute
File: `main.py`
What's wrong: The file ends with `main(` instead of a complete call, so `python main.py` raises a syntax error before the app can launch. The entry point is also missing an explicit Windows-only guard, even though the project is documented as Windows-only.
Fix: Replace the entire file body with this exact code:
```py
"""
GhostHarvest v2.1 — Entry point.

Requests UAC elevation on Windows, then launches the GUI.
"""

import sys

from ghost_harvest.utils import elevate, is_admin
from ghost_harvest.app import GhostHarvest


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("GhostHarvest runs on Windows only.")
    if not is_admin():
        elevate()
    GhostHarvest().mainloop()


if __name__ == "__main__":
    main()
```
---
PASS 2 — HIGH SEVERITY TEST BUGS
Pass 2: no issues found.
---
PASS 3 — MEDIUM SEVERITY
BUG-002 [MEDIUM] — Destination skip-dirs are matched case-sensitively
File: `ghost_harvest/scanner.py`
What's wrong: `os.walk()` returns the directory names exactly as they exist on disk, but the scanner compares them against `self.skip_dirs` with a case-sensitive `d not in self.skip_dirs` test. On NTFS, `Node_Modules`, `NODE_MODULES`, and `node_modules` are the same directory for the user, but only the exact-cased form currently gets skipped. That lets known bloat/system folders slip through the post-copy scan.
Fix: Normalize the skip list once in `__init__`, then compare using a case-folded value during traversal. Replace the constructor and walk filter with this exact code:
```py
    def __init__(
        self,
        blocked_exts: set[str],
        skip_dirs: set[str] | None = None,
        zip_doc_exts: set[str] | None = None,
        ole_doc_exts: set[str] | None = None,
        scan_plain: bool = True,
    ) -> None:
        self.blocked_exts = blocked_exts
        self.skip_dirs = {d.casefold() for d in (skip_dirs or set())}
        self.zip_doc_exts = zip_doc_exts or ZIP_DOC_EXTS
        self.ole_doc_exts = ole_doc_exts or OLE_DOC_EXTS
        self.scan_plain = scan_plain
```
and:
```py
        for root_dir, dirs, files in os.walk(directory):
            # Skip bloat / system dirs even inside destination
            dirs[:] = [d for d in dirs if d.casefold() not in self.skip_dirs]
```
---
BUG-003 [MEDIUM] — Pre-flight summary parsing depends on row position
File: `ghost_harvest/app.py`
What's wrong: `_thread_preflight()` stores every colon-delimited robocopy summary row in a list, then assumes `summary_rows[1]` is always the `Files` row and `summary_rows[2]` is always the `Bytes` row. That is brittle: any robocopy wording change, locale variation, or extra summary line can silently produce the wrong file count and size estimate without raising an exception.
Fix: Parse the summary by label instead of by position. Replace the current `summary_rows` block in `_thread_preflight()` with a keyed dictionary and use the labels explicitly:
```py
                summary: dict[str, str] = {}
                if proc.stdout:
                    for line in proc.stdout:
                        clean_line = strip_ansi(line)
                        self.after(0, self._log, clean_line)
                        if ":" not in clean_line:
                            continue
                        label, payload = clean_line.split(":", 1)
                        key = label.strip().lower()
                        if key in {"dirs", "files", "bytes"}:
                            summary[key] = payload.strip()
                proc.wait()

                files_line = summary.get("files")
                if files_line:
                    f_parts = files_line.split()
                    if len(f_parts) >= 3:
                        total_files += int(f_parts[0].replace(",", ""))
                        skipped += int(f_parts[2].replace(",", ""))

                bytes_line = summary.get("bytes")
                if bytes_line:
                    total_bytes += self._parse_robocopy_bytes(f"Bytes: {bytes_line}")
```
---
PASS 4 — ENVIRONMENT & STRUCTURAL
BUG-004 [MEDIUM] — Windows-only behavior is only documented, not enforced
File: `main.py`
What's wrong: The README says the tool is Windows-only, but the entry point previously tried to proceed on any platform. That creates a confusing crash path outside Windows instead of a clean, immediate stop.
Fix: This is already enforced by the new `sys.platform != "win32"` guard in BUG-001. Keep that guard in place and do not remove it.
---
PASS 5 — IMPROVEMENTS
IMP-001 [IMPROVEMENT] — Escape embedded quotes in the GUI command preview
File: `ghost_harvest/command.py`
What's wrong: `build_display_cmd()` wraps arguments containing spaces in double quotes, but embedded `"` characters are not escaped. The preview can therefore misrepresent a path that contains a quote, even though the real subprocess call is safe because it uses an argument list.
Fix: Escape quotes before wrapping the display string:
```py
def build_display_cmd(args: list[str]) -> str:
    """
    Convert an argument list into a human-readable command string
    for the GUI preview text box.

    Quotes any argument containing spaces.
    """
    parts: list[str] = []
    for a in args:
        if '"' in a:
            a = a.replace('"', r'"')
        if " " in a or '"' in a:
            parts.append(f'"{a}"')
        else:
            parts.append(a)
    return "  ".join(parts)
```
---
EXECUTION ORDER FOR AGENT
Apply fixes in this exact order. Each Group is a working checkpoint.
Group 1 — Make the app bootable
BUG-001
Checkpoint: `python -m py_compile main.py`
Group 2 — Fix destination scanning and pre-flight summary parsing
BUG-002
BUG-003
Checkpoint: `python -X utf8 ghost_harvest\tests\validate_security.py`
Group 3 — Apply the preview-text improvement
IMP-001
Checkpoint: `python -X utf8 ghost_harvest\tests\validate_security.py`
Final checkpoint: `python -X utf8 ghost_harvest\tests\validate_security.py`
---
KNOWN STUBS (not bugs — expected at this stage)
None identified.