# 👻 GhostHarvest v2.1 — Complete User Manual & Practical Testing Guide

This guide is a comprehensive reference manual for **GhostHarvest v2.1**. It explains the technical purpose, security implications, and argument mapping of every GUI option, slider, toggle, and command preview, followed by a step-by-step sandboxed tutorial to test them.

---

## 🖥️ 1. Interface & Controls Reference

GhostHarvest's interface is divided into functional zones designed to construct a secure, zero-trust migration pipeline.

```
┌────────────────────────────────────────────────────────┐
│ 1. SOURCE QUEUE                                        │
├────────────────────────────────────────────────────────┤
│ 2. DESTINATION SELECTION & PATH VALIDATION             │
├────────────────────────────────────────────────────────┤
│ 3. FILTERS (EXCLUSIONS & PATTERNS)                     │
├────────────────────────────────────────────────────────┤
│ 4. PERFORMANCE & PIPELINE SETTINGS                     │
├────────────────────────────────────────────────────────┤
│ 5. COMMAND PREVIEW & SYSTEM CONTROLS                   │
└────────────────────────────────────────────────────────┘
```

---

### Zone 1: Source Queue Management

The **Source Queue** allows you to consolidate multiple source folders into a single surgical migration batch. To ensure maximum device security, you can type paths directly to avoid system file dialogs.

| GUI Control | Action | Security / Technical Purpose |
|:---|:---|:---|
| **`Type folder path directly...`** | Direct text input field. | Allows typing or pasting absolute source paths manually (e.g. `E:\InfectedFolder`) to completely bypass file explorer shell interaction. |
| **`+ Add Typed Path`** | Appends the manually typed path. | Adds the typed text path to the list queue with zero drive communication. |
| **`Browse…`** | Spawns a native directory selector. | Convenient directory browser. Use **only** for trusted/clean local paths. |
| **`↑` (Move Up)** | Shifts the selected folder up in the queue. | Reorders execution sequence (folders copy in top-down order). |
| **`↓` (Move Down)** | Shifts the selected folder down in the queue. | Reorders execution sequence. |
| **`✕` (Remove)** | Deletes the selected folder path from the queue. | Excludes the folder from the current migration batch. |

> [!NOTE]
> **Path Validation:** The source queue rejects empty entries and duplicate paths to prevent redundant copy processes.

---

### Zone 2: Destination Selection

Sets the target recovery location where your clean, sanitized files will be written.

* **`Destination:` Text Entry:** Displays the active recovery path (default: `C:\CleanWorkspace`).
* **`Browse...` Button:** Spawns a folder picker to easily select your destination.
* **Real-time Path Assertion Label:** Dynamically monitors the path state to prevent critical errors:
  * ⚠️ *Destination folder does not exist yet:* A warning printed if the folder must be created.
  * 🛑 *Path errors:* Displays error alerts if the source queue contains paths nesting within the destination, or if the destination is located inside a source directory (bidirectional recursion protection).

---

### Zone 3: Filters (Exclusions & Patterns)

Controls what files and directories are allowed to cross the security boundary at the **initial Robocopy level**.

#### 1. `Block dangerous executables` Checkbox
* **Robocopy Mapping:** `/XF` (Exclude Files)
* **Default Arguments Applied:** Excludes `*.exe`, `*.bat`, `*.cmd`, `*.vbs`, `*.js`, `*.wsf`, `*.scr`, `*.pif`, `*.lnk`, `*.msi`, `*.ps1`, `*.reg`, `*.inf`, `*.com`, `*.hta`, `*.jar`, `*.wsh`, `*.sys`, `*.drv`, `*.ocx`, `*.cpl`, `*.msp`, `*.mst`, `*.application`, `*.gadget`, `*.psc1`, `*.docm`, `*.xlsm`, `*.pptm`, `*.dotm`, `*.xltm`, `*.potm`, `*.chm`, `*.url`, `*.website`
* **Purpose:** Blocks known executable file types and macro-enabled documents from ever copying to the destination, stopping malware before it reaches your filesystem.

#### 2. `Skip dev bloat + system dirs` Checkbox
* **Robocopy Mapping:** `/XD` (Exclude Directories)
* **Default Arguments Applied:** Excludes `node_modules`, `.git`, `node_modules`, `build`, `dist`, `target`, `.gradle`, `.idea`, `.tox`, `.next`, `.nuxt`, `coverage`, `.cache`, `.mypy_cache`, `.pytest_cache`, `$Recycle.Bin`, `"System Volume Information"`, `Recovery`, `Windows.old`
* **Purpose:** Skips useless developer dependency caches and high-risk Windows system directories (like `$Recycle.Bin` and hidden recycler volumes) where drive-penetration viruses frequently deposit active payloads.

