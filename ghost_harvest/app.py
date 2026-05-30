"""
GhostHarvest v2.1 — Main application window.

Tkinter GUI that orchestrates robocopy-based file migration from an
infected drive with post-copy security scanning, parallelised hash
verification, and a blocked-file manifest.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .command import build_args, build_display_cmd
from .constants import BLOAT_DIRS, DANGEROUS_EXTS, ZIP_DOC_EXTS, OLE_DOC_EXTS, ROBOCOPY_SUCCESS_CODES
from .hasher import ParallelHashVerifier
from .manifest import write_manifest
from .utils import strip_ansi, format_size
from .scanner import PostCopyScanner
from .theme import (
    ACCENT, BG, GREEN, MAUVE, RED, SUBTEXT, SURFACE, TEXT, YELLOW,
    apply_theme,
)
from typing import Any, Callable

__all__ = ["GhostHarvest"]


class GhostHarvest(tk.Tk):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.title("👻 GhostHarvest v2.1 — Safe Migration Tool")
        self.geometry("900x820")
        self.minsize(760, 680)
        self.configure(bg=BG)

        # ── Queue & settings ──────────────────────────────────────────
        self.queue: list[str] = []
        self.dest_var    = tk.StringVar(value=r"C:\CleanWorkspace")
        self.threads_var = tk.IntVar(value=16)
        self.block_exts  = tk.BooleanVar(value=True)
        self.skip_bloat  = tk.BooleanVar(value=True)
        self.restartable = tk.BooleanVar(value=True)
        self.dry_run     = tk.BooleanVar(value=False)
        self.magic_scan  = tk.BooleanVar(value=True)
        self.scan_plain  = tk.BooleanVar(value=True)
        self.hash_verify = tk.BooleanVar(value=True)
        self.save_log    = tk.BooleanVar(value=True)

        # ── Runtime state ─────────────────────────────────────────────
        self.running = False
        self.abort_event = threading.Event()
        self.process_lock = threading.Lock()
        self.process: subprocess.Popen | None = None
        self._refresh_timer: str | None = None
        self._alive = True

        apply_theme(self)
        self._build()
        self._refresh_preview()
        self._update_space()

    def destroy(self) -> None:
        self._alive = False
        super().destroy()

    # ══════════════════════════════════════════════════════════════════
    # BUILD UI
    # ══════════════════════════════════════════════════════════════════

    def _build(self) -> None:
        root = ttk.Frame(self, padding="20 16 20 16")
        root.pack(fill="both", expand=True)

        # ── Header ────────────────────────────────────────────────────
        hdr = ttk.Frame(root)
        hdr.pack(fill="x", pady=(0, 3))
        ttk.Label(hdr, text="👻  GhostHarvest", style="H1.TLabel").pack(side="left")
        ttk.Label(
            hdr,
            text="   v2.1  ·  Surgical migration from infected drives",
            style="Dim.TLabel",
        ).pack(side="left", pady=(7, 0))
        ttk.Separator(root).pack(fill="x", pady=(8, 12))

        # ── Source queue ──────────────────────────────────────────────
        qh = ttk.Frame(root)
        qh.pack(fill="x", pady=(0, 4))
        ttk.Label(qh, text="Source Queue", style="H2.TLabel").pack(side="left")
        ttk.Button(qh, text="+ Add Folder", command=self._q_add).pack(side="right")

        qb = ttk.Frame(root)
        qb.pack(fill="x")

        lb_wrap = ttk.Frame(qb)
        lb_wrap.pack(side="left", fill="both", expand=True)
        sb = tk.Scrollbar(
            lb_wrap, orient="vertical",
            bg=SURFACE, troughcolor=SURFACE,
            highlightthickness=0, relief="flat", bd=0,
        )
        self.q_lb = tk.Listbox(
            lb_wrap, height=4, selectmode="single",
            bg=SURFACE, fg=TEXT, selectbackground=ACCENT, selectforeground=BG,
            font=("Consolas", 10), relief="flat", bd=0,
            activestyle="none", yscrollcommand=sb.set,
        )
        sb.config(command=self.q_lb.yview)
        self.q_lb.pack(side="left", fill="both", expand=True, ipady=4)
        sb.pack(side="right", fill="y")

        ctrl = ttk.Frame(qb)
        ctrl.pack(side="right", padx=(8, 0), fill="y")
        for label, cmd in [("↑", self._q_up), ("↓", self._q_down), ("✕", self._q_rm)]:
            ttk.Button(ctrl, text=label, width=3, command=cmd).pack(pady=(0, 3))

        # ── Destination ───────────────────────────────────────────────
        ttk.Separator(root).pack(fill="x", pady=12)
        self._path_row(root, "Destination:", self.dest_var, self._browse_dest)
        self.space_lbl = ttk.Label(root, text="", style="Dim.TLabel")
        self.space_lbl.pack(anchor="w", pady=(3, 0))
        self.dest_var.trace_add("write", lambda *_: self._update_space())
        ttk.Separator(root).pack(fill="x", pady=12)

        # ── Filters ───────────────────────────────────────────────────
        ttk.Label(root, text="Filters", style="H2.TLabel").pack(anchor="w", pady=(0, 5))
        ttk.Checkbutton(
            root,
            text="🛡  Block dangerous executables  "
                 "(.exe .bat .vbs .cmd .lnk .msi .ps1 .scr .dll .sys .chm …)",
            variable=self.block_exts,
            command=self._debounced_refresh,
        ).pack(anchor="w", pady=2)
        ttk.Checkbutton(
            root,
            text="🗑  Skip dev bloat + system dirs  "
                 "(node_modules .git $Recycle.Bin System Volume Information …)",
            variable=self.skip_bloat,
            command=self._debounced_refresh,
        ).pack(anchor="w", pady=2)

        xd = ttk.Frame(root)
        xd.pack(fill="x", pady=(6, 0))
        ttk.Label(
            xd, text="Extra folder exclusions (space-separated):",
            style="Dim.TLabel",
        ).pack(anchor="w")
        self.custom_xd = ttk.Entry(xd, font=("Consolas", 10))
        self.custom_xd.pack(fill="x", pady=(3, 0), ipady=4)
        self.custom_xd.bind("<KeyRelease>", lambda _: self._debounced_refresh())
        ttk.Separator(root).pack(fill="x", pady=12)

        # ── Settings ──────────────────────────────────────────────────
        ttk.Label(root, text="Settings", style="H2.TLabel").pack(anchor="w", pady=(0, 6))

        sf = ttk.Frame(root)
        sf.pack(fill="x", pady=(0, 6))
        ttk.Label(sf, text="Threads:", style="H2.TLabel").pack(side="left")
        self.thread_lbl = tk.Label(
            sf, text="16", bg=BG, fg=ACCENT, font=("Segoe UI", 12, "bold"),
        )
        self.thread_lbl.pack(side="left", padx=(8, 12))

        def _slide(v: str) -> None:
            self.thread_lbl.config(text=str(int(float(v))))
            self._debounced_refresh()

        ttk.Scale(
            sf, from_=1, to=32, variable=self.threads_var,
            orient="horizontal", command=_slide,
        ).pack(side="left", fill="x", expand=True)
        ttk.Label(sf, text=" 32", style="Dim.TLabel").pack(side="left")

        cbr = ttk.Frame(root)
        cbr.pack(fill="x", pady=(0, 4))
        for text, var, cmd in [
            ("⚡ Restartable /ZB",  self.restartable, self._debounced_refresh),
            ("🔍 Dry run",          self.dry_run,     self._debounced_refresh),
            ("🔬 Magic byte scan",  self.magic_scan,  lambda: None),
            ("📄 Scan plain-text",  self.scan_plain,  lambda: None),
            ("🔑 SHA-256 verify",   self.hash_verify, lambda: None),
            ("📄 Save log",         self.save_log,    lambda: None),
        ]:
            ttk.Checkbutton(
                cbr, text=text, variable=var,
                command=cmd,
            ).pack(side="left", padx=(0, 14))

        ttk.Separator(root).pack(fill="x", pady=12)

        # ── Command preview ───────────────────────────────────────────
        ph = ttk.Frame(root)
        ph.pack(fill="x", pady=(0, 4))
        ttk.Label(ph, text="Command Preview", style="H2.TLabel").pack(side="left")
        self.q_count_lbl = ttk.Label(ph, text="", style="Dim.TLabel")
        self.q_count_lbl.pack(side="left", padx=(8, 0), pady=(1, 0))

        self.cmd_box = tk.Text(
            root, height=3, font=("Consolas", 9),
            bg="#181825", fg=SUBTEXT, relief="flat", wrap="word",
            state="disabled", pady=8, padx=10,
            selectbackground=ACCENT, selectforeground=BG,
        )
        self.cmd_box.pack(fill="x")

        br = ttk.Frame(root)
        br.pack(fill="x", pady=(8, 10))
        ttk.Button(br, text="⟳  Refresh", command=self._refresh_preview).pack(side="left")
        ttk.Button(br, text="📋  Copy", command=self._copy_cmd).pack(side="left", padx=(6, 0))
        ttk.Button(
            br, text="🔍  Pre-flight",
            style="Accent.TButton", command=self._preflight,
        ).pack(side="left", padx=(6, 0))

        self.run_btn = ttk.Button(
            br, text="▶   RUN MIGRATION",
            style="Run.TButton", command=self._toggle_run,
        )
        self.run_btn.pack(side="right")

        # ── Progress + log ────────────────────────────────────────────
        self.progress = ttk.Progressbar(root, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 4))

        self.status_lbl = tk.Label(
            root, text="Ready.", bg=BG, fg=SUBTEXT,
            font=("Segoe UI", 9), anchor="w",
        )
        self.status_lbl.pack(fill="x", pady=(0, 5))

        self.log = scrolledtext.ScrolledText(
            root, height=8, font=("Consolas", 9),
            bg="#181825", fg=SUBTEXT, relief="flat",
            insertbackground=TEXT, wrap="word", state="disabled",
            pady=6, padx=10, selectbackground=ACCENT, selectforeground=BG,
        )
        self.log.pack(fill="both", expand=True)

        for tag, colour in [
            ("good", GREEN), ("bad", RED), ("info", ACCENT),
            ("dim", SUBTEXT), ("warn", YELLOW), ("magic", MAUVE),
        ]:
            self.log.tag_config(tag, foreground=colour)

    # ══════════════════════════════════════════════════════════════════
    # WIDGET HELPERS
    # ══════════════════════════════════════════════════════════════════

    def _path_row(
        self, parent: ttk.Frame, label: str,
        var: tk.StringVar, cmd: Callable[[], None],
    ) -> None:
        f = ttk.Frame(parent)
        f.pack(fill="x", pady=3)
        ttk.Label(f, text=label, width=16).pack(side="left")
        ttk.Entry(f, textvariable=var, font=("Consolas", 10)).pack(
            side="left", fill="x", expand=True, padx=(0, 8), ipady=5,
        )
        ttk.Button(f, text="Browse…", command=cmd, width=10).pack(side="left")

    def _browse_dest(self) -> None:
        p = filedialog.askdirectory(title="Select Destination on Clean Drive")
        if p:
            self.dest_var.set(p.replace("/", "\\"))

    def _update_space(self) -> None:
        try:
            target = Path(self.dest_var.get().strip())
            if target.exists():
                _, used, free = shutil.disk_usage(target)
                style = "Good.TLabel" if free / 1024**3 > 50 else "Warn.TLabel"
                self.space_lbl.config(
                    text=f"Destination folder — {used / 1024**3:.1f} GB used · {free / 1024**3:.1f} GB free",
                    style=style,
                )
            else:
                self.space_lbl.config(text="Destination folder does not exist yet", style="Warn.TLabel")
        except (OSError, ValueError, PermissionError):
            self.space_lbl.config(text="Unable to check disk space", style="Warn.TLabel")


    # ══════════════════════════════════════════════════════════════════
    # QUEUE MANAGEMENT
    # ══════════════════════════════════════════════════════════════════

    def _q_add(self) -> None:
        p = filedialog.askdirectory(title="Add Source Folder to Queue")
        if p:
            p = p.replace("/", "\\")
            if p not in self.queue:
                self.queue.append(p)
                self.q_lb.insert("end", p)
                self._refresh_preview()

    def _q_rm(self) -> None:
        sel = self.q_lb.curselection()
        if sel:
            idx = sel[0]
            self.queue.pop(idx)
            self.q_lb.delete(idx)
            self._refresh_preview()

    def _q_up(self) -> None:
        sel = self.q_lb.curselection()
        if sel and sel[0] > 0:
            i = sel[0]
            self.queue[i], self.queue[i - 1] = self.queue[i - 1], self.queue[i]
            self._sync_lb()
            self.q_lb.selection_set(i - 1)

    def _q_down(self) -> None:
        sel = self.q_lb.curselection()
        if sel and sel[0] < len(self.queue) - 1:
            i = sel[0]
            self.queue[i], self.queue[i + 1] = self.queue[i + 1], self.queue[i]
            self._sync_lb()
            self.q_lb.selection_set(i + 1)

    def _sync_lb(self) -> None:
        self.q_lb.delete(0, "end")
        for p in self.queue:
            self.q_lb.insert("end", p)

    # ══════════════════════════════════════════════════════════════════
    # COMMAND PREVIEW
    # ══════════════════════════════════════════════════════════════════

    def _current_args(
        self,
        src: str | None = None,
        dst: str | None = None,
        settings: dict | None = None,
    ) -> list[str]:
        """Build robocopy arg list from settings dict or current UI state."""
        if settings:
            source = src or (settings["queue"][0] if settings["queue"] else "<SOURCE>")
            dest = dst or settings["dest"] or "<DESTINATION>"
            return build_args(
                source=source,
                dest=dest,
                threads=settings["threads"],
                restartable=settings["restartable"],
                dry_run=settings["dry_run"],
                block_exts=settings["block_exts"],
                skip_bloat=settings["skip_bloat"],
                custom_xd=settings["custom_xd"],
                save_log=settings["save_log"],
            )

        source = src or (self.queue[0] if self.queue else "<SOURCE>")
        dest = dst or self.dest_var.get().strip() or "<DESTINATION>"
        return build_args(
            source=source,
            dest=dest,
            threads=int(self.threads_var.get()),
            restartable=self.restartable.get(),
            dry_run=self.dry_run.get(),
            block_exts=self.block_exts.get(),
            skip_bloat=self.skip_bloat.get(),
            custom_xd=self.custom_xd.get().strip(),
            save_log=self.save_log.get(),
        )

    def _refresh_preview(self) -> None:
        n = len(self.queue)
        label = (
            "(no folders queued)" if n == 0
            else f"({n} folder{'s' if n > 1 else ''} queued"
                 + (" — showing #1)" if n > 1 else ")")
        )
        self.q_count_lbl.config(text=label)

        cmd = build_display_cmd(self._current_args())
        self.cmd_box.config(state="normal")
        self.cmd_box.delete("1.0", "end")
        self.cmd_box.insert("1.0", cmd)
        self.cmd_box.config(state="disabled")

    def _debounced_refresh(self) -> None:
        """Debounce preview rebuilds (200 ms) to avoid per-keystroke lag."""
        if self._refresh_timer is not None:
            self.after_cancel(self._refresh_timer)
        self._refresh_timer = self.after(200, self._refresh_preview)

    def _copy_cmd(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(build_display_cmd(self._current_args()))
        self._log("📋  Command copied to clipboard\n", "info")

    # ══════════════════════════════════════════════════════════════════
    # PRE-FLIGHT
    # ══════════════════════════════════════════════════════════════════

    def _preflight(self) -> None:
        if not self.queue:
            messagebox.showwarning("Empty Queue", "Add at least one source folder.")
            return
        if not self.dest_var.get().strip():
            messagebox.showwarning("No Destination", "Set a destination folder.")
            return

        settings: dict[str, Any] = {
            "queue": list(self.queue),
            "dest": self.dest_var.get().strip(),
            "threads": int(self.threads_var.get()),
            "restartable": self.restartable.get(),
            "dry_run": True,
            "block_exts": self.block_exts.get(),
            "skip_bloat": self.skip_bloat.get(),
            "custom_xd": self.custom_xd.get().strip(),
            "save_log": self.save_log.get(),
            "scan_plain": self.scan_plain.get(),
        }

        extra = settings.get("custom_xd", "").strip()
        if extra:
            import shlex
            try:
                parsed_tokens = shlex.split(extra)
                for p in parsed_tokens:
                    if " " in p:
                        self._log(f"⚠  Warning: custom exclusion '{p}' contains a space – robocopy may not exclude it correctly.\n", "warn")
            except ValueError:
                self._log("⚠  Error: Mismatched quote boundaries identified in custom folder exclusions.\n", "warn")

        self._log("\n🔍  Pre-flight scan running…\n", "info")
        self._set_status("Pre-flight…", ACCENT)
        self.progress.start(12)
        threading.Thread(target=self._thread_preflight, args=(settings,), daemon=True).start()

    def _thread_preflight(self, settings: dict[str, Any]) -> None:
        total_files = total_bytes = skipped = 0
        dest = settings["dest"]

        for src in settings["queue"]:
            src_name = Path(src).name or Path(src).drive.replace(":", "").strip()
            dst = str(Path(dest) / src_name)
            args = self._current_args(src=src, dst=dst, settings=settings)

            try:
                proc = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="oem",
                    errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )

                summary: dict[str, str] = {}
                if proc.stdout:
                    for line in proc.stdout:
                        clean_line = strip_ansi(line)
                        if self._alive:
                            self.after(0, self._log, clean_line)
                        if ":" not in clean_line:
                            continue
                        label, payload = clean_line.split(":", 1)
                        key = label.strip().lower()
                        if key in {"dirs", "files", "bytes"}:
                            summary[key] = payload.strip()
                proc.wait()

                # Safely extract metrics
                files_line = summary.get("files")
                if files_line:
                    parts = files_line.split()
                    if len(parts) >= 3:
                        try:
                            total_files += int(parts[0].replace(",", ""))
                            skipped += int(parts[2].replace(",", ""))
                        except (ValueError, IndexError):
                            if self._alive:
                                self.after(0, self._log, "  ⚠  Could not parse file counts from robocopy output.\n", "warn")

                bytes_line = summary.get("bytes")
                if bytes_line:
                    total_bytes += self._parse_robocopy_bytes(f"Bytes: {bytes_line}")
            except OSError as e:
                if self._alive:
                    self.after(0, self._log, f"  Error on {src}: {e}\n", "bad")

        size_str = format_size(total_bytes)

        summary_text = (
            f"\n{'─' * 52}\n"
            f"  PRE-FLIGHT SUMMARY\n"
            f"{'─' * 52}\n"
            f"  Folders queued   :  {len(settings['queue'])}\n"
            f"  Total files found:  {total_files:,}\n"
            f"  Files to copy    :  {max(0, total_files - skipped):,}\n"
            f"  Estimated size   :  {size_str}\n"
            f"  Already at dest  :  {skipped:,}  (will be skipped)\n"
            f"{'─' * 52}\n\n"
        )
        if self._alive:
            self.after(0, self._log, summary_text, "info")
            self.after(
                0, self._set_status,
                f"Pre-flight done — {max(0, total_files - skipped):,} files to copy · {size_str}", GREEN,
            )
            self.after(0, self.progress.stop)

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
            # A comma is only a decimal separator if it appears exactly once and near the end
            if numeric_part.count(',') == 1:
                comma_idx = numeric_part.rfind(',')
                if len(numeric_part) - comma_idx - 1 in (1, 2):
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

    # ══════════════════════════════════════════════════════════════════
    # RUN / STOP
    # ══════════════════════════════════════════════════════════════════

    def _toggle_run(self) -> None:
        if self.running:
            self._stop()
        else:
            self._start()

    def _start(self) -> None:
        if not self.queue:
            messagebox.showwarning("Empty Queue", "Add at least one source folder.")
            return
        dest = self.dest_var.get().strip()
        if not dest:
            messagebox.showwarning("No Destination", "Set a destination folder.")
            return

        settings: dict[str, Any] = {
            "queue": list(self.queue),
            "dest": dest,
            "threads": int(self.threads_var.get()),
            "restartable": self.restartable.get(),
            "dry_run": self.dry_run.get(),
            "block_exts": self.block_exts.get(),
            "skip_bloat": self.skip_bloat.get(),
            "custom_xd": self.custom_xd.get().strip(),
            "save_log": self.save_log.get(),
            "magic_scan": self.magic_scan.get(),
            "scan_plain": self.scan_plain.get(),
            "hash_verify": self.hash_verify.get(),
        }

        # Check destination-inside-source guard (IMP-001 / BUG-009)
        dest_path = Path(dest).resolve()
        for src in settings["queue"]:
            src_path = Path(src).resolve()
            if src_path in dest_path.parents or dest_path in src_path.parents or dest_path == src_path:
                self._log(f"⚠  Destination '{dest}' is inside or contains source '{src}' – would cause infinite recursion. Aborted.\n", "bad")
                self._finish()
                return

        # Check custom XD spaces (BUG-006 / BUG-011)
        extra = settings.get("custom_xd", "").strip()
        if extra:
            import shlex
            try:
                parsed_tokens = shlex.split(extra)
                for p in parsed_tokens:
                    if " " in p:
                        self._log(f"⚠  Warning: custom exclusion '{p}' contains a space – robocopy may not exclude it correctly.\n", "warn")
            except ValueError:
                self._log("⚠  Error: Mismatched quote boundaries identified in custom folder exclusions.\n", "warn")

        n = len(settings["queue"])
        mode = "DRY RUN  (no files written)" if settings["dry_run"] else "LIVE COPY"
        flags: list[str] = []
        if settings["magic_scan"]:
            flags.append("post-copy magic scan")
        if settings["hash_verify"]:
            flags.append("SHA-256 verify (parallel)")
        if settings["restartable"]:
            flags.append("restartable /ZB")

        if not messagebox.askyesno(
            "Confirm Migration",
            f"Mode    : {mode}\n"
            f"Folders : {n}\n"
            f"Dest    : {dest}\n"
            f"Options : {', '.join(flags) or 'none'}\n\n"
            "Proceed?",
        ):
            return

        os.makedirs(dest, exist_ok=True)
        self.running = True
        self.abort_event.clear()
        self.run_btn.config(text="⬛  STOP", style="Stop.TButton")
        self.progress.start(12)
        self._set_status("Running…", ACCENT)

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._log(f"\n{'═' * 58}\n", "dim")
        self._log(f"▶  Migration started  {ts}\n", "info")
        self._log(f"   {n} folder(s)  →  {dest}\n", "dim")
        self._log(f"{'═' * 58}\n", "dim")

        threading.Thread(target=self._pipeline, args=(settings,), daemon=True).start()

    # ══════════════════════════════════════════════════════════════════
    # PIPELINE  (runs on a background thread)
    # ══════════════════════════════════════════════════════════════════

    def _pipeline(self, settings: dict[str, Any]) -> None:
        manifest: list[dict] = []
        all_ok = True
        stats = {
            "blocked_magic": 0,
            "warned": 0,
            "hash_ok": 0,
            "hash_fail": 0,
            "double_ext": 0,
        }
        dest = settings["dest"]

        # Build the blocked-extension set once (using removeprefix — S2 fix)
        blocked_exts_set: set[str] = {
            e.removeprefix("*.").lower() for e in DANGEROUS_EXTS
        }
        skip_dirs_set: set[str] = set(BLOAT_DIRS) if settings["skip_bloat"] else set()

        for i, src in enumerate(settings["queue"], 1):
            if self.abort_event.is_set():
                break

            src_name = Path(src).name or Path(src).drive.replace(":", "").strip()
            folder_dest = str(Path(dest) / src_name)
            os.makedirs(folder_dest, exist_ok=True)

            if self._alive:
                self.after(
                    0, self._log,
                    f"\n{'─' * 58}\n  [{i}/{len(settings['queue'])}]  {src}\n{'─' * 58}\n",
                    "info",
                )

            # ── Step 1: Robocopy ──────────────────────────────────────
            args = self._current_args(src=src, dst=folder_dest, settings=settings)
            display = build_display_cmd(args)
            if self._alive:
                self.after(0, self._log, f"\n$ {display}\n\n", "dim")

            rc: int | None = None
            log_file = None
            if settings.get("save_log") and not settings.get("dry_run"):
                try:
                    log_path = Path(folder_dest) / "_GhostHarvest_log.txt"
                    log_file = open(log_path, "a", encoding="utf-8", errors="replace")
                except OSError as log_err:
                    if self._alive:
                        self.after(0, self._log, f"  ⚠  Could not open log file: {log_err}\n", "warn")

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
                        if self._alive:
                            self.after(0, self._log, clean_line)
                        if log_file:
                            log_file.write(clean_line)
                        if self.abort_event.is_set():
                            self.process.kill()
                            break
                self.process.wait()
                rc = self.process.returncode

                if rc is not None and rc in ROBOCOPY_SUCCESS_CODES:
                    if self._alive:
                        self.after(
                            0, self._log,
                            f"\n  ✅  Robocopy done  (exit {rc})\n", "good",
                        )
                else:
                    if self._alive:
                        self.after(
                            0, self._log,
                            f"\n  ❌  Robocopy error  (exit {rc})\n", "bad",
                        )
                    all_ok = False

            except OSError as exc:
                if self._alive:
                    self.after(0, self._log, f"\n  ❌  {exc}\n", "bad")
                all_ok = False
            finally:
                if log_file:
                    log_file.close()
                with self.process_lock:
                    self.process = None

            # ── Step 2: Post-copy magic scan (Q3 — destination only) ─
            if rc is not None and rc in ROBOCOPY_SUCCESS_CODES and settings["magic_scan"] and not settings["dry_run"] and not self.abort_event.is_set():
                def _scan_cb(msg: str, tag: str) -> None:
                    if self._alive:
                        self.after(0, self._log, msg, tag)

                scanner = PostCopyScanner(
                    blocked_exts=blocked_exts_set,
                    skip_dirs=skip_dirs_set,
                    zip_doc_exts=ZIP_DOC_EXTS,
                    ole_doc_exts=OLE_DOC_EXTS,
                    scan_plain=settings["scan_plain"],
                )
                flagged = scanner.scan_directory(
                    folder_dest,
                    callback=_scan_cb,
                    abort_event=self.abort_event,
                )

                # Purge or warn
                purged = 0
                for item in flagged:
                    manifest.append(item)
                    if item["action"] == "purge":
                        try:
                            p = Path(item["path"])
                            if p.exists():
                                p.unlink()
                                purged += 1
                                if self._alive:
                                    self.after(
                                        0, self._log,
                                        f"  🗑  Purged: {p.name}\n", "warn",
                                    )
                                if "DOUBLE_EXT" in item["reason"]:
                                    stats["double_ext"] += 1
                                else:
                                    stats["blocked_magic"] += 1
                        except OSError as e:
                            if self._alive:
                                self.after(
                                    0, self._log,
                                    f"  ⚠  Could not purge {Path(item['path']).name}: {e}\n",
                                    "bad",
                                )
                    elif item["action"] == "warn":
                        stats["warned"] += 1

                if purged:
                    if self._alive:
                        self.after(
                            0, self._log,
                            f"  Purged {purged} suspicious file(s) from destination\n",
                            "warn",
                        )

            # ── Step 3: SHA-256 verification (parallelised) ──────────
            if rc is not None and rc in ROBOCOPY_SUCCESS_CODES and settings["hash_verify"] and not settings["dry_run"] and not self.abort_event.is_set():
                def _hash_cb(msg: str, tag: str) -> None:
                    if self._alive:
                        self.after(0, self._log, msg, tag)

                verifier = ParallelHashVerifier(
                    max_workers=settings["threads"],
                )
                ok, fail, _missing = verifier.verify(
                    src, folder_dest,
                    callback=_hash_cb,
                    abort_event=self.abort_event,
                )
                stats["hash_ok"] += ok
                stats["hash_fail"] += fail
                if fail > 0:
                    all_ok = False

        # ── Step 4: Write blocked manifest ────────────────────────────
        if not settings["dry_run"]:
            if manifest:
                mpath = write_manifest(manifest, dest)
                if mpath:
                    if self._alive:
                        self.after(
                            0, self._log,
                            f"\n📄  Blocked manifest → {mpath}\n", "dim",
                        )
                else:
                    if self._alive:
                        self.after(
                            0, self._log,
                            "\n⚠  Failed to write blocked manifest.\n", "warn",
                        )

        # ── Step 5: Security summary (H6) ────────────────────────────
        if not settings["dry_run"]:
            summary = (
                f"\n{'═' * 58}\n"
                f"  SECURITY SUMMARY\n"
                f"{'═' * 58}\n"
                f"  Blocked by magic bytes   :  {stats['blocked_magic']}\n"
                f"  Double-extension purged  :  {stats['double_ext']}\n"
                f"  Archive warnings         :  {stats['warned']}\n"
                f"  SHA-256 verified OK      :  {stats['hash_ok']:,}\n"
                f"  SHA-256 mismatches       :  {stats['hash_fail']}\n"
                f"{'═' * 58}\n\n"
            )
            tag = "good" if stats["hash_fail"] == 0 and stats["blocked_magic"] == 0 and stats["double_ext"] == 0 else "warn"
            if self._alive:
                self.after(0, self._log, summary, tag)

        # ── Final status ──────────────────────────────────────────────
        if self._alive:
            if self.abort_event.is_set():
                self.after(0, self._set_status, "⬛  Stopped by user.", SUBTEXT)
            elif all_ok:
                self.after(
                    0, self._log,
                    f"\n{'═' * 58}\n✅  All folders migrated successfully.\n{'═' * 58}\n",
                    "good",
                )
                self.after(0, self._set_status, "✅  Migration complete.", GREEN)
            else:
                self.after(
                    0, self._set_status,
                    "⚠  Done with errors — check log.", YELLOW,
                )

            self.after(0, self._finish)

    def _stop(self) -> None:
        self.abort_event.set()
        with self.process_lock:
            if self.process:
                try:
                    self.process.kill()
                except OSError:
                    pass
        self._log("\n⬛  Stop requested.\n", "bad")

    def _finish(self) -> None:
        self.running = False
        with self.process_lock:
            self.process = None
        self.run_btn.config(text="▶   RUN MIGRATION", style="Run.TButton")
        self.progress.stop()

    # ══════════════════════════════════════════════════════════════════
    # LOG / STATUS HELPERS
    # ══════════════════════════════════════════════════════════════════

    def _set_status(self, text: str, colour: str) -> None:
        if not self._alive:
            return
        self.status_lbl.config(text=text, fg=colour)

    def _log(self, text: str, tag: str = "") -> None:
        if not self._alive:
            return
        self.log.config(state="normal")
        if tag:
            self.log.insert("end", text, tag)
        else:
            self.log.insert("end", text)
        self.log.see("end")
        self.log.config(state="disabled")
