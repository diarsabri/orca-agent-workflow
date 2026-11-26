"""Describe the local Git revisions used at the first project handoff."""

import subprocess
from pathlib import Path

from orca_agent_workflow import task_scope


def revisions(root: Path) -> dict[str, str]:
    def git_text(*args: str) -> str:
        try:
            return task_scope.git_bytes(root, *args).decode().strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ""

    def policy(commit: str) -> str:
        if not commit:
            return "unresolved"
        entry = git_text("ls-tree", commit, "--", task_scope.CONFIG)
        return f"{commit} (policy {'present' if entry else 'unavailable'})"

    head = gate = worker = default_ref = ""
    if (root / ".git").exists():
        head = git_text("rev-parse", "--verify", "HEAD^{commit}")
        default_ref = git_text("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
        if default_ref:
            gate = git_text("rev-parse", "--verify", default_ref + "^{commit}")
        worker = git_text("merge-base", "HEAD", "origin/HEAD")
    return {
        "workspace (committed HEAD)": policy(head),
        "gate (origin default branch)": policy(gate) if default_ref else "origin/HEAD unavailable",
        "worker (merge base with origin/HEAD)": policy(worker) if default_ref else "origin/HEAD unavailable",
    }
