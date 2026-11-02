## Context

- `.claude/rules/git-workflow.md` has `trigger: model_decision` and loads when a
  commit message or PR is being written. §1 covers commit message format and says
  nothing about attribution.
- `.claude/` has `settings.local.json` (personal, not committed) and no committed
  `settings.json`, so there are no project-wide hooks yet.
- The remote is Azure DevOps, so PRs are opened with `az repos pr create` or in the
  web UI. `gh pr create` is included only in case someone uses GitHub tooling.
- `python3` is available on the host; `jq` is not assumed. The host `python3`
  can be as old as 3.8 (found during apply), so the hook uses
  `from __future__ import annotations` and nothing newer than 3.8 at runtime.

## Goals / Non-Goals

**Goals:**
- Claude Code stops adding attribution to commits and PRs in this repo, and is
  stopped and told what to fix if it tries.
- No false positives on ordinary messages that mention `.claude/` paths or the
  word "Claude" in context (for example, a commit that edits `.claude/rules/`).

**Non-Goals:**
- Rewriting existing history to strip old trailers.
- A git `commit-msg` hook. Git hooks live in `.git/hooks`, which is not committed,
  so it would only protect one machine.
- Catching manual commits or PRs created in the web UI. The written rule covers
  those.

## Decisions

1. **The rule goes in `git-workflow.md` as a new paragraph in §1 "Commit
   Messages", applying to PR titles and descriptions as well.** That file already
   loads when commits and PRs are written. The rule states that it overrides any
   default attribution the tool adds, because the attribution text comes from
   Claude Code's own defaults, not from this repo.

2. **Enforcement is a `PreToolUse` hook on `Bash`, in a committed
   `.claude/settings.json`.** The hook runs
   `python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/check_commit_attribution.py`, which:
   - reads the hook JSON from stdin and takes `tool_input.command`;
   - does nothing (exit 0) unless the command contains `git commit`,
     `gh pr create`, or `az repos pr create`;
   - scans the command text, plus any file named by `-F`/`--file`/`--body-file`,
     for attribution markers;
   - on a match, exits 2 and writes a message to stderr naming the matched line and
     saying to remove it. Exit code 2 blocks the call and returns stderr to Claude.

   *Considered:* putting the hook in `settings.local.json`. Rejected, because that
   file isn't committed, so teammates wouldn't get it.
   *Considered:* a shell script with `grep`. Rejected, because parsing the hook JSON
   without `jq` is fragile; Python's `json` module handles it.

3. **Markers are attribution patterns, not the bare word "Claude".** Matching is
   case-insensitive:
   - `Co-Authored-By:` lines that name `claude` or `anthropic`;
   - `noreply@anthropic.com`;
   - `Generated with/by [Claude …` (with or without the markdown link);
   - the 🤖 emoji;
   - `(written|generated|authored|created) (by|with) (claude|an? AI)`, and
     `AI-generated` / `AI-assisted`.

   A bare `claude` would block every commit that touches `.claude/`, including the
   commit for this change.

## Risks / Trade-offs

- [An attribution phrasing the patterns don't cover gets through] → The written
  rule still applies, and the pattern list sits in one function that is easy to
  extend.
- [A legitimate message trips a pattern, e.g. a commit about the 🤖 emoji] → The
  hook's message names the matched line. A developer committing by hand isn't
  affected, because the hook only runs on Claude Code's tool calls.
- [The hook blocks a message passed through a temp file it can't read] → If a named
  file can't be read, the hook scans only the command text and does not block.
