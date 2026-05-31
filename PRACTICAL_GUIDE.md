# 📖 GhostHarvest v2.1 — Practical Usage & Test Guide

This guide provides a step-by-step walkthrough to safely test and run **GhostHarvest v2.1** in a sandboxed environment on your PC. You do not need to risk connecting an actual infected drive to test the security boundaries, scanners, and verifiers.

---

## 🛠️ Step 1: Set Up a Safe Mock Sandbox

We will create a dummy "infected" source folder containing both safe files and mock malicious payloads to see exactly how GhostHarvest sanitizes and protects your system.

### 1. Create the Test Folders
Create two new empty folders on your Desktop (or anywhere in your user space):
* `C:\Users\USER\Desktop\Ghost_Source` (Our mock "infected" drive)
* `C:\Users\USER\Desktop\Ghost_Destination` (Our clean recovery location)

### 2. Populate the Mock "Infected" Source
Inside your `Ghost_Source` folder, create the following test files:

* **File 1: A Safe Document**
  * Name: `my_document.txt`
  * Content: `This is a completely safe plain text file containing recipes.`

* **File 2: Double-Extension Attack (Will be purged)**
  * Name: `tax_invoice.pdf.exe`
  * Content: *(Any dummy text)*
  * *Why:* GhostHarvest flags double extensions containing hazardous trailing formats.

* **File 3: Renamed Executable Magic-Byte Attack (Will be purged)**
  * Name: `image.png`
  * Content: Start the file with the executable magic bytes `MZ` (hex `4D 5A`). You can create this by writing `MZ - This is actually a disguised program!` inside it.
  * *Why:* The magic-byte scanner reads the first 16 bytes of all copied files, identifying header mismatches even if renamed.

* **File 4: Legitimate ZIP/Office Document (Will be warned, not purged)**
  * Name: `presentation.pptx`
  * Content: Start the file with standard ZIP magic bytes `PK` (hex `50 4B 03 04`).
  * *Why:* The zip document allowlist identifies this as a valid zip-container file format, triggering a `warn` warning rather than a delete purge.

* **File 5: Excluded Bloat Directory (Will be skipped)**
  * Create a subfolder inside `Ghost_Source` named `$Recycle.Bin`.
  * Add a dummy file `deleted_malware.exe` inside it.
  * *Why:* GhostHarvest automatically excludes systemic bloat folders during the initial Robocopy pass.

---

## 🚀 Step 2: Start the Application

### 1. Disable AutoPlay (Windows Native Protection)
Before interacting with any potentially hazardous drive, disable AutoPlay globally to prevent Windows from auto-running scripts on plugin:
1. Open **Settings** (`Win + I`).
2. Search for **AutoPlay settings**.
3. Toggle **Use AutoPlay for all media and devices** to **Off**.

### 2. Launch GhostHarvest
Open PowerShell or Command Prompt as an administrator and run:

```powershell
cd "C:\Users\USER\Desktop\APPS\Ghost Harvest"
python main.py
```

*Note: If you run it normally, the application will trigger a secure Windows User Account Control (UAC) dialog to auto-elevate itself. This elevation is native and necessary to grant Robocopy the `SeBackupPrivilege` privileges required to bypass damaged file permissions.*

---

## 🖥️ Step 3: Run the Extraction Test

Once the beautiful dark-themed GUI loads, configure it as follows:

1. **Source Directory:** Set this to your mock folder: `C:\Users\USER\Desktop\Ghost_Source`
2. **Destination Directory:** Set this to: `C:\Users\USER\Desktop\Ghost_Destination`
3. **Execution Settings:**
   * Make sure **Multi-threaded copy** is set (default is 16).
   * Leave **Pre-Scan Plain Text** checked (or uncheck to see the performance bypass).
   * Leave **Exclude System Bloat** checked.
4. **Click "Pre-Flight Scan"**
   * Watch the console output. It will execute a safe, instantaneous Robocopy dry run (`/L` mode) to estimate the total size and file counts before writing a single byte.

### 5. Click "Start Migration"
A confirmation dialog will appear summarizing the security boundaries. Click **Yes** to initiate the surgical extraction.

---

## 🔍 Step 4: Verify the Results

After the run finishes, check the logs and your folders to observe the zero-trust sanitization in action:

### 1. Inspect the Destination Folder (`Ghost_Destination`)
Open your recovery directory. You will find:
* ✅ `my_document.txt` (Safely migrated and verified).
* ❌ `tax_invoice.pdf.exe` is **completely gone** (Purged and deleted).
* ❌ `image.png` is **completely gone** (Identified as disguised executable magic bytes, purged and deleted).
* ⚠️ `presentation.pptx` is **safely retained** (Identified as a valid Office document container, skipped from purging, but logged with a warning).

### 2. Read the Manifest File (`_BLOCKED.txt`)
Inside the root of `Ghost_Destination`, open the generated `_BLOCKED.txt` file. You will see a detailed timestamped audit trail:
```
[PURGE] image.png | Reason: Magic signature match (Executable (MZ))
[PURGE] tax_invoice.pdf.exe | Reason: Double extension (.pdf.exe)
[WARN]  presentation.pptx | Reason: Magic signature match (ZIP Archive (PK))
```

### 3. Read the Log File (`_GhostHarvest_log.txt`)
A complete CLI log file is written to your destination folder containing every Robocopy output line, ANSI logs, and parallel verification summaries for administrative records.

### 4. Verification Check
Observe the GUI log panel. You will see the **Parallel SHA-256 Verifier** successfully matched the hash signatures between source and destination copies, confirming zero files were corrupted during transit.

---

## 💡 Future Real-World Runs
When running this on actual infected external drives:
1. **Disable AutoPlay** before plugging the drive in.
2. **Run a full Malwarebytes/Windows Defender scan** on the drive to neutralize active memory boot-payloads.
3. Launch **GhostHarvest** and point it to the drive letter root (e.g. `E:\`).
4. Click **Start Migration** and let the surgical extraction pipeline handle the rest safely!
