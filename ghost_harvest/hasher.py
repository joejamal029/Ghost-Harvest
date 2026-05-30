"""
GhostHarvest v2.1 — Parallelised SHA-256 verification.

After robocopy copies files, this module walks the destination and
verifies each file's SHA-256 hash against its source counterpart
using a ThreadPoolExecutor for I/O-bound parallelism.
"""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from .constants import INTERNAL_PREFIX
from .utils import sha256

__all__ = ["ParallelHashVerifier"]


class ParallelHashVerifier:
    """
    Verify SHA-256 hashes of copied files against their source originals.

    Uses a thread pool whose size matches the robocopy MT thread count
    to keep I/O throughput high without exhausting file handles.
    """

    def __init__(self, max_workers: int = 16) -> None:
        self.max_workers = max(1, min(max_workers, 64))

    # ------------------------------------------------------------------ #

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

        # Parallel hashing
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

                if not sh and not dh:
                    cb(f"  ⚠  Cannot hash both source and destination: {rel_display}\n", "warn")
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
