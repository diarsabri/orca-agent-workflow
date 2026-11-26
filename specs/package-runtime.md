---
title: Ship the runtime as a pinned, installable package
status: implemented
---

# Task brief

## Routing

Planner/coordinator: Claude `claude-opus-5-5`, implemented directly in this
repository in two PRs (A: package, configuration and trust; B: release and
distribution). No implementation worker: the change moves and restructures the
runtime the file-only worker depends on. Reviewer: a fresh Claude `claude-opus-5-5`
session per PR, the only enabled reviewer profile in the trusted base policy.
Decisions taken by the user on 2026-11-20: PyPI with `uvx`; package and command
`orca-agent-workflow`; vendoring kept as an opt-in. The user approved this spec in
the coordinator session on 2026-11-20.

```agent-task
{
  "tier": "full",
  "implementer": {"read": [], "write": [], "sensitive": []},
  "review": {"read": [
    "src/orca_agent_workflow/task_scope.py",
    "src/orca_agent_workflow/task_plan.py",
    "src/orca_agent_workflow/review_gate.py",
    "src/orca_agent_workflow/run_gates.py",
    "src/orca_agent_workflow/codex_review.py",
    "src/orca_agent_workflow/check_sync.py",
    "src/orca_agent_workflow/cli.py",
    "src/orca_agent_workflow/install.py",
    "src/orca_agent_workflow/migrate.py",
    "src/orca_agent_workflow/start.py",
    "src/orca_agent_workflow/template/agents/workflow.py",
    "src/orca_agent_workflow/template/agents/workflow.json",
    "skills/setup-orca-workflow/scripts/adopt.py",
    "pyproject.toml",
    ".agents/workflow.json",
    "tests/kit/test_init.py",
    "tests/agents/test_task_scope.py",
    "tests/agents/test_review_gate.py",
    "docs/security.md",
    "docs/architecture.md"
  ]}
}
```

The read list above is PR A's; PR B gets its own when its spec section is planned.

## Goal and acceptance

Today every adopting project carries the kit's runtime (`scripts/agents/`,
`workflow.py`) and four configuration files, owns code it did not write, and
re-reviews it on every upgrade. After this change a project holds configuration,
skills and agent docs; the runtime is a versioned package that the project pins.

### PR A: package, configuration and trust

1. **Package.** `src/orca_agent_workflow/` (standard library only, Python 3.11+)
   with a `pyproject.toml` and one command, `orca-agent-workflow`, also runnable as
   `python -m orca_agent_workflow`. Subcommands replace today's scripts one for one:
   `init`, `start`, `status`, `check`, `doctor`, `plan`, `scope prepare|probe|launch|serve`,
   `gate`, `review-gate`, `codex-review`, `migrate`. `task_scope` stays a single
   self-contained module, because `prepare` copies it into each bundle.
2. **One configuration file.** `.agents/workflow.json` replaces `project.json`,
   `orchestration.json`, `gates.json` and `sensitive.json`. It records the project
   (name, repository, stack, checks, coordinator), roles, the reviewer-provider
   preference, gates, project-specific sensitive patterns, and the runtime pin
   (`{"package": "orca-agent-workflow", "version": "X.Y.Z"}`). The default sensitive
   patterns and the default gate Dockerfile ship in the package for that version;
   a project adds patterns or names its own reviewed Dockerfile.
3. **Smaller install.** A default `init` writes about 25 files and no runtime code:
   `.agents/workflow.json`, `.agents/workflow.py` (launcher), the skills, agent docs
   and guide under `.agents/`, the Claude adapters, and merged `AGENTS.md`,
   `CLAUDE.md` and ignore/attribute lines. Nothing in `scripts/`, `docs/`, `tests/`
   or `specs/`. `--opencode` and `--pre-push-hook` work as today. `init` previews by
   default and writes with `--apply`, preserving every existing file and listing
   semantic merges, as `adopt.py prepare/apply` does now.
4. **Pinned runtime.** `.agents/workflow.py` (about 40 lines) runs the pinned
   version: the vendored copy if present, otherwise
   `uvx orca-agent-workflow@<pin>`. Every subcommand refuses to run when its own
   version differs from the pin and prints the command that runs the right one.
   Skills and docs use `python3 .agents/workflow.py <command>` everywhere.
