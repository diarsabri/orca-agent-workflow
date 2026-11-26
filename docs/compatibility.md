# Compatibility and evidence

The source workflow was exercised in an internal macOS pilot. This extracted kit
has its own fixture, scaffold and local-container checks. A new project or host
must repeat relevant qualification rather than inherit the pilot's receipts.

| Surface | Current support | Required before real work |
| --- | --- | --- |
| Planner/coordinator | Claude or Codex using shared files and Orca CLI | Configure an available exact model; preserve project authorization |
| Claude implementer/reviewer | Experimental file-only adapter | Verify CLI flags, prepare and probe the exact bundle, retain lifecycle receipts |
| Codex reviewer | Opt-in, initially disabled | Run local qualification, inspect all results/absent targets, then deliberately enable the profile |
| Codex implementer | Disabled | A separately verified native-capability restriction; do not enable by editing a flag alone |
| OpenCode | Shared instructions, commands and handoff conventions | Confined worker dispatch has not been qualified |
| Gate runner | Local Docker, pinned Linux image; standard-library Python starter | Add and review application dependencies/runtime and real checks |
| Node/web gates | Not preconfigured | Supply and validate a project-specific trusted image |
| Windows native host | Supported: broker, gates, adoption and launcher; tested in CI | Docker Desktop for gates; Orca's native `orca.exe` on PATH. Codex review qualification remains macOS/Linux-only |
| Runtime | `orca-agent-workflow` package, standard library only, Python 3.11+ | [uv](https://docs.astral.sh/uv/) for `uvx`, or `init --vendor` to keep a copy in `.agents/runtime/` |

On Windows, `scope prepare` pins and hashes the `claude` it finds. An npm-installed
`claude.cmd` shim is the shim, not the client code it starts, so a changed client
behind an unchanged shim goes unnoticed; prefer the native `claude.exe` install.

The originating CLI interfaces were inspected on `codex-cli 0.166.0` and Claude
Code `2.1.309`. These are compatibility observations, not pinned installer
requirements or promises that every later version accepts the same flags.

The Codex adapter currently accepts only a versioned installation folder such as
Homebrew's version directory. It refuses an unversioned shared prefix. Its
qualification probes the CLI's `sandbox` command rather than every capability of
a live `exec` session. Missing targets are reported, and the operator must decide
whether that evidence is sufficient for the actual host. No saved receipt ships
with this repository.

Codex model evidence is client-recorded session turn context, not a server echo.
Document and accept that evidence level before enabling the reviewer. No provider
or model is claimed equivalent to another, and the examples may need account-
specific model IDs.

See [security](security.md) and [validation](validation.md) for the precise limits.

## Setup skill distribution

The standalone `setup-orca-workflow` skill is designed for Skills CLI installation
into Claude Code, Codex or OpenCode for installation. It contains its own helper, source pin and guide asset;
no original checkout is assumed. The other four skills remain project procedures
that depend on adopted project files. Use the documented `--copy` mode because
the gate snapshot rejects symlinks. A local skill install and model-free helper
smoke do not establish live provider compatibility or worker qualification.

## Agent-first dependency bootstrap

An existing coding agent can start setup without Orca or the Skills CLI installed.
`INSTALL.md` routes it to the portable skill; Git/Python are needed for its helper,
and Node/npm only for the optional Skills CLI path. OpenCode can run setup without
changing its unqualified confined-worker status.

Explicit bootstrap application automates missing Orca installation on macOS with
Homebrew and startup of a stopped runtime through the official CLI. Other native
platform/install methods remain agent-guided using upstream installers. No claim
of unattended OS permission handling or automatic provider-account setup is made.
On Windows, `workflow.py` refuses `.cmd`/`.bat` Orca launchers because `cmd.exe`
re-parses their arguments, and `init --apply` lists the files that need
`git add --chmod=+x` because Windows file modes carry no executable bit. Existing installations and running runtimes are
preserved; remaining setup actions are reported for resolution rather than hidden.
