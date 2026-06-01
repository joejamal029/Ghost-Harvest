"""
GhostHarvest v2.1 — Constants and configuration.

All security-critical lists are centralised here so they can be
audited, expanded, and tested in one place.
"""

__all__ = [
    "DANGEROUS_EXTS",
    "BLOAT_DIRS",
    "PLAIN_TEXT_EXTS",
    "EXEC_SIGS",
    "MAGIC_READ_SIZE",
    "ZIP_DOC_EXTS",
    "OLE_DOC_EXTS",
    "INTERNAL_PREFIX",
    "ROBOCOPY_SUCCESS_CODES",
]

# ── Dangerous file extensions ──────────────────────────────────────────────────
# Blocked via robocopy /XF — never copied from an infected source.

DANGEROUS_EXTS: list[str] = [
    # Classic executables / scripts
    "*.exe", "*.bat", "*.cmd", "*.vbs", "*.js", "*.wsf",
    "*.scr", "*.pif", "*.lnk", "*.msi", "*.ps1", "*.reg",
    "*.inf", "*.com", "*.hta", "*.jar", "*.wsh",
    # DLLs, drivers, COM objects
    "*.dll", "*.sys", "*.drv", "*.ocx",
    # Control-panel / installer artefacts
    "*.cpl", "*.msp", "*.mst", "*.application", "*.gadget",
    # PowerShell artefacts
    "*.psc1",
    # Macro-enabled Office documents
    "*.docm", "*.xlsm", "*.pptm", "*.dotm", "*.xltm", "*.potm",
    # Compiled HTML Help (can execute scripts)
    "*.chm",
    # URL shortcuts — can redirect to malware
    "*.url", "*.website",
]

# ── Directories to skip ───────────────────────────────────────────────────────
# Dev bloat + known malware hiding locations on NTFS.

BLOAT_DIRS: list[str] = [
    # Dev bloat
    "node_modules", ".git", ".venv", "venv", "__pycache__",
    "build", "dist", "target", ".gradle", ".idea",
    ".tox", ".next", ".nuxt", "coverage", ".cache",
    ".mypy_cache", ".pytest_cache",
    # System / malware hiding locations
    "$Recycle.Bin", "System Volume Information", "Recovery",
    "Windows.old",
]

# ── Plain-text extensions ──────────────────────────────────────────────────────
# Files that are definitively plain text — no binary header to inspect during
# magic-byte scanning, so we skip them for performance.

PLAIN_TEXT_EXTS: set[str] = {
    # Common text / config
    ".txt", ".md", ".py", ".ts", ".js", ".json", ".xml", ".yaml", ".yml",
    ".html", ".css", ".sql", ".sh", ".csv", ".toml", ".ini", ".cfg",
    ".rst", ".log", ".env", ".m3u", ".m3u8", ".gitignore", ".editorconfig",
    # Frontend
    ".jsx", ".tsx", ".vue", ".svelte", ".scss", ".less", ".sass",
    # Systems / backend languages
    ".rb", ".go", ".rs", ".java", ".kt", ".swift", ".c", ".h",
    ".cpp", ".hpp", ".cs", ".fs", ".r", ".lua", ".pl", ".php",
    # Scripting (text-safe; already blocked by extension filter)
    ".bat", ".cmd", ".ps1",
    # Misc config
    ".gitattributes", ".dockerignore", ".prettierrc", ".eslintrc",
    ".tf", ".tfvars", ".hcl", ".proto", ".graphql", ".gql",
    ".properties", ".gradle", ".sbt", ".cmake", ".mk",
}

# ── Executable / dangerous file signatures ─────────────────────────────────────
# (byte-offset, magic bytes, human label)
# Matched against the first 16 bytes of every non-plain-text file.

EXEC_SIGS: list[tuple[int, bytes, str]] = [
    # Windows executables
    (0, b"\x4D\x5A",                         "Windows PE Executable (MZ)"),
    (0, b"\x4C\x00\x00\x00\x01\x14\x02\x00", "Windows Shell Link (LNK)"),
    # Linux / macOS executables
    (0, b"\x7F\x45\x4C\x46",                 "ELF Executable"),
    (0, b"\xCA\xFE\xBA\xBE",                 "Mach-O / Java Class"),
    (0, b"\xCE\xFA\xED\xFE",                 "Mach-O 32-bit"),
    (0, b"\xCF\xFA\xED\xFE",                 "Mach-O 64-bit"),
    (0, b"\xFE\xED\xFA\xCE",                 "Mach-O Fat Binary (BE)"),
    # Archives that can contain executables
    (0, b"\x4D\x53\x43\x46",                 "Windows Cabinet (CAB)"),
    (0, b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1", "OLE Compound File (MSI/DOC)"),
    (0, b"\x50\x4B\x03\x04",                 "ZIP Archive (DOCX/JAR/APK)"),
    (0, b"\x52\x61\x72\x21\x1A\x07",         "RAR Archive"),
    (0, b"\x37\x7A\xBC\xAF\x27\x1C",         "7-Zip Archive"),
    # Dangerous document / help formats
    (0, b"\x49\x54\x53\x46",                 "Compiled HTML Help (CHM)"),
    (0, b"\x46\x57\x53",                     "Shockwave Flash (SWF)"),
    (0, b"\x43\x57\x53",                     "Compressed SWF"),
    # Script shebangs
    (0, b"\x23\x21",                         "Script with Shebang (#!)"),
]

# Maximum header bytes to read for magic-byte matching.
MAGIC_READ_SIZE: int = 16

# ── ZIP-based document allowlist ───────────────────────────────────────────────
# Extensions where ZIP (PK) magic bytes are expected and benign.
# These get a WARNING in the log but are NOT purged from the destination.

ZIP_DOC_EXTS: set[str] = {
    ".docx", ".xlsx", ".pptx",
    ".odt", ".ods", ".odp", ".odg",
    ".epub",
    ".dotx", ".xltx", ".potx",
    ".cbz",
    ".zip",
}

# ── OLE document allowlist ─────────────────────────────────────────────────────
# Extensions where OLE (D0 CF 11 E0) magic bytes are expected and benign.

OLE_DOC_EXTS: set[str] = {
    ".doc", ".xls", ".ppt", ".msg", ".vsd", ".pub",
}

# ── GhostHarvest internal file prefixes ────────────────────────────────────────
INTERNAL_PREFIX = "_GhostHarvest"

# Robocopy exit code ranges (0-7 indicate success/copied without errors)
ROBOCOPY_SUCCESS_CODES = range(8)
