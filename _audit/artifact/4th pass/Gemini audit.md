## Phase 1: Audit & Work Order

The codebase snapshot for **Ghost Harvest v2.1** has been analyzed across four distinct layers. While the architectural layout is well-structured and handles Windows standard library restrictions gracefully, subtle edge-case flaws exist in boundary validation, path tokenization, and verification logic coverage.

The complete architectural remediation work order has been compiled below.

```markdown
# SPRINT_FIX.md — Ghost Harvest
**Audit Date:** May 30, 2026
**Auditor:** Senior Architect Review
**Target:** Autonomous Agent Implementation Sprint
**Base Ref:** README.md

---

## HOW TO USE THIS FILE
This document contains the findings of a structural and logical audit of GhostHarvest v2.1. Identified vulnerabilities and silent bugs are tagged by severity. The autonomous agent must execute the precise modifications detailed in this work order sequentially, validating each working checkpoint before moving forward.

---

## PASS 1 — CRITICAL BLOCKERS
*Pass 1 Scan Complete: No compilation, initialization, or import blockers found. The modular packaging runs smoothly and interfaces correctly with the tkinter event loop container.*

---

## PASS 2 — HIGH SEVERITY TEST BUGS
*Pass 2 Scan Complete: No existing test framework failures found. The 37-assertion security regression suite passes out-of-the-box but suffers from coverage gaps regarding nested directory limits.*

---

## PASS 3 — MEDIUM SEVERITY (SILENT FAILURES)

### BUG-001 [MEDIUM] — Inverted Destination-Inside-Source Recursion Guard
**File:** `ghost_harvest/app.py`
**What's wrong:** The source/destination boundary validation logic on lines 341–344 only detects if the source directory is nested inside the destination workspace. If a user sets a destination directory *inside* an infected source hierarchy (e.g., source root `C:\InfectedData` and destination target `C:\InfectedData\Recovered`), the safety guard is bypassed. This causes Robocopy to recursively traverse the newly created destination subdirectory over and over, producing an infinite replication loop.
**Fix:** Update the boundary evaluation to scan both parent streams using `Path.parents`. Replace lines 341–344 in `ghost_harvest/app.py` with the following code block:

```python
        # Check destination-inside-source guard (IMP-001)
        dest_path = Path(dest).resolve()
        for src in settings["queue"]:
            src_path = Path(src).resolve()
            if src_path in dest_path.parents or dest_path in src_path.parents or dest_path == src_path:
                self._log(f"⚠  Destination '{dest}' is inside or contains source '{src}' – would cause infinite recursion. Aborted.\n", "bad")
                self._finish()
                return

