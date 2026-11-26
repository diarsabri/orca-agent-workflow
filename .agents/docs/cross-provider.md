# Shared planner, implementer and reviewer roles

The [workflow](../WORKFLOW.md) is the starting point. Profiles live in
`.agents/workflow.json`; the coordinator records the selected exact models in
the approved spec. Disabled profiles are blocked, not silently substituted.

`light` tasks contain no sensitive writes and use one scoped implementation,
coordinator checks and a fresh review. `full` tasks touch sensitive inputs,
workflow controls, CI or infrastructure and retain complete frozen evidence.
The coordinator performs workflow-control changes directly; a worker cannot edit
the files that define its own permissions or evidence.

Use Orca's installed guides (`orca skills get orca-cli` and `orca skills get
orchestration`) for current launch and messaging commands. Read their recovery
reference when dispatch state is ambiguous. A manually prepared scoped terminal
is attached as an existing terminal; an ordinary unrestricted agent launch does
not reproduce that scope. End the turn after independent Orca workers launch;
Orca wakes the coordinator when they report. Do not poll their inbox.

## Reviewer provider

`reviewer_provider_differs_from_planner` is `"preferred"`: the reviewer comes from
a provider other than the planner's. The implementer is always Claude today, so an
Opus-planned change gets a Codex review, and a Codex-planned change, whose diff the
Codex coordinator already inspected, gets a Claude review of its spec and result.
A fresh session of the same model removes context, not shared blind spots. The
review record names the planner (`{"agent", "model"}`, or `{"agent": "human"}`).

When the trusted policy enables a reviewer from another provider and that provider
genuinely cannot run, a fresh same-provider review is an accepted, disclosed
fallback: the record carries `cross_provider_fallback: {"reason": ...}` with one of
`quota_exhausted`, `launch_failed`, `unqualified` or `model_unavailable`, and the PR
review summary states it. Preference is never a reason. While the policy enables
only one provider's reviewers (the default until Codex review is qualified), a
same-provider review is the normal path and records no fallback. `review-gate`
enforces both cases; `check` requires the preference in the policy.

## Review evidence

Keep the complete report, receipt and normalized record in ignored
`.tmp/agent-reviews/<head>/`. Use the [record example](../../.agents/skills/review-pr/references/record.example.json)
and independently corroborate authorship, the planner (against the approved
spec's Routing section), exact model, report completeness and the current
base/head before marking coverage true. The gate trusts the recorded planner.

Run the validator at the version the reviewed base pins, never the branch's own
launcher. It reads the policy from `--base` and refuses when its version differs
from that commit's pin:

```sh
uvx orca-agent-workflow@BASE_PINNED_VERSION review-gate \
  --record .tmp/agent-reviews/HEAD/review.json \
  --launch-receipt .tmp/agent-reviews/HEAD/launch.json \
  --review-report .tmp/agent-reviews/HEAD/report.md \
  --sensitive-paths .tmp/agent-reviews/HEAD/sensitive-paths.txt \
  --head FULL_HEAD_SHA --base FULL_BASE_SHA
```

A runtime inside the checkout (a vendored `.agents/runtime/`, or the kit's own
`src/`) is the branch's code. Run the base's copy instead, extracted outside the
checkout, for example
`git archive BASE .agents/runtime | tar -x -C /tmp/base-runtime` and then
`PYTHONPATH=/tmp/base-runtime/.agents/runtime python3 -m orca_agent_workflow review-gate ...`
(use `src` for the kit). As a backstop, `review-gate` refuses to run from inside the
checkout unless every one of its files matches the base commit.

The sensitive list is mandatory even when it is an empty file. Codex records use
their actual thread ID for both `session_id` and `dispatch_id`, record
`model_evidence: codex-session-turn-context`, and bind the qualification digest.
The validator requires a receipt for the same head with integer zero exit, no
ended grant and unchanged inputs. It does not prove the reviewer read the files.

For an initial project bootstrap, explicitly approve the initial policy/tooling
snapshot before using it as authority; it is not yet a reviewed base. Never
silently promote proposed policy changes merely because they enable a desired model.
After the independent initial review, retain that reviewed snapshot for later tasks.

New head/base commits invalidate readiness. CI and project documentation checks
remain separate, and PR merging remains a human action.
