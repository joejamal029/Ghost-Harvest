"""
GhostHarvest v2 — Safe File Migration Tool
Features: folder queue · magic byte scan · SHA256 verify ·
          pre-flight summary · blocked manifest · restartable mode
"""

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import subprocess, threading, hashlib, os, shutil, ctypes, sys
from pathlib import Path
from datetime import datetime


# ── Constants ──────────────────────────────────────────────────────────────────

DANGEROUS_EXTS = [
    "*.exe","*.bat","*.cmd","*.vbs","*.js","*.wsf",
    "*.scr","*.pif","*.lnk","*.msi","*.ps1","*.reg",
    "*.inf","*.com","*.hta","*.jar",
]

BLOAT_DIRS = [
    "node_modules",".git",".venv","venv","__pycache__",
    "build","dist","target",".gradle",".idea",
    ".tox",".next",".nuxt","coverage",".cache",
    ".mypy_cache",".pytest_cache",
]

# File extensions that are plain text — no binary header to check
PLAIN_TEXT_EXTS = {
    ".txt",".md",".py",".ts",".js",".json",".xml",".yaml",".yml",
    ".html",".css",".sql",".sh",".csv",".toml",".ini",".cfg",
    ".rst",".log",".env",".m3u",".m3u8",".gitignore",".editorconfig",
}

# Executable file signatures (offset, bytes, label)
EXEC_SIGS = [
    (0, b"\x4D\x5A",         "Windows PE Executable (MZ)"),
    (0, b"\x7F\x45\x4C\x46", "ELF Executable"),
    (0, b"\xCA\xFE\xBA\xBE", "Mach-O / Java Class"),
    (0, b"\xCE\xFA\xED\xFE", "Mach-O 32-bit"),
    (0, b"\xCF\xFA\xED\xFE", "Mach-O 64-bit"),
]

# Catppuccin Mocha
BG      = "#1e1e2e"
SURFACE = "#313244"
OVERLAY = "#45475a"
TEXT    = "#cdd6f4"
SUBTEXT = "#a6adc8"
ACCENT  = "#89b4fa"
GREEN   = "#a6e3a1"
RED     = "#f38ba8"
YELLOW  = "#f9e2af"
MAUVE   = "#cba6f7"


# ── Utilities ──────────────────────────────────────────────────────────────────

def is_admin() -> bool:
    try:    return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except: return False

def elevate():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit(0)

def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(chunk), b""):
                h.update(block)
        return h.hexdigest()
    except Exception:
        return ""

def is_exec_by_magic(path: Path) -> tuple[bool, str]:
    """Read first 8 bytes; return (True, description) if an executable signature matches."""
    try:
        with open(path, "rb") as f:
            header = f.read(8)
        for offset, sig, label in EXEC_SIGS:
            if header[offset : offset + len(sig)] == sig:
                return True, label
    except Exception:
        pass
    return False, ""


# ── Application ────────────────────────────────────────────────────────────────

