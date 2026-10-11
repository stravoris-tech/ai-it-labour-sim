---
description: Execute a slice prompt under this repo's cadence (Python gate, ship report, HOLD)
argument-hint: <prompt-file-under-temp/prompts/>
---

Read the slice prompt at `temp/prompts/$ARGUMENTS` (bare names resolve under `temp/prompts/`). If it does not exist, STOP and say so. Do not reconstruct a slice from memory or conversation.

Execute it under the cadence in CLAUDE.md. The cadence applies even where the prompt does not restate it:

- **The prompt file is the procedure of record.** Follow it exactly. Its prohibitions ("only", "never", "do not", "nothing else") rank equal with its steps.
- **Branch.** Work on the feature branch the prompt names. If you are not on it, STOP.
- **Minor decisions** the prompt did not anticipate: take them and report each as a D-ruling with its reason. Anything above minor: STOP and ask rather than improvise.
- **Gates are scripts that propagate exit codes.** A verdict is an exit code, never printed text.
- **Absence claims need a positive control.** A sweep that reports zero hits must first show it can detect a planted instance.
- **`reference/` is read-only** unless the prompt says otherwise. Goldens are regenerated only when the prompt says so.
- **Every slice exits through the full gate** unless the prompt says otherwise: `uv run python scripts/gate.py` exits 0. State the test count before (on `main`) and after.
- **Friction log.** Anything that fought you (a tool, a standard, a command, the prompt) is a logged finding, not smoothed over.
- **Hyphens only.** Never U+2014 or U+2013.

Write the ship report to `temp/outputs/<slice-name>-ship-report.md`. The slice name is the prompt file name without `.md` and without a trailing `-build`. The report has:

- a summary
- every instruction with its evidence (a command with its exit code, or a file and line)
- the D-rulings
- the gate table and test counts
- the CI run URL and conclusion
- the friction log
- open questions

Summarise the report in chat.

Then:

1. Commit as the prompt instructs, with a conventional commit subject under 72 characters.
2. Push the branch.
3. Wait for its CI run and record the result.
4. **HOLD:** no PR and no merge, however green everything is.

The conformance check (`/verify-slice` in a fresh session) and the operator's ship decision come next.
