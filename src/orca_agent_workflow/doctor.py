#!/usr/bin/env python3
"""Inspect local prerequisites. Never launches a model or changes client settings."""

import json
import shutil
import sys

from orca_agent_workflow import check_sync, task_scope


def main() -> int:
    root = task_scope.project_folder()
    project = task_scope.load_config((root / task_scope.CONFIG).read_bytes())["project"]
    executables = {
        name: bool(shutil.which(name)) for name in ("git", "orca", "claude", "codex", "docker")
    }
    problems = check_sync.check(root)
    record = {
        "python_supported": sys.version_info >= (3, 11),
        "executables": executables,
        "contract_valid": not problems,
        "project_checks_configured": bool(project.get("checks")),
        "model_calls": 0,
        "note": "Executable presence is not qualification. Review model IDs, run local probes, and prepare the trusted gate image before real dispatch.",
    }
    print(json.dumps(record, indent=2))
    return (
        0 if record["python_supported"] and executables["git"] and record["contract_valid"] else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
