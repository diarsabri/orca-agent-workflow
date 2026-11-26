# Using this project's Orca workflow

On a new machine, ask your existing coding agent to check this project's workflow
configuration and install its missing dependencies, including Orca. The
[agent installation procedure](https://github.com/diarsabri/orca-agent-workflow/blob/main/INSTALL.md)
can guide that setup; preserve this application's existing configuration.

[Orca](https://github.com/stablyai/orca) manages the coding-agent worktrees and
sessions and is required for task execution. The setup agent can arrange its
installation/startup. OS permission dialogs, first-launch choices and account
sign-in may need the user. `orca status --json` checks its runtime after setup.
The [official installation guide](https://www.onorca.dev/docs/install) and
[CLI guide](https://www.onorca.dev/docs/cli/overview) cover other native install
methods and registration. Applying project files alone does not install software;
the separate bootstrap step handles that dependency setup.

After reviewing and committing adoption, open Claude Code or Codex in this
project and describe your task normally. `AGENTS.md` selects the installed
`start-task` skill for substantive implementation; your current session becomes
the coordinator. Questions, read-only work and small edits stay lightweight.
Assigned workers/reviewers keep their roles, and follow-ups continue the current
task. You do not need an initialization message or another coordinator session.

Use a fresh session after first adoption, or have the existing agent read the
updated `AGENTS.md` and `start-task` skill once. Routing is agent instruction,
not a mandatory execution hook.

For an explicit new Orca workspace, use the optional launcher from a clean,
committed checkout:

```sh
python3 .agents/workflow.py start "Describe what you want to build or change"
```

Or run `python3 .agents/workflow.py start` and answer the task question. Orca opens a fresh
worktree with the selected coordinator and the planning instructions. Discuss the
goal, approve the spec, and let the coordinator handle scoped implementation,
checks and independent review. You review and merge the PR.

For the next step or a preview without starting a session:

```sh
python3 .agents/workflow.py status
python3 .agents/workflow.py start "Your task" --dry-run
```

A committed Git baseline is required because new worktrees contain committed
files only. Start preserves existing changes and explains when a commit or clean
checkout is needed. Review files before committing; do not stage unrelated work.

`.agents/workflow.json` holds the project identity, selected coordinator, actual
check commands, exact role models and enabled profiles, the check environment
(`gates`: the runtime's standard-library image, or a reviewed Dockerfile and build
inputs), extra sensitive paths, and the pinned runtime version. Every command runs
through `.agents/workflow.py`, which uses that version: through
[uv](https://docs.astral.sh/uv/)'s `uvx`, or the copy in `.agents/runtime/` when the
project vendors it. Commands refuse to act when their version differs from the pin.
The coordinator
must confirm runtime dependencies, meaningful checks and scoped model access
before implementation workers run; installation does not qualify them.

Read the [workflow](WORKFLOW.md) for the mechanics. The kit's
[architecture](https://github.com/diarsabri/orca-agent-workflow/blob/main/docs/architecture.md),
[supported configurations](https://github.com/diarsabri/orca-agent-workflow/blob/main/docs/compatibility.md) and
[security model](https://github.com/diarsabri/orca-agent-workflow/blob/main/docs/security.md) describe its limits for the runtime version
pinned in `.agents/workflow.json`. An existing task should use
handoff/recovery when switching clients; `start` requests a new task workspace.

Review runtime upgrades and preserve project-specific changes when updating the pin.

## Projects from earlier versions

Earlier versions copied the runtime (`scripts/agents/`, `workflow.py`) and four
configuration files into the project. `uvx orca-agent-workflow@VERSION migrate`
previews the move to `.agents/workflow.json` and the pinned runtime, `--apply` writes
it, and the report lists the files that can then be removed. It never deletes
anything; files you changed are listed for a hand merge, with candidates under
`.tmp/orca-agent-workflow/merge/`.
