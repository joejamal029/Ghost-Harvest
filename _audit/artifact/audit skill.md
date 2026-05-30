---
name: code-audit-sprint
description: >
  Deep multi-pass codebase audit that produces a structured SPRINT_FIX.md work order
  and a matching autonomous agent initiation prompt. Use this skill whenever the user
  shares a codebase (as a file, snapshot, or upload) and asks for a bug audit, code
  review, sprint planning, or agent implementation prompt. Also triggers for phrases
  like "go deep find bugs", "find bugs in many passes", "make a sprint fix file",
  "audit this codebase", "prepare this for an agent", or "make the initiation prompt".
  This skill handles both phases of the workflow: (1) producing SPRINT_FIX.md, and
  (2) generating the agent initiation prompt from it. Always use this skill when the
  user has spec documents alongside a codebase and wants an autonomous agent to
  implement or fix it.
---
 
# Code Audit → Sprint Fix → Agent Initiation
 
This skill encodes a two-phase workflow that has produced exceptional results across
multiple software projects. It turns a codebase + spec into an autonomous agent work
order that is precise, executable, and safe to hand off without human supervision.
 
---
 
## WHEN TO RUN EACH PHASE
 
**Phase 1 — Audit → SPRINT_FIX.md**
Run when the user shares a codebase and wants bugs found and a work order produced.
Output: `SPRINT_FIX.md` file.
 
**Phase 2 — Agent Initiation Prompt**
Run immediately after Phase 1, or when the user says "now give the initiation prompt."
Output: a ready-to-paste prompt block for the autonomous agent.
 
Both phases may be requested in the same turn. When they are, complete Phase 1 fully
before generating Phase 2.
 
---
 
## PHASE 1: THE AUDIT
 
### 1.1 — Read everything before writing anything
 
Before finding a single bug, read all provided documents in this order:
 
1. The **governing spec** (authoritative architecture doc, if present)
2. Any **prior research or design docs**
3. The **codebase snapshot** — every file, not just the ones that look interesting
The governing spec is the source of truth. Where code diverges from spec, the spec wins
unless you can articulate a clear technical reason the code's approach is superior.
When the code is better, document this as a spec override in SPRINT_FIX.md.
 
### 1.2 — The Five Audit Passes
 
Run exactly five passes, in order. Do not collapse or skip passes.
 
---
 
**PASS 1 — Blockers**
Look for anything that prevents the codebase from running, compiling, or being tested
at all. These are absolute stoppers. Common blocker categories:
 
