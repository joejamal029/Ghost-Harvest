"""
GhostHarvest v2.1 — Catppuccin Mocha theme.

Provides colour constants and a function to configure ttk styling.
"""

import tkinter as tk
from tkinter import ttk

__all__ = ["BG", "SURFACE", "OVERLAY", "TEXT", "SUBTEXT", "ACCENT", "GREEN", "RED", "YELLOW", "MAUVE", "apply_theme"]

# ── Catppuccin Mocha palette ───────────────────────────────────────────────────

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


def apply_theme(root: tk.Tk) -> None:
    """Apply the Catppuccin Mocha dark theme to every ttk widget."""
    s = ttk.Style(root)
    s.theme_use("clam")

    base = dict(background=BG, foreground=TEXT, borderwidth=0, relief="flat")
    s.configure(".",              **base)
    s.configure("TFrame",        background=BG)
    s.configure("TSeparator",    background=OVERLAY)

    # Labels
    s.configure("TLabel",        background=BG, foreground=TEXT,    font=("Segoe UI", 10))
    s.configure("H1.TLabel",     background=BG, foreground=ACCENT, font=("Segoe UI", 16, "bold"))
    s.configure("H2.TLabel",     background=BG, foreground=TEXT,   font=("Segoe UI", 10, "bold"))
    s.configure("Dim.TLabel",    background=BG, foreground=SUBTEXT, font=("Segoe UI", 9))
    s.configure("Good.TLabel",   background=BG, foreground=GREEN,  font=("Segoe UI", 9))
    s.configure("Warn.TLabel",   background=BG, foreground=RED,    font=("Segoe UI", 9))

    # Checkbuttons
    s.configure("TCheckbutton",  background=BG, foreground=TEXT,
                font=("Segoe UI", 10), focuscolor=BG)
    s.map("TCheckbutton",
          background=[("active", BG)], foreground=[("active", TEXT)])

    # Entries
    s.configure("TEntry", fieldbackground=SURFACE, foreground=TEXT,
                insertcolor=TEXT, selectbackground=ACCENT,
                selectforeground=BG, borderwidth=0)
    s.map("TEntry", fieldbackground=[("focus", OVERLAY)])

    # Scale / progress
    s.configure("TScale",       background=BG, troughcolor=SURFACE, borderwidth=0)
    s.configure("TProgressbar", background=ACCENT, troughcolor=SURFACE,
                borderwidth=0, thickness=5)

    # Buttons
    for name, bg, fg, font_ in [
        ("TButton",        OVERLAY, TEXT, ("Segoe UI", 10)),
        ("Accent.TButton", ACCENT,  BG,  ("Segoe UI", 10, "bold")),
        ("Run.TButton",    GREEN,   BG,  ("Segoe UI", 11, "bold")),
        ("Stop.TButton",   RED,     BG,  ("Segoe UI", 11, "bold")),
    ]:
        s.configure(name, background=bg, foreground=fg,
                    font=font_, padding=(10, 6), relief="flat")

    s.map("TButton",        background=[("active", "#585b70"), ("disabled", SURFACE)])
    s.map("Accent.TButton", background=[("active", "#9ec5ff")])
    s.map("Run.TButton",    background=[("active", "#b9f5b4"), ("disabled", OVERLAY)])
    s.map("Stop.TButton",   background=[("active", "#f5a3b2")])
