# Validation record

This release extracts the reusable workflow mechanics from an internal pilot into
a fresh repository. The pilot's historical model sessions and local qualification
receipts are not shipped, and their results do not qualify another machine.

The public tree is checked with:

```sh
python3 -m unittest discover -s tests -q
python3 scripts/check_docs.py
python3 scripts/scan_public.py
python3 examples/offline_demo.py
```

The suite covers file scope/traversal, ignored and credential paths, sensitive
declarations, revision changes, paging, immutable reviewer inputs, model/profile
refusals, owned-child revocation, review-record consistency, scaffold conflict
handling, the installed file set and optional groups, the runtime tests run against
a freshly scaffolded project, gate configuration/snapshot restrictions,
and synthetic Claude/Codex history reading. No provider calls are made by the suite.

The local Docker check uses a trusted committed snapshot:

```sh
python3 .agents/workflow.py gate --ref FULL_REVIEWED_SHA \
  --self-test 'python3 -m unittest discover -s tests -q'
```

The two repository census checks need `.git`; they skip in a container checkout
archive and are covered on the host. A passing offline suite does not establish
live-client compatibility, model availability, universal native-client isolation,
or suitability for every project runtime. See [compatibility](compatibility.md).

GitHub CI runs the provider-free suite, documentation links, publication guard
and demo on pull requests and pushes to `main`. Feature-branch pushes use the PR
run, avoiding duplicate matrices. Any live model/client qualification must be recorded separately for the
actual installed versions and host, without committing private transcripts.

## Release checks, 2026-11-04

- 85 provider-free tests pass on the local Python 3.11 and Python 3.15.2 hosts.
- An independent read-only adoption pass verified preview, conflict handling,
  configured/unconfigured applications, idempotency, generated docs and license
  preservation. Its two initial findings were corrected and rechecked.
- The disposable local Docker self-test passes safe imports, runtime network denial
  and the credential-environment check. Its suite runs 85 tests successfully, with
  the two Git-census checks skipped as expected; both pass on the host.
- Four packaged shared skills pass frontmatter/reference validation. Local links,
  contract consistency, publication scanning and the offline example pass.
- These checks make no model calls. They do not add a new live-client qualification
  to the compatibility claims or ship any prior host's qualification receipts.

## Guided onboarding checks, 2026-11-04

- 98 provider-free tests pass on local Python 3.11.15 and Python 3.15.2, with no
  skips. Thirteen tests exercise guided adoption and the installed task entry point.
- Coverage includes real terminal prompts, project/check detection, optional model
  choices, conflict preflight, idempotency, Git bootstrap guidance, pinned task bases,
  safe argument passing, conditional Orca registration and uncertain launch receipts.
- The trusted local Docker image runs 98 tests: 92 pass and 6 skip. Two skips need
  Git metadata; four fake-executable launch tests require an executable temporary
  mount. The gate's temporary mounts stay `noexec`; those four tests pass on the host.
- Contract consistency, local documentation links, publication scanning and the
  offline demo pass. These checks make no model calls. Launch integration uses a
  synthetic Orca executable and does not claim a live provider qualification.

## Installable setup skill checks, 2026-11-04

- 107 provider-free tests pass without skips on local Python 3.11.15 and 3.15.2.
  Nine adoption tests cover relocated/project-local skill installs, committed-only
  source export, custom-file preservation, stale-plan refusal, idempotency,
  symlink/traversal handling and generated project contracts/docs.
- The trusted local Docker image runs 107 tests: 101 pass and the same six
  Git-metadata/noexec fixture checks explicitly skip; all six pass on the host.
- Skills CLI 1.7.6 installs only `setup-orca-workflow` in project scope for Claude
  Code and Codex using `--copy`. The installed helper fetches the immutable public
  runtime pin without a sibling starter checkout, prepares 53 managed candidates,
  and applies them to a disposable standard-library application. Its contract,
  24 documentation links and 64 application/workflow tests pass.
- An independent forward test adopted into an existing synthetic application,
  preserving custom project/provider instructions and handoff behavior. It passed
  the 63 installed workflow tests and 64 tests through the requested application
  command. Two onboarding/documentation issues were corrected and independently
  rechecked; generated onboarding then worked without manual repairs.
- Launch dry-run checks confirm readable multiline prompts without starting models.
- The real CLI/bootstrap smoke uses public package/source downloads. The automated
  suite stays offline and makes no model calls. No live provider session, worker
  qualification or actual application rollout is claimed by installation testing.

## Orca prerequisite checks, 2026-11-05

- 113 offline tests pass on local Python 3.11.15 and 3.15.2. Six new prerequisite
  tests cover missing/unchecked Orca, confirmed runtime reachability, failed or
  malformed status, timeouts and CLI exit behavior. Probe responses do not echo
  extra account/runtime fields.
