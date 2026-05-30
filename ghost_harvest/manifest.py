"""
GhostHarvest v2.1 — Blocked file manifest writer.

Writes a human-readable manifest of every file that was blocked,
purged, or warned about during the migration.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from . import __version__

__all__ = ["write_manifest"]


def write_manifest(blocked: list[dict], dest: str) -> Path | None:
    """
    Write ``_BLOCKED.txt`` to *dest* listing every flagged file.

    Each entry records the source path, extension, reason, and
    whether it was purged or just warned about.

    Returns the manifest Path on success, or None on failure / no items.
    """
    if not blocked:
        return None

    path = Path(dest) / "_BLOCKED.txt"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"GhostHarvest {__version__} — Blocked / Flagged File Manifest\n")
            f.write(f"Generated : {datetime.now():%Y-%m-%d %H:%M:%S}\n")
            f.write(f"Total items: {len(blocked)}\n")
            f.write("=" * 64 + "\n\n")

            for i, entry in enumerate(blocked, 1):
                action_label = entry.get("action", "purge").upper()
                f.write(f"[{i:04d}] [{action_label}]  {entry['path']}\n")
                f.write(f"       Extension : {entry['ext']}\n")
                f.write(f"       Reason    : {entry['reason']}\n\n")

        return path

    except OSError:
        # Caller should log this
        return None
