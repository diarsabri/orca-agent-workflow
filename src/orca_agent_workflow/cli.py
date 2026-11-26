"""One command for the workflow runtime; each subcommand keeps its module's own options."""

from __future__ import annotations

import importlib
import json
import sys

from orca_agent_workflow import __version__

COMMANDS = {
    "init": ("install", "Install the project files (preview; --apply writes)"),
    "migrate": ("migrate", "Convert a v1 project to the pinned runtime (preview first)"),
    "start": ("start", "Open a planning task in a fresh Orca worktree"),
    "status": ("start", "Show what is needed before a task can start"),
    "check": ("check_sync", "Check the project's workflow contract"),
    "doctor": ("doctor", "Inspect local prerequisites"),
    "plan": ("task_plan", "Generate a worker or reviewer manifest and brief"),
    "scope": ("task_scope", "Prepare, probe, launch or serve a scoped client"),
    "resume-dispatch": ("resume_dispatch", "Wait for Claude trust and dispatch a prepared brief"),
    "gate": ("run_gates", "Run project checks in the isolated gate container"),
    "native-check": ("native", "Run reviewed Xcode tests on the coordinator host"),
    "review-gate": ("review_gate", "Validate revision-bound review evidence"),
    "codex-review": ("codex_review", "Qualify or run the Codex reviewer adapter"),
}
# init and migrate run before a project pins a version; review-gate checks itself against
# the reviewed base's pin, not the branch's working tree.
UNPINNED = {"init", "migrate", "review-gate"}


def usage() -> str:
    lines = [f"usage: orca-agent-workflow <command> [options]  (version {__version__})", ""]
    lines += [f"  {name:<14}{summary}" for name, (_, summary) in COMMANDS.items()]
    return "\n".join(lines)


def pin_problem() -> str | None:
    """A project pins one runtime version; any other version refuses to act on it."""
    from orca_agent_workflow import task_scope

    try:
        data = (task_scope.project_folder() / task_scope.CONFIG).read_bytes()
    except (OSError, ValueError):
        return None  # outside a configured project; the command reports what it needs
    try:
        pinned = json.loads(data)["runtime"]["version"]
    except (ValueError, KeyError, TypeError):
        return f"{task_scope.CONFIG} has no runtime version pin"
    if pinned != __version__:
        return (
            f"this is orca-agent-workflow {__version__}, but the project pins {pinned}; "
            "run it through python3 .agents/workflow.py"
        )
    return None


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        # Windows pipes use the ANSI code page; printing must never fail a finished launch.
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print(usage())
        return 0 if argv else 2
    if argv[0] == "--version":
        print(__version__)
        return 0
    if argv[0] not in COMMANDS:
        print(usage(), file=sys.stderr)
        return 2
    if argv[0] not in UNPINNED:
        problem = pin_problem()
        if problem:
            print(f"orca-agent-workflow: {problem}", file=sys.stderr)
            return 1
    module = importlib.import_module("orca_agent_workflow." + COMMANDS[argv[0]][0])
    if module.__name__.endswith(".start"):
        sys.argv = ["orca-agent-workflow", *argv]  # start and status share one parser
    else:
        sys.argv = [f"orca-agent-workflow {argv[0]}", *argv[1:]]
    result = module.main()
    return result if isinstance(result, int) else 0