- Missing or wrong dependencies in `pyproject.toml` / `package.json` / `requirements.txt`
- Broken imports (module doesn't exist, wrong path, symbol not exported)
- Missing shared infrastructure that many files depend on (e.g., `conftest.py`, base classes)
- Schema conflicts between the ORM model definitions and migration files
- Database URL hardcoded to CWD-relative paths (causes split databases across run directories)
- Environment conflicts (e.g., PyQt6 and PySide6 both installed)
- Entry point (`main.py`) is a placeholder that can't start the application
---
 
**PASS 2 — Test Bugs**
With blockers identified, look at every test file and find bugs that will cause test
failures once stubs are implemented. Common categories:
 
- Tests that call a function with the wrong signature (mismatched parameter names or types)
- Tests that monkeypatch the wrong namespace (patching `library.Symbol` instead of
  `module.Symbol` where the module imported it with `from library import Symbol`)
- Tests that assert against values from a non-existent enum variant
- Tests that assert a regex pattern that doesn't match the actual tool's output format
- Tests that assume an output field exists on a stub object but never set it
- Tests that use a fixture from `conftest` that doesn't exist yet
- Integration tests with no skip guard, that will try to hit live services in CI
For each test bug: identify what the test *intends* to verify, then determine whether
to fix the test or fix the interface to match what the test assumes. Document which
choice you made and why.
 
---
 
**PASS 3 — Silent Failures**
Look for bugs that don't raise exceptions but produce wrong behavior. These are the
most dangerous because they slip past test suites. Common categories:
 
- Empty strings emitted where null/absent is correct (e.g., credentials serialized as `""`)
- Enum value casing mismatch between model definitions and migration DDL
- Configuration or schema written to CWD that diverges from what the running app reads
- Subprocess that resolves correctly in shell but fails inside a GUI app's spawn context
- A "monkeypatch target" issue (see Pass 2) that produces no error but also no mock
- Alembic migrations that create tables but don't stamp the version table — causes
  `alembic upgrade head` to fail on an already-initialized database
- Downgrade scripts that call DB-engine-specific operations on the wrong engine (e.g.,
  dropping named enum types on SQLite)
---
 
**PASS 4 — Environment & Structural Issues**
Step back from the code and look at the project as a deployed artifact:
 
- Are there redundant config files that fight each other? (`pytest.ini` + `pyproject.toml`
  both defining markers; `alembic.ini` hardcoding a URL that contradicts the app's URL)
- Are `__init__.py` files missing from packages that need them?
- Does the OS-specific context in the repo (e.g., an `env.txt` snapshot showing Windows)
  reveal platform assumptions that will break on other platforms?
- Is the dependency pinning strategy correct? (critical tools should be pinned exactly;
  utility libraries can float with a lower bound)
- Are setup scripts (`.ps1`, `.sh`) actual working scripts or empty placeholders?
- Is the entry point (`main.py`) wired to real application code?
---
 
**PASS 5 — Critical Improvements**
After all bugs are documented, make one final pass looking for improvements that are:
 
- Small enough to implement in the same sprint
- High enough leverage to be worth doing before any feature work begins
- Clearly scoped (not "refactor the whole service layer")
Improvements are tagged `[IMPROVEMENT]` and placed at the end of SPRINT_FIX.md.
They are optional but should always be presented. The agent executes them after all
bug fixes pass their checkpoints.
 
---
 
### 1.3 — Blindspot Scanning
 
After the five passes, explicitly scan for these systemic blindspots that are commonly
missed in early-stage scaffolds:
 
- **Lazy vs. eager initialization:** does the module create DB connections or engines at
  import time? This pollutes test environments and creates CWD-dependent side effects.
- **Subprocess resolution:** does the code assume CLI tools (`spotdl`, `ffmpeg`, etc.)
  are on PATH? On Windows, venv scripts may not be unless explicitly resolved.
- **Signal/slot thread safety:** if a QThread emits a signal, is the connected slot
  guaranteed to run on the GUI thread? Cross-thread direct connections crash Qt.
- **Missing status fields on test stub objects:** fake/mock objects built with `type()`
  often lack fields that the real implementation will access — causing `AttributeError`
  only when the stub is replaced with real code.
- **Relative path assumptions in exporters:** `Path.relative_to()` raises `ValueError`
  if the target is not under the base. Always provide a fallback to absolute path.
- **ANSI escape codes in subprocess output:** tools using `rich`, `click`, or `tqdm`
  emit ANSI sequences that break naive regex parsing. Always strip before matching.
- **Alembic + `create_all()` coexistence:** `create_all()` doesn't stamp the version
  table. Running both leaves the DB in a state where `alembic upgrade head` errors.
---
 
### 1.4 — SPRINT_FIX.md Format
 
Every SPRINT_FIX.md must follow this exact structure. Do not deviate.
 
```markdown
# SPRINT_FIX.md — [Project Name]
**Audit Date:** [date]
**Auditor:** Senior Architect Review
**Target:** Autonomous Agent Implementation Sprint
**Base Ref:** [governing spec filename] (§ references below point there)
 
---
 
## HOW TO USE THIS FILE
[2-3 sentences: severity tags, work order direction, conflict resolution rule]
 
---
 
## PASS 1 — CRITICAL BLOCKERS
### BUG-001 [BLOCKER] — [short title]
**File:** [exact filepath]
**What's wrong:** [precise description — what the code does vs. what it should do]
**Fix:** [exact replacement code or exact instructions — no ambiguity]
 
---
 
## PASS 2 — HIGH SEVERITY TEST BUGS
### BUG-NNN [HIGH] — ...
 
---
 
## PASS 3 — MEDIUM SEVERITY
### BUG-NNN [MEDIUM] — ...
 
---
 
## PASS 4 — ENVIRONMENT & STRUCTURAL
### BUG-NNN [MEDIUM] — ...
 
---
 
## PASS 5 — IMPROVEMENTS
### IMP-001 [IMPROVEMENT] — ...
 
---
 
## EXECUTION ORDER FOR AGENT
 
Apply fixes in this exact order. Each Group is a working checkpoint.
 
**Group 1 — [name]**
[numbered list of BUG IDs to apply]
**Checkpoint:** `[exact command to run]`
 
**Group 2 — [name]**
...
 
**Final checkpoint:** `[full pytest or equivalent command]`
 
---
 
## KNOWN STUBS (not bugs — expected at this stage)
[list of files that are intentional placeholders, deferred per the roadmap]
```
 
**Rules for writing bug entries:**
 
- Every `**Fix:**` block must be executable without interpretation. Either provide
  exact replacement code, or provide exact step-by-step shell commands. Never write
  "refactor this to be better" — write the refactored code.
- When a fix overrides the governing spec, call this out explicitly:
  `> **Spec override:** This changes §X.Y. The new interface is the authoritative one.`
- When two fixes have a dependency (Fix B assumes Fix A has already been applied),
  they must be in the same Group.
- Group sizes: aim for 3–6 fixes per group. Smaller groups = faster feedback loops.
- Every Group must have exactly one checkpoint command. The checkpoint must be a real
  command that will actually pass when the group's fixes are correctly applied.
---
 
## PHASE 2: AGENT INITIATION PROMPT
 
The initiation prompt is a standalone text block, formatted as a fenced code block,
that can be pasted directly into the agent's context. It must contain everything the
agent needs to begin without further clarification.
 
### 2.1 — Required Sections (always present)
 
**READ FIRST, CODE SECOND**
Tell the agent to read SPRINT_FIX.md in full, then re-read the blockers section,
before making any file changes. Explain that fix dependencies exist and the execution
order at the bottom of the file is mandatory.
 
**OBJECTIVE**
One clear success criterion statement. Always ends with the final checkpoint command
from SPRINT_FIX.md and the expected result (e.g., "N tests pass, 0 failures").
 
**EXECUTION RULES**
Hard rules for how the agent must behave. Always include:
1. Work file-by-file; never rewrite files not touched by a fix
2. Use provided fix code verbatim during the bug-fix sprint; don't "improve" it
3. Complete each Group's checkpoint before proceeding to the next Group
4. SPRINT_FIX.md overrides the governing spec where they conflict; call out any
   such conflicts explicitly in the SPRINT_FIX.md and reinforce them here
5. Any untracked bug discovered must be documented as `UNTRACKED-BUG: [file] — [desc] — [fix]`
   before fixing it
**ENVIRONMENT CHECK** (when environment issues were found in the audit)
List the exact commands to verify and fix environment problems, in order.
Mark which are blocking (must fix before continuing) vs. advisory (note and continue).
 
**CHECKPOINT COMMANDS**
List every checkpoint command from SPRINT_FIX.md verbatim, labeled by Group.
The agent copies these exactly — no interpretation.
 
**WHEN AMBIGUITY ARISES**
A decision tree for common failure modes discovered during the audit. Each entry:
`- [symptom] → [diagnosis] → [resolution]`
This replaces the need for the agent to interrupt and ask questions.
 
**DELIVERABLE**
What the agent produces at the end of the sprint. Always includes:
- List of every file modified, created, or deleted
- Any UNTRACKED-BUG entries discovered
- Final pytest/test result (N passed, 0 failed)
- Explicit list of anything deferred or requiring human decision
### 2.2 — Implementation Variant
 
When the user requests an initiation prompt for **implementing** services (not just
fixing bugs) — i.e., the stubs need to become real code — the prompt must also include:
 
**IMPLEMENTATION ORDER**
Maps to the spec's "Agent Execution Order" section. Restates each step with its
specific success test (how the agent knows the step is done before moving to the next).
 
**HARD RULES** (implementation-specific additions)
- Pin critical tool versions; never let the package manager float them
- Subprocess must never be called on the GUI thread
- All stdout from external processes goes through `strip_ansi()` before any regex
- Named functions/classes from the spec must match exactly — other modules depend on them
**GREY AREAS** (when the spec acknowledges uncertainty)
List the spec's grey areas and the recommended resolution for each, so the agent
doesn't halt on them.
 
---
 
## DELIVERABLES CHECKLIST
 
Before presenting output to the user, verify:
 
- [ ] SPRINT_FIX.md has been created as a file (use `create_file` tool), not just
      printed inline. It should be available for download.
- [ ] Every bug entry has both "What's wrong" and "Fix" sections with concrete code
- [ ] No fix says "refactor" or "improve" without providing the exact replacement
- [ ] Execution groups are sequenced so no group's fix depends on a later group's fix
- [ ] Every group has a checkpoint command that will actually pass when applied correctly
- [ ] The initiation prompt is a single fenced code block, ready to paste
- [ ] The initiation prompt's "When Ambiguity Arises" section addresses at least 3
      failure modes specific to this codebase (not generic advice)
- [ ] Known Stubs section is present and honest about what is deferred
---
 
## ANTI-PATTERNS TO AVOID
 
**Don't write vague fixes.** "Fix the enum mismatch" is not a fix. Provide the exact
corrected enum values.
 
**Don't moralize about architecture in bug entries.** The bug entry is for fixing, not
for expressing opinions. Architectural opinions belong in the governing spec.
 
**Don't over-scope the sprint.** If a fix requires implementing a new service from
scratch, it belongs in the spec's roadmap, not in SPRINT_FIX.md. SPRINT_FIX.md
is for making what exists correct, not for building what doesn't exist.
 
**Don't merge passes.** A blocker found during Pass 3 still gets promoted to Pass 1.
But don't skip a pass because "nothing came up" — run all five, document the scan,
and write "Pass N: no issues found" if that's the result.
 
**Don't omit the Known Stubs section.** Without it, the agent will attempt to implement
stubs, go out of scope, and return a broken sprint.
 
**Don't make the agent initiation prompt conversational.** It is a work order, not a
discussion. Declarative sentences only. No "please" or "you might want to."
 
---
 
## REFERENCE: Severity Tag Definitions
 
| Tag | Meaning | Agent behavior |
|-----|---------|----------------|
| `[BLOCKER]` | Prevents compile, import, or test execution | Fix in Group 1, always |
| `[HIGH]` | Test or runtime failure when stub is implemented | Fix before any stub work |
| `[MEDIUM]` | Silent corruption, latent crash, or wrong behavior under specific conditions | Fix before feature work |
| `[IMPROVEMENT]` | Proactive quality fix; small, high-leverage, clearly scoped | Apply after all bugs fixed |
 
---
 
## REFERENCE: Common Bug Patterns by Stack
 
### Python + SQLAlchemy + Alembic
- Enum values (lowercase in model) vs. DDL strings (uppercase in migration)
- `create_all()` bypasses Alembic version stamp → `upgrade head` fails on existing DB
- `downgrade()` calls named enum `.drop()` on SQLite (not supported)
- Engine created at module import time → pollutes test isolation
- `alembic.ini` URL hardcoded to `sqlite:///name.db` (CWD-relative)
### Python + subprocess
- Bare tool name (`["spotdl", ...]`) fails when venv Scripts dir not on PATH (Windows)
- ANSI escape codes from `rich`/`click` break regex on stdout
- `stderr` not merged → errors silently dropped; add `stderr=subprocess.STDOUT`
- No `PYTHONUNBUFFERED=1` → buffered output makes progress parsing laggy/impossible
- No encoding fallback (`errors='replace'`) → crash on non-UTF-8 filenames
### Python + PySide6 / PyQt6
- PyQt6 and PySide6 installed in same env → import ambiguity and Qt DLL conflicts
- Blocking call on GUI thread (subprocess.run, heavy scan) → UI freeze
- Worker signals connected with `Qt.DirectConnection` across threads → crash
- `QApplication` instantiated before `import PySide6` check → confusing error message
### pytest
- `conftest.py` missing shared fixtures or utility functions used by 3+ test files
- `pytest.ini` and `pyproject.toml [tool.pytest.ini_options]` both present → one ignored
- `monkeypatch.setattr("library.Symbol")` when module did `from library import Symbol`
  → patch doesn't affect already-imported binding
- `type("Stub", (), {...})()` objects missing fields that implementation accesses
- Integration tests without `@pytest.mark.skipif` guard → fail in CI with no credentials