5. **Trust from the base commit.** `scope prepare` and `review-gate` read the
   policy with `git show <base>:.agents/workflow.json` (base recorded in the
   manifest or passed explicitly), never from the working tree and never from a
   file beside the runtime. The review gate refuses unless the running version
   equals the base's pin. A branch that edits `.agents/workflow.json` or
   `.agents/workflow.py` gains nothing until that edit is reviewed and merged.
   Workers no longer see runtime code in their checkout.
6. **Vendored mode.** `init --vendor` copies the package into
   `.agents/runtime/orca_agent_workflow/`, which the launcher prefers. The runtime
   test suite passes in both modes, on Ubuntu, macOS and Windows.
7. **Migration.** `migrate` converts a v1 adoption (the four configuration files,
   `scripts/agents/`, `workflow.py`) into v2: it previews, writes only with
   `--apply`, never deletes, and lists the files that can then be removed. Tested
   on a fixture produced by the previous release's installer, and run as a dry run
   on a real adopted project before release.
8. **Versioned doc links.** `init` renders kit-doc links in the installed guide
   and workflow at the pinned version's tag instead of `main` (#9 review F2).
   `docs/compatibility.md` notes that an npm `claude.cmd` shim pins only the shim
   (#8 review F1).

### PR B: release and distribution

9. **Release workflow.** On a `v*` tag, GitHub Actions builds the sdist and wheel,
   runs the suite against the built wheel on all three OSes, and publishes through
   PyPI trusted publishing (no stored token). Creating the PyPI project and the
   publisher, and pushing the first tag, are the user's actions.
10. **Install path.** README, `INSTALL.md` and the setup skill use
    `uvx orca-agent-workflow@<version> init`. The skill keeps its Orca bootstrap;
    its kit export and `prepare/apply` are replaced by `init`. A git-tag form
    (`uvx --from git+https://github.com/diarsabri/orca-agent-workflow@v<version> ...`)
    is documented as the fallback.
11. **Supply chain stated plainly.** Docs say what the pin guarantees (PyPI never
    reuses a version number; releases are built and attested by this repository's
    workflow) and what it does not (no hash pinning through `uvx`; vendored mode
    for teams that need to review every line).

## Context

`docs/research/2026-11-adoption-distribution-providers.md` section 7, phase 3;
the trimmed layout from #9. The runtime is about 2,900 lines over ten files.
Today `task_scope.prepare` falls back to `../../.agents/orchestration.json` beside
its own file, and the review gate's trusted copy is extracted from the base by
hand; both become explicit base reads. `review_gate.policy_sha256` will cover the
whole `workflow.json` from the base, so a change to checks or roles invalidates
records made under the old configuration, as a policy change does today.

## Changes and scope

PR A, coordinator: `git mv scripts/agents/*.py` into `src/orca_agent_workflow/`;
new `__main__.py`, CLI dispatcher, `pyproject.toml`, `.agents/workflow.py`,
`migrate`; `scaffold.py` and `workflow.py` setup logic move into `init`; the
gate Dockerfile and default sensitive patterns move into package data; tests move
with their modules and gain installed-wheel and vendored runs; `kit-files.json`
becomes the package's install manifest; skills, agent docs, README, architecture,
security, compatibility and validation docs follow. The kit repository runs
itself from source through the same launcher.

PR B, coordinator: `.github/workflows/release.yml`, CI wheel jobs, setup skill
(`SKILL.md`, `adopt.py` reduced to Orca bootstrap plus `init`), `INSTALL.md`,
`README.md`, `docs/getting-started.md`.

## Sensitive files

- `src/orca_agent_workflow/task_scope.py`: the worker boundary; its policy
  source changes.
- `src/orca_agent_workflow/review_gate.py`: what counts as reviewed.
- `src/orca_agent_workflow/run_gates.py` and the packaged Dockerfile: trusted
  gate inputs.
- `.agents/workflow.py`: decides which code runs.
- `.github/workflows/ci.yml`, `.github/workflows/release.yml`: what CI proves and
  what gets published.

## Verification and operational permissions

Each PR: the full suite on Python 3.11 and the current host Python; contract,
link and publication checks; the offline demo; CI on all three OSes. PR A also:
a fresh `init --apply` and `init --vendor --apply` into disposable projects, each
running `check`, `doctor`, `plan` and `scope probe`; `migrate` on the v1 fixture
and as a dry run on a disposable copy of the pilot project. PR B also: build and install the
wheel locally with `uvx --from dist/…whl`, and a TestPyPI dry run only if the user
sets one up. Network: GitHub, and PyPI/TestPyPI reads. Publishing to PyPI happens
only from the release workflow after the user configures it.

## Out of scope

The per-launch Claude trust prompt, guided Codex qualification, new providers,
an Orca listing, hash-pinned installs, and automatic upgrades between versions.

## Implementation notes (PR A)

Deliberate differences from the plan above, recorded for review:

- **Manifests are version 3** and carry `policy_base` (the commit whose
  `.agents/workflow.json` is trusted) and `sensitive_extra` (that commit's project
  patterns). Implementers default to the merge base with `origin/HEAD`; with no
  `origin/HEAD`, `plan` asks for `--base` rather than trusting `HEAD`.
- **Review gate and pin check.** The CLI refuses any command whose version differs
  from the working tree's pin, except `init`, `migrate` and `review-gate`;
  `review-gate` instead compares itself with the base commit's pin, because a branch
  must not be able to choose the validator. `codex-review run` also reads the
  policy from the manifest's base unless a copy is passed with `--policy`.
- **Launcher.** `.agents/workflow.py` changes to the project root before running,
  so documented relative paths work from anywhere. It accepts a runtime folder from
  `ORCA_AGENT_WORKFLOW_RUNTIME` (the user's own environment, like `PATH`), used by
  tests and until the first release exists. `check` and `doctor` work before
  `git init`.
- **Template location.** The installed files live in the package under `template/`
  with leading dots dropped (packaging skips dotfiles); the kit's own copies must
  match them, which `test_init` enforces. `scripts/check_docs.py` skips the stored
  template, whose links are checked after installation instead.
- **Interactive wizard removed.** `workflow.py setup` (prompts, `--advanced` model
  questions) is gone; `init` takes flags and project detection, and models are
  edited in `.agents/workflow.json`. The default project name is title-cased.
- **Merges.** `init` writes a candidate for every differing file under
  `.tmp/orca-agent-workflow/merge/` instead of refusing (scaffold) or staging in a
  scratch folder (adopt). The setup helper's plan records each target file's digest
  and the runtime's tree digest, and `apply` re-runs the same `init` only if both
  are unchanged.
- **Setup helper.** `adopt.py prepare/apply` now drives the pinned kit's `init`
  and refuses a kit revision without the package. Like #9, remote adoption needs a
  pin bump right after merge; until then the shipped pin (pre-package) is refused
  with a clear message. PR B replaces the Git export with `uvx`.
- **Migration of pilot layouts.** `migrate` also accepts a project with only
  `.agents/orchestration.json` (a pilot layout), keeps a customised gate
  Dockerfile, and separates files only the kit installed (`removable`) from generic
  names and the project's own files in shared folders (`review_before_removing`).
  The pilot dry run surfaced both cases.
- **Gate image.** `gates.dockerfile: null` builds the packaged `gate.Dockerfile`;
  a project names its own reviewed Dockerfile to change it.
- **Independent review fixes.** With `gates.dockerfile: null` and the runtime inside
  the checkout (the kit's `src/`, a vendored `.agents/runtime/`), the default image
  is read from the trusted ref, not the working tree. `src/orca_agent_workflow/` is
  workflow control, so no worker can be granted writes to the kit's runtime. A
  review gate running from inside the checkout refuses unless every one of its files
  matches the base commit, and the docs show how to run the base's copy.
- **Bootstrapping this PR's own review.** The base (`main` before this PR) has no
  `.agents/workflow.json`, so this PR is planned, prepared and gated with the
  base's `scripts/agents/` tooling and `orchestration.json`, extracted from the base
  commit; `policy_sha256` is that file's digest. Later PRs use the packaged runtime.
- **Installed-wheel test.** The wheel was built and run by hand here; its automated
  run on all three OSes is part of PR B's release CI.