- The trusted local Docker image runs 113 tests: 107 pass and the existing six
  Git-metadata/noexec fixture checks explicitly skip. The prerequisite tests pass
  without an installed Orca or runtime.
- A read-only check against the installed Orca reports its runtime ready. The
  probe runs only `orca status --json`; installation and first-launch choices are
  separate user actions. No software installation or model session was started.
- The macOS install command, CLI registration step and upstream links were checked
  against Orca's official installation and CLI documentation. Links, publication
  scanning, shared contract and skill-format validation pass.

## Agent-first setup checks, 2026-11-06

- 125 offline tests pass on Python 3.11.15 and 3.15.2. New bootstrap cases cover
  preview-only behavior, install/open/recheck ordering, existing app reuse, stopped
  versus active/unknown runtimes, failed or uncertain operations, missing CLI and
  unsupported automatic-install paths. A provider test covers OpenCode setup with
  missing future workflow clients and unverified model access.
- The trusted local Docker gate runs 125 tests: 119 pass and the existing six
  Git-metadata/noexec fixture checks skip. No host installer is invoked by tests.
- Skills CLI 1.7.6 installs the portable skill for Claude Code, Codex and OpenCode
  in a disposable project. The installed bootstrap preview reuses the host's
  already-ready Orca runtime with no actions. The Homebrew cask's CLI artifact and
  the supported `orca open --json` command were checked against upstream sources.
- An independent forward test used a virtual fresh macOS machine with Homebrew,
  Git/Python available, Node/npm and Orca absent. It exercised simulated bootstrap
  and local-source adoption in the existing agent, preserved custom instructions
  and dirty original work, and passed 63 workflow tests plus two application tests.
  A provider-choice ambiguity was corrected and rechecked: missing future clients
  and unverified account/model access are now explicit in the proposal.
- A fresh native OS installation, real first-launch permission dialogs and provider
  sign-in were not executed on the development host. Install/start operations use
  controlled fixtures; the host smoke is read-only. No new CLI model sessions or
  worker qualification is claimed. Other platform installers remain agent-guided.
- The manual scaffold and skill share the application-guide asset, so generated
  projects do not inherit source-only `INSTALL.md` links. Local links, shared
  contract, publication scanning, skill-format and formatting checks pass.

## Default task intake checks, 2026-11-09

- 126 offline tests pass without skips on Python 3.11.15 and 3.15.2. Adoption
  coverage verifies the new skill and both client entrypoints, rejects missing
  entrypoints, and blocks launch until a custom contract imports task routing.
- The trusted local Docker gate runs 126 tests: 120 pass and the existing six
  Git-metadata/noexec fixture checks skip. No provider calls or installers run.
- An independent instruction evaluation covers seven requests: a substantial
  feature, a question, a typo, an assigned implementer, a review request, a task
  follow-up and a dirty checkout. Its disposable scaffold, shared contract and
  local links pass. Review-role and dirty-checkout wording were clarified and
  rechecked. Scenario routing was simulated, not a live client dispatch test.
- Skill-format validation, shared contract, local links, publication scanning and
  the offline demo pass. Task selection remains instruction-based; these checks
  do not qualify providers or establish mandatory routing in every client.
- A relocated portable setup skill adopts its new immutable runtime pin into a
  disposable standard-library application without a sibling kit dependency. All
  56 managed candidates apply, 64 application/workflow tests and 25 documentation
  links pass, and the dry-run prompt uses `start-task`. No model session launches.

## Planner-based reviewer provider checks, 2026-11-09

- 135 offline tests pass on local Python 3.11 and 3.14.5. New gate cases cover
  a single-provider policy reviewing without a fallback, a required disclosed
  fallback reason once another provider's reviewer is enabled, rejected
  non-reasons, a Codex planner reviewed by Codex, an unrecorded or unknown
  or disabled planner, a malformed fallback (reported, not raised), a human
  planner with and without a fallback and a policy without the preference. A
  scaffold test rejects a policy missing it.
- Shared contract, local links and publication scanning pass. The trusted Docker
  gate runner, Codex reviewer launches and Codex qualification were not run.
