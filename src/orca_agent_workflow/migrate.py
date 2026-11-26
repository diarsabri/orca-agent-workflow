"""Convert a project from the vendored v1 layout to the pinned runtime; never deletes files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from orca_agent_workflow import __version__, install, task_scope

V1_PROJECT = ".agents/project.json"
V1_POLICY = ".agents/orchestration.json"
V1_GATES = ".agents/gates.json"
V1_SENSITIVE = "scripts/agents/sensitive.json"
V1_DOCKERFILE = "scripts/agents/gate_sandbox/Dockerfile"
# Files only the kit installed, now replaced by the pinned runtime. Listed, never deleted.
V1_KIT_ONLY = (
    "scaffold.py",
    "kit-files.json",
    ".agents/project.json",
    ".agents/orchestration.json",
    ".agents/gates.json",
    "specs/_TEMPLATE.md",
)
# Earlier installs also used these generic names; a project may own files called the same.
V1_MAYBE = (
    "workflow.py",
    "WORKFLOW.md",
    "scripts/check_docs.py",
    "scripts/scan_public.py",
    "docs/architecture.md",
    "docs/compatibility.md",
    "docs/security.md",
    "docs/validation.md",
    "docs/getting-started.md",
)
V1_RUNTIME = (
    "scripts/agents/task_scope.py",
    "scripts/agents/task_plan.py",
    "scripts/agents/review_gate.py",
    "scripts/agents/codex_review.py",
    "scripts/agents/check_sync.py",
    "scripts/agents/doctor.py",
    "scripts/agents/sensitive.json",
    "scripts/agents/gate_sandbox/run_gates.py",
    "scripts/agents/gate_sandbox/run_gates.sh",
    "tests/agents/__init__.py",
    "tests/agents/test_codex_review.py",
    "tests/agents/test_review_gate.py",
    "tests/agents/test_task_plan.py",
    "tests/agents/test_task_scope.py",
    "docs/agents/cross-provider.md",
    "docs/agents/task-permissions.md",
    "docs/agents/roles/implementer.md",
)
# Folders the kit shared with projects: other files there are the project's own.
V1_FOLDERS = ("scripts/agents", "tests/agents", "docs/agents")


def read(target: Path, relative: str) -> dict:
    return install.load(install.safe_path(target, relative))


def convert(target: Path) -> tuple[bytes, list[str]]:
    """The equivalent .agents/workflow.json, and what the conversion could not carry over."""
    policy = read(target, V1_POLICY)
    notes = []
    if install.safe_path(target, V1_PROJECT).is_file():
        project = read(target, V1_PROJECT)
    else:
        # Pilot layouts kept identity in the policy and checks in their own docs.
        project = {"name": target.name, "repository": policy.get("repository"), "checks": []}
        notes.append("no .agents/project.json: set project.name and project.checks")
    config = json.loads((install.TEMPLATE / "agents/workflow.json").read_text(encoding="utf-8"))
    config["runtime"]["version"] = __version__
    config["project"] = {
        key: project[key]
        for key in ("name", "repository", "stack", "checks", "coordinator")
        if key in project
    }
    if policy.get("repository") != project.get("repository"):
        notes.append("project.json and orchestration.json named different repositories")
    config["roles"] = policy["roles"]
    config["max_fix_rounds"] = policy.get("max_fix_rounds", 2)
    if policy.get("reviewer_provider_differs_from_planner") != "preferred":
        notes.append("reviewer_provider_differs_from_planner is now \"preferred\"")
    gates_path = install.safe_path(target, V1_GATES)
    stock = install.safe_path(target, V1_DOCKERFILE)
    if gates_path.is_file() or stock.is_file():
        gates = install.load(gates_path) if gates_path.is_file() else {"dockerfile": V1_DOCKERFILE}
        dockerfile = gates.get("dockerfile")
        default = install.PACKAGE / "gate.Dockerfile"
        candidate = install.safe_path(target, dockerfile) if dockerfile else None
        if candidate and candidate.is_file() and candidate.read_bytes() == default.read_bytes():
            dockerfile = None  # the starter image, now shipped with the runtime
        elif dockerfile and dockerfile.startswith("scripts/agents/"):
            notes.append(f"keep {dockerfile}: the gate image was customised")
        config["gates"] = {
            **config["gates"],
            "dockerfile": dockerfile,
            **{k: gates[k] for k in ("inputs", "timeout_seconds", "memory") if k in gates},
        }
    sensitive = install.safe_path(target, V1_SENSITIVE)
    if sensitive.is_file():
        defaults = set(task_scope.sensitive_patterns())
        patterns = install.load(sensitive).get("patterns", [])
        config["sensitive_patterns"] = [p for p in patterns if p.casefold() not in defaults]
    task_scope.load_config(json.dumps(config).encode())  # refuse anything the runtime can't read
    return (json.dumps(config, indent=2) + "\n").encode(), notes


def leftovers(target: Path, keep: set[str]) -> tuple[list[str], list[str]]:
    """Files the kit installed that are now unused, and other files in its shared folders."""
    known = [*V1_KIT_ONLY, *V1_RUNTIME, V1_DOCKERFILE]
    removable = [p for p in known if (target / p).is_file() and p not in keep]
    others = [p for p in V1_MAYBE if (target / p).is_file()]
    for folder in V1_FOLDERS:
        if (target / folder).is_dir():
            others += sorted(
                p.relative_to(target).as_posix()
                for p in (target / folder).rglob("*")
                if p.is_file() and "__pycache__" not in p.parts
            )
    return removable, [p for p in others if p not in known and p not in keep]


def main() -> int:
    parser = argparse.ArgumentParser(prog="orca-agent-workflow migrate", description=__doc__)
    parser.add_argument("--target", type=Path, default=Path("."), help="Project folder")
    parser.add_argument("--apply", action="store_true", help="Write; without it, only preview")
    parser.add_argument(
        "--vendor", action="store_true", help="Copy the runtime into .agents/runtime/"
    )
    args = parser.parse_args()
    try:
        target = args.target.expanduser().resolve()
        if (target / task_scope.CONFIG).is_file():
            raise ValueError(f"{task_scope.CONFIG} exists already; use init to add missing files")
        if not (target / V1_POLICY).is_file():
            raise ValueError("No v1 configuration (.agents/orchestration.json)")
        config, notes = convert(target)
        options = argparse.Namespace(
            opencode=(target / ".opencode/commands").is_dir(),
            pre_push_hook=(target / ".githooks/pre-push").is_file(),
            vendor=args.vendor,
        )
        operations = install.plan(target, options, config)
        if args.apply:
            install.apply(target, operations)
        gates = json.loads(config)["gates"]
        keep = {gates["dockerfile"], *gates.get("inputs", [])} - {None}
        removable, unrecognised = leftovers(target, keep)
        report = {
            "target": str(target),
            "version": __version__,
            "applied": args.apply,
            "files": [{"path": op["path"], "action": op["action"]} for op in operations],
            "requires_merge": [op["path"] for op in operations if op["action"] == "merge"],
            "notes": notes,
            "removable": removable,
            "review_before_removing": unrecognised,
            "next": (
                "Merge the listed files (candidates in "
                f"{install.MERGE_FOLDER}/), delete the removable files once nothing of "
                "yours remains in them, run python3 .agents/workflow.py check, and commit."
                if args.apply
                else "Nothing written. Re-run with --apply to migrate."
            ),
        }
        print(json.dumps(report, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"migrate: {exc}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
