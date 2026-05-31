
# 👻 GhostHarvest v2.1

**Surgical file migration from malware-infected NTFS drives.**

Wraps `robocopy` in a tkinter GUI with post-copy magic-byte scanning, parallel SHA-256 integrity verification, double-extension detection, and a full blocked-file audit manifest. Zero external dependencies — Python 3.9+ stdlib only.

---

## Quick Start

```powershell
cd "C:\Users\USER\Desktop\APPS\Ghost Harvest"
python main.py          # auto-elevates via UAC
```

> **Runtime:** Python 3.9+ (uses `str.removeprefix`). Windows only (`robocopy`, `ctypes.windll`).
> No `pip install` needed — entire tool runs on the standard library.

---

## 📖 The Story Behind GhostHarvest (The Human Element)

GhostHarvest was not born in a boardroom or as a theoretical exercise—it was forged out of real-world necessity, survival, and a literal dream.

### The Geacata Infection
Years ago, the creator's laptop was compromised by the **Geacata virus**—a stealthy malware family notorious for infecting external media immediately upon connection. Lacking a safe way to extract files without compromising other devices, the infected hard drive sat in isolation for years.

After eventually acquiring a clean computer, the frustration of not being able to safely access years of personal data reached a boiling point. Rather than giving up, the creator dove into deep technical research to understand how Geacata spreads: primarily relying on Windows AutoPlay media auto-runs and naive folder-access triggers. 

### From a Dream to Code
By disabling AutoPlay and standardizing a highly secure clean environment, the creator managed to isolate the drive safely. However, standard file explorer transfers were still highly unsafe. That is when the creator learned about `robocopy` and paired it with the ultra-fast directory indexing principles of tools like WizTree.

The final spark was a **dream**. The creator literally had a dream about building a dedicated software suite that could securely "harvest" files from infected environments. Upon waking up, despite not having formal training in advanced device security, the creator set to work with a singular focus: turning that dream GUI into reality.

### The Evolution to v2.1
What began as a single-file debug script has trailed off into an enterprise-hardened recovery system. Through rigorous iterations, GhostHarvest evolved to include:
* **Bidirectional recursion protection** to prevent endless copy loops.
* **A robust two-pass integrity walk** to verify every copied byte and call out dropped files.
* **Locale-agnostic regex parsers** to handle different OS settings safely.
* **A hardened post-copy scanner** checking magic byte signatures and double extensions to keep executables out.

> [!TIP]
> ### A Message of Reassurance
> If you are holding an old, compromised drive full of years of photos, code, or personal memories, and you are terrified to plug it in: **there is really nothing to worry about.** 
>
> GhostHarvest is built on top of rock-solid file-transfer technology that has existed and been trusted for decades, fortified by our custom, modern security authentications and multi-stage verifications.

---

## Project Layout

```
Ghost Harvest/
│
├── main.py                          # Entry point — UAC elevation → GUI
├── README.md                        # ← you are here
├── GhostHarvest.py                  # Archived v2 monolith (755 lines)
│
└── ghost_harvest/                   # v2.1 modular package
    ├── __init__.py                  # __version__ = "2.1.0"
    ├── app.py                       # GUI shell + pipeline orchestration
    ├── command.py                   # Robocopy CLI builder (list args)
    ├── constants.py                 # Security-critical lists (single source of truth)
    ├── hasher.py                    # Parallel SHA-256 verification
    ├── manifest.py                  # _BLOCKED.txt writer
    ├── scanner.py                   # Post-copy magic-byte + double-ext scanner
    ├── theme.py                     # Catppuccin Mocha palette + ttk style config
    ├── utils.py                     # Admin detection, UAC elevation, file hashing
    │
    └── tests/
        ├── __init__.py              # Tests package descriptor
        └── validate_security.py     # 41-assertion security regression suite
```

---

## Architecture

### Dependency Graph

```
main.py
  └─► ghost_harvest.app        (GhostHarvest window)
        ├─► .command            (build_args / build_display_cmd)
        │     └─► .constants
        ├─► .scanner            (PostCopyScanner)
        │     └─► .constants
        ├─► .hasher             (ParallelHashVerifier)
        │     ├─► .constants
        │     └─► .utils        (sha256)
        ├─► .manifest           (write_manifest)
        ├─► .theme              (apply_theme + colour constants)
        └─► .utils              (is_admin / elevate / format_size)
```

