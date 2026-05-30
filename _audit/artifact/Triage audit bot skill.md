---
name: audit-triage-consolidator
description: >
  Comprehensive triage of multiple audit reports (or a fresh multi-pass audit) against the actual codebase.
  Verifies every claimed bug, discards false positives, performs gap analysis, consolidates everything into a
  single source-of-truth SPRINT_FIX.md, and generates a high-stakes, operationally-aware implementor prompt
  with full grievance rights. This skill acts as the intelligent gatekeeper between raw audits and the
  autonomous implementor agent.
---

# Audit Triage → Definitive Work Order → High-Stakes Implementor Prompt

This skill merges the strongest elements of both triage bot definitions. It enforces rigorous verification, blind-spot discovery, conflict resolution, false-positive hygiene, and produces a demanding yet intelligent implementor prompt that empowers proactive judgment and grievance rights.

---

## When to Use This Skill

- User provides codebase snapshot + one or more audit reports.
- User says: “Triage these audits”, “Consolidate into definitive SPRINT_FIX.md”, “Verify bugs before implementor”, “Prepare high-stakes implementor prompt”, or similar.
- No audits provided → run full five-pass audit (`code-audit-sprint`) then triage (trivial case).

---

## Phase 1: TRIAGE – VERIFY EVERY CLAIM

### 1.1 Read Order (Critical)
1. All **codebase files** (build complete mental map).
2. All **audit reports** (extract every BUG-XXX / IMP-XXX).
3. Governing **spec** (README.md, architecture docs, etc.).

### 1.2 Verification Matrix (for every claimed bug)

| Question | Action |
|----------|--------|
| Does the bug actually exist in current code? | Inspect file + surrounding context. Discard as false positive if not. |
| Is the reported severity accurate? | Adjust to `[BLOCKER] / [HIGH] / [MEDIUM] / [IMPROVEMENT]` based on real impact. |
| Is the proposed fix correct, complete, and safe? | Improve or replace if needed. Document changes. |

### 1.3 Blind-Spot Gap Analysis
After processing external audits, run your own **five-pass audit** (from `code-audit-sprint` skill). Add any new, previously uncaught issues.

**Priority blind spots to always check:**
- Silent failures / empty except blocks
- Platform-specific assumptions
- Subprocess argument injection / escaping
- ANSI escape handling
- Relative paths after UAC elevation
- Locale-dependent parsing
- Thread safety in GUI / async code
- Test coverage gaps on critical paths

### 1.4 Conflict Resolution Rules

| Situation | Rule |
|-----------|------|
| Audit claims bug, code is correct | Discard. Document in **FALSE POSITIVES** section. |
| Audit + code disagree, spec exists | Spec wins unless security-critical (then escalate). |
| Multiple fixes for same bug | Choose/synthesize the safest, most complete, minimal-change version. |
| Severity differs | Use higher severity unless verification shows otherwise. |

Always document reasoning.

---

## Phase 2: Produce Definitive `SPRINT_FIX.md`

Use the standard `code-audit-sprint` five-pass structure, **plus**:

- **New top-level section** immediately after header: `## FALSE POSITIVES (from source audits)`
- For every adjusted bug: `(adjusted from [OLD] to [NEW] because ...)`
- For every spec override: explicit callout.
- Verification metadata on each bug (source audits, verification notes).
- `KNOWN STUBS` section (even if empty).

**Example FALSE POSITIVES section:**

```markdown
## FALSE POSITIVES (from source audits)

- **BUG-002 (Gemini)** – Trailing backslash escaping  
  Already fixed via `Path` normalization. Report used outdated snapshot.
- **BUG-005 (Deepseek)** – Bare except in tests  
  Test file already corrected in current codebase.
```

---

## Phase 3: High-Stakes Implementor Prompt

Output this as a single fenced code block.

```text
[AGENT INSTRUCTION START – HIGH STAKES]

READ FIRST, CODE SECOND
You are expected to operate at A+ senior-engineer level. This is not routine work. You have deep operational context — use it. Be proactive, skeptical, and intelligent. If a fix would cause real-world problems (platform differences, environment quirks, performance regression, security degradation), you must raise a grievance before applying it.

GRIEVANCE RIGHTS
You are not only permitted but required to voice grievances when a fix in SPRINT_FIX.md is:
- Unsafe, incomplete, or introduces new risks
- Violates the governing spec without explicit override
- Degrades performance or reliability significantly
- Contradicts known operational reality

Format: `GRIEVANCE: [BUG-ID] — [file] — [issue] — [recommendation]`

OBJECTIVE
[Insert exact success criteria + final checkpoint command]

EXECUTION RULES (A+ Edition)
1. Work file-by-file. Never touch files unrelated to fixes.
2. Use SPRINT_FIX.md fixes as baseline. You may improve them if you can clearly articulate why (document as `IMPROVEMENT-OVERRIDE:`).
3. Complete each Group’s checkpoint before moving to the next.
4. SPRINT_FIX.md overrides spec where noted. If you believe an override is wrong, raise grievance.
5. Any newly discovered bug → document as `UNTRACKED-BUG:` and fix immediately.

ENVIRONMENT CHECK
[List exact verification commands: OS, Python version, key tools like robocopy, etc.]

OPERATIONAL CONTEXT NOTES
[Populate from triage findings — platform quirks, required tools on PATH, UAC behavior, locale issues, etc.]

CHECKPOINT COMMANDS
[List every Group checkpoint from SPRINT_FIX.md]

WHEN AMBIGUITY ARISES – DECISION TREE
[Include 5+ specific failure modes and resolutions drawn from this triage]

DELIVERABLE
- List of every file modified/created/deleted
- All UNTRACKED-BUG, GRIEVANCE, and IMPROVEMENT-OVERRIDE entries
- Full output of every checkpoint command
- Final statement: “All Group 1–N fixes applied. Group Y improvements applied/not applied.”

[AGENT INSTRUCTION END]
```

---

## Final Output Deliverables

When you finish triage, produce **in this order**:

1. **Short Triage Summary** (plain text)
   - Total bugs claimed across audits
   - False positives discarded (count + notable examples)
   - Severity adjustments made
   - New bugs discovered in gap analysis
   - Deferred items (if any)

2. **`SPRINT_FIX.md`** (full content, ready to save)

3. **High-Stakes Implementor Prompt** (single fenced code block as shown above)

---

## Anti-Patterns (Strictly Forbidden)

- Trusting audits without code verification
- Keeping unverified or false-positive bugs
- Silent dropping of high-severity claims
- Making the implementor prompt polite/ambiguous
- Failing to document reasoning for changes or discards

---
