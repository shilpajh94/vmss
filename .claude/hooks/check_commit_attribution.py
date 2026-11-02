"""PreToolUse hook: block Claude/AI attribution in commit messages and PR descriptions.

Enforces `.claude/rules/git-workflow.md` §1. Exit 2 blocks the Bash call and
returns stderr to Claude; exit 0 lets it through. Runs on the host `python3`
(3.8 on some dev machines), not the project's uv-managed 3.13.
"""

from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path

_COMMANDS = re.compile(r"\bgit\s+commit\b|\bgh\s+pr\s+create\b|\baz\s+repos\s+pr\s+create\b")

# Attribution patterns only — a bare "claude" would block every commit touching `.claude/`.
_MARKERS = [
    re.compile(r"co-authored-by:.*(claude|anthropic)", re.IGNORECASE),
    re.compile(r"noreply@anthropic\.com", re.IGNORECASE),
    re.compile(r"generated\s+(with|by)\s+\[?claude", re.IGNORECASE),
    re.compile("\U0001f916"),
    re.compile(
        r"\b(written|generated|authored|created)\s+(by|with)\s+(claude|an?\s+ai)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bai[-\s](generated|assisted)\b", re.IGNORECASE),
]

_FILE_FLAGS = ("-F", "--file", "--body-file")


def _message_files(command: str, cwd: Path) -> list[Path]:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return []
    files: list[Path] = []
    for i, token in enumerate(tokens):
        value: str | None = None
        if token in _FILE_FLAGS and i + 1 < len(tokens):
            value = tokens[i + 1]
        else:
            for flag in ("--file=", "--body-file="):
                if token.startswith(flag):
                    value = token[len(flag) :]
        if value and value != "-":
            path = Path(value)
            files.append(path if path.is_absolute() else cwd / path)
    return files


def _find_marker(text: str) -> str | None:
    for line in text.splitlines():
        if any(marker.search(line) for marker in _MARKERS):
            return line.strip()
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not _COMMANDS.search(command):
        return 0

    texts = [command]
    cwd = Path(payload.get("cwd") or ".")
    for path in _message_files(command, cwd):
        try:
            texts.append(path.read_text(encoding="utf-8"))
        except OSError:
            continue  # unreadable message file: scan the command text only

    for text in texts:
        hit = _find_marker(text)
        if hit:
            print(
                "Blocked: Claude/AI attribution is not allowed in commit messages or PR "
                f"descriptions (.claude/rules/git-workflow.md §1). Remove this line: {hit!r}",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
