---
title: Prefer a reviewer from the other provider than the planner
status: implemented
---

# Task brief

## Routing

Planner/coordinator: Claude `claude-opus-5-5`, implemented directly in
this repository on `feat/planner-cross-provider-review`
(PR #5); no implementation worker. Reviewer: a fresh Claude `claude-opus-5-5`
session, the only enabled reviewer profile in the trusted base policy. The user
approved the plan in the coordinator session on 2026-11-09.

```agent-task
{
  "tier": "full",
  "implementer": {"read": [], "write": [], "sensitive": []},
  "review": {"read": [
    "scaffold.py",
    "workflow.py",
    "kit-files.json",
    "docs/compatibility.md",
    "docs/agents/task-permissions.md",
    "tests/kit/test_workflow.py"
  ]}
}
```

## Goal and acceptance

Generalize an adopter's independent review rule for the starter kit.

1. The policy key `reviewer_provider_differs_from_planner: "preferred"` replaces
   `prefer_cross_provider_review`; `check_sync.py` fails when it is not `"preferred"`.
2. Under the preference, `review_gate.py` requires `planner` in the review record:
   an enabled exact planner profile from the trusted policy, or `{"agent": "human"}`.
3. When the trusted policy enables a reviewer from a provider other than the
   planner's, a same-provider review passes only with
   `cross_provider_fallback.reason` in `quota_exhausted`, `launch_failed`,
   `unqualified`, `model_unavailable`.
4. When no other-provider reviewer is enabled (the starter default), a
   same-provider review passes without a fallback. A fallback on any review that
   is not a qualifying same-provider review is rejected.
5. A policy without the preference keeps the previous gate behavior.
6. Codex defaults move from `gpt-6.1-terra` to `gpt-6.1-sol` (planner, disabled
   reviewer, `codex_review.py --model` default).
7. Skills, the record example, README and `docs/agents/cross-provider.md` describe
   the rule and the reason it follows the planner rather than the implementer.

## Context

The pilot project's `check_sync.py` additionally fails when a planner has no other-provider
reviewer; that is deliberately omitted because generated projects start with Codex
review disabled. New adoption generates `.agents/orchestration.json` from the kit; already adopted
projects migrate the key deliberately, as `docs/getting-started.md` describes.

## Changes and scope

Already committed by the coordinator: `AGENTS.md`, `.agents/orchestration.json`,
`.agents/skills/review-pr/SKILL.md`, `.agents/skills/review-pr/references/record.example.json`,
`.agents/skills/spec-and-delegate/SKILL.md`, `README.md`,
`docs/agents/cross-provider.md`, `docs/validation.md`, `scripts/agents/check_sync.py`,
`scripts/agents/codex_review.py`, `scripts/agents/review_gate.py`,
`tests/agents/test_codex_review.py`, `tests/agents/test_review_gate.py`,
`tests/kit/test_scaffold.py`, and this spec.

## Sensitive files

None match `scripts/agents/sensitive.json`. The change edits workflow controls
(review gate, policy, contract check), so it is tier full and reviewed in full.

## Verification and operational permissions

Coordinator checks: `python3 -m unittest discover -s tests -q` (135 tests, OK on
Python 3.14.5 and 3.11), `python3 scripts/check_docs.py`,
`python3 scripts/scan_public.py`, `python3 scripts/agents/check_sync.py`.
Infrastructure/network/credentials/service operations: none.

## Out of scope

Enabling or qualifying the Codex reviewer, Codex implementation, upgrading
or modifying already adopted projects.
