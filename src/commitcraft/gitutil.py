"""Thin wrapper around git subprocess calls.

Kept deliberately small: commitcraft only ever reads staged state (never
writes) unless the user explicitly passes --apply, and even then it only
runs `git commit -m`.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass


class NotAGitRepoError(RuntimeError):
    pass


class NoStagedChangesError(RuntimeError):
    pass


@dataclass
class StagedChange:
    diff: str
    files: list[str]
    insertions: int
    deletions: int


def _run(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def is_git_repo() -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def get_staged_change() -> StagedChange:
    if not is_git_repo():
        raise NotAGitRepoError("Not inside a git repository.")

    files_output = _run(["diff", "--cached", "--name-only"])
    files = [f for f in files_output.splitlines() if f]

    if not files:
        raise NoStagedChangesError("No staged changes found. Run `git add` first.")

    diff = _run(["diff", "--cached"])

    stat_output = _run(["diff", "--cached", "--numstat"])
    insertions = deletions = 0
    for line in stat_output.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            insertions += int(parts[0])
            deletions += int(parts[1])

    return StagedChange(diff=diff, files=files, insertions=insertions, deletions=deletions)


def commit(message: str) -> None:
    _run(["commit", "-m", message])
