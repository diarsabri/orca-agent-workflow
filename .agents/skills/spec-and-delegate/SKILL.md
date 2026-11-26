---
name: spec-and-delegate
description: Turn a settled change into an approved committed spec and delegate bounded implementation through the project's scoped Orca workflow.
---

# Specify and delegate

Read `AGENTS.md`, `.agents/workflow.json` and
[the workflow](../../WORKFLOW.md). Use this for a concrete planned change;
finish discovery with the coordinator before treating it as bounded implementation.

1. Draft `specs/<task>.md` from [the spec template](references/spec-template.md). List exact read/write paths,
   acceptance criteria, sensitive-file reasons and actual coordinator checks. Record
   the planner and select enabled exact implementer/reviewer profiles before
   approval, preferring a reviewer from a provider other than the planner's; never
   silently substitute a disabled profile.
2. Ask the user to approve the draft. Existing authorization governs routine work
   inside scope; a cold implementation dispatch still requires the spec itself to
   be explicitly approved. Mark approved and commit only that brief before launch.
3. Generate the task manifest and brief with `python3 .agents/workflow.py plan`. Prepare,
   probe and launch the scoped client using [task permissions](../../docs/task-permissions.md).
   Read Orca's installed orchestration guide and attach the exact scoped terminal.
   Include the shared implementer role and every context path in the readable scope.
4. Workers use file tools, scoped questions/mailbox and report; no shell or recursive
   delegation. Explain the exact Task/Dispatch IDs and completion protocol. End your
   turn after independent Orca dispatch; the runtime wakes you with replies/results.
5. Inspect the full diff, run the approved checks with the trusted gate runner,
   reconcile docs and commit scoped work. Never execute worker-written code with
   inherited credentials or an unreviewed build/gate definition.
6. Use `review-pr` for a fresh complete-branch review of final base/head. Fix blockers
   within the configured automatic-round limit; new commits require fresh evidence.
   Report remaining blockers to the user when that limit is exhausted.
7. Open a PR only within authorization. CI and current review remain required;
   a human merges. Record actual outcomes and verification limits.

Direct coordinator changes remain subject to project scope and review policy and
do not require an artificial implementation worker when it would add no value.