#### 3. `Extra folder exclusions (space-separated)` Text Field
* **Robocopy Mapping:** Appends custom arguments to `/XD`
* **Parsing Engine:** Uses standard `shlex.split` to parse the string.
* **Purpose:** Allows you to exclude specific folder names. Since it uses `shlex.split`, you can safely input folder names containing spaces by wrapping them in double quotes (e.g. `"My Old Temp Folder" "Trash"`).

---

### Zone 4: Settings & Performance

Toggles the execution parameters of the recovery thread, Robocopy options, and post-copy verification sweeps.

#### 1. `Threads:` Slider
* **Robocopy Mapping:** `/MT:N` (Multi-threaded copy, range: `1` to `32`)
* **Verification Mapping:** Sets the worker pool limit inside the parallel `ThreadPoolExecutor` SHA-256 verifier.
* **Purpose:** Maximizes file-copy throughput on multi-core systems. Set higher for fast SSDs/NVMe drives; set lower (1-4) for mechanical external drives to avoid mechanical head thrashing.

#### 2. `Restartable /ZB` Checkbox
* **Robocopy Mapping:** `/ZB` (Restartable mode with backup mode fallback)
* **Purpose:** If a file copy is interrupted mid-transfer (due to drive disconnects), Robocopy can resume from the exact byte offset instead of restarting. If it hits an access-denied permission boundary, it falls back to backup mode using admin credentials (`SeBackupPrivilege`) to force-copy unreadable files.

#### 3. `Dry run` Checkbox
* **Robocopy Mapping:** `/L` (List only)
* **Purpose:** When checked, no directories are written, and no files are copied. The tool simulates the migration, allowing you to preview exactly what files *would* be transferred, which filters would trigger, and what size is expected.

#### 4. `Magic byte scan` Checkbox
* **Scanner Mapping:** `scanner.PostCopyScanner`
* **Purpose:** Triggers a post-copy deep scan of the destination filesystem. It reads the first 16 bytes of every copied file and compares it against 16 distinct executable magic signatures (such as PE headers `MZ`, zip archives `PK`, cabinet files, and script shebangs). Disguised executables (e.g., a `.exe` renamed to `.png`) are automatically identified and purged.

#### 5. `Scan plain-text` Checkbox
* **Scanner Mapping:** Skip plain-text matching (`constants.PLAIN_TEXT_EXTS`)
* **Purpose:** Instructs the magic-byte scanner to skip checking known plain-text extensions (like `.txt`, `.py`, `.csv`, `.md`, `.css`, `.json`). Leave checked for absolute security; uncheck to significantly boost scanning performance on directories containing thousands of code or text files.

#### 6. `SHA-256 verify` Checkbox
* **Verifier Mapping:** `hasher.ParallelHashVerifier`
* **Purpose:** Runs a multi-threaded parallel SHA-256 check. It performs a **two-pass walk**:
  1. *First Pass:* Hashes copied files in the destination and compares them against their source counterpart to ensure zero corruption or transit alteration.
  2. *Second Pass:* Walks the source directory (excluding blocked folders) to verify if any files were missed entirely during copy, reporting them as `"missing from destination"`.

#### 7. `Save log` Checkbox
* **Logging Mapping:** Dynamic stream redirect to `_GhostHarvest_log.txt`
* **Purpose:** Streams the entire execution session—including the original Robocopy console logs, scan block lists, and hash verifications—into a persistent log file in the root of the destination directory.

---

### Zone 5: Command Preview & Control Panel

* **Command Preview Box:** Displays the exact command-line string that is passed to the OS in real-time.
  * **Security Note:** The preview quotes paths for readability, but the backend passes argument lists directly via `subprocess.Popen(args, shell=False)` to prevent argument injection.
* **`Refresh` Button:** Manually forces a refresh and redraw of the command preview box.
* **`Copy` Button:** Copies the active command preview string to your clipboard for manual execution.
* **`Pre-flight` Button:** Spawns a background thread to run an instantaneous dry-run analysis. It scans the source queue to calculate the exact file count and byte footprint of the migration, checking for permission constraints before execution.
* **`RUN MIGRATION` Button:** Initiates the 6-stage surgical recovery pipeline on a background daemon thread.
* **Progress Bar & Status Label:** Displays real-time operation status (`Ready.`, `Copying...`, `Scanning...`, `Verifying...`, `Completed.`).

