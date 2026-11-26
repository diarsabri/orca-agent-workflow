# Shared agent contract

Read `.agents/workflow.json` for this project's identity, verification commands and roles.
Use `.agents/WORKFLOW.md` for the workflow and `.agents/docs/task-permissions.md` for its
enforced file scope. Provider adapters add client mechanics, not broader authority.

## Default task routing

Honor an explicit worker/reviewer assignment, scoped manifest or Task/Dispatch IDs
first; those sessions stay in their assigned role and never start nested orchestration.
Otherwise, use the current session as coordinator. For substantive implementation
requests (features, substantial fixes, refactors), read and follow
[the start-task skill](.agents/skills/start-task/SKILL.md) automatically; the user
should only need to describe the task. Continue an existing task in its current
context rather than initializing another coordinator or worktree on each message.
Answer questions, read-only investigations and review requests directly in their
appropriate role; make small, understood, low-risk edits directly under the rules
below. If investigation grows into substantive implementation, enter `start-task`
before editing. Judge by uncertainty and impact, not just the number of files.

## Shared boundaries

- Inspect Git status and preserve existing work before editing. Use feature branches
  after initial empty-repository bootstrap. Commit only scoped changes. Push only
  when authorized; PR merges and production operations belong to the user.
- A cold implementation worker needs an explicitly user-approved, committed spec
  under `specs/` first. Direct coordinator work does not need a ceremonial spec.
- Resolve roles from `.agents/workflow.json`. Use Orca for cross-client
  workspaces, dispatch, questions and completion. Read its installed CLI guidance.
- Workers read/write only approved files through the probed scoped adapter; no
  shell, network, commits, infrastructure access or recursive delegation. Do not
  replace a blocked adapter with an unconstrained launch.
- The coordinator inspects the complete diff before running project checks in the
  isolated gate runner. Configure real application checks and trusted dependencies;
  the starter image only provides Python's standard library, Git and make.
- Meaningful delegated changes get a fresh independent review of the complete
  current base/head. Incomplete or failed review is unreviewed. Prefer an enabled
  reviewer from a provider other than the planner's. Never infer permission from
  model capability.
- Keep credentials, provider state, raw transcripts and ignored review evidence out
  of Git. Deployment, data migrations, paid product calls and service operations
  require task-specific authorization; never inherit production credentials.
- Keep living docs aligned with behavior. Record actual checks and their limits.
  A checkpoint does not prove another writer stopped; verify exact-session exit
  before takeover. Never reset coordination state or kill unrelated processes.

For this starter-kit repository, run `python3 -m unittest discover -s tests -q`,
`python3 scripts/check_docs.py`, and `python3 scripts/scan_public.py` before release.
Scaffolded projects use their own configured commands instead.
