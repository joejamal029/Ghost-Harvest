"""
GhostHarvest v2.1 — Utility functions.

Admin elevation, hashing, size formatting.
"""

import ctypes
import hashlib
import re
import sys
from pathlib import Path

__all__ = ["is_admin", "elevate", "sha256", "format_size", "strip_ansi"]


def is_admin() -> bool:
    """Return True if the current process has Administrator privileges."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except AttributeError:
        # Not on Windows — assume no admin required
        return True
    except OSError:
        return False


def elevate() -> None:
    """
    Re-launch the current script with UAC elevation ('Run as Administrator').

    Security: Only the script path is passed — no additional arguments.
    This prevents argument-injection attacks via crafted sys.argv values
    that could execute arbitrary commands as Administrator.
    """
    if sys.platform != "win32":
        print("Elevation requested but not on Windows. Run as administrator manually.")
        sys.exit(1)

    script = str(Path(sys.argv[0]).resolve())
    result = ctypes.windll.shell32.ShellExecuteW(
        None,                    # parent window handle
        "runas",                 # verb — request elevation
        sys.executable,          # program — python.exe / pythonw.exe
        f'"{script}"',           # parameters — properly quoted script path
        None,                    # working directory
        1,                       # show-window flag (SW_SHOWNORMAL)
    )
    if result <= 32:
        ctypes.windll.user32.MessageBoxW(
            None,
            "Administrator privileges are required to run this application.\n\nThe operation was cancelled or failed to elevate.",
            "Elevation Required",
            0x10 | 0x0  # MB_ICONERROR | MB_OK
        )
        sys.exit(1)
    sys.exit(0)


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    """
    Compute SHA-256 hex digest of a file.

    Returns empty string on any I/O error (logged by the caller).
    Uses 1 MiB chunks to keep memory pressure low on large files.
    """
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while True:
                block = f.read(chunk)
                if not block:
                    break
                h.update(block)
        return h.hexdigest()
    except (OSError, PermissionError):
        # Caller decides how to surface this
        return ""


def format_size(b: int) -> str:
    """Human-readable file size string."""
    if b >= 1024 ** 3:
        return f"{b / 1024 ** 3:.2f} GB"
    if b >= 1024 ** 2:
        return f"{b / 1024 ** 2:.1f} MB"
    if b >= 1024:
        return f"{b / 1024:.1f} KB"
    return f"{b:,} B"


_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[mK]')


def strip_ansi(text: str) -> str:
    """Strip ANSI escape sequences from a string."""
    return _ANSI_RE.sub('', text)
