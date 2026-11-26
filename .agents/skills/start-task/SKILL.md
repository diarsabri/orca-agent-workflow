---
name: start-task
description: Coordinate a substantive implementation task in this Orca project, from discovery through scoped implementation, checks and review. Use for new features, substantial fixes and refactors; continue existing tasks in place. Skip questions, read-only work, tiny edits and explicitly assigned worker/reviewer jobs.
---

# Start a task

Turn the user's ordinary task request into a coordinated change. The current
session is the coordinator; the request supplies the goal. Do not ask the user to
initialize an orchestrator or repeat a kickoff prompt.

## Establish ownership and scope

Read the project's `AGENTS.md`, `.agents/workflow.json`
and [workflow](../../WORKFLOW.md), plus relevant application guidance.

- Honor an explicit worker/reviewer assignment or Task/Dispatch IDs first. Follow
  that role and its scope; do not promote yourself to coordinator or dispatch
  nested workers. A request to arrange a branch/PR review uses `review-pr`;
  a dispatched reviewer follows its injected review contract, not the arranging
  steps of that skill.
- For a follow-up, resume the current task, approved scope and pending checks.
  Recover the exact session when necessary; do not create another task/worktree
  merely because a new message arrived.
- Answer questions and perform read-only investigation directly. Handle small,
  understood, low-risk edits directly under project rules. Classify by behavior,
  uncertainty and risk, not file or line count. If an investigation leads to a
  substantive change, use this intake before implementing it.

Inspect Git status and the relevant code before editing. Reuse a workspace already
owned by this task. Preserve unrelated work; if isolation is needed, use Orca's
installed workspace guidance to prepare a task checkout from committed files.
Never move, stash or commit unrelated changes to make a checkout clean. Do not
launch a second writer in an occupied checkout.

`python3 .agents/workflow.py start` is an optional launcher for a **new** coordinator session; do
not call it as initialization from an existing coordinator. If a separate client
is actually needed, make one explicit handoff with the objective, workspace,
branch/HEAD, current scope, evidence and next action; verify the original writer
has stopped before takeover.

## Make the work concrete

Investigate enough to state the intended behavior and observable acceptance
criteria. Explain the approach briefly. Ask only for missing product decisions or
constraints that affect the result; continue independent discovery meanwhile.
Do not ask for approval to read code or perform already authorized routine work.

Check the project's actual verification commands, trusted gate dependencies and
enabled role/model profiles. Use the current session for discovery; before any
worker dispatch, resolve coordinator eligibility, account/model availability,
Orca readiness and scoped adapter probes using the installed guidance. Missing
readiness blocks the affected dispatch, not independent planning. Never silently
enable a disabled provider/profile or fall back to an unconstrained worker.

When the implementation plan is bounded, follow
[spec-and-delegate](../spec-and-delegate/SKILL.md): draft the spec, obtain explicit
approval of that spec and commit it before launching a cold implementer. A task
request alone is not approval of a spec that has not yet been written. Reuse an
existing approved spec when the task remains inside its scope. Direct coordinator
changes remain possible when delegation adds no value; do not invent a worker or
an approval ceremony for a small edit.

## Carry the task through

Keep the same coordinator responsible for dispatch, questions, complete-diff
inspection, meaningful checks, documentation and fresh independent review under
the project contract. Use the existing authorization for commits/publication;
leave PR merge to the human. Report actual results and anything still blocked.
Instruction-based routing helps the agent select this workflow; the scoped tools
and review gates enforce their own boundaries. Do not claim the skill itself is
an execution hook or proof that worker/model access is qualified.
