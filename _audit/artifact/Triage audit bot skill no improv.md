```markdown
---
name: audit-triage-consolidator
description: >
  Extension of code-audit-sprint for multi-agent audit workflows. Takes N audit reports
  produced by running code-audit-sprint across multiple agents, verifies every claim
  against the actual codebase, discards false positives with documented reasoning,
  runs a gap analysis pass for issues missed by all agents, resolves cross-agent conflicts,
  and produces a single source-of-truth SPRINT_FIX.md plus a high-stakes implementor prompt
  with grievance rights. Acts as the intelligent gatekeeper between raw parallel audits
  and the autonomous implementor agent.
  Triggers: "triage these audits", "consolidate audit reports", "verify bugs before implementor",
  "prepare high-stakes implementor prompt", "merge sprint fix files", or whenever the user
  provides multiple SPRINT_FIX.md files or audit reports alongside a codebase.
---

# Audit Triage → Verified Work Order → High-Stakes Implementor Prompt

This skill is an extension of `code-audit-sprint`. It assumes that skill's four-pass
audit methodology, SPRINT_FIX.md format, and severity taxonomy are already understood.
It adds a triage layer between parallel multi-agent audits and the implementor agent —
the layer responsible for truth, de-duplication, and operational context.

---

## WHEN TO USE THIS SKILL

- User provides codebase + one or more audit reports / SPRINT_FIX.md files from different agents.
- User asks to triage, consolidate, verify, or merge audit outputs before handing off to an implementor.
- No audits provided → run `code-audit-sprint` first, then triage (trivial case; skip to Phase 2).

---

## INPUT MODEL

Before doing anything, identify and label your inputs:

```
CODEBASE        — The actual source files (snapshot, upload, or live files). Source of truth.
SPEC            — Governing architecture/spec doc, if present. Second source of truth.
AUDIT-[AGENT]   — Each audit report, labeled by agent identity. e.g., AUDIT-A, AUDIT-B, AUDIT-C.
```

If audits are unlabeled, assign labels yourself (AUDIT-A, AUDIT-B, ...) in the order received.
Track source attribution (which AUDIT label a bug came from) on every claim throughout triage.

---

## PHASE 1: TRIAGE

### 1.1 — Read Order (Non-Negotiable)

1. **CODEBASE** — Build a complete mental map before reading any audit. You are looking
   for the truth. Audits are hypotheses about the codebase, not facts.
2. **SPEC** — Internalize what the intended behavior is. Divergence from spec is a bug
   only if the spec is authoritative. Note any cases where the code is verifiably better.
3. **All AUDIT-[AGENT] reports** — Extract every claim (BUG-XXX) into a
   working list tagged by source. Do not discard or merge yet.

### 1.2 — Claim Registry

After reading all inputs, produce an internal working table (not shown to user) tracking:

```
Claim ID | Source AUDIT(s) | Severity claimed | File | Description | Verification status
```

This is your working surface. Every downstream decision traces back to it.

### 1.3 — Verification Protocol (Every Claim)

For each claim in the registry, answer these questions in order. Stop at the first
definitive answer.

**Q1: Does the alleged bug exist in the current codebase?**
- Inspect the exact file and surrounding context (minimum ±20 lines).
- If not found → **FALSE POSITIVE**. Document with specific code evidence. Do not carry forward.
- If found → continue to Q2.

**Q2: Is the severity classification accurate?**
- Compare claimed severity against the `code-audit-sprint` severity taxonomy:
  `[BLOCKER]` / `[HIGH]` / `[MEDIUM]`
- Adjust if needed. Document: `(adjusted from [OLD] to [NEW] — [one-line reason])`

**Q3: Is the proposed fix correct, complete, and safe?**
- Verify fix logic against codebase context.
- Check: does the fix introduce new bugs? Does it break adjacent code? Is it minimal?
- Improve or replace if needed. Document: `(fix revised — [one-line reason])`

**Q4: Does this claim overlap with another verified claim?**
- If yes: merge into the higher-severity claim. Document both source IDs on the merged entry.
- If no: carry forward as a standalone verified bug.

### 1.4 — False Positive Classification Tiers

Not all false positives are equal. Classify each one:

| Tier | Condition | Handling |
|------|-----------|----------|
| **Stale** | Bug existed in a prior snapshot; already fixed in current codebase | Document with file + line evidence |
| **Misread** | Auditor misread the code; behavior is correct as written | Document with explanation of actual behavior |
| **Scope error** | Issue is real but outside this codebase (dependency, OS, env) | Document and flag as an environment note |
| **Spec conflict** | Auditor applied wrong spec version or wrong authority | Document which spec section governs |

### 1.5 — Blocker False Positive Escalation

If a claimed `[BLOCKER]` is determined to be a false positive, do **not** silently discard it.

Required actions:
1. Document it in the FALSE POSITIVES section with tier classification.
2. Add a one-sentence note at the top of the consolidated SPRINT_FIX.md:
   `> ⚠ ESCALATION NOTE: [AUDIT-X BUG-NNN] was claimed BLOCKER but discarded as [tier] — [reason]. Verify manually before first run.`
3. This ensures the implementor agent sees it and can confirm, not just trust the triage.

### 1.6 — Cross-Agent Conflict Resolution

When two or more audits make different claims about the same code:

| Conflict type | Resolution rule |
|---------------|-----------------|
| Same bug, different severity | Use higher severity. Document both claims. |
| Same bug, different fix proposals | Choose safest, most minimal, most complete fix. Synthesize if both have partial value. Document rejected fix with reason. |
| Audit A flags it as bug, Audit B flags it as correct | Verify in codebase. Codebase wins. Document which audit was correct. |
| Audits agree but spec disagrees | Spec wins unless security-critical (escalate to human). |
| All sources conflict, no clear answer | Mark `[NEEDS-HUMAN]`, include all candidate fixes, defer. |

### 1.7 — Gap Analysis Pass

After processing all external audits, run one **gap analysis pass** over the codebase.

Scope: issues that zero audits caught. Do not re-examine already-verified claims.

Always scan the `code-audit-sprint` blindspot checklist:
- Silent failures / empty except blocks
- Platform-specific assumptions (OS path separators, encoding, shell behavior)
- Subprocess argument injection / escaping
- ANSI escape handling in stdout parsers
- Relative path failures after UAC elevation or CWD change
- Locale-dependent parsing (`float()`, date formats, collation)
- Thread safety in GUI / async code
- Test coverage gaps on critical paths
- Lazy vs. eager initialization at module import
- Missing `__init__.py` in packages
- Alembic + `create_all()` coexistence (version table not stamped)

Label all gap-found bugs with source: `GAP-ANALYSIS` to distinguish them from externally-reported claims.

### 1.8 — Confidence Tier Tagging

Every surviving bug in the consolidated output receives a confidence tag:

| Tag | Meaning |
|-----|---------|
| `[VERIFIED]` | Directly confirmed in codebase — exact file, line, code read |
| `[INFERRED]` | Logically follows from verified code patterns; not line-confirmed |
| `[DEFERRED]` | Real risk but unverifiable without runtime execution or env access |

The implementor agent must treat `[INFERRED]` and `[DEFERRED]` claims differently from
`[VERIFIED]` ones — with more skepticism and a lighter touch.

---

## PHASE 2: CONSOLIDATED SPRINT_FIX.md

Use the exact SPRINT_FIX.md format from `code-audit-sprint`. Extend it with these additions:

### 2.1 — Additional Header Fields

```markdown
# SPRINT_FIX.md — [Project Name] (Consolidated)
**Audit Date:** [date]
**Triage Method:** Multi-agent consolidation (N source audits)
**Source Audits:** AUDIT-A ([agent/tool name]), AUDIT-B ([agent/tool name]), ...
**Auditor:** Triage Consolidator
**Target:** Autonomous Agent Implementation Sprint
**Base Ref:** [governing spec filename]
```

### 2.2 — FALSE POSITIVES Section

Insert this section immediately after the header, before PASS 1. Even if empty, include it.

```markdown
## FALSE POSITIVES (Discarded Claims)

