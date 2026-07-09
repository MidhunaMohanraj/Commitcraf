"""Rule-based fallback for classifying a diff into a Conventional Commit
type and building a reasonable one-line message, used whenever no AI
backend is available.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from commitcraft.gitutil import StagedChange

TEST_PATTERN = re.compile(r"(^|/)(tests?|__tests__|spec)(/|_|\.)", re.IGNORECASE)
DOC_PATTERN = re.compile(r"\.(md|rst|txt)$|(^|/)docs?(/|$)", re.IGNORECASE)
CONFIG_PATTERN = re.compile(
    r"\.(ya?ml|toml|ini|cfg|json)$|^(Dockerfile|Makefile|\.gitignore|\.env.*)$",
    re.IGNORECASE,
)


@dataclass
class CommitMessage:
    type: str
    scope: str | None
    summary: str
    body: str | None = None

    def render(self) -> str:
        header = f"{self.type}({self.scope}): {self.summary}" if self.scope else f"{self.type}: {self.summary}"
        if self.body:
            return f"{header}\n\n{self.body}"
        return header


def _guess_scope(files: list[str]) -> str | None:
    dirs = {f.split("/")[0] for f in files if "/" in f}
    if len(dirs) == 1:
        return next(iter(dirs))
    return None


def classify(change: StagedChange) -> str:
    if all(TEST_PATTERN.search(f) for f in change.files):
        return "test"
    if all(DOC_PATTERN.search(f) for f in change.files):
        return "docs"
    if all(CONFIG_PATTERN.search(f) for f in change.files):
        return "chore"
    if change.deletions > 0 and change.insertions == 0:
        return "refactor"
    if any("fix" in f.lower() for f in change.files):
        return "fix"
    if change.insertions > change.deletions * 2:
        return "feat"
    return "chore"


def generate_offline(change: StagedChange) -> CommitMessage:
    commit_type = classify(change)
    scope = _guess_scope(change.files)

    if len(change.files) == 1:
        summary = f"update {change.files[0]}"
    else:
        summary = f"update {len(change.files)} files"

    body = "Files changed:\n" + "\n".join(f"- {f}" for f in change.files)

    return CommitMessage(type=commit_type, scope=scope, summary=summary, body=body)
