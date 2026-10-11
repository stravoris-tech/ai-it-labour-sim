---
description: Read-only reconnaissance from a prompt file; writes a report under temp/outputs/
argument-hint: <prompt-file-under-temp/prompts/>
---

Read the recon prompt at `temp/prompts/$ARGUMENTS` (a bare name resolves under `temp/prompts/`). If it does not exist, STOP and say so. Do not reconstruct a recon from memory or conversation.

These rules apply even where the prompt does not restate them:

- **Read-only.** Do not modify, add, stage, commit or push any tracked file, and do not switch branches.
- **Write only under `temp/`.** Run any code you need in `temp/scratch/`. Copy anything from `reference/` there before running it.
- **No global installs.** Use `uv run`, with `--with <package>` for one-off packages, and note what was needed.
- **Exit codes, not output.** A check's verdict is its exit code, never its printed text. State exit codes.
- **Facts, not plans.** Do not fix anything you find broken; record it.
- **Hyphens only.** Never U+2014 or U+2013.

Write the report to `temp/outputs/` under the same file name as the prompt. Give it one section per question in the prompt and a short summary at the top. Then summarise it in chat.
