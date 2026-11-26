#!/usr/bin/env python3
"""Run this project's pinned orca-agent-workflow runtime. Python 3.11+.

Usage: python3 .agents/workflow.py <command> [options]   (commands: --help)

The runtime is the folder named by ORCA_AGENT_WORKFLOW_RUNTIME, else the vendored
copy in .agents/runtime/ when present, otherwise
`uvx orca-agent-workflow@<version>` with the version pinned in .agents/workflow.json.
This launcher runs from the current checkout: for trusted steps (the review gate),
run the version pinned by the reviewed base, as the review-pr skill describes.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

AGENTS = Path(__file__).resolve().parent
ROOT = AGENTS.parent


def runtime_folder():
    # A runtime folder chosen in the user's own environment (development, CI, tests).
    chosen = os.environ.get("ORCA_AGENT_WORKFLOW_RUNTIME")
    if chosen:
        return Path(chosen)
    vendored = AGENTS / "runtime"
    if (vendored / "orca_agent_workflow" / "__init__.py").is_file():
        return vendored
    # The kit's own repository runs itself from source.
    pyproject = ROOT / "pyproject.toml"
    source = ROOT / "src"
    if (source / "orca_agent_workflow" / "__init__.py").is_file() and pyproject.is_file():
        if 'name = "orca-agent-workflow"' in pyproject.read_text(encoding="utf-8"):
            return source
    return None


def find_uvx():
    """uvx from absolute PATH entries outside this checkout; Windows would search here first."""
    names = ("uvx.exe",) if os.name == "nt" else ("uvx",)
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        folder = Path(entry.strip('"'))
        if not folder.is_absolute():
            continue
        for name in names:
            candidate = folder / name
            if candidate.is_file() and not candidate.resolve().is_relative_to(ROOT):
                return str(candidate.resolve())
    return None


def main():
    folder = runtime_folder()
    folder = folder.resolve() if folder is not None else None
    # Commands act on this project, and its documented paths are relative to the root.
    os.chdir(ROOT)
    if folder is not None:
        sys.path.insert(0, str(folder))
        from orca_agent_workflow.cli import main as run

        return run(sys.argv[1:])
    try:
        pin = json.loads((AGENTS / "workflow.json").read_text(encoding="utf-8"))["runtime"]
        version = pin["version"]
    except (OSError, ValueError, KeyError, TypeError):
        print("workflow: .agents/workflow.json has no runtime version pin", file=sys.stderr)
        return 1
    uvx = find_uvx()
    if uvx is None:
        print(
            "workflow: install uv (https://docs.astral.sh/uv/) or vendor the runtime with "
            f"`uvx orca-agent-workflow@{version} init --vendor --apply`",
            file=sys.stderr,
        )
        return 1
    return subprocess.call([uvx, f"orca-agent-workflow@{version}", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