class GhostHarvest(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("👻 GhostHarvest v2 — Safe Migration Tool")
        self.geometry("900x820")
        self.minsize(760, 680)
        self.configure(bg=BG)

        # Queue & settings
        self.queue:       list[str] = []
        self.dest_var     = tk.StringVar(value=r"C:\CleanWorkspace")
        self.threads_var  = tk.IntVar(value=16)
        self.block_exts   = tk.BooleanVar(value=True)
        self.skip_bloat   = tk.BooleanVar(value=True)
        self.restartable  = tk.BooleanVar(value=True)
        self.dry_run      = tk.BooleanVar(value=False)
        self.magic_scan   = tk.BooleanVar(value=True)
        self.hash_verify  = tk.BooleanVar(value=True)
        self.save_log     = tk.BooleanVar(value=True)

        # Runtime
        self.running = False
        self.aborted = False
        self.process = None

        self._style()
        self._build()
        self._refresh_preview()
        self._update_space()

    # ── Styling ────────────────────────────────────────────────────────────────

    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")

        base = dict(background=BG, foreground=TEXT, borderwidth=0, relief="flat")
        s.configure(".",              **base)
        s.configure("TFrame",        background=BG)
        s.configure("TSeparator",    background=OVERLAY)
        s.configure("TLabel",        background=BG, foreground=TEXT,    font=("Segoe UI", 10))
        s.configure("H1.TLabel",     background=BG, foreground=ACCENT,  font=("Segoe UI", 16, "bold"))
        s.configure("H2.TLabel",     background=BG, foreground=TEXT,    font=("Segoe UI", 10, "bold"))
        s.configure("Dim.TLabel",    background=BG, foreground=SUBTEXT, font=("Segoe UI", 9))
        s.configure("Good.TLabel",   background=BG, foreground=GREEN,   font=("Segoe UI", 9))
        s.configure("Warn.TLabel",   background=BG, foreground=RED,     font=("Segoe UI", 9))

        s.configure("TCheckbutton",  background=BG, foreground=TEXT,
                    font=("Segoe UI", 10), focuscolor=BG)
        s.map("TCheckbutton",
              background=[("active", BG)], foreground=[("active", TEXT)])

        s.configure("TEntry", fieldbackground=SURFACE, foreground=TEXT,
                    insertcolor=TEXT, selectbackground=ACCENT,
                    selectforeground=BG, borderwidth=0)
        s.map("TEntry", fieldbackground=[("focus", OVERLAY)])

        s.configure("TScale",       background=BG, troughcolor=SURFACE, borderwidth=0)
        s.configure("TProgressbar", background=ACCENT, troughcolor=SURFACE,
                    borderwidth=0, thickness=5)

        for name, bg, fg, font_ in [
            ("TButton",      OVERLAY, TEXT,  ("Segoe UI", 10)),
            ("Accent.TButton", ACCENT, BG,   ("Segoe UI", 10, "bold")),
            ("Run.TButton",  GREEN,   BG,    ("Segoe UI", 11, "bold")),
            ("Stop.TButton", RED,     BG,    ("Segoe UI", 11, "bold")),
        ]:
            s.configure(name, background=bg, foreground=fg,
                        font=font_, padding=(10, 6), relief="flat")

        s.map("TButton",      background=[("active", "#585b70"), ("disabled", SURFACE)])
        s.map("Accent.TButton", background=[("active", "#9ec5ff")])
        s.map("Run.TButton",  background=[("active", "#b9f5b4"), ("disabled", OVERLAY)])
        s.map("Stop.TButton", background=[("active", "#f5a3b2")])

    # ── Build UI ───────────────────────────────────────────────────────────────

    def _build(self):
        root = ttk.Frame(self, padding="20 16 20 16")
        root.pack(fill="both", expand=True)

        # Header
        hdr = ttk.Frame(root)
        hdr.pack(fill="x", pady=(0, 3))
        ttk.Label(hdr, text="👻  GhostHarvest", style="H1.TLabel").pack(side="left")
        ttk.Label(hdr, text="   v2  ·  Surgical migration from infected drives",
                  style="Dim.TLabel").pack(side="left", pady=(7, 0))
        ttk.Separator(root).pack(fill="x", pady=(8, 12))

        # ── Source queue
        qh = ttk.Frame(root)
        qh.pack(fill="x", pady=(0, 4))
        ttk.Label(qh, text="Source Queue", style="H2.TLabel").pack(side="left")
        ttk.Button(qh, text="+ Add Folder",
                   command=self._q_add).pack(side="right")

        qb = ttk.Frame(root)
        qb.pack(fill="x")

        lb_wrap = ttk.Frame(qb)
        lb_wrap.pack(side="left", fill="both", expand=True)
        sb = tk.Scrollbar(lb_wrap, orient="vertical",
                          bg=SURFACE, troughcolor=SURFACE,
                          highlightthickness=0, relief="flat", bd=0)
        self.q_lb = tk.Listbox(
            lb_wrap, height=4, selectmode="single",
            bg=SURFACE, fg=TEXT, selectbackground=ACCENT, selectforeground=BG,
            font=("Consolas", 10), relief="flat", bd=0,
            activestyle="none", yscrollcommand=sb.set)
        sb.config(command=self.q_lb.yview)
        self.q_lb.pack(side="left", fill="both", expand=True, ipady=4)
        sb.pack(side="right", fill="y")

        ctrl = ttk.Frame(qb)
        ctrl.pack(side="right", padx=(8, 0), fill="y")
        for label, cmd in [("↑", self._q_up), ("↓", self._q_down), ("✕", self._q_rm)]:
            ttk.Button(ctrl, text=label, width=3, command=cmd).pack(pady=(0, 3))

        # ── Destination
        ttk.Separator(root).pack(fill="x", pady=12)
        self._path_row(root, "Destination:", self.dest_var, self._browse_dest)
        self.space_lbl = ttk.Label(root, text="", style="Dim.TLabel")
        self.space_lbl.pack(anchor="w", pady=(3, 0))
        self.dest_var.trace_add("write", lambda *_: self._update_space())
        ttk.Separator(root).pack(fill="x", pady=12)

        # ── Filters
        ttk.Label(root, text="Filters", style="H2.TLabel").pack(anchor="w", pady=(0, 5))
        ttk.Checkbutton(root,
            text="🛡  Block dangerous executables  (.exe .bat .vbs .cmd .lnk .msi .ps1 .scr .hta ...)",
            variable=self.block_exts, command=self._refresh_preview,
        ).pack(anchor="w", pady=2)
        ttk.Checkbutton(root,
            text="🗑  Skip dev bloat  (node_modules .git .venv __pycache__ build dist target ...)",
            variable=self.skip_bloat, command=self._refresh_preview,
        ).pack(anchor="w", pady=2)

        xd = ttk.Frame(root)
        xd.pack(fill="x", pady=(6, 0))
        ttk.Label(xd, text="Extra folder exclusions (space-separated):",
                  style="Dim.TLabel").pack(anchor="w")
        self.custom_xd = ttk.Entry(xd, font=("Consolas", 10))
        self.custom_xd.pack(fill="x", pady=(3, 0), ipady=4)
        self.custom_xd.bind("<KeyRelease>", lambda _: self._refresh_preview())
        ttk.Separator(root).pack(fill="x", pady=12)

        # ── Settings
        ttk.Label(root, text="Settings", style="H2.TLabel").pack(anchor="w", pady=(0, 6))

        sf = ttk.Frame(root)
        sf.pack(fill="x", pady=(0, 6))
        ttk.Label(sf, text="Threads:", style="H2.TLabel").pack(side="left")
        self.thread_lbl = tk.Label(sf, text="16", bg=BG, fg=ACCENT,
                                    font=("Segoe UI", 12, "bold"))
        self.thread_lbl.pack(side="left", padx=(8, 12))

        def _slide(v):
            self.thread_lbl.config(text=str(int(float(v))))
            self._refresh_preview()

        ttk.Scale(sf, from_=1, to=32, variable=self.threads_var,
                  orient="horizontal", command=_slide
                  ).pack(side="left", fill="x", expand=True)
        ttk.Label(sf, text=" 32", style="Dim.TLabel").pack(side="left")

        cbr = ttk.Frame(root)
        cbr.pack(fill="x", pady=(0, 4))
        for text, var, cmd in [
            ("⚡ Restartable /ZB",     self.restartable, self._refresh_preview),
            ("🔍 Dry run",             self.dry_run,     self._refresh_preview),
            ("🔬 Magic byte scan",     self.magic_scan,  None),
            ("🔑 SHA256 verify",       self.hash_verify, None),
            ("📄 Save log",            self.save_log,    None),
        ]:
            ttk.Checkbutton(cbr, text=text, variable=var,
                            command=cmd or (lambda: None)).pack(side="left", padx=(0, 14))

        ttk.Separator(root).pack(fill="x", pady=12)

        # ── Command preview
        ph = ttk.Frame(root)
        ph.pack(fill="x", pady=(0, 4))
        ttk.Label(ph, text="Command Preview", style="H2.TLabel").pack(side="left")
        self.q_count_lbl = ttk.Label(ph, text="", style="Dim.TLabel")
        self.q_count_lbl.pack(side="left", padx=(8, 0), pady=(1, 0))

        self.cmd_box = tk.Text(
            root, height=3, font=("Consolas", 9),
            bg="#181825", fg=SUBTEXT, relief="flat", wrap="word",
            state="disabled", pady=8, padx=10,
            selectbackground=ACCENT, selectforeground=BG)
        self.cmd_box.pack(fill="x")

        br = ttk.Frame(root)
        br.pack(fill="x", pady=(8, 10))
        ttk.Button(br, text="⟳  Refresh",    command=self._refresh_preview).pack(side="left")
        ttk.Button(br, text="📋  Copy",       command=self._copy_cmd       ).pack(side="left", padx=(6, 0))
        ttk.Button(br, text="🔍  Pre-flight",
                   style="Accent.TButton",    command=self._preflight      ).pack(side="left", padx=(6, 0))

        self.run_btn = ttk.Button(br, text="▶   RUN MIGRATION",
                                   style="Run.TButton", command=self._toggle_run)
        self.run_btn.pack(side="right")

        # ── Progress + log
        self.progress = ttk.Progressbar(root, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 4))

        self.status_lbl = tk.Label(root, text="Ready.", bg=BG, fg=SUBTEXT,
                                    font=("Segoe UI", 9), anchor="w")
        self.status_lbl.pack(fill="x", pady=(0, 5))

        self.log = scrolledtext.ScrolledText(
            root, height=8, font=("Consolas", 9),
            bg="#181825", fg=SUBTEXT, relief="flat",
            insertbackground=TEXT, wrap="word", state="disabled",
            pady=6, padx=10, selectbackground=ACCENT, selectforeground=BG)
        self.log.pack(fill="both", expand=True)

        for tag, color in [("good", GREEN),("bad", RED),("info", ACCENT),
                           ("dim", SUBTEXT),("warn", YELLOW),("magic", MAUVE)]:
            self.log.tag_config(tag, foreground=color)

    # ── Widget helpers ─────────────────────────────────────────────────────────

    def _path_row(self, parent, label, var, cmd):
        f = ttk.Frame(parent)
        f.pack(fill="x", pady=3)
        ttk.Label(f, text=label, width=16).pack(side="left")
        ttk.Entry(f, textvariable=var, font=("Consolas", 10)).pack(
            side="left", fill="x", expand=True, padx=(0, 8), ipady=5)
        ttk.Button(f, text="Browse…", command=cmd, width=10).pack(side="left")

    def _browse_dest(self):
        p = filedialog.askdirectory(title="Select Destination on New Laptop")
        if p:
            self.dest_var.set(p.replace("/", "\\"))

    def _update_space(self):
        try:
            anchor = str(Path(self.dest_var.get().strip()).anchor)
            if anchor and os.path.exists(anchor):
                _, used, free = shutil.disk_usage(anchor)
                style = "Good.TLabel" if free / 1024**3 > 50 else "Warn.TLabel"
                self.space_lbl.config(
                    text=(f"Destination drive — {used/1024**3:.1f} GB used"
                          f" · {free/1024**3:.1f} GB free"),
                    style=style)
        except Exception:
            pass

    # ── Queue management ───────────────────────────────────────────────────────

    def _q_add(self):
        p = filedialog.askdirectory(title="Add Source Folder to Queue")
        if p:
            p = p.replace("/", "\\")
            if p not in self.queue:
                self.queue.append(p)
                self.q_lb.insert("end", p)
                self._refresh_preview()

    def _q_rm(self):
        sel = self.q_lb.curselection()
        if sel:
            idx = sel[0]
            self.queue.pop(idx)
            self.q_lb.delete(idx)
            self._refresh_preview()

    def _q_up(self):
        sel = self.q_lb.curselection()
        if sel and sel[0] > 0:
            i = sel[0]
            self.queue[i], self.queue[i-1] = self.queue[i-1], self.queue[i]
            self._sync_lb(); self.q_lb.selection_set(i - 1)

    def _q_down(self):
        sel = self.q_lb.curselection()
        if sel and sel[0] < len(self.queue) - 1:
            i = sel[0]
            self.queue[i], self.queue[i+1] = self.queue[i+1], self.queue[i]
            self._sync_lb(); self.q_lb.selection_set(i + 1)

    def _sync_lb(self):
        self.q_lb.delete(0, "end")
        for p in self.queue:
            self.q_lb.insert("end", p)

    # ── Command builder ────────────────────────────────────────────────────────

    def _build_cmd(self, src: str = None, dst: str = None) -> str:
        source = src or (self.queue[0] if self.queue else "<SOURCE>")
        dest   = dst or self.dest_var.get().strip() or "<DESTINATION>"
        t      = int(self.threads_var.get())

        parts = [f'robocopy "{source}" "{dest}"', "/E /COPY:DAT", f"/MT:{t}"]
        if self.restartable.get(): parts.append("/ZB")
        parts.append("/R:2 /W:5")
        if self.dry_run.get():     parts.append("/L")
        if self.block_exts.get():  parts.append("/XF " + " ".join(DANGEROUS_EXTS))

        xd = list(BLOAT_DIRS) if self.skip_bloat.get() else []
        custom = self.custom_xd.get().strip()
        if custom: xd += custom.split()
        if xd: parts.append("/XD " + " ".join(f'"{d}"' for d in xd))

        if self.save_log.get() and not self.dry_run.get():
            parts.append(f'/LOG+:"{Path(dest) / "_GhostHarvest_log.txt"}"')

        return "  ".join(parts)

    def _refresh_preview(self):
        n = len(self.queue)
        label = ("(no folders queued)" if n == 0
                 else f"({n} folder{'s' if n > 1 else ''} queued"
                      + (" — showing #1)" if n > 1 else ")"))
        self.q_count_lbl.config(text=label)

        cmd = self._build_cmd()
        self.cmd_box.config(state="normal")
        self.cmd_box.delete("1.0", "end")
        self.cmd_box.insert("1.0", cmd)
        self.cmd_box.config(state="disabled")

    def _copy_cmd(self):
        self.clipboard_clear()
        self.clipboard_append(self._build_cmd())
        self._log("📋  Command copied to clipboard\n", "info")

    # ── Pre-flight ─────────────────────────────────────────────────────────────

    def _preflight(self):
        if not self.queue:
            messagebox.showwarning("Empty Queue", "Add at least one source folder."); return
        if not self.dest_var.get().strip():
            messagebox.showwarning("No Destination", "Set a destination folder."); return

        self._log("\n🔍  Pre-flight scan running…\n", "info")
        self._set_status("Pre-flight…", ACCENT)
        self.progress.start(12)
        threading.Thread(target=self._thread_preflight, daemon=True).start()

    def _thread_preflight(self):
        total_files = total_bytes = skipped = 0
        dest = self.dest_var.get().strip()

        for src in self.queue:
            dst = str(Path(dest) / Path(src).name)
            cmd = self._build_cmd(src=src, dst=dst)
            if "/L" not in cmd:
                cmd += "  /L"
            try:
                proc = subprocess.Popen(
                    cmd, shell=True,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW)

                in_summary = False
                for line in proc.stdout:
                    # Detect summary section
                    if "Total" in line and "Copied" in line and "Skipped" in line:
                        in_summary = True; continue
                    if in_summary:
                        if line.strip().startswith("Files"):
                            nums = [x.replace(",","") for x in line.split() if x.replace(",","").isdigit()]
                            if len(nums) >= 3:
                                total_files += int(nums[0])   # total
                                skipped     += int(nums[2])   # skipped
                        if line.strip().startswith("Bytes"):
                            # Parse size — robocopy uses k/m/g suffixes
                            parts = line.split()
                            for j, p in enumerate(parts):
                                if p in ("k","m","g","t") and j > 0:
                                    try:
                                        val = float(parts[j-1].replace(",","."))
                                        mult = {"k":1024,"m":1024**2,"g":1024**3,"t":1024**4}[p]
                                        total_bytes += int(val * mult)
                                    except Exception:
                                        pass
                proc.wait()
            except Exception as e:
                self.after(0, self._log, f"  Error on {src}: {e}\n", "bad")

        # Format size
        b = total_bytes
        size_str = (f"{b/1024**3:.2f} GB" if b >= 1024**3 else
                    f"{b/1024**2:.1f} MB" if b >= 1024**2 else
                    f"{b/1024:.1f} KB")

        summary = (
            f"\n{'─'*52}\n"
            f"  PRE-FLIGHT SUMMARY\n"
            f"{'─'*52}\n"
            f"  Folders queued   :  {len(self.queue)}\n"
            f"  Files to copy    :  {total_files:,}\n"
            f"  Estimated size   :  {size_str}\n"
            f"  Already at dest  :  {skipped:,}  (will be skipped)\n"
            f"{'─'*52}\n\n"
        )
        self.after(0, self._log, summary, "info")
        self.after(0, self._set_status,
                   f"Pre-flight done — {total_files:,} files · {size_str}", GREEN)
        self.after(0, self.progress.stop)

    # ── Magic byte scan ────────────────────────────────────────────────────────

    def _magic_scan(self, src: str, manifest: list) -> set[str]:
        """
        Walks src, flags files whose binary header is executable
        regardless of extension. Returns set of source paths to exclude.
        """
        flagged_paths: set[str] = set()
        self.after(0, self._log, f"\n🔬  Magic scan: {src}\n", "magic")

        skip_dirs = set(BLOAT_DIRS) if self.skip_bloat.get() else set()
        blocked_exts = {e.lstrip("*.").lower() for e in DANGEROUS_EXTS}

        for root_dir, dirs, files in os.walk(src):
            if self.aborted: break
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for fname in files:
                path = Path(root_dir) / fname
                ext  = path.suffix.lower().lstrip(".")
                # Already blocked by extension — skip (robocopy handles it)
                if ext in blocked_exts: continue
                # Plain text — no header to validate
                if path.suffix.lower() in PLAIN_TEXT_EXTS: continue

                hit, label = is_exec_by_magic(path)
                if hit:
                    flagged_paths.add(str(path))
                    manifest.append({
                        "path":   str(path),
                        "ext":    path.suffix or "(none)",
                        "reason": f"MAGIC_BYTE — {label}",
                    })
                    self.after(0, self._log,
                               f"  ⚠  {path.name}  [{path.suffix}]  →  {label}\n",
                               "magic")

        count = len(flagged_paths)
        self.after(0, self._log,
                   f"  Done — {count} disguised executable(s) found\n", "magic")
        return flagged_paths

    def _purge_flagged(self, flagged_src_paths: set[str], src: str, folder_dest: str):
        """
        After robocopy, remove any flagged files that landed in the destination.
        """
        removed = 0
        for src_path_str in flagged_src_paths:
            try:
                rel = Path(src_path_str).relative_to(src)
                dst_path = Path(folder_dest) / rel
                if dst_path.exists():
                    dst_path.unlink()
                    removed += 1
                    self.after(0, self._log,
                               f"  🗑  Removed from dest: {dst_path.name}\n", "warn")
            except Exception:
                pass
        if removed:
            self.after(0, self._log,
                       f"  Purged {removed} disguised executable(s) from destination\n", "warn")

    # ── SHA256 verification ────────────────────────────────────────────────────

    def _hash_verify(self, src: str, folder_dest: str):
        self.after(0, self._log,
                   f"\n🔑  SHA256 verify: {Path(folder_dest).name}\n", "info")
        ok = fail = missing = 0

        for root_dir, _, files in os.walk(folder_dest):
            if self.aborted: break
            for fname in files:
                if fname.startswith("_GhostHarvest"): continue
                dst_path = Path(root_dir) / fname
                try:
                    rel      = dst_path.relative_to(folder_dest)
                    src_path = Path(src) / rel
                except ValueError:
                    continue
                if not src_path.exists(): missing += 1; continue

                sh = sha256(src_path)
                dh = sha256(dst_path)
                if not sh or not dh: continue

                if sh == dh:
                    ok += 1
                else:
                    fail += 1
                    self.after(0, self._log,
                               f"  ❌  MISMATCH: {fname}\n", "bad")

        tag = "good" if fail == 0 else "bad"
        self.after(0, self._log,
                   f"  {ok:,} verified OK · {fail} mismatched · {missing} source-only\n",
                   tag)

    # ── Blocked manifest ───────────────────────────────────────────────────────

    def _write_manifest(self, blocked: list, dest: str):
        if not blocked: return
        path = Path(dest) / "_BLOCKED.txt"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write("GhostHarvest v2 — Blocked File Manifest\n")
                f.write(f"Generated : {datetime.now():%Y-%m-%d %H:%M:%S}\n")
                f.write("=" * 60 + "\n\n")
                for i, e in enumerate(blocked, 1):
                    f.write(f"[{i:04d}] {e['path']}\n")
                    f.write(f"       Extension : {e['ext']}\n")
                    f.write(f"       Reason    : {e['reason']}\n\n")
            self.after(0, self._log, f"\n📄  Blocked manifest → {path}\n", "dim")
        except Exception as ex:
            self.after(0, self._log, f"  Could not write manifest: {ex}\n", "bad")

    # ── Run / Stop ─────────────────────────────────────────────────────────────

    def _toggle_run(self):
        if self.running: self._stop()
        else:            self._start()

    def _start(self):
        if not self.queue:
            messagebox.showwarning("Empty Queue", "Add at least one source folder."); return
        dest = self.dest_var.get().strip()
        if not dest:
            messagebox.showwarning("No Destination", "Set a destination folder."); return

        n    = len(self.queue)
        mode = "DRY RUN  (no files written)" if self.dry_run.get() else "LIVE COPY"
        flags = []
        if self.magic_scan.get():  flags.append("magic scan")
        if self.hash_verify.get(): flags.append("SHA256 verify")
        if self.restartable.get(): flags.append("restartable /ZB")

        if not messagebox.askyesno("Confirm Migration",
            f"Mode    : {mode}\n"
            f"Folders : {n}\n"
            f"Dest    : {dest}\n"
            f"Options : {', '.join(flags) or 'none'}\n\n"
            "Proceed?"):
            return

        os.makedirs(dest, exist_ok=True)
        self.running = True
        self.aborted = False
        self.run_btn.config(text="⬛  STOP", style="Stop.TButton")
        self.progress.start(12)
        self._set_status("Running…", ACCENT)

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._log(f"\n{'═'*58}\n", "dim")
        self._log(f"▶  Migration started  {ts}\n", "info")
        self._log(f"   {n} folder(s)  →  {dest}\n", "dim")
        self._log(f"{'═'*58}\n", "dim")

        threading.Thread(target=self._pipeline, args=(dest,), daemon=True).start()

    def _pipeline(self, dest: str):
        manifest:  list[dict] = []
        all_ok = True

        for i, src in enumerate(self.queue, 1):
            if self.aborted: break

            folder_dest = str(Path(dest) / Path(src).name)
            os.makedirs(folder_dest, exist_ok=True)

            self.after(0, self._log,
                f"\n{'─'*58}\n  [{i}/{len(self.queue)}]  {src}\n{'─'*58}\n", "info")

            # 1 ── Magic byte pre-scan
            flagged_paths: set[str] = set()
            if self.magic_scan.get() and not self.dry_run.get():
                flagged_paths = self._magic_scan(src, manifest)

            # 2 ── Robocopy
            cmd = self._build_cmd(src=src, dst=folder_dest)
            self.after(0, self._log, f"\n$ {cmd}\n\n", "dim")
            try:
                self.process = subprocess.Popen(
                    cmd, shell=True,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW)
                for line in self.process.stdout:
                    self.after(0, self._log, line)
                self.process.wait()
                rc = self.process.returncode

                if rc <= 7:
                    self.after(0, self._log,
                               f"\n  ✅  Robocopy done  (exit {rc})\n", "good")
                else:
                    self.after(0, self._log,
                               f"\n  ❌  Robocopy error  (exit {rc})\n", "bad")
                    all_ok = False

            except Exception as exc:
                self.after(0, self._log, f"\n  ❌  {exc}\n", "bad")
                all_ok = False

            # 3 ── Purge disguised executables from destination
            if flagged_paths and not self.dry_run.get():
                self._purge_flagged(flagged_paths, src, folder_dest)

            # 4 ── SHA256 verification
            if self.hash_verify.get() and not self.dry_run.get() and not self.aborted:
                self._hash_verify(src, folder_dest)

        # 5 ── Write blocked manifest
        if not self.dry_run.get():
            self._write_manifest(manifest, dest)

        # Final
        if self.aborted:
            self.after(0, self._set_status, "⬛  Stopped by user.", SUBTEXT)
        elif all_ok:
            self.after(0, self._log,
                       f"\n{'═'*58}\n✅  All folders migrated successfully.\n{'═'*58}\n", "good")
            self.after(0, self._set_status, "✅  Migration complete.", GREEN)
        else:
            self.after(0, self._set_status, "⚠  Done with errors — check log.", YELLOW)

        self.after(0, self._finish)

    def _stop(self):
        self.aborted = True
        if self.process: self.process.kill()
        self._log("\n⬛  Stop requested.\n", "bad")

    def _finish(self):
        self.running = False
        self.process = None
        self.run_btn.config(text="▶   RUN MIGRATION", style="Run.TButton")
        self.progress.stop()

    # ── Utilities ──────────────────────────────────────────────────────────────

    def _set_status(self, text: str, color: str):
        self.status_lbl.config(text=text, fg=color)

    def _log(self, text: str, tag: str = ""):
        self.log.config(state="normal")
        self.log.insert("end", text, tag) if tag else self.log.insert("end", text)
        self.log.see("end")
        self.log.config(state="disabled")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if sys.platform == "win32" and not is_admin():
        elevate()
    GhostHarvest().mainloop()