---

## 🧪 2. Sandboxed Sandbox Test Walkthrough

Follow these steps to safely test every single option and security boundary of the GhostHarvest v2.1 pipeline.

### Step 1: Initialize the Mock Environment
Create two dummy folders on your Windows system:
* `C:\Ghost_Source` (Our mock infected external drive)
* `C:\Ghost_Destination` (Our clean target workspace)

Inside `C:\Ghost_Source`, create the following test assets:
1. **`clean.txt`** (Safe file) -> Write standard text inside.
2. **`malicious.exe`** (Dangerous executable) -> Create a dummy text file and rename the extension to `.exe`.
3. **`disguised.jpg`** (Renamed executable magic-byte attack) -> Create a text file, write `MZ - disguised binary payload` as the first characters, and rename the extension to `.jpg`.
4. **`document.docx`** (Allowlisted office zip container) -> Create a text file, write `PK - valid office container` as the first characters, and rename to `.docx`.
5. **`invoice.pdf.bat`** (Double extension) -> Create a text file and rename it to `.pdf.bat`.
6. **`System Volume Information`** (System bloat folder) -> Create a subfolder with this name, and put a dummy file `virus.dll` inside.

---

### Step 2: Test Pre-Flight & Command previews
1. Open PowerShell/CMD as administrator and launch the tool via the launcher:
   ```powershell
   cd "C:\Users\USER\Desktop\APPS\Ghost Harvest"
   .\launch.bat
   ```
2. **Type the Source Path:** Type `C:\Ghost_Source` directly into the path entry field (`Type folder path directly...`) and click **`+ Add Typed Path`** (or press Enter).
   * *Security Note:* This inserts the path with zero file explorer filesystem interaction, making it completely safe for infected drives.
3. Enter `C:\Ghost_Destination` in the **Destination** text field.
4. **Observe the Command Preview Box:** Notice how `/XF` lists all dangerous extensions, and `/XD` automatically includes the bloat folder list.
5. Click **`Pre-flight`**.
   * *Result:* The status label updates, showing the exact file count (6 files) and total size calculated during the dry run, without writing any data to your C: drive.

---

### Step 3: Run the Surgical Migration
1. Ensure all settings toggles are checked:
   * **`Restartable /ZB`**: [ON]
   * **`Magic byte scan`**: [ON]
   * **`Scan plain-text`**: [ON]
   * **`SHA-256 verify`**: [ON]
   * **`Save log`**: [ON]
2. Click the green **`RUN MIGRATION`** button.
3. Review the confirmation summary box and click **Yes**.
4. Watch the progress bar transition from copying, to magic scanning, to verifying.

---

### Step 4: Analyze the Security Sanitize Results

Open your destination folder `C:\Ghost_Destination` to observe how every zero-trust configuration executed:

#### 1. Filter Check (Robocopy Level)
* **`clean.txt`** is safely copied.
* **`document.docx`** is safely copied.
* ❌ **`malicious.exe`** is **missing** (Blocked at the Robocopy level by `/XF`).
* ❌ **`invoice.pdf.bat`** is **missing** (Blocked at the Robocopy level by `/XF`).
* ❌ **`System Volume Information`** is **missing** (Blocked at the Robocopy level by `/XD`).

#### 2. Deep Scanner Check (Magic-Byte Level)
* ❌ **`disguised.jpg`** was copied by Robocopy (since `.jpg` is not in the blocked extension list), but the **Post-Copy Scanner** analyzed its header, matched the `MZ` executable signature, and **permanently purged (deleted) it** from the destination directory.
* ⚠️ **`document.docx`** matched the `PK` zip-container magic header. However, the allowlist identified it as an approved office file format, **retaining it** while logging a warning.

#### 3. Verification Report (`_BLOCKED.txt` & `_GhostHarvest_log.txt`)
* Open `C:\Ghost_Destination\_BLOCKED.txt`. You will see the precise security audit trail:
  ```
  [PURGE] C:\Ghost_Destination\disguised.jpg | Reason: Magic signature match (Executable (MZ))
  [WARN]  C:\Ghost_Destination\document.docx | Reason: Magic signature match (ZIP Archive (PK))
  ```
* Open `_GhostHarvest_log.txt` to view the stream log containing the full output.
