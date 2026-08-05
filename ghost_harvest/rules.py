"""
GhostHarvest v2.1 — Rules and settings configuration model.

Provides a unified RulesConfig dataclass that synchronizes extension/folder
overrides between Robocopy command generation (/XF, /XD) and post-copy
magic-byte scanning. Supports JSON disk persistence.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .constants import (
    BLOAT_DIRS,
    DANGEROUS_EXTS,
    OLE_DOC_EXTS,
    SAFE_SCRIPT_EXTS,
    ZIP_DOC_EXTS,
)

__all__ = ["RulesConfig", "normalize_ext", "normalize_ext_set"]


def normalize_ext(s: str) -> str:
    """
    Normalize a raw extension string into a lowercased leading-dot format.

    Examples:
        "exe"    -> ".exe"
        "*.ZIP"  -> ".zip"
        " .png " -> ".png"
    """
    cleaned = s.strip().lower()
    if not cleaned:
        return ""
    if cleaned.startswith("*."):
        cleaned = cleaned[1:]
    elif cleaned.startswith("*"):
        cleaned = cleaned[1:]
    if not cleaned.startswith("."):
        cleaned = "." + cleaned
    return cleaned


def normalize_ext_set(items: str | list[str] | set[str]) -> set[str]:
    """
    Parse a comma-, space-, or list-delimited set of extension inputs into
    a normalized set of extensions.
    """
    if isinstance(items, str):
        # Handle comma or space separated string
        raw_list = items.replace(",", " ").split()
    else:
        raw_list = list(items)

    result: set[str] = set()
    for item in raw_list:
        norm = normalize_ext(item)
        if norm:
            result.add(norm)
    return result


@dataclass
class RulesConfig:
    """
    Unified rules configuration for GhostHarvest.

    Attributes:
        allowed_exts: Extensions explicitly unblocked (e.g. {".zip", ".py"}).
        extra_blocked_exts: Additional extensions to block via /XF and scanner.
        extra_blocked_dirs: Additional folder names to exclude via /XD.
        custom_zip_doc_exts: Extra extensions allowed for ZIP magic headers.
        custom_ole_doc_exts: Extra extensions allowed for OLE magic headers.
        custom_script_exts: Extra extensions allowed for Shebang (#!) headers.
        is_persistent: True if loaded from / saved to disk config.
    """

    allowed_exts: set[str] = field(default_factory=set)
    extra_blocked_exts: set[str] = field(default_factory=set)
    extra_blocked_dirs: set[str] = field(default_factory=set)
    custom_zip_doc_exts: set[str] = field(default_factory=set)
    custom_ole_doc_exts: set[str] = field(default_factory=set)
    custom_script_exts: set[str] = field(default_factory=set)
    is_persistent: bool = False

    def has_overrides(self) -> bool:
        """Return True if any custom rules or overrides are active."""
        return bool(
            self.allowed_exts
            or self.extra_blocked_exts
            or self.extra_blocked_dirs
            or self.custom_zip_doc_exts
            or self.custom_ole_doc_exts
            or self.custom_script_exts
        )

    def override_counts(self) -> tuple[int, int, int]:
        """Return (allowed_count, extra_blocked_exts_count, extra_blocked_dirs_count)."""
        return (
            len(self.allowed_exts),
            len(self.extra_blocked_exts),
            len(self.extra_blocked_dirs),
        )

    def get_effective_dangerous_exts(self) -> list[str]:
        """
        Compute the list of robocopy /XF pattern strings to apply.

        Default DANGEROUS_EXTS minus allowed_exts plus extra_blocked_exts.
        """
        effective: list[str] = []
        for pat in DANGEROUS_EXTS:
            clean_ext = normalize_ext(pat)
            if clean_ext not in self.allowed_exts:
                effective.append(pat)

        for ext in sorted(self.extra_blocked_exts):
            clean = normalize_ext(ext)
            pat = f"*{clean}"
            if pat not in effective:
                effective.append(pat)

        return effective

    def get_effective_blocked_exts_set(self) -> set[str]:
        """
        Compute the set of lowercased extension names (without leading dot)
        for double-extension checks in scanner.py.
        """
        effective_patterns = self.get_effective_dangerous_exts()
        result: set[str] = set()
        for pat in effective_patterns:
            ext_name = pat.lower().removeprefix("*.").removeprefix(".")
            if ext_name:
                result.add(ext_name)
        return result

    def get_effective_zip_doc_exts(self) -> set[str]:
        """Compute the set of extensions allowed for ZIP (PK) magic bytes."""
        return ZIP_DOC_EXTS | self.custom_zip_doc_exts | self.allowed_exts

    def get_effective_ole_doc_exts(self) -> set[str]:
        """Compute the set of extensions allowed for OLE magic bytes."""
        return OLE_DOC_EXTS | self.custom_ole_doc_exts | self.allowed_exts

    def get_effective_script_exts(self) -> set[str]:
        """Compute the set of extensions allowed for Shebang (#!) magic bytes."""
        return SAFE_SCRIPT_EXTS | self.custom_script_exts | self.allowed_exts

    def get_effective_bloat_dirs(self, default_dirs: list[str] | None = None) -> list[str]:
        """Compute the list of folder names for robocopy /XD."""
        base = list(default_dirs if default_dirs is not None else BLOAT_DIRS)
        for d in sorted(self.extra_blocked_dirs):
            if d not in base:
                base.append(d)
        return base

    # ── JSON Serialization / Persistence ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Convert RulesConfig to a serializable dictionary."""
        return {
            "allowed_exts": sorted(self.allowed_exts),
            "extra_blocked_exts": sorted(self.extra_blocked_exts),
            "extra_blocked_dirs": sorted(self.extra_blocked_dirs),
            "custom_zip_doc_exts": sorted(self.custom_zip_doc_exts),
            "custom_ole_doc_exts": sorted(self.custom_ole_doc_exts),
            "custom_script_exts": sorted(self.custom_script_exts),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], is_persistent: bool = False) -> RulesConfig:
        """Construct a RulesConfig from a dictionary."""
        return cls(
            allowed_exts=normalize_ext_set(data.get("allowed_exts", [])),
            extra_blocked_exts=normalize_ext_set(data.get("extra_blocked_exts", [])),
            extra_blocked_dirs={str(d).strip() for d in data.get("extra_blocked_dirs", []) if str(d).strip()},
            custom_zip_doc_exts=normalize_ext_set(data.get("custom_zip_doc_exts", [])),
            custom_ole_doc_exts=normalize_ext_set(data.get("custom_ole_doc_exts", [])),
            custom_script_exts=normalize_ext_set(data.get("custom_script_exts", [])),
            is_persistent=is_persistent,
        )

    @classmethod
    def get_config_path(cls) -> Path:
        """Return path to persistent user configuration file."""
        appdata = os.environ.get("APPDATA")
        if appdata:
            base_dir = Path(appdata) / "GhostHarvest"
        else:
            base_dir = Path.home() / ".ghost_harvest"
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir / "rules_config.json"

    @classmethod
    def load_from_disk(cls) -> RulesConfig:
        """Load persistent config from disk if present, else return default config."""
        path = cls.get_config_path()
        if path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return cls.from_dict(data, is_persistent=True)
            except Exception:
                pass
        return cls()

    def save_to_disk(self) -> None:
        """Save current configuration to disk."""
        path = self.get_config_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        self.is_persistent = True

    @classmethod
    def reset_disk_config(cls) -> None:
        """Remove persistent configuration file from disk."""
        path = cls.get_config_path()
        if path.is_file():
            try:
                path.unlink()
            except Exception:
                pass