Every module imports **only** from siblings within the `ghost_harvest` package.
There are no circular imports and no external dependencies.

### Migration Pipeline

Each source folder is processed through this sequential pipeline on a daemon thread:

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  ①  ROBOCOPY                                                         │
│      subprocess.Popen(args_list, shell=False)                        │
│      Flags: /E /COPY:DAT /MT:N /ZB /R:2 /W:5 /XJ /XF ... /XD ...   │
│      Exit codes 0–7 = success  │  ≥8 = error                        │
│                                                                      │
│  ②  POST-COPY SCAN  (scanner.PostCopyScanner)                        │
│      Walks the DESTINATION — never re-traverses the infected source  │
│      ├── Magic-byte check (16 signatures × first 16 bytes)           │
│      ├── Double-extension check  (e.g. report.pdf.exe)               │
│      └── ZIP/OLE allowlist → action = "warn" | "purge"               │
│                                                                      │
│  ③  PURGE                                                            │
│      Deletes every flagged file where action == "purge"              │
│                                                                      │
│  ④  SHA-256 VERIFY  (hasher.ParallelHashVerifier)                    │
│      ThreadPoolExecutor walks dest/src, hashes, and compares copies  │
│      Reports: ok / mismatch / missing from destination / destination-only │
│                                                                      │
│  ⑤  MANIFEST  (manifest.write_manifest)                              │
│      Writes _BLOCKED.txt listing every purged + warned file          │
│                                                                      │
│  ⑥  SECURITY SUMMARY                                                 │
│      Prints aggregated stats to the GUI log panel                    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Threading Model

```
┌──────────────────┐         ┌───────────────────────────┐
│   Main Thread    │         │    Pipeline Thread        │
│   (tkinter)      │         │    (daemon=True)          │
│                  │  after  │                           │
│  _log()     ◄────┼─────── │  Popen / scanner / hasher │
│  _set_status()   │   0ms   │                           │
│  progress.stop() │         │  callback → after(0, ...) │
│                  │         │                           │
│                  │         │  ┌──────────────────────┐ │
│                  │         │  │ ThreadPoolExecutor   │ │
│                  │         │  │ (SHA-256 workers)    │ │
│                  │         │  └──────────────────────┘ │
└──────────────────┘         └───────────────────────────┘
```

All GUI mutations are marshalled to the main thread via `self.after(0, ...)`.
The hasher's `ThreadPoolExecutor` runs inside the pipeline thread; its callbacks
also route through `after()`, so tkinter never sees concurrent writes.

---

## Module Reference

### `constants.py` — Security Lists

The single source of truth for every security-critical value.

| Constant | Type | Count | Purpose |
|----------|------|------:|---------|
| `DANGEROUS_EXTS` | `list[str]` | 36 | Glob patterns passed to robocopy `/XF` |
| `BLOAT_DIRS` | `list[str]` | 21 | Folder names passed to robocopy `/XD` |
| `PLAIN_TEXT_EXTS` | `set[str]` | 65 | Extensions skipped by magic-byte scanner |
| `EXEC_SIGS` | `list[tuple]` | 16 | `(offset, bytes, label)` for header matching |
| `ZIP_DOC_EXTS` | `set[str]` | 12 | ZIP-magic exts that get warn-not-purge |
| `OLE_DOC_EXTS` | `set[str]` | 6 | OLE-magic exts that get warn-not-purge |
| `MAGIC_READ_SIZE` | `int` | — | Bytes read per file for header check (16) |
| `INTERNAL_PREFIX` | `str` | — | `"_GhostHarvest"` — skipped during verify |

### `command.py` — Robocopy Argument Builder

```python
build_args(
    source: str, dest: str, threads: int = 16,
    *, restartable, dry_run, block_exts, skip_bloat, custom_xd, save_log
) -> list[str]
```

Returns a **list** — never a string. This is the S1 fix: `Popen(args_list)` with
`shell=False` (the default) avoids `cmd.exe` interpretation entirely, making
command injection via folder names impossible.

```python
build_display_cmd(args: list[str]) -> str
```

Quotes args containing spaces for human-readable preview. Used only in the
GUI text box — never passed to `Popen`.

### `scanner.py` — Post-Copy Security Scanner

```python
class PostCopyScanner:
    def __init__(self, blocked_exts, skip_dirs, zip_doc_exts, ole_doc_exts)
    def scan_directory(self, directory, callback) -> list[dict]
```

