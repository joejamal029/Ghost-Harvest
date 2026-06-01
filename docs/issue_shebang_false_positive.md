# 📝 ISSUE-014: Shebang (#!) Magic Signature Triggers False-Positive Purges on Legitimate Scripts

## 1. Executive Summary
* **Severity:** 🔴 **High (Data Loss / Code Deletion)**
* **Symptom:** When executing GhostHarvest v2.1 with **`Scan plain-text`** enabled, any plain-text developer script (e.g., `.py`, `.sh`, `.rb`, `.pl`) starting with a standard interpreter shebang line (e.g. `#!/usr/bin/env python`) is identified as an executable payload threat and **permanently deleted (purged)** from the destination directory.
* **First Occurrence:** Reported during a live migration of the `Html Merger` folder where `html_merger.py` was purged with the reason: `MAGIC_BYTE — Script with Shebang (#!)`.

---

## 2. Root Cause Analysis

### A. The Signature Definition
In [`ghost_harvest/constants.py`](file:///c:/Users/USER/Desktop/APPS/Ghost%20Harvest/ghost_harvest/constants.py), the `EXEC_SIGS` list contains the magic bytes for shell scripts starting with a shebang:
```python
EXEC_SIGS: list[tuple[int, bytes, str]] = [
    ...
    (0, b"#!", "Script with Shebang (#!)"),
]
```

### B. The Scanner Logic
In [`ghost_harvest/scanner.py`](file:///c:/Users/USER/Desktop/APPS/Ghost%20Harvest/ghost_harvest/scanner.py), the scanner walks the destination:
1. Since the file `html_merger.py` has a `.py` extension, it is listed in `PLAIN_TEXT_EXTS`.
2. However, if the user toggles **`Scan plain-text`** to **[ON]**, the scanner bypasses the fast-skip logic and reads the first 16 bytes of the file.
3. The scanner matches `#!` at offset `0` and flags the file with `MAGIC_BYTE`.
4. The scanner then checks if `.py` is an allowlisted document extension (which are only Office XML formats like `.docx`, `.pptx`, `.xlsx` in `ZIP_DOC_EXTS` or OLE binaries like `.doc`, `.xls` in `OLE_DOC_EXTS`).
5. Since `.py` is not allowlisted, the scanner assigns `"action": "purge"`.

### C. The Deletion Trigger
In [`ghost_harvest/app.py`](file:///c:/Users/USER/Desktop/APPS/Ghost%20Harvest/ghost_harvest/app.py), the migration pipeline processes the scanner's report:
```python
if item["action"] == "purge":
    os.remove(item["path"])
```
This instantly deletes the file from the recovered destination workspace, leaving only an entry in `_BLOCKED.txt`.

---

## 3. Proposed Remediation Strategies

We have identified two elegant solutions to resolve this without degrading the tool's zero-trust security boundaries.

### Option A: Script Extension Alignment (Recommended)
1. **Define Script Extensions:** Add a centralized set of legitimate script extensions in [`ghost_harvest/constants.py`](file:///c:/Users/USER/Desktop/APPS/Ghost%20Harvest/ghost_harvest/constants.py):
   ```python
   SAFE_SCRIPT_EXTS: set[str] = {
       ".py", ".pyw", ".sh", ".bash", ".pl", ".rb", ".php", ".lua", ".tcl"
   }
   ```
2. **Scanner Exception:** Update `PostCopyScanner` in [`ghost_harvest/scanner.py`](file:///c:/Users/USER/Desktop/APPS/Ghost%20Harvest/ghost_harvest/scanner.py) to check:
   * If a file matches the `Script with Shebang (#!)` signature **AND** its extension is in `SAFE_SCRIPT_EXTS`, downgrade the action from `"purge"` to `"warn"` (or skip entirely if the user prefers silent trust).
   * If a file matches `#!` but has a non-script extension (such as `.jpg` or `.png`), retain the `"purge"` action to prevent hidden polyglot executable script attacks.

### Option B: Plain-Text Shebang Downgrade
* **Logic:** If `Scan plain-text` is enabled and a shebang match occurs, check if the file's extension is in the `PLAIN_TEXT_EXTS` list. 
* **Action:** Downgrade the action to `"warn"` for any plain-text file extension, since a shebang is a standard plain-text header.

---

## 4. Current Workaround
Until this issue is patched in the next sprint:
> [!WARNING]
> **DEVELOPER WORKAROUND:** Ensure the **`Scan plain-text`** checkbox is turned **[OFF]** in the GUI settings panel before running migrations containing programming code, scripts, or repositories. This will skip scanning plain-text files entirely, preserving all shebang headers safely.