| Claim | Source | Tier | Evidence |
|-------|--------|------|----------|
| [AUDIT-A BUG-002] Trailing backslash escaping | AUDIT-A | Stale | `path.py:47` uses `Path()` normalization — already handles this |
| [AUDIT-B BUG-005] Bare except in tests | AUDIT-B | Stale | `test_runner.py:31` corrected in current snapshot |
| [AUDIT-A BUG-009] Thread safety on signal | AUDIT-A | Misread | Slot runs on GUI thread; connection is `Qt.QueuedConnection` at line 84 |
```

If no false positives: `*No false positives found. All claimed bugs verified.*`

### 2.3 — Per-Bug Triage Metadata

Add a **Source & Confidence** line to every bug entry:

```markdown
### BUG-007 [HIGH] — Monkeypatch targets wrong namespace
**File:** `tests/test_downloader.py:34`
**Source:** AUDIT-A BUG-003, AUDIT-B BUG-007 (merged — same root cause)
**Confidence:** [VERIFIED] — confirmed at `test_downloader.py:34`, wrong namespace `library.Symbol`
**What's wrong:** ...
**Fix:** ...
```

For gap-analysis bugs:
```markdown
**Source:** GAP-ANALYSIS (not reported by any source audit)
**Confidence:** [VERIFIED] — confirmed at `config.py:12`
```

### 2.4 — EXECUTION ORDER Extension

In the Execution Order section, add a pre-flight block:

```markdown
## EXECUTION ORDER FOR AGENT

