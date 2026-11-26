# Optional launch copy

Draft for the maintainer to edit and post. Nothing in the tooling publishes it.

---

I've open-sourced a small starter kit for how I work with coding agents.

The workflow is straightforward:

1. Plan with a strong model.
2. Approve a concrete spec.
3. Give an implementation agent only the files it needs.
4. Run checks in an isolated environment.
5. Get a fresh independent review.
6. Keep the merge decision human.

Orca handles the workspaces and coordination. Shared instructions and thin client
adapters keep the project contract consistent as I switch tools. The repository
includes an installable setup skill, one task-start command, scoped file tools, review evidence checks, session
recovery, tests and a model-free demonstration.

The provider support is deliberately explicit: Claude implementation is available
through the scoped adapter; Codex review needs local qualification; other execution
paths stay disabled until their restrictions are tested.

This is practical developer tooling with documented limits. I'd be interested to
hear how others separate planning, implementation and review in their own setups.

Code and setup: https://github.com/diarsabri/orca-agent-workflow

MIT licensed.
