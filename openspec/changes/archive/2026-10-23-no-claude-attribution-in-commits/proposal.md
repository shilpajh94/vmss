## Why

Commits made through Claude Code end with a `Co-Authored-By: Claude … <noreply@anthropic.com>`
trailer. PR descriptions it writes end with a "🤖 Generated with Claude Code" footer.
Recent history on this repo already carries these trailers. The team wants commit
messages and PR descriptions to describe the change only, with no Claude or AI
attribution.

## What Changes

- Add a rule to `.claude/rules/git-workflow.md`: commit messages, PR titles, and PR
  descriptions must not contain Claude or AI attribution. That covers
  `Co-Authored-By` trailers naming Claude or `anthropic.com`, "Generated with
  Claude Code" footers, the 🤖 marker, and wording such as "written by Claude" or
  "AI-generated". The rule says it overrides any default attribution the tool would
  otherwise add.
- Add a Claude Code `PreToolUse` hook, registered in a committed
  `.claude/settings.json`. It blocks a `git commit`, `gh pr create`, or
  `az repos pr create` command whose message or description contains those markers,
  and tells Claude what to remove.
- Existing commits are left as they are. History is not rewritten.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

_None._ This changes the developer workflow and tooling only; no product behavior
changes, so the change sets `skip_specs: true`.

## Impact

- **New files**: `.claude/settings.json`, `.claude/hooks/check_commit_attribution.py`.
- **Edited files**: `.claude/rules/git-workflow.md`.
- **Scope of enforcement**: the hook only sees commands Claude Code runs. Commits
  made by hand, and PRs created in the Azure DevOps web UI, are covered by the
  written rule only.
- **Out of scope**: VMMS_WEB. This change can only edit VMSS_API; the same rule and
  hook can be copied there in a follow-up.
- No application code, API, database, or CI changes.
