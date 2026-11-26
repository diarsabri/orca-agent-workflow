#!/usr/bin/env python3
"""Turn an approved spec's agent-task block into a scoped manifest and brief.

The coordinator runs this from the task checkout. It writes only under ignored
``.tmp/``: ``.tmp/agent-tasks/<head>-<role>/`` for the manifest and brief, and for
reviewers ``.tmp/agent-reviews/<head>/`` for the evidence. Every readable path is
listed in the brief, because scoped clients cannot list directories.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from orca_agent_workflow import task_scope

BLOCK = re.compile(r"^```agent-task\n(.*?)\n```$", re.MULTILINE | re.DOTALL)
STANDARDS = ["AGENTS.md"]
IMPLEMENTER_CONTEXT = [".agents/docs/roles/implementer.md"]
REVIEWER_CONTEXT = [
    "CLAUDE.md",
    ".agents/skills/review-pr/SKILL.md",
    ".agents/skills/review-pr/references/reviewer.md",
]


def git(root: Path, *args: str) -> str:
    return task_scope.git_bytes(root, *args).decode()


def strings(value: Any, where: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise ValueError(f"agent-task {where} must be a list of paths")
    return value


def load_block(spec: Path) -> dict[str, Any]:
    """Parse the single agent-task block strictly; unknown or misspelled keys are refused."""
    text = spec.read_text(encoding="utf-8")
    found = BLOCK.findall(text)
    if len(found) != 1:
        raise ValueError("The spec needs exactly one ```agent-task block")
    block = json.loads(found[0])
    if not isinstance(block, dict) or set(block) - {"tier", "implementer", "review"}:
        raise ValueError("agent-task keys are tier, implementer and review")
    if block.get("tier") not in ("light", "full"):
        raise ValueError("agent-task needs tier light or full")
    worker = block.get("implementer")
    review = block.get("review", {"read": []})
    if not isinstance(worker, dict) or set(worker) != {"read", "write", "sensitive"}:
        raise ValueError("agent-task implementer needs exactly read, write and sensitive")
    if not isinstance(review, dict) or set(review) != {"read"}:
        raise ValueError("agent-task review needs exactly read")
    for key in ("read", "write", "sensitive"):
        strings(worker[key], f"implementer.{key}")
    strings(review["read"], "review.read")
    block["review"] = review
    if worker["sensitive"]:
        if block["tier"] != "full":
            raise ValueError("Sensitive files require tier full")
        lines = sensitive_section(text)
        missing = [
            s
            for s in worker["sensitive"]
            if not any(re.search(rf"`{re.escape(s)}`\W+\w+\W+\w+", line) for line in lines)
        ]
        if missing:
            raise ValueError("Name each sensitive file with its reason: " + ", ".join(missing))
    return block


def sensitive_section(text: str) -> list[str]:
    """Lines of the '## Sensitive files' section, up to the next heading."""
    lines, inside = [], False
    for line in text.splitlines():
        if line.startswith("#"):
            inside = bool(re.match(r"#+\s+Sensitive files\b", line))
            continue
        if inside:
            lines.append(line)
    return lines


def require_approved(root: Path, spec: str) -> None:
    """The spec must be approved and committed unchanged at HEAD before it grants anything."""
    status = re.search(r"^status:\s*(\w+)", (root / spec).read_text(encoding="utf-8"), re.MULTILINE)
    if not status or status.group(1) not in ("approved", "implemented"):
        raise ValueError("The spec must have status approved before planning")
    try:
        task_scope.git_bytes(root, "diff", "--quiet", "HEAD", "--", spec)
        task_scope.git_bytes(root, "cat-file", "-e", f"HEAD:{spec}")
    except subprocess.CalledProcessError as exc:
        raise ValueError("Commit the approved spec unchanged before planning") from exc


def unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def write_manifest(out: Path, data: dict[str, Any]) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    manifest = out / "scope.json"
    task_scope.atomic_json(manifest, data)
    task_scope.Scope(manifest)  # validate with the broker's own rules before use
    return manifest


def path_list(paths: list[str]) -> str:
    return "\n".join(f"- `{p}`" for p in paths) if paths else "- (none)"


def default_base(root: Path) -> str:
    """Where the implementer's trusted policy comes from: the reviewed default branch."""
    try:
        return git(root, "merge-base", "HEAD", "origin/HEAD").strip()
    except subprocess.CalledProcessError:
        raise ValueError("No origin/HEAD to trust; pass --base with a reviewed commit")


def trusted(root: Path, base: str) -> dict[str, Any]:
    """Manifest fields that pin the policy to a reviewed commit."""
    _, config = task_scope.base_config(root, base)
    return {"policy_base": base, "sensitive_extra": config.get("sensitive_patterns", [])}


