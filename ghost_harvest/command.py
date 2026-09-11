"""
GhostHarvest v2.1 — Robocopy command builder.

Two functions:
  • ``build_args``  → list[str] for subprocess.Popen (shell=False, SAFE)
  • ``build_display_cmd`` → str for the GUI preview box (human-readable)
"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import TYPE_CHECKING

from .constants import BLOAT_DIRS, DANGEROUS_EXTS
from .utils import is_file_path

if TYPE_CHECKING:
    from .rules import RulesConfig

__all__ = ["build_args", "build_display_cmd"]


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


def build_args(
    source: str,
    dest: str,
    threads: int = 16,
    *,
    file_name: str | None = None,
    restartable: bool = True,
    dry_run: bool = False,
    block_exts: bool = True,
    skip_bloat: bool = True,
    custom_xd: str = "",
    save_log: bool = True,
    rules: RulesConfig | None = None,
) -> list[str]:
    """
    Build the robocopy argument list for subprocess.Popen(shell=False).

    Security: returns a **list** — never a single string that is handed
    to cmd.exe, eliminating command-injection via crafted folder names.
    Includes /XJ to block junction-point traversal attacks (S4).
    Supports copying individual files or full directory trees.
    """
    if file_name is not None:
        is_single_file = True
        source_dir = _normalize_path(source)
        target_file: str | None = file_name
    elif is_file_path(source):
        is_single_file = True
        src_path = Path(source)
        source_dir = _normalize_path(str(src_path.parent))
        target_file = src_path.name
    else:
        is_single_file = False
        source_dir = _normalize_path(source)
        target_file = None

    dest_dir = _normalize_path(dest)

    args: list[str] = [
        "robocopy",
        source_dir,
        dest_dir,
    ]

    if is_single_file and target_file:
        args.append(target_file)
    else:
        args.append("/E")  # recurse including empty dirs

    args.extend([
        "/COPY:DAT",        # Data + Attributes + Timestamps (no ADS)
        f"/MT:{threads}",   # multi-threaded
    ])

    if restartable:
        args.append("/ZB")  # restartable → backup mode fallback

    args.extend(["/R:2", "/W:5"])  # retries / wait

    # Junction-point exclusion — prevents symlink-based traversal (S4 / H4)
    args.append("/XJ")

    if dry_run:
        args.append("/L")

    # Dangerous extension filter
    if block_exts:
        args.append("/XF")
        if rules is not None:
            args.extend(rules.get_effective_dangerous_exts())
        else:
            args.extend(DANGEROUS_EXTS)

    # Directory exclusions
    if rules is not None and skip_bloat:
        xd: list[str] = rules.get_effective_bloat_dirs(BLOAT_DIRS)
    elif skip_bloat:
        xd = list(BLOAT_DIRS)
    else:
        xd = []

    extra = custom_xd.strip()
    if extra:
        xd.extend(shlex.split(extra))
    if xd:
        args.append("/XD")
        args.extend(xd)

    return args


def build_display_cmd(args: list[str]) -> str:
    """
    Convert an argument list into a human-readable command string
    for the GUI preview text box.

    Quotes any argument containing spaces or double quotes,
    and escapes embedded double quotes.
    """
    parts: list[str] = []
    for a in args:
        if '"' in a:
            a = a.replace('"', '\\"')
        if " " in a or '"' in a:
            parts.append(f'"{a}"')
        else:
            parts.append(a)
    return "  ".join(parts)
