"""
GhostHarvest v2.1 — Settings and custom rules dialog.

Provides a modal window for configuring extension overrides, extra blocklists,
and scanner allowlists, with options for session-only application or disk persistence.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from .rules import RulesConfig, normalize_ext_set
from .theme import BG

__all__ = ["SettingsDialog"]


class SettingsDialog(tk.Toplevel):
    """
    Modal window for customizing GhostHarvest rules and settings.
    """

    def __init__(
        self,
        parent: tk.Tk,
        current_rules: RulesConfig,
        on_apply: Callable[[RulesConfig], None],
    ) -> None:
        super().__init__(parent)
        self.title("⚙ GhostHarvest — Custom Rules & Settings")
        self.geometry("700x600")
        self.minsize(640, 520)
        self.configure(bg=BG)
        self.transient(parent)
        self.grab_set()

        self.on_apply = on_apply
        self.rules = current_rules

        self._build()
        self._load_current_values()

    def _build(self) -> None:
        root = ttk.Frame(self, padding="18 16 18 16")
        root.pack(fill="both", expand=True)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = ttk.Frame(root)
        hdr.pack(fill="x", pady=(0, 4))
        ttk.Label(hdr, text="⚙  Rules & Extension Settings", style="H1.TLabel").pack(side="left")

        desc = (
            "Customize file extensions and directory filters without modifying source code.\n"
            "Unblocking an extension updates both Robocopy (/XF) and the Post-Copy Scanner."
        )
        ttk.Label(root, text=desc, style="Dim.TLabel").pack(anchor="w", pady=(0, 10))
        ttk.Separator(root).pack(fill="x", pady=(0, 12))

        # ── Scrollable / Container Frame ──────────────────────────────────────
        container = ttk.Frame(root)
        container.pack(fill="both", expand=True, pady=(0, 10))

        # Section 1: Allowed / Unblocked Extensions
        ttk.Label(
            container, text="1. Allowed / Unblocked Extensions", style="H2.TLabel"
        ).pack(anchor="w", pady=(0, 2))
        ttk.Label(
            container,
            text="Unblocks extensions from Robocopy (/XF) and prevents scanner purges (e.g. .zip, .py, .iso):",
            style="Dim.TLabel",
        ).pack(anchor="w", pady=(0, 3))
        self.allowed_var = tk.StringVar()
        ttk.Entry(container, textvariable=self.allowed_var, font=("Consolas", 10)).pack(
            fill="x", ipady=4, pady=(0, 12)
        )

        # Section 2: Additional Blocked Extensions
        ttk.Label(
            container, text="2. Additional Blocked Extensions", style="H2.TLabel"
        ).pack(anchor="w", pady=(0, 2))
        ttk.Label(
            container,
            text="Extra file patterns to block in Robocopy and purge during double-ext checks (e.g. *.iso, *.vhd):",
            style="Dim.TLabel",
        ).pack(anchor="w", pady=(0, 3))
        self.extra_blocked_exts_var = tk.StringVar()
        ttk.Entry(container, textvariable=self.extra_blocked_exts_var, font=("Consolas", 10)).pack(
            fill="x", ipady=4, pady=(0, 12)
        )

        # Section 3: Additional Excluded Directories
        ttk.Label(
            container, text="3. Additional Excluded Directories", style="H2.TLabel"
        ).pack(anchor="w", pady=(0, 2))
        ttk.Label(
            container,
            text="Extra directory names to exclude during Robocopy (/XD) and scanner walking:",
            style="Dim.TLabel",
        ).pack(anchor="w", pady=(0, 3))
        self.extra_blocked_dirs_var = tk.StringVar()
        ttk.Entry(container, textvariable=self.extra_blocked_dirs_var, font=("Consolas", 10)).pack(
            fill="x", ipady=4, pady=(0, 12)
        )

        # Section 4: Safe Shebang Script & Archive Extensions
        ttk.Label(
            container, text="4. Safe Shebang (#!) Script Extensions", style="H2.TLabel"
        ).pack(anchor="w", pady=(0, 2))
        ttk.Label(
            container,
            text="Extra extensions allowed for Shebang (#!) script headers to prevent false-positive purges:",
            style="Dim.TLabel",
        ).pack(anchor="w", pady=(0, 3))
        self.custom_script_var = tk.StringVar()
        ttk.Entry(container, textvariable=self.custom_script_var, font=("Consolas", 10)).pack(
            fill="x", ipady=4, pady=(0, 12)
        )

        # ── Buttons Frame ─────────────────────────────────────────────────────
        ttk.Separator(root).pack(fill="x", pady=(0, 12))
        bf = ttk.Frame(root)
        bf.pack(fill="x")

        ttk.Button(
            bf, text="Apply for Session", style="Accent.TButton", command=self._apply_session
        ).pack(side="left", padx=(0, 6))

        ttk.Button(
            bf, text="Save as Permanent Default", style="Run.TButton", command=self._save_persistent
        ).pack(side="left", padx=(0, 6))

        ttk.Button(
            bf, text="Reset to Factory Defaults", style="Stop.TButton", command=self._reset_defaults
        ).pack(side="left", padx=(0, 6))

        ttk.Button(
            bf, text="Cancel", command=self.destroy
        ).pack(side="right")

    def _load_current_values(self) -> None:
        """Populate entry widgets from current RulesConfig."""
        self.allowed_var.set(", ".join(sorted(self.rules.allowed_exts)))
        self.extra_blocked_exts_var.set(", ".join(sorted(self.rules.extra_blocked_exts)))
        self.extra_blocked_dirs_var.set(", ".join(sorted(self.rules.extra_blocked_dirs)))
        self.custom_script_var.set(", ".join(sorted(self.rules.custom_script_exts)))

    def _get_rules_from_entries(self) -> RulesConfig:
        """Parse text fields into a fresh RulesConfig object."""
        return RulesConfig(
            allowed_exts=normalize_ext_set(self.allowed_var.get()),
            extra_blocked_exts=normalize_ext_set(self.extra_blocked_exts_var.get()),
            extra_blocked_dirs={
                d.strip() for d in self.extra_blocked_dirs_var.get().replace(",", " ").split() if d.strip()
            },
            custom_script_exts=normalize_ext_set(self.custom_script_var.get()),
        )

    def _apply_session(self) -> None:
        """Apply rules in-memory for current app session."""
        new_rules = self._get_rules_from_entries()
        new_rules.is_persistent = False
        self.on_apply(new_rules)
        self.destroy()

    def _save_persistent(self) -> None:
        """Save rules to disk and apply."""
        new_rules = self._get_rules_from_entries()
        try:
            new_rules.save_to_disk()
            messagebox.showinfo(
                "Saved Defaults",
                "Custom settings successfully saved to disk.\nThey will load automatically on startup.",
                parent=self,
            )
            self.on_apply(new_rules)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save settings to disk:\n{e}", parent=self)

    def _reset_defaults(self) -> None:
        """Reset config to factory defaults and remove disk file."""
        if messagebox.askyesno(
            "Reset Defaults",
            "Are you sure you want to reset all rules and overrides to factory defaults?",
            parent=self,
        ):
            RulesConfig.reset_disk_config()
            empty_rules = RulesConfig()
            self.on_apply(empty_rules)
            self.destroy()