def plan_implementer(
    root: Path, spec: str, block: dict[str, Any], hours: float, base: str | None = None
) -> Path:
    head = git(root, "rev-parse", "HEAD").strip()
    require_approved(root, spec)
    base = base or default_base(root)
    if not re.fullmatch(r"[0-9a-f]{40}", base):
        raise ValueError("--base must be a full commit SHA")
    worker = block["implementer"]
    policy = trusted(root, base)
    read = unique(STANDARDS + [spec] + IMPLEMENTER_CONTEXT + worker["read"])
    data = {
        "version": 3,
        "root": str(root),
        "head": head,
        "role": "implementer",
        "approval_reference": f"Approved spec {spec} at {head} (tier {block['tier']})",
        "expires_at": time.time() + hours * 3600,
        "read": read,
        "write": worker["write"],
        "sensitive": worker["sensitive"],
        "commands": {},
        "runtime_read": [],
        "infrastructure": [],
        **policy,
    }
    out = root / ".tmp/agent-tasks" / f"{head}-implementer"
    write_manifest(out, data)
    (out / "brief.md").write_text(
        f"""Implement the approved spec `{spec}` at head `{head}`. Follow `AGENTS.md` and
`.agents/docs/roles/implementer.md`. Tier: {block['tier']}.

Your client exposes only task-scoped file tools, a scope-question tool and report. It
cannot list directories, so every path you may read is listed below. Read responses are
paged: follow next_offset until null. Read the spec completely before writing.

Readable paths:
{path_list(read)}

Writable paths (create or overwrite only these; existing ones are readable too):
{path_list(data["write"])}

Sensitive paths (gate, build or deploy inputs; change them only as the spec says, and
explain each change in your report):
{path_list(data["sensitive"])}

You cannot run commands. Report checks as not run; the coordinator runs gates. If
something is ambiguous, ask with task.request_scope and end your turn; on an Orca wake,
read replies with task.mailbox. When done, call task.report with the exact Task and
Dispatch IDs injected by Orca and: changed files and purpose, verification (not run),
and deviations, assumptions and risks.
""", encoding="utf-8", newline="\n"
    )
    return out


def plan_reviewer(root: Path, spec: str, block: dict[str, Any], hours: float, base: str) -> Path:
    head = git(root, "rev-parse", "HEAD").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", base):
        raise ValueError("--base must be a full commit SHA")
    require_approved(root, spec)
    policy = trusted(root, base)
    evidence = root / ".tmp/agent-reviews" / head
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "base-AGENTS.md").write_text(git(root, "show", f"{base}:AGENTS.md"), encoding="utf-8", newline="\n")
    flags = ("--no-renames", "--no-ext-diff", "--no-textconv", "--text")
    (evidence / "full.diff").write_text(git(root, "diff", *flags, base, head), encoding="utf-8", newline="\n")
    deleted = [
        p
        for p in git(
            root, "diff", "--name-only", "-z", *flags, "--diff-filter=D", base, head
        ).split("\0")
        if p
    ]
    changed = [
        p
        for p in git(
            root, "diff", "--name-only", "-z", *flags, "--diff-filter=d", base, head
        ).split("\0")
        if p
    ]
    (evidence / "changed-paths.txt").write_text("\n".join(changed + deleted) + "\n", encoding="utf-8", newline="\n")
    patterns = task_scope.sensitive_patterns(policy["sensitive_extra"])
    sensitive = [p for p in changed if task_scope.is_sensitive(p, patterns)] + [
        f"{p} (deleted)" for p in deleted if task_scope.is_sensitive(p, patterns)
    ]
    (evidence / "sensitive-paths.txt").write_text("\n".join(sensitive) + "\n", encoding="utf-8", newline="\n")
    readable = []
    for path in changed:
        try:
            task_scope.relative(path)
        except ValueError:
            continue  # credential-pattern paths stay unreadable; the diff still shows them
        readable.append(path)
    rel = evidence.relative_to(root).as_posix()
    files = sorted(f"{rel}/{p.name}" for p in evidence.iterdir() if p.is_file())
    read = unique(
        STANDARDS + REVIEWER_CONTEXT + [spec] + readable + block["review"]["read"] + files
    )
    data = {
        "version": 3,
        "root": str(root),
        "head": head,
        "role": "reviewer",
        "approval_reference": f"Fresh review of {base}..{head} for approved spec {spec}",
        "expires_at": time.time() + hours * 3600,
        "read": read,
        "write": [],
        "sensitive": [],
        "commands": {},
        "runtime_read": [],
        "infrastructure": [],
        **policy,
    }
    out = root / ".tmp/agent-tasks" / f"{head}-reviewer"
    write_manifest(out, data)
    (out / "brief.md").write_text(
        f"""Independently review the complete change {base}..{head} for the approved spec
`{spec}` (tier {block['tier']}). Do not implement changes. You are a fresh session,
independent of the planner and implementer.

Your client exposes only task-scoped read tools, a scope-question tool and report. It
cannot list directories, so every path you may read is listed below. Read responses are
paged: follow next_offset until null. Read `{rel}/full.diff` completely.

Sensitive files changed (examine each one's diff explicitly and name it in your report):
{path_list(sensitive)}

Readable paths:
{path_list(read)}

Return a complete report: base and head; verdict pass, changes_requested or blocked,
stated at the top; coverage and gaps; each finding with an ID, severity, path and line,
the concrete problem and whether it blocks; remaining limitations. Never certify
coverage you did not achieve.

If your client has `task.report`, finish with it, using the exact Task and Dispatch IDs
injected by Orca; ask questions with `task.request_scope`, end your turn, and read replies
with `task.mailbox`. Otherwise reply with the complete report as your final message.
""", encoding="utf-8", newline="\n"
    )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--role", required=True, choices=["implementer", "reviewer"])
    parser.add_argument(
        "--base",
        help="Full reviewed base SHA; its .agents/workflow.json is the trusted policy "
        "(required for reviewers; implementers default to the merge base with origin/HEAD)",
    )
    parser.add_argument("--hours", type=float, default=3.0)
    args = parser.parse_args()
    root = task_scope.project_root().resolve()
    spec = args.spec
    task_scope.relative(spec)
    block = load_block(root / spec)
    if args.role == "implementer":
        out = plan_implementer(root, spec, block, args.hours, args.base)
    else:
        if not args.base:
            parser.error("--base is required for reviewers")
        out = plan_reviewer(root, spec, block, args.hours, args.base)
    print(json.dumps({"manifest": str(out / "scope.json"), "brief": str(out / "brief.md")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