### ⚠ PRE-FLIGHT: Triage Escalations
[List any BLOCKER false positives that were escalated for human verification]
[List any [NEEDS-HUMAN] items with their candidate fixes]
[If none: *No escalations. Proceed directly to Group 1.*]

**Group 1 — ...**
...
```

### 2.5 — TRIAGE INTEL Section

Add this section at the end of SPRINT_FIX.md, after KNOWN STUBS:

```markdown
## TRIAGE INTEL (Operational Notes for Implementor)

**Cross-agent conflicts resolved:**
- [BUG-ID]: AUDIT-A proposed X, AUDIT-B proposed Y — chose Y because [reason]

**Spec overrides:**
- [BUG-ID]: Fix diverges from §X.Y of spec — [reason for override]

**Environment signals (from codebase + audits):**
- [Any platform, OS, encoding, tool-path, or runtime signals that affect implementation]

**Deferred items:**
- [BUG-ID]: Deferred because [reason]. Human decision required: [question].
```

---

## PHASE 3: HIGH-STAKES IMPLEMENTOR PROMPT

Output as a single fenced code block, ready to paste.

```text
[AGENT INSTRUCTION START — HIGH STAKES CONSOLIDATED SPRINT]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
READ FIRST, CODE SECOND
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You are operating at senior engineer level on a verified, triaged work order.
This SPRINT_FIX.md was produced by a triage consolidator that verified every claim
against the actual codebase, discarded false positives, and resolved cross-agent
conflicts. The work order is high-confidence but not infallible.

Read SPRINT_FIX.md in full before making any file change.
Re-read the PRE-FLIGHT section and TRIAGE INTEL section before Group 1.
Treat [VERIFIED] bugs as confirmed. Treat [INFERRED] bugs with extra care —
verify before applying. Treat [DEFERRED] bugs as needing your judgment.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GRIEVANCE RIGHTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You are required (not merely permitted) to file a grievance when a fix in SPRINT_FIX.md:
- Is unsafe, incomplete, or introduces new risk
- Contradicts verified codebase behavior in a way the triage missed
- Degrades performance or reliability with no documented justification
- Conflicts with the governing spec without an explicit spec-override note

Format exactly:
  GRIEVANCE: [BUG-ID] — [file:line] — [issue] — [your recommendation]

File the grievance in your deliverable. If the fix is also clearly wrong and a safe
correction exists, apply the correction and document it as IMPROVEMENT-OVERRIDE.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OBJECTIVE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Insert exact success criterion. Always ends with: "Final checkpoint: `[command]` must return [expected result]."]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXECUTION RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Work file-by-file. Never touch files not targeted by a fix.
2. Use provided fix code verbatim for [VERIFIED] bugs. For [INFERRED] bugs, verify
   first — apply fix only after confirming the bug exists at the described location.
3. Complete each Group checkpoint before proceeding. A failing checkpoint is a stop signal.
4. SPRINT_FIX.md overrides spec where a spec-override note is present. Flag any
   spec-override in your deliverable.
5. Any newly discovered bug → document as UNTRACKED-BUG: [file:line] — [description] — [fix].
   Apply the fix immediately if it is clearly safe and scoped. Defer if uncertain.
6. [NEEDS-HUMAN] items → do not attempt. Include in your deliverable with a note.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ENVIRONMENT CHECK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Populated from TRIAGE INTEL — platform, OS, tool-path, encoding signals]
[Mark each as BLOCKING or ADVISORY]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRE-FLIGHT ESCALATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Copy from SPRINT_FIX.md PRE-FLIGHT section verbatim]
[If none: *No escalations. Proceed to Group 1.*]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CHECKPOINT COMMANDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Every Group checkpoint from SPRINT_FIX.md, verbatim, labeled by Group]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHEN AMBIGUITY ARISES — DECISION TREE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Minimum 5 entries, drawn from this specific codebase — not generic advice]
Format: [symptom] → [diagnosis] → [resolution]

Example entries generated during triage:
- "Import fails after applying BUG-001" → dependency not installed → run `pip install -e .[dev]` first
- "[INFERRED] bug not found at described line" → code was refactored → file grievance, skip fix
- "Checkpoint fails with unexpected error" → untracked bug interfering → document as UNTRACKED-BUG, fix, rerun checkpoint

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DELIVERABLE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Produce this at the end of the sprint, in this exact format:

