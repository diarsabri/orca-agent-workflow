"""Open a task in a fresh Orca worktree, or show what is missing before one can start."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from orca_agent_workflow import adoption, check_sync, review_gate, task_scope

LAUNCHER = "python3 .agents/workflow.py"


def ask(label: str, default: str = "", choices: tuple = ()) -> str:
    while True:
        answer = input(f"{label}" + (f" [{default}]" if default else "") + ": ").strip()
        answer = answer or default
        if not choices or answer in choices:
            return answer
        print("Choose " + " or ".join(choices) + ".")


def git(root: Path, *arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *arguments], capture_output=True, text=True, timeout=15
    )


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:45].rstrip("-") or "project"


def configuration(root: Path) -> tuple[dict, dict]:
    if not (root / task_scope.CONFIG).is_file():
        raise ValueError(f"No {task_scope.CONFIG}. Run orca-agent-workflow init first.")
    problems = check_sync.check(root)
    if problems:
        raise ValueError("Workflow configuration needs attention: " + "; ".join(problems))
    config = task_scope.load_config((root / task_scope.CONFIG).read_bytes())
    project = config["project"]
    planners = config["roles"].get("planner", [])
    coordinator = project.get("coordinator") or next(
        (p for p in planners if p.get("enabled") is True), {}
    )
    if not review_gate.exact_model(coordinator.get("agent"), coordinator.get("model")) or not any(
        p.get("enabled") is True
        and p.get("agent") == coordinator.get("agent")
        and p.get("model") == coordinator.get("model")
        for p in planners
    ):
        raise ValueError("Choose an enabled exact coordinator profile in .agents/workflow.json.")
    checks = project.get("checks", [])
    if not isinstance(checks, list) or any(
        not isinstance(c, str) or not c.strip() for c in checks
    ):
        raise ValueError("Project checks must be a list of non-empty commands.")
    project = {**project, "checks": checks}
    return project, {"agent": coordinator["agent"], "model": coordinator["model"]}


def readiness(root: Path, coordinator: dict) -> tuple[str | None, Path, list[str]]:
    problems = []
    for tool in ("git", "orca", coordinator["agent"]):
        if not shutil.which(tool):
            problems.append(f"Install {tool} and make it available on PATH.")
    head = None
    repo_path = root
    if shutil.which("git"):
        top = git(root, "rev-parse", "--show-toplevel")
        if top.returncode or Path(top.stdout.strip()).resolve() != root:
            problems.append(
                "Initialize Git in the project folder and review/commit its files first."
            )
        else:
            # Git lists the primary checkout first, even when called from a linked worktree.
            listing = git(root, "worktree", "list", "--porcelain", "-z")
            first_field = listing.stdout.partition("\0")[0]
            if listing.returncode or not first_field.startswith("worktree "):
                problems.append("Git could not identify the primary checkout for Orca registration.")
            else:
                repo_path = Path(first_field.removeprefix("worktree "))
            result = git(root, "rev-parse", "--verify", "HEAD")
            head = result.stdout.strip() if result.returncode == 0 else None
            tracked = git(
                root, "ls-files", "--error-unmatch", ".agents/workflow.py", task_scope.CONFIG
            )
            if not head or tracked.returncode:
                problems.append(
                    "Review and commit the generated workflow files first; worktrees copy committed files only."
                )
            if git(root, "status", "--porcelain").stdout.strip():
                problems.append(
                    "This launcher needs a clean committed checkout. Preserve unrelated changes and use an isolated clean checkout; no files were changed."
                )
    return head, repo_path, problems


def status() -> int:
    root = task_scope.project_folder()
    project, coordinator = configuration(root)
    _, _, problems = readiness(root, coordinator)
    print(
        f"Project: {project['name']}\nCoordinator: {coordinator['agent']} / {coordinator['model']}"
    )
    print("Ready to open a planning task." if not problems else "Before starting:")
    for problem in problems:
        print("- " + problem)
    revisions = adoption.revisions(root)
    for role, revision in revisions.items():
        print(f"{role}: {revision}")
    if any(not revision.endswith("(policy present)") for revision in revisions.values()):
        print(
            "To use the default gate and worker policy after adoption, refresh origin's "
            "default branch and check these revisions from the task checkout."
        )
    print(
        "Checks: "
        + (
            "; ".join(project["checks"])
            or "ask the coordinator to configure them before implementation"
        )
    )
    print(
        "Runtime/dependencies and scoped model access must be checked by the coordinator before worker dispatch."
    )
    return int(bool(problems))


def start(args: argparse.Namespace) -> int:
    root = task_scope.project_folder()
    project, coordinator = configuration(root)
    task = args.task
    if not task and not args.wait_for_task:
        if not sys.stdin.isatty():
            raise ValueError(
                f'Describe the task: {LAUNCHER} start "Your task". '
                f'To open a first coordinator and supply the task in Orca, run '
                f'{LAUNCHER} start --wait-for-task.'
            )
        task = ask("What would you like to build or change?")
    if not args.wait_for_task and not task.strip():
        raise ValueError("Describe a non-empty task.")
    head, repo_path, problems = readiness(root, coordinator)
    if args.wait_for_task:
        workspace = "first-task"
        prompt = (
            "You are the coordinator for this newly adopted project. Read AGENTS.md, "
            ".agents/WORKFLOW.md, .agents/workflow.json and .agents/skills/start-task/SKILL.md. "
            "Then ask the user for their first task and wait. Only the user supplies the goal. "
            "Do not edit files, draft a spec, launch workers or start another coordinator during this handoff."
        )
    else:
        workspace = slug(task)
        prompt = (
            "Use start-task for this task. You are the coordinator in this task workspace; "
            "reuse this session rather than launching another coordinator. Read AGENTS.md, "
            ".agents/WORKFLOW.md and .agents/workflow.json, then inspect the existing project. "
            "Help refine the goal into a bounded task and draft an understandable spec. "
            "Check that the project's verification commands and trusted gate runtime/dependencies are meaningful; "
            "if missing, help configure them before any implementation worker dispatch. "
            "Confirm model availability and probe the scoped adapters before workers run. "
            "Obtain explicit user approval and commit the spec before launching a cold implementer. "
            "Follow the fresh independent review and human merge workflow.\n\nUser goal:\n" + task
        )
    command = [
        "orca",
        "worktree",
        "create",
        "--repo",
        f"path:{repo_path}",
        "--name",
        workspace,
        "--base-branch",
        head or "HEAD",
        "--no-parent",
        "--setup",
        "skip",
        "--agent",
        coordinator["agent"],
        "--model",
        coordinator["model"],
        "--prompt",
        prompt,
        "--activate",
        "--json",
    ]
    if args.dry_run:
        print(
            json.dumps(
                {
                    "project": project["name"],
                    "ready_for_planning": not problems,
                    "before_starting": problems,
                    "command": command,
                    "model_calls": 0,
                },
                indent=2,
            )
        )
        return 0
    if problems:
        raise ValueError("\n".join(problems))
    # Register only on the documented not-found response; never treat transport failure as absence.
    result = subprocess.run(
        resolved(["orca", "repo", "show", "--repo", f"path:{repo_path}", "--json"]),
        capture_output=True,
        text=True,
        timeout=30,
    )
    reply = json.loads(result.stdout)
    if result.returncode or reply.get("ok") is False:
        if reply.get("error", {}).get("code") != "repo_not_found":
            raise ValueError(
                "Orca could not inspect this project. " + result.stdout + result.stderr
            )
        result = subprocess.run(
            resolved(["orca", "repo", "add", "--path", str(repo_path), "--json"]),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode or json.loads(result.stdout).get("ok") is False:
            raise ValueError("Orca registration failed. " + result.stdout + result.stderr)
    print("Opening a fresh planning worktree. Repository setup hooks are skipped.", flush=True)
    result = subprocess.run(resolved(command), capture_output=True, text=True, timeout=60)
    try:
        reply = json.loads(result.stdout)
        created = reply.get("result", {})
        workspace_path = created.get("worktree", {}).get("path")
        launch = created.get("launch", {})
        outcome = launch.get("outcome", {})
        confirmed = (
            reply.get("ok") is True
            and isinstance(workspace_path, str)
            and bool(workspace_path.strip())
            and outcome.get("kind") in ("structured", "terminal")
            and bool(outcome.get("handle"))
            and launch.get("prompt", {}).get("outcome") in ("journaled", "handed-to-terminal")
        )
    except (ValueError, AttributeError):
        confirmed = False
    if result.returncode or not confirmed:
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        raise ValueError(
            "Orca launch did not confirm success. Inspect the receipt above; do not retry as a fresh launch. Use Orca's --retry-launch operation ID if supplied."
        )
    print(f"Orca workspace: {workspace_path}")
    print(f"Session: {outcome['handle']}")
    print(f"Coordinator: {coordinator['agent']} / {coordinator['model']}")
    if args.wait_for_task:
        print("Continue in Orca by describing your first task in that session.")
    else:
        print(f"Task opened in Orca: {task}")
        print("Continue in Orca: refine the plan and approve the spec before implementation.")
    return 0


def resolved(command: list[str]) -> list[str]:
    """Launch the CLI that `shutil.which` found; Windows only appends .exe itself."""
    executable = shutil.which(command[0]) or command[0]
    if os.name == "nt" and Path(executable).suffix.lower() in (".cmd", ".bat"):
        # cmd.exe re-parses batch arguments, so task text could run as commands.
        raise ValueError(
            f"{executable} is a batch launcher; put Orca's native orca.exe first on PATH"
        )
    return [executable, *command[1:]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command")
    begin = commands.add_parser("start", help="Open a planning task in a fresh Orca worktree")
    goal = begin.add_mutually_exclusive_group()
    goal.add_argument("task", nargs="?")
    goal.add_argument(
        "--wait-for-task", action="store_true",
        help="Open the project coordinator and wait for the user's first task",
    )
    begin.add_argument("--dry-run", action="store_true", help="Show the launch without running it")
    commands.add_parser("status", help="Show the next steps without launching anything")
    args = parser.parse_args(sys.argv[1:] if len(sys.argv) > 1 else ["start"])
    try:
        if sys.version_info < (3, 11):
            raise ValueError("Python 3.11 or newer is required.")
        return start(args) if args.command == "start" else status()
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
        parser.exit(1, f"orca-agent-workflow: {exc}\n")
    except subprocess.TimeoutExpired:
        parser.exit(
            1,
            "orca-agent-workflow: Command timed out. A launch reply may be lost; inspect Orca before retrying. No automatic retry was made.\n",
        )
    except (EOFError, KeyboardInterrupt):
        parser.exit(1, "\norca-agent-workflow: Cancelled.\n")
    return 0
