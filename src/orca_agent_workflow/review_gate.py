#!/usr/bin/env python3
"""Validate local, head/base-bound review evidence; never launch or merge anything.

This validates coordinator-recorded evidence, not a signed model attestation or
GitHub branch protection. The coordinator must corroborate model/session identity
against the saved Orca receipt and provider transcript before writing the record.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from orca_agent_workflow import __version__, task_scope

# Exact, versioned model IDs only; aliases such as "opus" or "latest" never qualify.
MODEL_ID = {
    "claude": re.compile(r"claude-[a-z]+-\d+(?:-\d+)*"),
    "codex": re.compile(r"gpt-\d+(?:\.\d+)*(?:-[a-z]+)?"),
}
# Why the planner's provider may also review: the other provider genuinely could not run.
FALLBACK_REASONS = {"quota_exhausted", "launch_failed", "unqualified", "model_unavailable"}


def exact_model(agent: Any, model: Any) -> bool:
    pattern = MODEL_ID.get(agent) if isinstance(agent, str) else None
    return bool(pattern and isinstance(model, str) and pattern.fullmatch(model))


def enabled_reviewers(policy: dict[str, Any]) -> list[dict[str, Any]]:
    """Exact, enabled reviewer profiles from the trusted (reviewed-base) policy."""
    return enabled_profiles(policy, "reviewer")


def enabled_profiles(policy: dict[str, Any], role: str) -> list[dict[str, Any]]:
    """Exact, enabled profiles for one role from the trusted (reviewed-base) policy."""
    profiles = policy.get("roles", {}).get(role) if policy.get("version") == 2 else None
    if not isinstance(profiles, list):
        return []
    return [
        p
        for p in profiles
        if isinstance(p, dict)
        and p.get("enabled") is True
        and exact_model(p.get("agent"), p.get("model"))
    ]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def provider_preference_errors(
    record: dict[str, Any],
    policy: dict[str, Any],
    reviewer: dict[str, Any],
    allowed: list[dict[str, Any]],
) -> list[str]:
    """The planner's provider reviews only as a disclosed fallback.

    The fallback applies only while the trusted policy enables a reviewer from another
    provider; a single-provider policy has nothing to fall back from. A human-planned
    change has no planner provider to avoid.
    """
    errors: list[str] = []
    planner = record.get("planner")
    if not isinstance(planner, dict):
        planner = {}
    same_provider = False
    if planner.get("agent") != "human":
        if not any(
            p["agent"] == planner.get("agent") and p["model"] == planner.get("model")
            for p in enabled_profiles(policy, "planner")
        ):
            errors.append("planner is not an enabled exact policy profile")
        other_provider = any(p["agent"] != planner.get("agent") for p in allowed)
        same_provider = other_provider and planner.get("agent") == reviewer.get("agent")
    fallback = record.get("cross_provider_fallback")
    if same_provider:
        reason = fallback.get("reason") if isinstance(fallback, dict) else None
        if not isinstance(reason, str) or reason not in FALLBACK_REASONS:
            errors.append("same-provider review needs a cross_provider_fallback reason")
    elif fallback is not None:
        errors.append("cross_provider_fallback is only valid for a same-provider review")
    return errors


def validate_review(
    record: Any, policy: dict[str, Any], *, head: str, base: str, policy_digest: str
) -> list[str]:
    """Return all defects; missing, stale, incomplete, or malformed records fail."""
    if not isinstance(record, dict):
        return ["review record must be an object"]
    errors: list[str] = []
    if record.get("version") != 1 or isinstance(record.get("version"), bool):
        errors.append("unsupported record version")
    for key, expected in (("head_sha", head), ("base_sha", base)):
        if not re.fullmatch(r"[0-9a-f]{40}", expected):
            errors.append(f"expected {key} must be a full commit SHA")
        if record.get(key) != expected:
            errors.append(f"stale or missing {key}")
    if record.get("repository") != policy["repository"]:
        errors.append("wrong repository")
    if record.get("policy_sha256") != policy_digest:
        errors.append("review policy changed")
    if record.get("verdict") != "pass":
        errors.append("review has not passed")
    reviewer = record.get("reviewer")
    if not isinstance(reviewer, dict):
        reviewer = {}
    allowed = enabled_reviewers(policy)
    if not allowed:
        errors.append("trusted policy has no enabled reviewer profile")
    profile = {"agent": reviewer.get("agent"), "model": reviewer.get("requested_model")}
    if not any(p["agent"] == profile["agent"] and p["model"] == profile["model"] for p in allowed):
        errors.append("reviewer is not an enabled exact policy profile")
    if policy.get("reviewer_provider_differs_from_planner") == "preferred":
        errors.extend(provider_preference_errors(record, policy, reviewer, allowed))
    if reviewer.get("effective_model") != reviewer.get("requested_model"):
        errors.append("wrong or unverified effective_model; model fallback is not accepted")
    for field in ("session_id", "dispatch_id"):
        if not isinstance(reviewer.get(field), str) or not reviewer[field].strip():
            errors.append(f"missing reviewer {field}")
    if reviewer.get("fresh_session") is not True:
        errors.append("reviewer must be a fresh session")
    if reviewer.get("agent") == "codex":
        # Codex reports no served model; its session file records the client-side turn
        # model. Weaker than a response-level model and documented as such.
        if reviewer.get("model_evidence") != "codex-session-turn-context":
            errors.append("Codex reviewer needs codex-session-turn-context model evidence")
        if not re.fullmatch(r"[0-9a-f]{64}", str(reviewer.get("qualification_sha256", ""))):
            errors.append("Codex reviewer needs the qualification digest")
    sensitive = record.get("sensitive_files_reviewed")
    if not isinstance(sensitive, list) or not all(isinstance(s, str) for s in sensitive):
        errors.append("sensitive_files_reviewed must be an explicit list, including when empty")
    author = record.get("implementer_session_id")
    authorship = record.get("implementation_authorship")
    if authorship == "agent":
        if not isinstance(author, str) or not author.strip():
            errors.append("unknown implementer session; independence is unverified")
    elif authorship == "human":
        if author is not None:
            errors.append("human authorship must not hide an agent session")
    else:
        errors.append("implementation authorship is unknown")
    if isinstance(author, str) and author == reviewer.get("session_id"):
        errors.append("implementer cannot review its own work")
    coverage = record.get("coverage")
    if not isinstance(coverage, dict):
        coverage = {}
    for field in ("complete_diff", "acceptance_criteria", "test_evidence"):
        if coverage.get(field) is not True:
            errors.append(f"review coverage incomplete: {field}")
    findings = record.get("findings")
    if not isinstance(findings, list):
        errors.append("findings must be an explicit list, including when empty")
    else:
        for finding in findings:
            if not isinstance(finding, dict) or not isinstance(finding.get("blocking"), bool):
                errors.append("malformed finding")
            elif finding["blocking"] and finding.get("status") != "resolved":
                errors.append("unresolved blocking finding")
    if not isinstance(record.get("summary"), str) or not record["summary"].strip():
        errors.append("missing review summary")
    for field in ("launch_receipt_sha256", "review_report_sha256"):
        if not isinstance(record.get(field), str) or not re.fullmatch(
            r"[0-9a-f]{64}", record[field]
        ):
            errors.append(f"missing evidence digest: {field}")
    return errors


def validator_problem(base: str) -> str | None:
    """A runtime inside the checkout (the kit's source, a vendored copy) is the branch's
    own code: it may validate only if every file matches the reviewed base's copy."""
    package = Path(__file__).resolve().parent
    try:
        root = task_scope.project_root()
    except (ValueError, OSError):
        return None  # an installed runtime outside any checkout
    if not package.is_relative_to(root):
        return None
    for path in sorted(package.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(root).as_posix()
        try:
            committed = task_scope.git_bytes(root, "show", f"{base}:{relative}")
        except Exception:
            committed = None
        if committed != path.read_bytes():
            return f"{relative} differs from the reviewed base; run the base's copy"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--policy",
        type=Path,
        help="A saved copy of the base's .agents/workflow.json; default: read it from --base",
    )
    parser.add_argument("--record", required=True, type=Path)
    parser.add_argument("--head", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--launch-receipt", required=True, type=Path)
    parser.add_argument("--review-report", required=True, type=Path)
    parser.add_argument(
        "--sensitive-paths",
        required=True,
        type=Path,
        help="The reviewer brief's sensitive-paths.txt; each must be in sensitive_files_reviewed",
    )
    args = parser.parse_args()
    try:
        if args.policy:
            data = args.policy.read_bytes()
        else:
            data, _ = task_scope.base_config(task_scope.project_root(), args.base)
        config = task_scope.load_config(data)
        pinned = config["runtime"].get("version")
        if pinned != __version__:
            print(
                f"review-gate: BLOCKED (this is version {__version__}; the reviewed base pins "
                f"{pinned}; run the pinned version)",
                file=sys.stderr,
            )
            return 1
        problem = validator_problem(args.base)
        if problem:
            print(f"review-gate: BLOCKED (validator: {problem})", file=sys.stderr)
            return 1
        policy = task_scope.roles_policy(config)
        record = json.loads(args.record.read_text(encoding="utf-8"))
        errors = validate_review(
            record,
            policy,
            head=args.head,
            base=args.base,
            policy_digest=hashlib.sha256(data).hexdigest(),
        )
        if isinstance(record, dict):
            for field, path in (
                ("launch_receipt_sha256", args.launch_receipt),
                ("review_report_sha256", args.review_report),
            ):
                if (
                    not path.is_file()
                    or not path.stat().st_size
                    or record.get(field) != digest(path)
                ):
                    errors.append(f"missing or changed evidence: {field}")
            expected = {s for s in args.sensitive_paths.read_text(encoding="utf-8").splitlines() if s}
            missing = expected - set(record.get("sensitive_files_reviewed") or [])
            if missing:
                errors.append("sensitive files not reviewed: " + ", ".join(sorted(missing)))
            reviewer = record.get("reviewer") or {}
            if reviewer.get("agent") == "codex":
                receipt = json.loads(args.launch_receipt.read_text(encoding="utf-8"))
                if (
                    not isinstance(receipt, dict)
                    or receipt.get("qualification_sha256") != reviewer.get("qualification_sha256")
                    or receipt.get("thread_id") != reviewer.get("session_id")
                    or receipt.get("thread_id") != reviewer.get("dispatch_id")
                    or receipt.get("session_models") != [reviewer.get("requested_model")]
                    or receipt.get("head") != args.head
                    or type(receipt.get("returncode")) is not int
                    or receipt.get("returncode") != 0
                    or "grant_ended" not in receipt
                    or receipt["grant_ended"] is not None
                    or receipt.get("inputs_changed") != []
                ):
                    errors.append("Codex record does not match its launch receipt")
    except (OSError, ValueError, KeyError, TypeError):
        print("review-gate: BLOCKED (missing or invalid local evidence/policy)", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"review-gate: BLOCKED ({error})", file=sys.stderr)
        return 1
    print("review-gate: PASS (local workflow evidence; human merge remains required)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