FILES MODIFIED:    [list every file modified, created, or deleted]
SPEC OVERRIDES:    [list BUG IDs where fix diverged from spec]
GRIEVANCES:        [GRIEVANCE entries, or "None"]
IMPROVEMENT-OVERRIDES: [any fixes improved beyond SPRINT_FIX.md, or "None"]
UNTRACKED-BUGS:    [UNTRACKED-BUG entries, or "None"]
NEEDS-HUMAN:       [deferred [NEEDS-HUMAN] items, or "None"]
CHECKPOINT RESULTS:[output of every checkpoint command run]
FINAL STATUS:      "All Group 1–N fixes applied. Final checkpoint: [N] passed, 0 failed."

[AGENT INSTRUCTION END]
```

---

## FINAL OUTPUT SEQUENCE

When triage is complete, produce deliverables in this exact order:

### 1. Triage Summary (plain text, shown inline)

```
TRIAGE SUMMARY
==============
Source audits processed:   N (AUDIT-A, AUDIT-B, ...)
Total claims received:     [total across all audits]
False positives discarded: [count] — [notable example if any]
  Stale:         [count]
  Misread:       [count]
  Scope errors:  [count]
  Spec conflicts:[count]
Severity adjustments:      [count] — [highest-impact example]
Cross-agent conflicts:     [count] resolved, [count] deferred to [NEEDS-HUMAN]
Bugs merged (duplicate):   [count]
New bugs from gap analysis:[count] (GAP-ANALYSIS source)
Escalations (BLOCKER FPs): [count]

Confidence breakdown (surviving bugs):
  [VERIFIED]:  [count]
  [INFERRED]:  [count]
  [DEFERRED]:  [count]

Items requiring human decision: [count]
```

### 2. Consolidated SPRINT_FIX.md (file artifact)

Save as `SPRINT_FIX_consolidated.md` using `create_file`. Do not print inline — it's a download artifact.

### 3. High-Stakes Implementor Prompt (single fenced code block, shown inline)

---

## DELIVERABLES CHECKLIST

Before presenting any output, verify:

- [ ] Every claim was verified against codebase, not just taken from audit
- [ ] Every false positive has a tier classification and code evidence
- [ ] Every `[BLOCKER]` false positive has an escalation note in the header
- [ ] Every surviving bug has Source + Confidence tags
- [ ] Cross-agent conflicts are resolved with documented reasoning
- [ ] Gap analysis ran against `code-audit-sprint` blindspot list
- [ ] SPRINT_FIX.md follows exact `code-audit-sprint` format, plus triage extensions
- [ ] TRIAGE INTEL section is populated (not empty placeholders)
- [ ] PRE-FLIGHT section lists all escalations
- [ ] Implementor prompt's DECISION TREE has ≥5 codebase-specific entries
- [ ] Implementor prompt's ENVIRONMENT CHECK is populated from TRIAGE INTEL
- [ ] Consolidated SPRINT_FIX.md is saved as a file artifact
- [ ] Triage Summary is accurate (counts match actual work done)

---

## ANTI-PATTERNS (Strictly Forbidden)

**Trusting audits without code verification.**
An audit is a hypothesis. The codebase is the truth. Never carry a claim forward without line-level confirmation or an explicit `[INFERRED]` tag with reasoning.

**Silent false positive drops.**
Every discarded claim is documented with tier, evidence, and source attribution. Silent drops poison the audit history.

**Double-counting gap analysis.**
If a gap analysis pass finds something an audit also caught, merge it — don't add a new entry. Gap analysis contributes only net-new findings.

**Generic decision trees.**
The DECISION TREE in the implementor prompt must be derived from *this codebase's* specific triage findings. "Check your imports" is not a decision tree entry.

**Ambiguous confidence tagging.**
If you cannot find the exact line but believe the bug is real, use `[INFERRED]` and document why. Never use `[VERIFIED]` without a file and line citation.

**Making the implementor prompt soft.**
No hedging, no politeness, no passive voice. The implementor prompt is a work order. Declarative sentences only.

**Omitting TRIAGE INTEL.**
The implementor agent needs operational context (platform signals, conflict resolution outcomes, spec overrides). If TRIAGE INTEL is empty, the triage was incomplete.

---

## RELATIONSHIP TO code-audit-sprint

This skill extends `code-audit-sprint`. It does not replace it.

| `code-audit-sprint` | `audit-triage-consolidator` |
|---------------------|---------------------------|
| Runs on one codebase, no prior audits | Runs on N audits already produced |
| Produces first-pass SPRINT_FIX.md | Produces verified, consolidated SPRINT_FIX.md |
| Agent is the sole auditor | Agent is gatekeeper between multiple auditors and implementor |
| No false positive handling needed | False positive triage is core function |
| No cross-agent conflict resolution | Conflict resolution is mandatory |
| Gap analysis = the four passes | Gap analysis = incremental pass on top of external audits |
| Standard implementor prompt | High-stakes prompt with grievance rights + confidence tiers |
```