Walks the **destination** after robocopy finishes (not the infected source).
Each returned dict:

```python
{
    "path":   str,              # absolute path in destination
    "ext":    str,              # file extension (or "(none)")
    "reason": str,              # human-readable flag reason
    "action": "purge" | "warn"  # purge = delete; warn = log only
}
```

**Decision matrix for magic-byte hits:**

| Magic match | Extension in allowlist? | Action |
|-------------|------------------------|--------|
| ZIP (`PK..`) | `.docx`, `.xlsx`, etc. | `warn` |
| OLE (`D0 CF 11 E0`) | `.doc`, `.xls`, etc. | `warn` |
| Any executable sig | No allowlist match | `purge` |
| Double extension detected | — | `purge` |

Standalone helpers exposed for testing:

```python
is_exec_by_magic(path: Path) -> tuple[bool, str]
has_double_extension(path: Path, blocked_exts_set: set[str]) -> bool
```

### `hasher.py` — Parallel SHA-256 Verification

```python
class ParallelHashVerifier:
    def __init__(self, max_workers: int = 16)
    def verify(self, src, dest, callback) -> tuple[int, int, int]
    #                                         ok   fail  missing
```

Uses `concurrent.futures.ThreadPoolExecutor`. Worker count matches the
robocopy `/MT:` thread slider. Each worker hashes one `(src, dest)` file pair
independently — I/O bound, so threads > GIL is fine.

### `manifest.py` — Blocked File Manifest

```python
write_manifest(blocked: list[dict], dest: str) -> Path | None
```

Writes `_BLOCKED.txt` with a timestamped header and one entry per flagged file.
Each entry shows the action taken (`[PURGE]` or `[WARN]`), the file path,
extension, and reason string.

### `utils.py` — System Utilities

| Function | Purpose |
|----------|---------|
| `is_admin() → bool` | Calls `IsUserAnAdmin()` via ctypes |
| `elevate()` | Re-launches via `ShellExecuteW("runas")` with **only** `sys.argv[0]` |
| `sha256(path, chunk) → str` | Streaming SHA-256 in 1 MiB chunks; returns `""` on error |
| `format_size(b) → str` | `1234567890` → `"1.15 GB"` |

### `theme.py` — Catppuccin Mocha

Exports ten colour constants (`BG`, `SURFACE`, `OVERLAY`, `TEXT`, `SUBTEXT`,
`ACCENT`, `GREEN`, `RED`, `YELLOW`, `MAUVE`) and:

```python
apply_theme(root: tk.Tk) -> None
```

Configures ttk `clam` theme with custom styles: `H1.TLabel`, `H2.TLabel`,
`Dim.TLabel`, `Good.TLabel`, `Warn.TLabel`, `Accent.TButton`, `Run.TButton`,
`Stop.TButton`.

### `app.py` — Main Window

The `GhostHarvest(tk.Tk)` class. Key internal methods:

| Method | Thread | Purpose |
|--------|--------|---------|
| `_build()` | main | Constructs all widgets |
| `_current_args()` | main | Snapshots UI state → `build_args()` |
| `_refresh_preview()` | main | Updates command preview text box |
| `_debounced_refresh()` | main | 200 ms debounce via `after_cancel`/`after` |
| `_preflight()` | main→bg | Spawns dry-run thread for file/size estimate |
| `_start()` | main | Validates inputs, shows confirmation, starts pipeline |
| `_pipeline(dest)` | **bg** | Runs the 6-step pipeline per folder |
| `_stop()` | main | Sets `aborted` flag, kills Popen |
| `_log(text, tag)` | main | Inserts coloured text into the ScrolledText |

---

## Threat Model

GhostHarvest is designed for **one specific scenario**: extracting clean user
files from an NTFS drive already treated by an AV/anti-malware tool (e.g.
Malwarebytes), where residual infected or suspicious files may remain.

### What it defends against

| Threat | Defence | Bypass risk |
|--------|---------|-------------|
| Known executable extensions | `/XF` blocklist (36 exts) | Rename to unlisted ext |
| Renamed executables | Magic-byte header scan (16 sigs) | Polyglot files, encrypted payloads |
| Double-extension tricks | `has_double_extension()` | Triple extensions, RTL override |
| NTFS junction/symlink escape | `/XJ` flag on robocopy | Hardlinks (not excluded) |
| Command injection via paths | `shell=False` + list args | None (fully mitigated) |
| Argument injection in UAC | Only script path passed | None (fully mitigated) |
| File corruption during copy | SHA-256 source ↔ dest verify | Read errors returning partial data |
| Macro-enabled Office docs | `.docm`/`.xlsm`/`.pptm` blocked by ext | Manual rename to `.docx` |

