---
description: Independent conformance check of a held slice against its prompt (run in a FRESH session that did not do the work)
argument-hint: <prompt-file-under-temp/prompts/> <held-branch>
---

Parse two arguments from `$ARGUMENTS`: the slice prompt file (bare names resolve under `temp/prompts/`) and the held branch. If either is missing or does not exist, STOP and say so. The current branch must be the held branch, so that the gate runs on its code. If it is not, STOP and tell the operator to switch.

You are the conformance reviewer. You did not do this work and you do not defend it. If this session has prior context about executing this slice, STOP and tell the operator to run this command in a fresh session. Independence is the mechanism: a doer re-reading its own work re-reads its own misreadings.

## Procedure

1. **Build the checklist.** Read the slice prompt in full and extract every instruction: numbered steps, requirements embedded in prose, and every prohibition ("only", "never", "do not", "nothing else"). List them as a checklist with source references. Prohibitions rank equal with steps.
2. **Read the artifact, not the testimony.** Use `git diff main...<branch>` for content, `git log main..<branch>` for commit claims, and the committed files directly where the diff lacks context. Do not read the ship report yet.
3. **Walk the checklist.** Give each instruction one verdict:
   - **CONFORMS**, with quoted evidence: a diff hunk, a file line, or a command you re-ran with its exit code.
   - **DEVIATES**, quoting both the requirement and the artifact. Class it as a judgment call the prompt delegated, or as a violation.
   - **UNVERIFIABLE FROM THE ARTIFACT**, naming the evidence that would settle it.
4. **Re-run the mechanical claims yourself.** Run:
   - `uv sync --locked`
   - `uv run python scripts/gate.py` (record its exit code and test count)
   - any slow tests or scripts the prompt names
   - `gh run list --branch <branch>` for the branch's CI result

   Read exit codes, never output text. Where a check asserts an absence, confirm that its positive control exists and ran. Without one, the claim is UNVERIFIABLE, not CONFORMS.
5. **Compare with the ship report.** Now read `temp/outputs/<slice-name>-ship-report.md` and diff it against your findings in both directions: claims the artifact does not show, and artifact content the report omits.
6. **Write the result.** Write the full output to `temp/outputs/<slice-name>-conformance.md` and summarise it in chat:
   - the checklist with verdicts
   - the deviation table (an empty table is a finding worth stating)
   - the discrepancies between report and artifact
   - one closing line: **"ship-safe"**, or **"hold for rulings"** with the items that need the operator

Rules:

- **Strictly read-only outside `temp/`.** Change nothing tracked, commit nothing, fix nothing, not even trivia. A checker that edits stops being a checker. Running `uv sync` and writing gate output under `temp/` are allowed.
- **Quote, never paraphrase,** when citing the prompt or the diff.
- **Deviations are the operator's rulings,** not your fixes.
- **Hyphens only.** Never U+2014 or U+2013.
