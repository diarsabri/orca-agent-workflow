# A project workflow with clear ownership

**Planner → approved spec → scoped implementer → checks → fresh reviewer → human merge.**

The coordinator may be Claude or Codex. Orca provides workspace and task placement;
project files preserve the contract across clients. Model choices live in
`.agents/workflow.json`; choose IDs available to your account before dispatch.

1. Read the project's existing instructions and `.agents/workflow.json`. Configure
   actual verification commands. Use an isolated feature checkout for the task.
2. Use `spec-and-delegate` to write a draft spec with exact read/write paths,
   observable acceptance criteria, sensitive-file reasons and coordinator checks.
   Obtain user approval and commit the approved spec before worker launch.
3. Run `python3 .agents/workflow.py plan --spec specs/TASK.md --role implementer`.
   Prepare and probe the scoped Claude adapter using the [permission guide](docs/task-permissions.md).
   Attach the scoped terminal through Orca's installed orchestration procedure.
4. Let the implementer report its file changes through Orca. The coordinator reads
   the complete diff, runs the approved checks in the trusted gate image, reconciles
   docs and commits scoped changes.
5. Use `review-pr` for a fresh review of the complete final base/head. Freeze inputs,
   verify the effective client-recorded model and completion, and validate the
   report, receipt, policy and sensitive list. New commits invalidate the review.
6. Open a PR when authorized, wait for applicable checks, and leave merge to the user.

Workers cannot approve their own extra access. Follow the configured two automatic
fix rounds, then report unresolved blockers for user direction. Existing explicit
user authorization remains authoritative; do not introduce repeat approvals for
routine actions already inside the approved task.

## Starting a task

After adoption, open Claude Code or Codex in the application and describe your
task normally. The shared `AGENTS.md` routes substantive implementation through
[the start-task skill](skills/start-task/SKILL.md). That session becomes
the coordinator, investigates the goal, then uses `spec-and-delegate` when the plan
is concrete. Questions, read-only work and small edits stay lightweight; assigned
workers/reviewers keep their own role, and follow-ups reuse the current task.

For an explicit new Orca workspace, use
`python3 .agents/workflow.py start "Describe your task"` in a clean, committed application
checkout. This opens a fresh worktree and supplies the same `start-task` entry
instructions. Do not run it to initialize an already active coordinator. Use
`python3 .agents/workflow.py status` for the next step or read the
[project guide](README.md). The coordinator must establish
missing checks, reviewed runtime dependencies and scoped adapter qualification
before workers run; setup does not certify these.

## Adoption checklist

- Preserve existing `AGENTS.md`, hooks, instructions and project policies. `init`
  never replaces a file; it writes a candidate for each differing one under
  `.tmp/orca-agent-workflow/merge/`. Merge custom contracts by hand.
- Fill `.agents/workflow.json` with real checks, then adapt the trusted gate image
  and explicit build inputs under its `gates` to your dependencies/runtime.
- Review exact model IDs and client versions. Run `python3 .agents/workflow.py doctor` for
  prerequisite discovery; it is not a capability or model qualification.
- Probe every prepared Claude bundle before launch. Codex review is disabled by
  default until local qualification and a deliberate policy change.
- Optional: install `.githooks/pre-push` (setup's `--pre-push-hook`), then run
  `git config core.hooksPath .githooks`. It blocks protected-branch pushes for all
  clients, including a human using Git. It does not implement merge protection.

See the kit's [architecture](https://github.com/diarsabri/orca-agent-workflow/blob/main/docs/architecture.md),
[supported configurations](https://github.com/diarsabri/orca-agent-workflow/blob/main/docs/compatibility.md) and
[scope/security model](https://github.com/diarsabri/orca-agent-workflow/blob/main/docs/security.md) before treating a new host as qualified.
