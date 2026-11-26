#!/usr/bin/env python3
"""Check the project's workflow contract without calling a model or changing settings."""

import sys
from pathlib import Path

from orca_agent_workflow import __version__, review_gate, task_scope


def check(root: Path) -> list[str]:
    problems = []
    try:
        config = task_scope.load_config((root / task_scope.CONFIG).read_bytes())
        policy = task_scope.roles_policy(config)
        pinned = config["runtime"].get("version")
        if config["runtime"].get("package") != "orca-agent-workflow" or not pinned:
            problems.append("runtime must pin an orca-agent-workflow version")
        elif pinned != __version__:
            problems.append(f"Runtime {__version__} differs from the pinned {pinned}")
        if not isinstance(config["project"].get("checks", []), list):
            problems.append("project.checks must be a list of commands")
        if policy.get("reviewer_provider_differs_from_planner") != "preferred":
            problems.append('reviewer_provider_differs_from_planner must be "preferred"')
        for role in ("planner", "implementer", "reviewer"):
            profiles = policy.get("roles", {}).get(role)
            if not isinstance(profiles, list):
                problems.append(f"Missing role: {role}")
                continue
            for profile in profiles:
                if profile.get("enabled") is True and not review_gate.exact_model(
                    profile.get("agent"), profile.get("model")
                ):
                    problems.append(f"Enabled {role} requires an exact model ID")
                if (
                    role == "implementer"
                    and profile.get("agent") != "claude"
                    and profile.get("enabled")
                ):
                    problems.append("Only the qualified Claude file-only implementer is supported")
        skills = (
            "start-task",
            "spec-and-delegate",
            "review-pr",
            "project-handoff",
            "session-recover",
        )
        for skill in skills:
            canonical = root / f".agents/skills/{skill}/SKILL.md"
            adapter = root / f".claude/skills/{skill}/SKILL.md"
            command = root / f".opencode/commands/{skill}.md"
            if not canonical.is_file():
                problems.append(f"Missing shared skill: {skill}")
            if (
                not adapter.is_file()
                or f".agents/skills/{skill}/SKILL.md" not in adapter.read_text(encoding="utf-8")
            ):
                problems.append(f"Claude adapter drift: {skill}")
            # OpenCode commands are optional; once installed they must stay thin.
            if (root / ".opencode/commands").is_dir() and (
                not command.is_file()
                or f".agents/skills/{skill}/SKILL.md" not in command.read_text(encoding="utf-8")
            ):
                problems.append(f"OpenCode command drift: {skill}")
        if ".agents/skills/start-task/SKILL.md" not in (root / "AGENTS.md").read_text(encoding="utf-8"):
            problems.append(
                "AGENTS.md must route substantive tasks to the shared start-task skill"
            )
        if "@AGENTS.md" not in (root / "CLAUDE.md").read_text(encoding="utf-8"):
            problems.append("CLAUDE.md must import the shared contract")
        for path in (
            ".agents/workflow.py",
            ".agents/WORKFLOW.md",
            ".agents/docs/roles/implementer.md",
            ".agents/skills/spec-and-delegate/references/spec-template.md",
        ):
            if not (root / path).is_file():
                problems.append(f"Missing workflow file: {path}")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        problems.append(f"Invalid workflow configuration: {exc}")
    return problems


def main() -> int:
    problems = check(task_scope.project_folder())
    for problem in problems:
        print("workflow-check: " + problem, file=sys.stderr)
    if not problems:
        print("workflow-check: OK (shared contract, roles, and thin adapters)")
    return int(bool(problems))


if __name__ == "__main__":
    raise SystemExit(main())