```

### BUG-002 [MEDIUM] — Integrity Verification Omits Missing Source Files

**File:** `ghost_harvest/hasher.py`
**What's wrong:** The multi-threaded hash verifier walks the destination folder and references paths back to the source drive. If Robocopy fails to extract a file due to transient file locking, read limits, or intermittent media degradation, the file is quietly omitted from the destination. Because the verifier only loops over what *successfully* arrived at the destination, it completely misses these dropped data sets, breaking the specification promise to capture missing files.
**Fix:** Augment `ParallelHashVerifier.verify` to include a forward pass from the source filesystem, capturing missing target entries while correctly filtering out the configured exclusions.

Replace the entire `verify` method block in `ghost_harvest/hasher.py` with:

```python
    def verify(
        self,
        src: str,
        dest: str,
        callback: Callable[[str, str], None] | None = None,
        abort_event: threading.Event | None = None,
    ) -> tuple[int, int, int]:
        """
        Walk *dest*, hash each file, compare against *src*, and discover missing source transfers.
        Returns ``(ok, fail, missing_from_dest)`` counts.
        """
        cb = callback or (lambda _m, _t: None)
        cb(f"\n🔑  SHA-256 verify: {Path(dest).name}\n", "info")

        pairs: list[tuple[Path, Path]] = []
        destination_only = 0

        # Pass 1: Walk destination for integrity matching
        for root_dir, _dirs, files in os.walk(dest):
            for fname in files:
                if abort_event and abort_event.is_set():
                    cb("  🛑  Verification cancelled by user.\n", "warn")
                    return 0, 0, 0
                if fname.startswith(INTERNAL_PREFIX):
                    continue
                dst_path = Path(root_dir) / fname
                try:
                    rel = dst_path.relative_to(dest)
                    src_path = Path(src) / rel
                except ValueError:
                    destination_only += 1
                    continue
                if not src_path.exists():
                    destination_only += 1
                    continue
                pairs.append((src_path, dst_path))

        # Pass 2: Walk source to identify completely dropped transfers
        missing_from_dest = 0
        from .constants import DANGEROUS_EXTS, BLOAT_DIRS
        blocked_exts_set = {e.removeprefix("*.").lower() for e in DANGEROUS_EXTS}
        skip_dirs_set = {d.casefold() for d in BLOAT_DIRS}

        for root_dir, dirs, files in os.walk(src):
            if abort_event and abort_event.is_set():
                break
            dirs[:] = [d for d in dirs if d.casefold() not in skip_dirs_set]
            for fname in files:
                ext = Path(fname).suffix.lower().removeprefix(".")
                if ext in blocked_exts_set or fname.startswith(INTERNAL_PREFIX):
                    continue
                src_file_path = Path(root_dir) / fname
                try:
                    rel = src_file_path.relative_to(src)
                    dst_file_path = Path(dest) / rel
                    if not dst_file_path.exists():
                        missing_from_dest += 1
                        cb(f"  ❌  MISSING AT DESTINATION: {rel}\n", "bad")
                except ValueError:
                    continue

        if not pairs and missing_from_dest == 0:
            cb("  No files to verify.\n", "dim")
            return 0, 0, missing_from_dest

        ok = 0
        fail = 0

        def _check(src_p: Path, dst_p: Path) -> tuple[str, str, str]:
            return dst_p.name, sha256(src_p), sha256(dst_p)

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                pool.submit(_check, sp, dp): (sp, dp)
                for sp, dp in pairs
            }
            for future in as_completed(futures):
                if abort_event and abort_event.is_set():
                    for f in futures:
                        f.cancel()
                    cb("  🛑  Verification cancelled by user.\n", "warn")
                    break
                sp, dp = futures[future]
                try:
                    name, sh, dh = future.result()
                    rel_display = str(dp.relative_to(dest))
                except Exception:
                    fail += 1
                    continue

                if not sh or not dh:
                    fail += 1
                    cb(f"  ⚠  Could not hash: {rel_display}\n", "warn")
                    continue

                if sh == dh:
                    ok += 1
                else:
                    fail += 1
                    cb(f"  ❌  MISMATCH: {rel_display}\n", "bad")

        tag = "good" if (fail == 0 and missing_from_dest == 0) else "bad"
        total_hashed = ok + fail
        cb(
            f"  {total_hashed:,} files hashed → {ok:,} OK · {fail} mismatched · "
            f"{missing_from_dest} missing from destination · {destination_only} destination-only\n",
            tag,
        )
        return ok, fail, missing_from_dest

```

---

## PASS 4 — ENVIRONMENT & STRUCTURAL

### BUG-003 [MEDIUM] — Space-Containing Directory Exclusions Broken by Naive Splitting

**File:** `ghost_harvest/command.py` and `ghost_harvest/app.py`
**What's wrong:** The entry handling for custom directory exclusions relies on simple whitespace splitting (`custom_xd.strip().split()`). This fragments paths containing literal spaces into broken parameter arguments (e.g., `"Target Workspace"` expands into `'"Target'` and `'Workspace"'`). Concurrently, the path safety validation scanner in `app.py` (`for p in extra.split(): if " " in p:`) can never evaluate to True because the splitting process strips out the target spaces before parsing.
**Fix:** Incorporate shell-aware path evaluation using standard library `shlex` parsing to sustain encapsulated strings.

In `ghost_harvest/command.py`, add `import shlex` and update the directory logic block (lines 56–60) as follows:

```python
    # Directory exclusions
    xd: list[str] = list(BLOAT_DIRS) if skip_bloat else []
    extra = custom_xd.strip()
    if extra:
        import shlex
        xd.extend(shlex.split(extra))

