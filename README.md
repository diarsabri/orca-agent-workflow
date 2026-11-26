# Orca Agent Workflow

**A reusable workflow for building projects with Claude Code and Codex in Orca.**

Describe a task, approve its plan, and review the resulting PR. Orca manages the
workspaces; this kit supplies shared instructions and the tools for scoped
implementation, checks, independent review and client handoffs.

## Get started from your coding agent

Open your existing repository in **Claude Code, Codex or OpenCode**, then paste:

> Install and set up https://github.com/diarsabri/orca-agent-workflow in this
> repository, including Orca if it is missing. Follow INSTALL.md, preserve existing
> work, and verify the result.

Your agent handles dependency setup and workflow adoption in one flow. You do not
need to install Orca first or move the current session into it. It will check what
is already installed, install missing prerequisites within your request, start
Orca when needed, merge your project's instructions, and validate the result.
System permission dialogs, first-launch choices and sign-in can still need you;
the agent continues after those steps. OpenCode can perform setup; the full task
workflow currently requires a supported Claude/Codex coordinator and Claude Code
for implementation. Missing clients/accounts are resolved during setup.

See [the agent installation entry point](INSTALL.md) or the
[getting-started guide](docs/getting-started.md) for details. This repository must
be accessible to you; private installations need GitHub access.

## Where Orca fits

