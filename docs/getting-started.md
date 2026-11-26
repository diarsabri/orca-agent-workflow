# Adopt the workflow, then describe a task

## Begin in Claude Code, Codex or OpenCode

You can start from the coding agent you already use. Open the target repository
and paste:

> Install and set up https://github.com/diarsabri/orca-agent-workflow in this
> repository, including Orca if it is missing. Follow INSTALL.md, preserve existing
> work, and verify the result.

The agent follows [INSTALL.md](../INSTALL.md) to obtain the setup skill, ensure its
Git/Python prerequisites, bootstrap Orca and adopt the workflow. Orca is not needed
to begin this process, and there is no required switch to another coding session.
The agent can read the installed skill directly or use it from a temporary source
checkout. Private repository access requires the user's GitHub authentication.

Orca is an [open-source desktop environment](https://github.com/stablyai/orca)
for managing coding agents and Git worktrees. Its app/runtime/CLI remain required
for executing the coordinated workflow. Setup makes installing that dependency
part of the same agent-guided task. You still use your own coding-agent account.

The agent performs supported installation/configuration steps itself, asking only
for real system permissions, first-launch choices, sign-in or essential missing
preferences. Those steps can prevent fully unattended installation on a new
machine. Afterward it resumes preparation, merging and validation.

## What bootstrap does

The included helper's `bootstrap` command prints a plan; `bootstrap --apply`
performs the supported dependency setup. It detects a ready runtime and reuses
it, avoiding upgrades/reinstalls. On macOS with Homebrew, it installs a missing
Orca through the official cask, which provides the app and CLI, then opens it when
needed with `orca open --json`. Readiness is checked again after changes. It does
not start an implementation/coordinator session or reset a running runtime.

Automatic installation currently covers macOS with an existing Homebrew. Other
platforms/install methods use [Orca's official installation guide](https://www.onorca.dev/docs/install)
and [GitHub Releases](https://github.com/stablyai/orca/releases/latest); the agent
can perform the appropriate supported installation within the request. The helper
reports remaining steps rather than pretending unsupported installs succeeded.
It does not install a new package manager or change account settings silently.

For an app installed without a PATH command, register the CLI through
**Settings → General → Orca CLI**, following the [official CLI guide](https://www.onorca.dev/docs/cli/overview).
System or GUI interaction may require the user. An unavailable runtime can also
mean sandbox/access issues; do not infer the app needs reinstalling or restarting.
Use the client's normal approval mechanism for read-only runtime access.

## Optional direct skill install

If Node/npm is available, this installs the setup skill into the current project:

```sh
npx skills add diarsabri/orca-agent-workflow --skill setup-orca-workflow --copy
```

Select your agent, then ask it to set up the workflow including Orca if missing.
If the session was already open, it can read the installed `SKILL.md` directly.
The Skills CLI installs instructions/helpers, not the whole application workflow;
the agent completes adoption next. Use `--copy` for regular files compatible with
the gate snapshot. Explicit `-g` makes the setup skill available across projects
instead; each target still gets a deliberate adoption.

Node/npm is optional with the temporary-checkout path. Git, uv and Python 3.11+ are
needed for the helper; the agent can arrange missing prerequisites. Claude Code is
required for the currently supported implementation worker, Codex can coordinate
and optionally review after qualification, and OpenCode can perform installation
without becoming a qualified confined worker. `--coordinator` selects the later
task provider, not the current setup agent. Inspect the selected profiles and installed provider binaries. Resolve missing
clients and actual provider preferences before claiming task readiness. A local
Docker engine runs gates.

## Existing repositories

The agent inspects repository instructions, code layout, meaningful checks and
Git status while arranging prerequisites. `prerequisites --check-runtime` remains
a read-only probe with upstream links. Repository preview/apply do not install
software; explicit bootstrap handles dependency changes. If Orca cannot be
installed or opened yet, configuration can proceed, but operational setup remains
incomplete.

The agent prepares adoption on a feature branch, preserving unrelated work and
using an isolated checkout when needed. Preview with the pinned `init` command
below. Applying the same options writes missing files and stages merge candidates
under `.tmp/orca-agent-workflow/merge/`. Review each candidate alongside the
existing project instructions. The installed runtime pin is in `.agents/workflow.json`.

The agent configures real project checks and the trusted gate runtime. A Lua
project may need Lua 5.1.5; a Node app needs its own runtime, package manager and
dependencies. The default image has only Python standard library, Git and make.
Runtime detection is not runtime validation. Model choices must match available
exact IDs, and scoped workers need their local probes/qualification before launch.

The agent validates the configuration and explains completed checks, remaining
prerequisites and proposed changes. Follow your repo's commit/PR authorization;
review and merge the adoption yourself. No Git hooks, account settings, provider
sessions, production operations or automatic kit upgrades are enabled by installing
this skill. The application's README and license remain its own; the kit's MIT
notice is installed separately in `.agents/LICENSE`.

For a new folder, review the generated files and establish a Git baseline before
starting task worktrees. Adopted applications own their configuration; updating the
setup skill does not overwrite it. Later upgrades need a reviewed migration.
A project on the earlier layout (`.agents/project.json`, `orchestration.json`,
`gates.json` and a copied `scripts/agents/` runtime) moves to the pinned runtime with
`migrate`: it previews, writes only with `--apply`, never deletes, and lists the
files that can then be removed. It also sets
`"reviewer_provider_differs_from_planner": "preferred"`, which `check` requires.

## Start a task

If you already have a Claude Code or Codex session open in the adopted project,
describe your task there. `AGENTS.md` selects the installed `start-task` skill for
substantive implementation. Explicit worker and reviewer assignments stay in
their own roles. Follow-ups go to the current coordinator.

If you want a first coordinator in a new Orca workspace before choosing a task,
check `python3 .agents/workflow.py start --help` from the clean, committed project.
When it lists `--wait-for-task`, run `python3 .agents/workflow.py start --wait-for-task`
once. Open the reported workspace and answer the coordinator's first question.
A repeated launch creates another workspace. To recover a missing reply, use the
Orca lookup commands below. If the installed candidate predates this option,
supply the task at launch using the command below.

Use a fresh session after first adoption, or ask the existing agent to read the
updated `AGENTS.md` and `start-task` skill once. This routing is agent instruction,
not a mandatory execution hook. Existing applications need a deliberate upgrade
to receive it; updating the setup skill alone does not change their instructions.

For an explicit new Orca workspace, run from a clean, committed checkout:

```sh
python3 .agents/workflow.py start "Describe what you want to build or change"
```

Or run `python3 .agents/workflow.py start` and answer the task question. The helper checks local
launch prerequisites, registers a missing Orca project, and opens a fresh independent
worktree from the current committed checkout. It supplies the task and planning
instructions to your chosen coordinator. Repository setup hooks are skipped.
This starts a model session through your existing Orca/client account.

Discuss the goal and approve the draft spec. The coordinator establishes meaningful
checks/runtime and worker access, then handles scoped implementation, checks and
fresh review. You review and merge the resulting PR. See [the workflow](../.agents/WORKFLOW.md).

For the next step or a launch preview without calling Orca or a model:

```sh
python3 .agents/workflow.py status
python3 .agents/workflow.py start "Your task" --dry-run
```

Status checks configuration and local prerequisites, not account access, running
Orca or client qualification. If a launch reply is missing, recover the existing
session from Orca. Substitute the adopter's repository path and the exact checkout
path returned by the first command:

```sh
orca worktree list --repo path:/absolute/project --json
orca terminal list --worktree path:/absolute/checkout --json
```

Match the session to your task or handoff prompt before continuing in that
workspace. A second `start` creates a new worktree. If Orca supplies a retry
operation ID, follow its instructions to retry that specific launch.
To continue an existing task in another client, use handoff/recovery rather than
`start`, which requests a new task workspace.

## Verify an Apple app on the coordinator host

Installer preview lists any top-level Xcode project or workspace, its shared
schemes, the test targets and test plans declared by those schemes, and common
dependency locks. Select the scheme and simulator for your project. Read the
project's dependency instructions and prepare required local build artifacts.
Pass their paths with repeatable `--requires` options, for example an ignored
XCFramework. Preview does not run Xcode or install dependencies.

Use a clean commit in a disposable or dedicated macOS checkout. Review the
application code, build phases, and dependency setup before running on the
host. Copy the simulator ID from `xcrun simctl list devices booted` or choose
one from the available devices:

```sh
python3 .agents/workflow.py native-check --container App.xcodeproj --scheme App \
  --destination 'platform=iOS Simulator,id=01234567-89AB-CDEF-0123-456789ABCDEF'
```

Keep the command under coordinator control. Record its JSON output with review
evidence. It reports the commit, Xcode, simulator, test counts, log and result
bundle paths. An unavailable simulator, missing prerequisite, build failure or
run with zero executed tests fails the host check. Portable checks still run
through the isolated Docker gate and have their own results.

## Manual setup or automation

For a private candidate, install the exact wheel under test. Add `--apply` to
the same command after inspecting its preview. Vendoring keeps the candidate
runtime with the application:

```sh
uvx --from /absolute/path/to/candidate.whl orca-agent-workflow init --target ../my-project --coordinator codex --vendor
```

Once version 0.2.0 is published, its equivalent commands are:

```sh
uvx orca-agent-workflow@0.2.0 init --target ../my-project --coordinator codex
uvx orca-agent-workflow@0.2.0 init --target ../my-project --coordinator codex --apply
```

The Git-tag fallback is `uvx --from git+https://github.com/diarsabri/orca-agent-workflow@v0.2.0 orca-agent-workflow init`.
Add `--vendor --apply` to keep the runtime in the application.

It detects Python/Node projects and suggests checks without executing them; edit
exact models in `.agents/workflow.json` afterwards. `init` never replaces an existing
file: differing ones are listed for a semantic merge, with candidates under
`.tmp/orca-agent-workflow/merge/`. Add `--vendor` to keep the runtime in
`.agents/runtime/`. Generated projects use
their installed launcher; they do not need this repository beside them.