```

In `ghost_harvest/app.py`, update the raw configuration parsing within both `_preflight` and `_start` blocks to gracefully handle malformed quoting profiles:

```python
        extra = settings.get("custom_xd", "").strip()
        if extra:
            import shlex
            try:
                parsed_tokens = shlex.split(extra)
            except ValueError:
                self._log("⚠  Error: Mismatched quote boundaries identified in custom folder exclusions.\n", "warn")

```

---

## EXECUTION ORDER FOR AGENT

Apply fixes in this exact order. Each Group establishes a distinct operational release.

**Group 1 — Path Inversion & Command Argument Hardening**

* BUG-001
* BUG-003
**Checkpoint:** `python -X utf8 ghost_harvest\tests\validate_security.py` runs with zero regression drops.

**Group 2 — Verification Stream Update**

* BUG-002
**Checkpoint:** Validate pipeline verification logging metrics against dummy directory trees containing missing files.

**Final checkpoint:** Execute full suite via `python -X utf8 ghost_harvest\tests\validate_security.py`.

---

## KNOWN STUBS (not bugs — expected at this stage)

* No functional placeholders exist. The current implementation is structurally cohesive.

```

---

## Phase 2: Autonomous Agent Initiation Prompt

```text
READ FIRST, CODE SECOND: Read SPRINT_FIX.md entirely before executing any file mutations. Re-verify dependency chains in Group 1 before changing downstream verification loops. You must follow the precise execution order and implement code replacements exactly as drafted.

OBJECTIVE:
Eliminate path traversal risks, infinite recursion loops, and integrity verification gaps in GhostHarvest v2.1.
Success Criterion: Application launches flawlessly, prevents inverse directory recursion, respects multi-word paths, flags missing source items, and passes the terminal regression suite via command:
`python -X utf8 ghost_harvest\tests\validate_security.py`

EXECUTION RULES:
1. Work file-by-file; do not modify unaffected system code layout architectures.
2. Inject specified replacement blocks verbatim during the optimization run; do not add unrequested structural elements.
3. Complete and check each execution group checkpoint cleanly before rolling changes into subsequent groups.
4. SPRINT_FIX.md directives supersede previous documentation where layout structures conflict.
5. Record any runtime errors or hidden anomalies discovered during modifications exactly as:
   "UNTRACKED-BUG: [file] — [desc] — [fix]" before adjusting that file.

CHECKPOINT COMMANDS:
- Group 1 Checkpoint: `python -X utf8 ghost_harvest\tests\validate_security.py`
- Final Verification: `python -X utf8 ghost_harvest\tests\validate_security.py`

WHEN AMBIGUITY ARISES:
- Symptom: User types unbalanced or uneven quotes in custom entry fields.
  → Diagnosis: shlex splitting engine throws a ValueError.
  → Resolution: Log an warning statement cleanly inside the Tkinter logging container via self._log() and drop processing of the customized field.
- Symptom: Recursive directory nesting validation captures an identical match boundary loop.
  → Diagnosis: Target backup area falls inside the active source path target range.
  → Resolution: Halt background pipeline generation instantly, issue a direct warning via the logs, and terminate processing via the internal self._finish() routing loop.
- Symptom: ThreadPoolExecutor execution worker hits a locked or unreadable binary stream.
  → Diagnosis: Operating system locking rule holds back handle access during hashing steps.
  → Resolution: Return an empty file string representation "", write a caution line inside the execution panel log, and count the instance as a standard hash verification mismatch error.

DELIVERABLE SUMMARY REQUIREMENT:
Provide a crisp closing log outlining:
1. Explicit list of files modified.
2. Any newly documented UNTRACKED-BUG tracking lines captured during processing.
3. Final execution capture text indicating 37 passed regression metrics.

```