[Orca](https://github.com/stablyai/orca) is the required desktop environment and
runtime for managing coding-agent sessions and isolated Git worktrees. **It is a
workflow dependency that the setup agent can install, not a prerequisite for
starting setup.** Bring your own coding-agent account.

Automated Orca bootstrap currently supports macOS with an existing Homebrew:
the [official cask](https://github.com/stablyai/homebrew-orca/blob/main/Casks/orca.rb)
installs the app and its CLI. The helper uses the upstream command
`brew install --cask stablyai/orca/orca`, then `orca open --json` when needed. It
reuses existing installations and never forces an upgrade or runtime restart.
Other platforms/install methods use [Orca's official installers](https://www.onorca.dev/docs/install)
with the agent guiding or performing the supported steps. OS interaction may be
required. The kit runs natively on macOS, Linux and Windows (no WSL); its tests
run on all three in CI. On Windows, use `python` or `py -3` where this guide says
`python3`, and Codex review qualification is not available yet (see
[compatibility](docs/compatibility.md)).

Once adoption is reviewed and committed, open Claude Code or Codex in the project
and describe your task normally, for example: “Add a weekly habit summary.” The
shared project instructions select `start-task` for substantive implementation;
that session coordinates discovery, implementation, checks and review. Questions
and small edits stay lightweight. Assigned workers/reviewers keep their roles,
and follow-ups continue the existing task. No separate initialization prompt.

Use a fresh session after first adoption, or have the existing agent read the
updated `AGENTS.md` and `start-task` skill once. This is instruction-based routing,
not an execution hook that guarantees every agent follows it.

For an explicit new Orca workspace, the optional launcher remains:

```sh
python3 .agents/workflow.py start "Build a simple habit tracker"
```

This opens a fresh Orca worktree with your coordinator and planning instructions.
You approve the spec before a scoped implementation worker runs. Use
`python3 .agents/workflow.py status` for the next step or `start --dry-run` to preview.
Claude Code is currently required for the implementation worker; Codex can
coordinate and review after qualification. OpenCode can perform setup; its confined
worker dispatch is not qualified. Docker supplies isolated project checks.

## Optional skill installation

If you prefer to install the skill yourself, run this inside the target repo:

```sh
npx skills add diarsabri/orca-agent-workflow --skill setup-orca-workflow --copy
```

Then ask your current agent to set up the workflow, including Orca if needed.
The Skills CLI needs Node/npm; the direct agent/temporary-checkout path above
uses Git and Python instead. The `--copy` option keeps installed skill files
compatible with gate snapshots. Your agent can read the installed skill directly
without requiring a new coding session.

## Manual setup and automation

The workflow's runtime is a Python package, `orca-agent-workflow` (standard library
only, Python 3.11+), run through [uv](https://docs.astral.sh/uv/). From release 0.2.0:

```sh
uvx orca-agent-workflow@0.2.0 init --target ./my-project
uvx orca-agent-workflow@0.2.0 init --target ./my-project --apply
```

For a vendored install from the release tag:

```sh
uvx --from git+https://github.com/diarsabri/orca-agent-workflow@v0.2.0 orca-agent-workflow init --target ./my-project --vendor --apply
```

The PyPI pin selects a version whose uploaded filenames cannot be reused.
The release workflow builds the wheel from the source distribution, tests that wheel
on Linux, macOS and Windows, and publishes both files with attestations. A version
pin in `uvx` does not verify a specific artifact hash. Use `--vendor` to review
and commit the runtime code with the application.

`init` previews by default and writes with `--apply`. It suggests checks from the
project, never replaces an existing file, and lists files that need a semantic
merge with a candidate under `.tmp/orca-agent-workflow/merge/`; the setup skill
does that merge with you. Projects from an earlier version use `migrate` instead.

An application receives about 27 files, all under `.agents/` and `.claude/` plus
`AGENTS.md`, `CLAUDE.md` and ignore/attribute rules, and no runtime code. The runtime
version is pinned in `.agents/workflow.json`; `.agents/workflow.py` runs exactly that
version through `uvx`, or the copy in `.agents/runtime/` with `--vendor`. Add `--opencode` for OpenCode
commands or `--pre-push-hook` for the protected-branch hook. The project guide is
installed as `.agents/README.md`.

The kit's MIT notice is preserved in `.agents/LICENSE`; your application's license
stays yours to choose. A GitHub template copy gives you the starter kit itself;
use the skill or `init` to adopt it into a separate application.

## Try the mechanics without a model account

```sh
cd orca-agent-workflow
python3 examples/offline_demo.py
python3 -m unittest discover -s tests -q
python3 scripts/check_docs.py
python3 .agents/workflow.py doctor
```

The offline demo creates a disposable project, plans a synthetic approved task,
checks allowed/denied file operations, and freezes reviewer inputs. It performs
no model calls and does not pretend to be an independent model review.

## What is included

| Capability | Implementation |
| --- | --- |
| Shared project contract | `AGENTS.md`, `CLAUDE.md`, project configuration and thin skill adapters |
| Approved task scope | Exact read/write/sensitive paths from `plan` |
| Constrained implementation | Experimental Claude file-only broker with preparation/probe receipts |
| Coordinator verification | Disposable local Docker gates, trusted build inputs, no runtime network |
| Independent review | Frozen inputs, exact base/head, complete-coverage reporting and local evidence gate |
| Client recovery | Model-free local transcript reader plus exact-session handoff procedure |
| Adoption | Agent-led setup, shared default task routing, careful instruction merging and an optional workspace launcher |

## Provider support is explicit

- **Planner:** configure Claude or Codex in the shared roles policy.
- **Implementer:** Claude through the prepared/probed file-only adapter.
- **Reviewer:** a fresh scoped Claude session, or an opt-in locally qualified
  Codex reviewer. Codex review starts disabled in generated projects. Once
  both providers can review, the reviewer comes from a provider other than
  the planner's unless that provider cannot run, which the review discloses.
- **Codex implementation:** disabled until native capability scope is verified.
- **OpenCode:** shared instructions/command adapters; confined worker dispatch is
  not qualified by this release.

Model IDs in the example policy are editable examples from the originating setup,
not a promise of account availability. The starter gate image supports standard-
library Python checks; application dependencies and Node/web support need a
reviewed project-specific image. See [compatibility](docs/compatibility.md).

## Why this shape

```mermaid
flowchart LR
    P[Planner] --> A[Approved spec]
    A --> I[Scoped implementer]
    I --> G[Isolated checks]
    G --> R[Fresh reviewer]
    R --> H[Human merge]
```

Planning needs context. Implementation benefits from a small, explicit job.
Review needs fresh context and the complete diff. Keeping those roles distinct
makes handoffs and permission decisions visible without expecting every provider
to expose identical native features.

The approved spec is the primary scope. A small fixed backstop protects the
workflow itself and credentials; sensitive build/configuration files are declared
and reviewed rather than added to an endlessly expanding forbidden-file list.

Read the [architecture](docs/architecture.md), [workflow](.agents/WORKFLOW.md),
[permission guide](.agents/docs/task-permissions.md), [security model](docs/security.md),
and [validation record](docs/validation.md) for operational details and limits.

## Contribute or adapt

See [contributing](CONTRIBUTING.md). The public release has fresh history and
synthetic fixtures; it contains no application source, project transcripts,
credentials or production configuration from the originating private pilot.

[MIT licensed](LICENSE). Independent project by Diar Sabri, built for use with
separately installed Orca and model CLIs. No affiliation or endorsement is implied;
their subscriptions, trademarks and licenses remain separate.
