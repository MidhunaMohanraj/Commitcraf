"""AI-assisted commit message generation.

Sends the staged diff to Claude and asks for a single Conventional Commit
message. Falls back to the offline heuristic generator (heuristics.py) if
no API key is configured, the `anthropic` package isn't installed, or the
request fails for any reason — commitcraft should never block a commit
because a network call didn't work.
"""

from __future__ import annotations

import os

from commitcraft.gitutil import StagedChange
from commitcraft.heuristics import CommitMessage, generate_offline

MAX_DIFF_CHARS = 12000  # keep the prompt bounded for very large diffs

SYSTEM_PROMPT = (
    "You write Conventional Commit messages from git diffs. "
    "Reply with ONLY the commit message, nothing else — no preamble, "
    "no markdown fences. Format: '<type>(<scope>): <summary>' as the "
    "first line (scope is optional, omit its parens if there isn't one), "
    "optionally followed by a blank line and a short body of bullet points "
    "for non-trivial changes. Valid types: feat, fix, docs, style, "
    "refactor, perf, test, chore, build, ci. Keep the summary line under "
    "72 characters, imperative mood, no trailing period."
)


def _build_user_prompt(change: StagedChange) -> str:
    diff = change.diff
    truncated = False
    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS]
        truncated = True

    note = "\n\n[diff truncated for length]" if truncated else ""
    return (
        f"Files changed: {', '.join(change.files)}\n"
        f"Insertions: {change.insertions}, Deletions: {change.deletions}\n\n"
        f"Diff:\n{diff}{note}"
    )


def _parse_message(text: str) -> CommitMessage:
    lines = text.strip().splitlines()
    header = lines[0].strip()
    body = "\n".join(lines[2:]).strip() if len(lines) > 2 else None

    scope = None
    if "(" in header.split(":")[0]:
        type_part = header.split(":")[0]
        commit_type = type_part.split("(")[0].strip()
        scope = type_part.split("(")[1].rstrip(")").strip()
    else:
        commit_type = header.split(":")[0].strip()

    summary = header.split(":", 1)[1].strip() if ":" in header else header

    return CommitMessage(type=commit_type or "chore", scope=scope or None, summary=summary, body=body or None)


def generate_ai_message(change: StagedChange) -> CommitMessage | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic
    except ImportError:
        return None

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_user_prompt(change)}],
        )
        text_blocks = [b.text for b in response.content if getattr(b, "type", None) == "text"]
        text = "\n".join(text_blocks).strip()
        return _parse_message(text) if text else None
    except Exception:
        return None


def generate(change: StagedChange, use_ai: bool = True) -> tuple[CommitMessage, bool]:
    """Returns (message, was_ai_generated)."""
    if use_ai:
        ai_message = generate_ai_message(change)
        if ai_message is not None:
            return ai_message, True

    return generate_offline(change), False