- A fresh scoped Claude Opus 5.5 review of the first head passed with three
  non-blocking findings (planner corroboration, "model fallback" wording, the
  shared contract's reviewer sentence) and two test gaps; all were addressed.
  Its second review passed with five non-blocking findings (stale spec count,
  a crash on an unhashable fallback reason, no migration note, three test gaps,
  wording); all were addressed except the documented self-reported planner.

## Native Windows checks, 2026-11-09

- Windows 10 22H2, Python 3.12.10, Git for Windows 2.55, Docker Desktop 4.98:
  the full offline suite passes with seven skips: four interactive prompts that
  need a POSIX pseudo-terminal, two Codex qualification probes (POSIX-only by
  design) and the 8.3 short-name test (short names disabled on the volume). Contract, local links, publication scan and offline demo pass.
- The same tree passes in the Linux gate image (Python 3.11, network off) with
  eight skips: six Windows-only tests (broker paths and batch-launcher refusal)
  and two existing fixture skips.
- New Windows broker tests cover a junction swapped into an approved path, a
  junction swapped in after the reparse-point walk (caught by the opened handle's
  final path), alternate data streams, drive-relative and device names, trailing
  dots/spaces and a kill-on-close Job Object ending a client's child. The 8.3
  short-name test skipped because short names are disabled on the host volume.
- A disposable application adopted this branch natively on Windows: 57 managed
  files applied with LF endings and no merges; `apply` listed the two executable
  files, which committed as mode 100755; its installed suite passed. The broker's
  `validate`, `prepare` (installed Claude Code CLI) and `probe` passed all six
  checks, and the frozen MCP server served an approved read and write over stdin
  and refused an unlisted read. No model session launched; Windows CI runs on push.

## Install trim, 2026-11-20

- A fresh `scaffold.py` install writes 39 files (adoption adds the provenance
  record): nothing under the application's `docs/`, `tests/` or `specs/`. Its
  installed `check_sync.py` and `doctor.py` pass. `--opencode` and
  `--pre-push-hook` add their groups, and `check_sync.py` checks OpenCode commands
  only once installed.
- The kit's `tests/agents` suite passes against the installed runtime of a
  scaffolded project, and the kit's link checker passes on an adopted project.
- The suite (151 tests, 6 skipped), local links, publication guard, contract check
  and offline demo pass on macOS with Python 3.14 and 3.11.

## Packaged runtime, 2026-11-20

- The runtime is the `orca-agent-workflow` package. `uv build` produces a wheel with
  every source and template file; installed from that wheel with `uvx --from`, `init
  --apply` writes 27 files into an empty project and its `check` and `doctor` pass.
- `init --vendor --apply` writes 74 files (the runtime under `.agents/runtime/`); the
  kit's `tests/agents` suite passes against that vendored copy.
- `migrate` converted a project made by the previous release's installer (`b4afa1e`):
  25 files unchanged, `workflow.json` and the launcher created, 4 docs and
  `AGENTS.md` listed for merge, 14 files listed as removable; its `check` passes.
- A dry run of `migrate` on a disposable copy of the pilot project (with
  no `project.json` or `gates.json`) wrote nothing and proposed 17 new files, 14
  merges, 16 removable kit files and 8 project files to review, keeping the
  project's customised gate Dockerfile.
- The suite, local links, publication guard, contract check and offline demo pass
  on macOS with Python 3.14 and 3.11.

## Fresh adopter pilot, 2026-11-21

A disposable Python project on macOS installed the vendored runtime from a local
wheel. The setup agent merged the project's existing `AGENTS.md` with the
generated instructions. The packaged `start` command opened a Codex coordinator
in Orca with the user-approved task. A scoped Claude implementer changed the two
application files listed in the spec. A fresh Claude reviewer examined the full
diff and the coordinator's test evidence and returned a passing verdict.

The host test initially passed while the Docker gate failed to import the
application. The implementer made the project import explicit in the test file.
The original gate command then passed all three tests without an environment
override. Both Claude sessions required a separate human folder-trust decision.

## First coordinator handoff, 2026-11-25

At `392fdc9`, a fresh disposable macOS app vendored the private candidate wheel. From its
clean adoption commit, `start --wait-for-task` opened the configured Codex
coordinator. It read the project instructions, asked for the first task and
waited. The checkout stayed clean. Orca's worktree and terminal inventories
matched the printed checkout path and session handle. Reactivating that checkout
reused the same coordinator.

A second, intentional launch supplied a read-only question. A test wrapper
withheld Orca's successful create receipt from the launcher. The launcher
reported uncertainty and exited. Looking up the workspace and terminal recovered
the original session, which had answered the question. Recovery issued no new
create request. The test covered local terminal sessions on this host. The
automated CLI fixture checks that the launcher displays the path returned by
Orca and reports uncertainty for an incomplete receipt.

At `7223cbb`, a new pilot rebuilt the wheel after the Sol planner policy landed.
The configured GPT-6.2 Sol terminal asked for the first task. The pilot repeated
the withheld-reply test for a typed task and located the original terminal.
The inventory showed the two intended workspaces, each with its original terminal.

## Native verification pilot

A disposable iOS app with a committed shared scheme and one XCTest adopted the
vendored candidate. The installer preview reported the Xcode project, shared
scheme and test target. The installed `native-check` passed one test with no
failures or skips using Xcode 27.2 on an iPhone 17 simulator. A separate check
with a missing required XCFramework failed before Xcode ran. Neither result
depends on the Docker gate.

Installing in the Python adopter without applying changes preserved its portable
test command and returned no Xcode suggestions. The kit's portable suite also
passed in the existing Docker gate. This pilot used a local simulator.
