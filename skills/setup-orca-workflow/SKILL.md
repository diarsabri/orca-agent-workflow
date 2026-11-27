---
name: setup-orca-workflow
description: Install and adopt the Orca Agent Workflow from an existing coding-agent session, including missing Orca setup, merging project instructions and configuring real checks/runtime. Use for initial setup or a deliberate migration.
---

# Set up the Orca workflow

Make this repository usable with the Orca planning, scoped implementation, isolated
checks, fresh review and human merge workflow. Inspect the project and adapt the
kit to it. Ask only for choices you cannot infer from the request and repository.

This skill includes its own [Orca bootstrap helper](scripts/adopt.py). It works without the original starter
checkout. Resolve helper paths relative to this installed `SKILL.md`; never assume
scripts at the target repository root already belong to this kit.

## Bootstrap dependencies in this session

You can run setup from the user's current Claude Code, Codex or OpenCode session.
Orca is required to execute the installed workflow, but it need not be present to
start installation. Keep the current agent as the setup agent. Explain
[what Orca is](https://github.com/stablyai/orca) briefly when useful.

Ensure uv (including uvx), Git and Python 3.11+ exist, using an existing compatible interpreter or
installing missing tools through the platform's supported method within the
request. Node/npm is needed only for Skills CLI distribution; a temporary kit
checkout can provide this skill directly without Node. Inspect the target's rules
before changing files. Do not turn missing prerequisites into a separate manual
onboarding checklist when your tools can handle them.

On Windows, run the helper with `py -3` or the installed `python.exe` (`python3` is
often a Store placeholder), prefer `winget` for missing Python, Orca and Docker
Desktop, and make sure Orca's native `orca.exe` is on PATH; batch launchers are
refused because `cmd.exe` re-parses their arguments.

Inspect the bootstrap plan, then apply it when dependency installation/startup is
within the user's request. A request to inspect or explain setup alone does not
authorize installation.

```sh
python3 "<skill-dir>/scripts/adopt.py" bootstrap
python3 "<skill-dir>/scripts/adopt.py" bootstrap --apply
```

The helper reuses a ready runtime. On macOS with Homebrew, it installs a missing
app through `brew install --cask stablyai/orca/orca`; the official cask also exposes
the CLI. It can open an explicitly stopped runtime with `orca open --json` and
rechecks readiness. It does not force upgrades/reinstalls or restart a running
runtime, and it never starts a coding agent. Preview/apply of repository files
remain non-installing operations; only this explicit bootstrap application mutates
dependency state.

Resolve reported `remaining_steps` with your tools where possible. For platforms
or install methods outside automatic bootstrap, use [the official installers](https://www.onorca.dev/docs/install).
A new package manager is not required just for Orca; use a direct official release
installer when appropriate if the platform has no existing package manager.
For an existing app missing its CLI, use [the official CLI registration](https://www.onorca.dev/docs/cli/overview)
in Settings → General → Orca CLI instead of reinstalling. When a native permission,
first-launch/import choice or sign-in requires the user, explain the exact action
and resume afterward. Do not bypass OS security or change account settings on
their behalf. If runtime access is sandbox-blocked, use the client's normal
approval mechanism for the read-only check. Continue independent project work if
blocked and report operational readiness as incomplete.

The setup agent and later task coordinator are different roles. OpenCode can run
this installation, but the kit's enabled task-coordinator profiles are currently
Claude/Codex, and the implementation worker requires Claude Code. `--coordinator`
selects that later task provider, not the agent doing setup. Inspect the project's selected profiles and provider executables. Install missing supported clients within scope
and resolve actual account preferences with the user when essential. Do not leave
an unavailable template default silently presented as ready, or enable an
unsupported profile to avoid the choice. CLI presence is not account/model access.

Also check the project's required runtime and local Docker engine for gates. Use
existing installations. Where installation is requested and authorized, the agent
can install missing dependencies using official methods; OS/virtualization dialogs
may require the user. Keep existing Docker contexts and running services intact.

## Inspect and prepare

Read the target's instructions, README, relevant architecture/design docs and Git
status. Identify its actual stack, package manager, checks, existing workflow and
model preferences. Preserve application behavior and project-specific rules.

Use a feature branch for adoption. If the checkout has unrelated changes, leave
those intact and work from a clean committed baseline in an isolated checkout;
use Orca for workspace operations once ready and read its installed CLI guide. Do not stash, discard
or sweep unrelated changes into an adoption commit. Installing this skill may have
created untracked skill/lock files; identify them separately from pre-existing work.
Use the documented Skills CLI `--copy` install mode: gate snapshots require regular
files. If this skill's own installer-created adapter is a symlink, inspect it and
convert only that adapter to an equivalent copy; do not remove other project links.
Never launch another writer in an occupied checkout merely to do setup.

## Install and adapt

For a private pilot, preview the exact candidate wheel with
`uvx --from /absolute/path/to/candidate.whl orca-agent-workflow init --target /absolute/project --vendor`
and the project's stack, checks and coordinator. Vendoring ensures the installed
project uses the same candidate. After publication, preview the pinned package:

```sh
uvx orca-agent-workflow@0.2.0 init --target /absolute/project --stack other --check './scripts/test.sh' --coordinator codex
```

Inspect the proposed actions. Repeat the same command with `--apply` to install.
Select `--opencode` and `--pre-push-hook` only when requested. Use `--vendor` when
the team wants to review and commit the runtime. The Git-tag fallback is
`uvx --from git+https://github.com/diarsabri/orca-agent-workflow@v0.2.0 orca-agent-workflow init` with the same arguments.
Read the resulting `requires_merge` list and the candidates under
`.tmp/orca-agent-workflow/merge/` in the target project.

Merge each listed file with the project's rules, preserving useful custom behavior.
Read both versions: existing handoff/recovery procedures may contain capabilities
absent from the template. Merge role policies and project configuration, retaining
chosen available models and matching the selected coordinator to an enabled exact
planner profile. Keep Codex implementation disabled and Codex review disabled
unless this machine has passing qualification and enabling it is within scope.
Check the entire proposed file list; do not treat a partial copy as finished setup.
When merging `AGENTS.md`, retain its default task routing to the installed
`start-task` skill, including the lightweight-task, ongoing-task and explicit
worker/reviewer exceptions. Preserve `CLAUDE.md`'s shared-contract import and the
thin discovery adapters. This is what lets ordinary future task requests select
the workflow without a remembered kickoff prompt.

`init --apply` lists the managed files that must be executable. Windows file modes carry
no executable bit, so stage those with `git add --chmod=+x -- <paths>` before
committing; otherwise macOS/Linux checkouts and gate snapshots cannot run them.

Configure the checks and `gates` in `.agents/workflow.json` (Dockerfile/build inputs) for
this application's runtime. The starter image has Python standard library, Git
and make only. A Lua project needs its required Lua version; a Node app needs its
package manager and dependencies. An existing host interpreter or ignored local
dependency folder will not appear in a fresh worktree/container. Add relevant
runtime/build paths to the project's sensitive-file policy when needed. See
[adoption details](references/adoption.md) for dependency and validation decisions.

## Verify and hand back

Run the contract check (`python3 .agents/workflow.py check`), prerequisite discovery
(`python3 .agents/workflow.py doctor`) and meaningful application checks in the reviewed gate
environment when available. The kit's own tests and link checks are not installed.
For Apple simulator tests, give `native-check --destination` the platform and device UUID,
for example `platform=iOS Simulator,id=<UUID>` from `xcrun simctl list devices available`.
Review the complete diff, including any previously existing custom instructions.
Keep the version pin in `.agents/workflow.json`. Do not inherit the kit's
release validation claims or claim model access from executable presence.

Follow this project's authorization for scoped commits and PR publication. Leave
merge to the user. Do not start workers, change global account settings or install
Git hooks merely to finish setup. If Docker, a runtime or client qualification is
missing, finish independent configuration work and state exactly what is unverified.

Show the three revisions printed by `python3 .agents/workflow.py status`.
A new workspace inherits committed HEAD. The default Docker gate reads policy
and build inputs from the locally recorded origin default branch. A new worker
trusts the merge base of HEAD with origin/HEAD. For a bootstrap check, inspect
the exact committed policy, Dockerfile and build inputs first, then run
`python3 .agents/workflow.py gate --ref REVIEWED_SHA 'PROJECT_CHECK'` with the
project's real command. Record this as a check of that explicit revision.
After the user integrates adoption, refresh the default branch reference and
verify policy at both default revisions from the intended task checkout. A
diverged task branch can still have an older merge base. Preserve local commits
and existing coordinator sessions while verifying that transition.

After adoption is committed, reuse an open project coordinator and have it read
the merged `AGENTS.md` and `start-task` skill. If setup is handing the user into
Orca for the first time, check `python3 .agents/workflow.py start --help` for
`--wait-for-task`. With a runtime that supports it, run that option once
from the clean checkout containing the adoption commit. With published 0.2.0,
launch from the main checkout once it contains that commit. The fixed launcher
also supports linked workspaces and uses their current commit as the base.
Report the workspace and session shown in the receipt, the checks that passed and any remaining prerequisites. The coordinator asks for
the first task there. If the launch receipt is uncertain, inspect Orca before
retrying. Use `orca worktree list --repo path:/absolute/main-checkout --json` and
`orca terminal list --worktree path:/absolute/checkout --json` to locate the
existing coordinator. With an older runtime, use
`start "Your task"` when the user has a task. For an installation-only request,
report the command for later use.
