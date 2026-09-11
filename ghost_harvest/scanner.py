"""
GhostHarvest v2.1 — Post-copy security scanner.

Scans the DESTINATION directory after robocopy finishes.
This avoids walking the slow/damaged infected source drive twice.

Checks:
  • Magic-byte signatures — flags disguised executables
  • Double-extension tricks — e.g. photo.jpg.exe
  • Extension ↔ magic mismatch — e.g. a .jpg with MZ header
  • ZIP/OLE document allowlisting — warns but does not purge
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Callable

from .constants import (
    EXEC_SIGS,
    MAGIC_READ_SIZE,
    PLAIN_TEXT_EXTS,
    ZIP_DOC_EXTS,
    OLE_DOC_EXTS,
    SAFE_SCRIPT_EXTS,
    INTERNAL_PREFIX,
)

__all__ = ["PostCopyScanner", "is_exec_by_magic", "has_double_extension"]


# ── Low-level helpers ──────────────────────────────────────────────────────────

def is_exec_by_magic(path: Path) -> tuple[bool, str]:
    """
    Read the first MAGIC_READ_SIZE bytes of *path* and test against EXEC_SIGS.

    Returns (True, label) on match, (False, "") otherwise.
    """
    try:
        with open(path, "rb") as f:
            header = f.read(MAGIC_READ_SIZE)
        for offset, sig, label in EXEC_SIGS:
            if header[offset: offset + len(sig)] == sig:
                return True, label
    except PermissionError:
        raise
    except OSError:
        pass
    return False, ""


def has_double_extension(path: Path, blocked_exts_set: set[str]) -> bool:
    """
    Detect double-extension social-engineering tricks.

    Returns True if a file has ≥ 2 suffixes and the final one is in the
    dangerous-extension set  (e.g. `report.pdf.exe`).
    """
    suffixes = path.suffixes  # e.g. ['.pdf', '.exe']
    if len(suffixes) >= 2:
        # removeprefix used correctly — see S2 audit fix
        final_ext = suffixes[-1].lower().removeprefix(".")
        return final_ext in blocked_exts_set
    return False


# ── Public scanner ─────────────────────────────────────────────────────────────

class PostCopyScanner:
    """
    Walk a destination directory and flag suspicious files.

    Each flagged item is a dict::

        {
            "path":   str,          # absolute path in destination
            "ext":    str,          # file extension (or "(none)")
            "reason": str,          # human-readable reason
            "action": "purge"|"warn"
        }

    *purge* → the file should be deleted from the destination.
    *warn*  → the file has a known-safe container extension; log a
              warning but leave it in place.
    """

    def __init__(
        self,
        blocked_exts: set[str],
        skip_dirs: set[str] | None = None,
        zip_doc_exts: set[str] | None = None,
        ole_doc_exts: set[str] | None = None,
        script_doc_exts: set[str] | None = None,
        scan_plain: bool = True,
    ) -> None:
        self.blocked_exts = blocked_exts
        self.skip_dirs = {d.casefold() for d in (skip_dirs or set())}
        self.zip_doc_exts = zip_doc_exts or ZIP_DOC_EXTS
        self.ole_doc_exts = ole_doc_exts or OLE_DOC_EXTS
        self.script_doc_exts = script_doc_exts or SAFE_SCRIPT_EXTS
        self.scan_plain = scan_plain

    # ------------------------------------------------------------------ #

    def _inspect_file(self, path: Path, cb: Callable[[str, str], None]) -> dict | None:
        """Examine a single file against double-extension and magic byte signatures."""
        fname = path.name
        ext = path.suffix.lower()

        # ── Double extension check (H2) ───────────────────────
        if has_double_extension(path, self.blocked_exts):
            entry = {
                "path":   str(path),
                "ext":    ext or "(none)",
                "reason": f"DOUBLE_EXT — suspicious multi-extension: "
                          f"{''.join(path.suffixes)}",
                "action": "purge",
            }
            cb(
                f"  ⚠  {fname}  →  DOUBLE EXTENSION  "
                f"{''.join(path.suffixes)}\n",
                "magic",
            )
            return entry

        # ── Skip known plain-text files (performance) ─────────
        if not self.scan_plain and ext in PLAIN_TEXT_EXTS:
            return None

        # ── Magic-byte check ──────────────────────────────────
        try:
            hit, label = is_exec_by_magic(path)
        except PermissionError:
            cb(f"  ⚠  Permission denied – cannot scan: {fname}\n", "warn")
            return None
        except OSError as e:
            cb(f"  ⚠  I/O error reading {fname}: {e}\n", "warn")
            return None
        if not hit:
            return None

        # Determine action: purge or warn
        action = "purge"
        reason = f"MAGIC_BYTE — {label}"

        if label == "ZIP Archive (DOCX/JAR/APK)" and ext in self.zip_doc_exts:
            action = "warn"
            reason = f"MAGIC_BYTE_WARN — {label} (safe doc ext {ext})"
        elif label == "OLE Compound File (MSI/DOC)" and ext in self.ole_doc_exts:
            action = "warn"
            reason = f"MAGIC_BYTE_WARN — {label} (safe doc ext {ext})"
        elif label == "Script with Shebang (#!)" and ext in self.script_doc_exts:
            action = "warn"
            reason = f"MAGIC_BYTE_WARN — {label} (safe script ext {ext})"

        entry = {
            "path":   str(path),
            "ext":    ext or "(none)",
            "reason": reason,
            "action": action,
        }

        icon = "⚠" if action == "purge" else "ℹ"
        tag = "magic" if action == "purge" else "dim"
        cb(f"  {icon}  {fname}  [{ext}]  →  {label}"
           f"{'  (warn only)' if action == 'warn' else ''}\n", tag)
        return entry

    def scan_file(
        self,
        file_path: str | Path,
        callback: Callable[[str, str], None] | None = None,
    ) -> list[dict]:
        """Inspect an individual file in the destination for security risks."""
        cb = callback or (lambda _m, _t: None)
        path = Path(file_path)
        cb(f"\n🔬  Post-copy scan: {path.name}\n", "magic")
        if not path.is_file():
            return []

        flagged: list[dict] = []
        entry = self._inspect_file(path, cb)
        if entry:
            flagged.append(entry)

        purge_count = sum(1 for e in flagged if e["action"] == "purge")
        warn_count = sum(1 for e in flagged if e["action"] == "warn")
        cb(
            f"  Scan done — {purge_count} to purge · "
            f"{warn_count} warned · {len(flagged)} total flagged\n",
            "magic",
        )
        return flagged

    def scan_directory(
        self,
        directory: str,
        callback: Callable[[str, str], None] | None = None,
        abort_event: threading.Event | None = None,
    ) -> list[dict]:
        """
        Walk *directory* and return a list of flagged items.
        If *directory* points directly to a single file, scans that file.
        """
        if Path(directory).is_file():
            return self.scan_file(directory, callback=callback)

        flagged: list[dict] = []
        cb = callback or (lambda _m, _t: None)

        cb(f"\n🔬  Post-copy scan: {directory}\n", "magic")

        for root_dir, dirs, files in os.walk(directory):
            if abort_event and abort_event.is_set():
                cb("  🛑  Scan cancelled by user.\n", "warn")
                break
            # Skip bloat / system dirs even inside destination (case-folded comparison)
            dirs[:] = [d for d in dirs if d.casefold() not in self.skip_dirs]

            for fname in files:
                if abort_event and abort_event.is_set():
                    break
                # Skip GhostHarvest's own output files and manifest file
                if fname.startswith(INTERNAL_PREFIX) or fname == "_BLOCKED.txt":
                    continue

                path = Path(root_dir) / fname
                entry = self._inspect_file(path, cb)
                if entry:
                    flagged.append(entry)

        purge_count = sum(1 for e in flagged if e["action"] == "purge")
        warn_count = sum(1 for e in flagged if e["action"] == "warn")
        cb(
            f"  Scan done — {purge_count} to purge · "
            f"{warn_count} warned · {len(flagged)} total flagged\n",
            "magic",
        )
        return flagged
