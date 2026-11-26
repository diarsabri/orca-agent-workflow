---
title: Install only what the application needs
status: implemented
---

# Task brief

## Routing

Planner/coordinator: Claude `claude-opus-5-5`, implemented directly in this
repository on `feat/install-trim`, branched from `main` after #8 merges. No
implementation worker: most of the change is deletions and moves, which the
file-only worker cannot do. Reviewer: a fresh Claude `claude-opus-5-5` session,
the only enabled reviewer profile in the trusted base policy. The user
approved this spec in the coordinator session on 2026-11-20.

```agent-task
{
  "tier": "full",
  "implementer": {"read": [], "write": [], "sensitive": []},
  "review": {"read": [
    "specs/install-trim.md",
    "kit-files.json",
    "scaffold.py",
    "workflow.py",
    "skills/setup-orca-workflow/scripts/adopt.py",
    "skills/setup-orca-workflow/SKILL.md",
    "scripts/agents/check_sync.py",
    "tests/kit/test_scaffold.py",
    "tests/kit/test_setup_skill.py",
    "tests/kit/test_workflow.py",
    "AGENTS.md",
    ".agents/WORKFLOW.md",
    ".agents/README.md",
    ".agents/docs/task-permissions.md",
    "scripts/agents/task_plan.py",
    "scripts/agents/task_scope.py",
    "skills/setup-orca-workflow/references/adoption.md",
    "templates/project-gitattributes",
    "examples/offline_demo.py",
    "docs/architecture.md",
    "README.md",
    "INSTALL.md"
  ]}
}
```

## Goal and acceptance

The first thing a team sees when adopting the kit is the install diff. Today it
is 57 files spread over `docs/`, `tests/`, `scripts/`, `specs/`, `.githooks/` and
three client folders; the application's own test runner collects the kit's tests,
and its doc checks pick up the kit's docs. This change cuts the install to what the
workflow actually uses at run time and keeps it out of the application's `docs/`
and `tests/`.

Acceptance:

1. A default adoption (`scaffold.py`, and `adopt.py prepare`/`apply`) installs no
   kit tests, no human-facing kit docs, no kit release checks, no pre-push hook and
   no OpenCode commands, and writes nothing under the application's `docs/`,
   `tests/` or `specs/`. About 57 files become about 37.
2. Agent-facing docs move from `docs/agents/` to `.agents/docs/`, `WORKFLOW.md`
   moves to `.agents/WORKFLOW.md`, and the spec template moves to
   `.agents/skills/spec-and-delegate/references/spec-template.md`. All links and
   `check_sync.py` follow the moves; `specs/` is created only when the first spec is.
3. The project-specific getting-started guide becomes `.agents/README.md`; it links
   to the kit's architecture, compatibility and security docs at the installed
   version instead of copying them. `docs/validation.md` is no longer generated;
   `.agents/project.json` remains the record of the project's checks.
4. `--opencode` installs the OpenCode commands and `--pre-push-hook` installs the
   hook, on both `scaffold.py` and `adopt.py prepare`. `check_sync.py` checks
   OpenCode adapters only when `.opencode/commands/` exists.
5. The kit's CI still proves the installed runtime works: the kit's `tests/agents`
   suite runs against a fresh scaffolded project's runtime, on all three OSes.
6. Re-running the installer over an older adoption is still idempotent for managed
   files and never deletes anything; `.agents/README.md` lists the files earlier
   versions installed that can now be deleted.
7. The runtime (`scripts/agents/`, `workflow.py`) and the four configuration files
   stay where they are, byte-for-byte except for path references. The broker's
   trusted-policy lookup is unchanged.

## Context

