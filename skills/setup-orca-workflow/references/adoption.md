# Adoption decisions

Read this when merging custom workflow files or configuring a non-default runtime.
The target project's instructions and the user's actual request govern the work.

## Required Orca installation

Orca's official project is https://github.com/stablyai/orca and its installation
guide is https://www.onorca.dev/docs/install. The upstream macOS Homebrew command
is `brew install --cask stablyai/orca/orca`; the full cask name identifies the
correct app. Use official release downloads for other platforms. Keep these links
in the application's onboarding so future contributors know the dependency.

Check `prerequisites --check-runtime` using the installed helper. Missing CLI and
unreachable runtime are distinct conditions. Installation/first-launch work follows
the user's authorization and system prompts; preview/apply perform neither.
A reachable Orca runtime does not prove model availability, qualification or Docker
readiness. Report those separately. Offline file preparation can proceed without
Orca, but task execution must remain explicitly unready until it is available.

## Existing instructions and earlier workflow versions

Review generated merge candidates alongside existing project policy. `AGENTS.md` should combine the project's real constraints
with the kit mechanics. `CLAUDE.md` should retain necessary provider guidance and
load the shared contract. Keep one clear route for each capability; merge useful
handoff/recovery behavior rather than deleting a more capable local procedure.

An existing `.agents/workflow.json` is kept as it is; a project on the earlier layout
(`.agents/project.json` and role policies) needs `migrate` instead of setup.
Preserve additional project checks, selected model IDs, and deliberate disabled
profiles. Update the project and policy identities together. A selected coordinator
must match an enabled planner profile. Avoid inventing available model IDs; use
explicit preferences or explain the kit's examples and let local qualification
establish availability. Installation itself grants no new worker capability.

Merge the shared default task-routing rule into the application's `AGENTS.md`,
pointing to `.agents/skills/start-task/SKILL.md`. Preserve the explicit role bypass,
continuation behavior and lightweight-task path. Verify that all five shared
skills and their client adapters are installed; an unmerged custom `AGENTS.md`
is not completed automatic routing. Existing sessions need an instruction reload
or one explicit read of the updated contract; future sessions load project rules.

Inspect optional hooks and CI independently. The helper does not install a Git
hooks path or copy the starter repository's CI. Respect existing CI and checks.
Do not automatically replace the application's license; the kit's MIT notice is
installed separately in `.agents/LICENSE`.

## Runtime and dependencies

Find the actual check command in project docs/scripts. Detection suggestions are
not validation. Configure a reviewed Dockerfile plus explicit inputs in
the `gates` section of `.agents/workflow.json`, and include the package manager/lockfiles actually used.
Build dependencies into the trusted image; runtime checks stay offline without
host credentials or mounts. Review and commit trusted build inputs before using
a gate ref that includes them. Do not substitute a host test run for container proof.

For a Lua addon using `./scripts/test.sh`, inspect its interpreter lookup and pinned
version. If it requires Lua 5.1.5, the image must provide compatible `lua5.1` and
`luac5.1` commands or the exact expected paths. A checksum-verified source build is
one option. Ignored `.tools/` folders are not copied into gate snapshots. Offline
addon tests do not prove real-game compatibility.

For Node apps, inspect the lockfile and package manager version. Include the right
runtime, install dependencies during trusted image construction, and declare build
inputs explicitly. Do not claim Node support just because setup detected a
`package.json`. Follow the same reasoning for other runtimes.

## Validation and stopping points

Use the adopted project's commands, including:

```sh
python3 .agents/workflow.py check
python3 .agents/workflow.py doctor
python3 .agents/workflow.py start "Your task" --dry-run
```

Inspect project scripts before executing them. Run meaningful application checks
in the reviewed gate, and separately report any host checks. `workflow.py status`
checks configuration and local launch prerequisites; it does not verify accounts,
running Orca, scoped adapters or runtime dependencies. Local probes/qualification
are required before their corresponding worker launch, not replaced by setup.

After installation, classify the result as configuration complete, checks complete,
or prerequisites still missing using actual evidence. Preserve existing work when
something is unavailable; do not reset files or launch a model to manufacture a pass.
Commit only scoped adoption changes and publish a PR within authorization. Explain
that a newly generated project with no Git baseline needs one before task worktrees
can contain its files. Do not claim automatic kit upgrades: provenance records the
shipped snapshot; upgrades require a reviewed migration and deliberate pin updates.

## Maintaining the runtime pin

Review upgrades deliberately and keep the release version in the setup instructions
aligned with the package. Each application records its selected version in
`.agents/workflow.json`.
