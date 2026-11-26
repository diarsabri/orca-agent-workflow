#!/usr/bin/env python3
"""Exercise scoped workflow mechanics in a disposable synthetic project; zero model calls."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from orca_agent_workflow import task_plan, task_scope  # noqa: E402


def main():
    with tempfile.TemporaryDirectory(prefix="orca-workflow-demo-") as directory:
        project = Path(directory).resolve() / "project"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "orca_agent_workflow",
                "init",
                "--target",
                str(project),
                "--name",
                "Synthetic Demo",
                "--repository",
                "example/demo",
                "--coordinator",
                "claude",
                "--apply",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            env=dict(os.environ, PYTHONPATH=str(ROOT / "src")),
        )
        for folder in ("docs", "specs"):  # setup creates neither; an application has its own
            (project / folder).mkdir()
        (project / "docs/guide.md").write_text("original\n", encoding="utf-8", newline="\n")
        (project / "private.txt").write_text("synthetic unlisted input\n", encoding="utf-8", newline="\n")
        spec = """---
status: approved
---
# Synthetic approved fixture, not a real user task
## Sensitive files
None.
```agent-task
{"tier":"light","implementer":{"read":["docs/guide.md"],"write":["docs/guide.md"],"sensitive":[]},"review":{"read":[]}}
```
"""
        (project / "specs/demo.md").write_text(spec, encoding="utf-8", newline="\n")

        def git(*args):
            return subprocess.check_output(["git", "-C", str(project), *args], text=True).strip()

        git("init", "-q")
        git("add", ".")
        git(
            "-c",
            "user.name=Synthetic Demo",
            "-c",
            "user.email=demo@example.invalid",
            "commit",
            "-qm",
            "synthetic fixture",
        )
        base = git("rev-parse", "HEAD")
        block = task_plan.load_block(project / "specs/demo.md")
        out = task_plan.plan_implementer(project, "specs/demo.md", block, 1, base)
        scope = task_scope.Scope(out / "scope.json")
        assert scope.call("read_file", {"path": "docs/guide.md"})["text"] == "original\n"
        try:
            scope.call("read_file", {"path": "private.txt"})
        except PermissionError:
            print("Unlisted read: denied")
        else:
            raise AssertionError("Unlisted read unexpectedly allowed")
        scope.call(
            "write_file",
            {"path": "docs/guide.md", "content": "updated by a synthetic file-tool call\n"},
        )
        git(
            "-c",
            "user.name=Synthetic Demo",
            "-c",
            "user.email=demo@example.invalid",
            "commit",
            "-qam",
            "synthetic scoped edit",
        )
        task_plan.plan_reviewer(project, "specs/demo.md", block, 1, base)
        print("Approved fixture -> scoped edit -> frozen review manifest: PASS")
        print("Model calls: 0. Independent model review: not run.")


if __name__ == "__main__":
    main()