Install-footprint findings in `docs/research/2026-11-adoption-distribution-providers.md`
section 4 (from #8). The research proposed moving the runtime into `.agents/orca/`
in this step; that is deliberately left out. The packaging step moves the runtime
out of the checkout entirely (pinned release, broker reading its policy from the
base commit), so moving it inside the checkout first would be churn that every
adopter has to re-review twice. Merging the four configuration files belongs to the
same packaging step, because it changes what the review gate's `policy_sha256` covers.

## Changes and scope

Coordinator, directly:

- `kit-files.json`: drop `tests/agents/*` (5), `docs/architecture.md`,
  `docs/compatibility.md`, `docs/security.md`, `docs/validation.md`,
  `docs/getting-started.md`, `scripts/check_docs.py`, `scripts/scan_public.py`,
  `.githooks/pre-push` and `specs/_TEMPLATE.md`; mark `.opencode/commands/*` and
  `.githooks/pre-push` optional; rename the moved paths.
- `git mv` `docs/agents/*` to `.agents/docs/*`, `WORKFLOW.md` to
  `.agents/WORKFLOW.md`, `specs/_TEMPLATE.md` to the spec-and-delegate references.
  The kit repository keeps its own `docs/`, `tests/`, `specs/` and release checks.
- `scaffold.py`, `skills/setup-orca-workflow/scripts/adopt.py`: optional groups and
  flags, `.agents/README.md` from the getting-started template, no
  `docs/validation.md`.
- `scripts/agents/check_sync.py`: new paths; OpenCode check conditional.
- `workflow.py`: doc references.
- Links: `AGENTS.md`, `CLAUDE.md` adapters, skills, `README.md`, `INSTALL.md`,
  setup skill and its references, `templates/`.
- Tests: `tests/kit/test_scaffold.py` (installed set, flags, no writes under
  `docs/`/`tests/`/`specs/`, runtime suite against the installed runtime),
  `tests/kit/test_setup_skill.py`, `tests/kit/test_workflow.py`.

## Sensitive files

None match `scripts/agents/sensitive.json` except `.gitignore` handling, which is
unchanged. Tier full because the change edits the installer and `check_sync.py`.

## Verification and operational permissions

`python3 -m unittest discover -s tests -q`, `python3 scripts/check_docs.py`,
`python3 scripts/scan_public.py`, `python3 scripts/agents/check_sync.py`; a fresh
scaffold into a disposable folder, listing its files and running its installed
`check_sync.py` and `doctor.py`; CI on Ubuntu, macOS and Windows.
Infrastructure/network/credentials/service operations: none beyond push and CI.

## Out of scope

Moving the runtime out of the checkout or into `.agents/orca/`, merging the
configuration files, an upgrade or uninstall command, deleting files from existing
adoptions, release packaging, and new providers.

## Implementation notes

Deliberate differences from the plan above, recorded for review:

- The project guide is a real file, `.agents/README.md`, moved from the setup
  skill's `assets/getting-started.md.tmpl`. Both `scaffold.py` and `adopt.py`
  previously replaced the kit's own `docs/getting-started.md` with that template;
  both special cases are gone. `adopt.py` hashes whichever guide the pinned kit
  installs, so it still works with a kit pinned before this change.
- Kit docs are linked at `main`, not at the installed version: the guide is a
  static file, and `.agents/workflow-source.json` records the installed revision.
- The default install is 39 files (40 with adoption's provenance record), not
  about 37: the spec template and the project guide stay in the install.
- `scaffold.py` now ends a generated `AGENTS.md` with the application's checks
  instead of the kit's release commands. Before, only `adopt.py` did this, so the
  wizard installed the kit's `check_docs.py`/`scan_public.py` instructions.
  `adopt.py` keeps its rewrite for older pinned kits.
- `workflow.py setup` also takes `--opencode` and `--pre-push-hook`, so the wizard
  matches the other installers, and its exact-model error no longer points at the
  uninstalled `docs/compatibility.md`.
- `task_plan.py` gives implementers `.agents/docs/roles/implementer.md`; workers
  may read `.agents/` (the restriction there is on writes), as reviewers already do.
- `templates/project-validation.md` is deleted. The offline demo now creates the
  `docs/` and `specs/` folders it uses, because setup no longer creates them.
- The scaffold test's allowed skips include the Windows symlink-privilege reason
  (finding F4 of the #8 review).
- Remote adoption fetches the pin in `skills/setup-orca-workflow/references/source.json`,
  which cannot point at this change from inside it. Until a follow-up bumps the pin
  after merge, the shipped skill still installs the earlier layout and refuses the
  new flags with a clear error. The helper's fallbacks for an older kit are not
  exercised by a test.