### What it does NOT defend against

- **Kernel-level rootkits** — if the OS itself is compromised, no user-mode tool
  is trustworthy. Boot from a clean OS / live USB instead.
- **Fileless malware** — payloads in registry, WMI, or memory aren't file-based.
- **Encrypted/packed payloads** — a `.dat` file with AES-encrypted malware won't
  trigger any signature. Consider entropy analysis as a future enhancement.
- **NTFS Alternate Data Streams** — robocopy with `/COPY:DAT` does not copy ADS
  (which is safe), but the tool doesn't *warn* about ADS on the source. Future
  enhancement: enumerate streams via `FindFirstStreamW`.
- **Steganographic payloads** — e.g. Gatak/Stegoloader hiding code in PNG pixels.
  Requires specialised analysis beyond header scanning.

---

## Extending the Tool

### Adding a new blocked extension

Edit `DANGEROUS_EXTS` in [`constants.py`](ghost_harvest/constants.py):

```python
DANGEROUS_EXTS: list[str] = [
    ...
    "*.my_new_ext",
]
```

Robocopy picks it up via `/XF` automatically. If the extension is also
a known plain-text format, add it to `PLAIN_TEXT_EXTS` as well so the
magic-byte scanner skips it.

### Adding a new magic-byte signature

Append to `EXEC_SIGS` in [`constants.py`](ghost_harvest/constants.py):

```python
EXEC_SIGS: list[tuple[int, bytes, str]] = [
    ...
    (0, b"\xDE\xAD", "My Custom Signature"),
]
```

If the signature shares magic bytes with a legitimate document format,
add the safe extensions to `ZIP_DOC_EXTS` or `OLE_DOC_EXTS` to avoid
false-positive purges.

### Adding a new scan check

Subclass or extend `PostCopyScanner.scan_directory()` in
[`scanner.py`](ghost_harvest/scanner.py). The scanner yields dicts with
`action: "purge" | "warn"` — the pipeline in `app.py` consumes these
generically, so no changes needed there.

---

## Running Tests

```powershell
python -X utf8 ghost_harvest\tests\validate_security.py
```

Expected output:

```
========================================================
  GhostHarvest v2.1 — Security Validation
========================================================
  ...
  41 passed · 0 failed
========================================================
```

The test suite validates every security fix (S1–S7) with concrete assertions:
argument list types, `removeprefix` correctness, `elevate()` source inspection,
`/XJ` presence, bare-except absence, extension completeness, and signature
coverage.

---

## Robocopy Flag Reference

Flags used by GhostHarvest and why:

| Flag | Purpose | Security relevance |
|------|---------|-------------------|
| `/E` | Copy subdirectories including empty ones | — |
| `/COPY:DAT` | Data + Attributes + Timestamps | Deliberately excludes **S**ecurity (ACLs) and ADS |
| `/MT:N` | Multi-threaded copy (1–32) | — |
| `/ZB` | Restartable mode → backup mode fallback | Uses `SeBackupPrivilege` to bypass ACLs (desired for recovery) |
| `/R:2 /W:5` | 2 retries, 5 sec wait | Prevents hanging on locked files |
| `/XJ` | Exclude junction points | **S4** — prevents symlink traversal attacks |
| `/L` | List only (dry run) | Used by pre-flight scan |
| `/XF` | Exclude files by pattern | **S6** — 36 dangerous extensions |
| `/XD` | Exclude directories by name | **H1** — bloat + malware-hiding dirs |
| `/LOG+:` | Append to log file | Audit trail at destination |

### Exit code interpretation

Robocopy uses bitmap exit codes:

| Bit | Value | Meaning |
|-----|------:|---------|
| 0 | 0 | No errors, no copies (already synced) |
| 0 | 1 | Files copied successfully |
| 1 | 2 | Extra files detected at destination |
| 2 | 4 | Mismatched files detected |
| 3 | 8 | **Copy errors** (retry limit exceeded) |
| 4 | 16 | **Fatal error** (usage / access) |

GhostHarvest treats `0–7` as success, `≥ 8` as error.

---

## Licence

Private tool — not licensed for redistribution.
