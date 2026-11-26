# Preparing and supervising scoped work

Use the project's `sensitive_patterns` list in `.agents/workflow.json` for
custom build, verification and deployment paths. The runtime also marks CI
gate scripts under `scripts/` and those in `tests/` subdirectories that match its
default naming patterns. Review the adopter's own build and deployment inputs
when configuring its policy.

The coordinator runs these commands; the implementer does not receive shell access.
Use exact paths emitted by `plan`. Read `.agents/workflow.json` for an enabled
exact model ID before preparation. The manifest names the reviewed commit whose
`.agents/workflow.json` is trusted (`policy_base`: the merge base with `origin/HEAD`
for implementers, or `--base`); `prepare` reads the policy from that commit, never
from the working tree. The bundle is a new private folder outside the checkout.

```sh
python3 .agents/workflow.py plan --spec specs/TASK.md --role implementer
python3 .agents/workflow.py scope prepare \
  --manifest .tmp/agent-tasks/HEAD-implementer/scope.json \
  --bundle /absolute/private/task-bundle \
  --harness claude --model EXACT_CLAUDE_MODEL
python3 -I /absolute/private/task-bundle/task_scope.py probe \
  --manifest /absolute/private/task-bundle/manifest.json \
  --bundle /absolute/private/task-bundle
python3 -I /absolute/private/task-bundle/task_scope.py launch \
  --manifest /absolute/private/task-bundle/manifest.json \
  --bundle /absolute/private/task-bundle --harness claude
```

Launch the frozen adapter inside the intended Orca terminal, then attach that
exact terminal to the task through the installed orchestration procedure. Deliver
the emitted brief with its exact Task and Dispatch IDs. Set `ORCA_CLI` only when
the `orca` executable is not discoverable on PATH. An override changes which
coordinator CLI is trusted; review it as local configuration.

On a local macOS Orca session, after the scoped Claude client appears, the
owning coordinator can wait through the provider's folder-trust screen:

```sh
python3 .agents/workflow.py resume-dispatch \
  --bundle /absolute/private/task-bundle --terminal CLAUDE_TERMINAL \
  --run RUN_ID --brief /absolute/path/to/brief.md --title 'Review the change'
```

Select trust in the Claude tab. Orca must report the intended terminal ready
before the helper sends the brief. An interrupted wait can be resumed with the
same command, terminal, bundle and brief. If dispatch was already attempted,
inspect the saved receipt in the bundle and the original run. Use Orca's
documented recovery for that task if delivery is uncertain. A rejected trust
prompt or a dead or replaced client needs a new scoped launch after inspection.

The probe checks an approved read/write, denied unlisted sibling read, read-only
write, traversal and execution. It uses synthetic files, not real secrets. A
passing probe is a required local broker check, not proof of every native-client
capability. Preparation pins the client/interpreter entry points; launch rechecks
the complete bundle and executable hashes. A changed/missing input blocks launch.

Workers can only create/overwrite exact approved files. Directory creation,
renames, deletions, tests and gate outputs belong to the coordinator. Paths under
workflow control directories, instruction Markdown files beginning `AGENTS` or
`CLAUDE`, root-level Python modules, ignored paths and credential patterns are
protected. Sensitive files are declared separately in the approved spec and scope.
Use source layouts such as `src/` for application Python modules.

The supervisor owns exactly its new child. Completion, expiry or revocation ends
the grant and closes that child. To revoke it, use the supported operation:

```sh
python3 -I /absolute/private/task-bundle/task_scope.py revoke \
  --bundle /absolute/private/task-bundle
```

Read `controller.json` and corroborate actual exit before another writer takes
over. Native-client exit and logical Orca assignment settlement are separate.
Use Orca's guarded stop/release protocol for owned workers; a legacy externally
created terminal can require separate explicitly authorized exact-session cleanup.
Never infer exit from a quiet screen or a quota error.

## Codex reviewer

The reviewer profile starts disabled on a new project. From that checkout:

```sh
python3 .agents/workflow.py codex-review qualify
```

Inspect every result, absent target, installed-binary path, profile and adapter
digest in `.tmp/agent-qualification/codex-reviewer.json`. Requalify after those
inputs change. This is a local host decision; no qualification ships with the kit.
After accepting the disclosed [evidence limits](https://github.com/diarsabri/orca-agent-workflow/blob/main/docs/compatibility.md), deliberately
enable only the reviewer profile in the approved policy.

```sh
python3 .agents/workflow.py plan --spec specs/TASK.md --role reviewer --base FULL_BASE_SHA
python3 .agents/workflow.py codex-review run \
  --manifest .tmp/agent-tasks/HEAD-reviewer/scope.json \
  --brief .tmp/agent-tasks/HEAD-reviewer/brief.md \
  --out .tmp/agent-reviews/HEAD/codex
```

The adapter freezes permitted Git blobs/evidence into a separate folder, denies
writes and network through its qualified permission profile, supervises only its
owned child, and stores the report/events/receipt under the output path. Model
identity is client-recorded turn context and must be disclosed in the record.
Read long inputs in bounded pages and verify complete coverage. A truncated or
incomplete review remains blocked; preserved summaries do not replace the raw diff.

## Coordinator gates

Review the `gates` section of `.agents/workflow.json`, its Dockerfile and explicit
inputs at the trusted ref.
Do not use a worktree Makefile as the outer launcher. Build may use network; the
runtime receives no network, host environment or bind mount.

```sh
python3 .agents/workflow.py gate --ref FULL_TRUSTED_SHA --self-test 'python3 -c "print(1)"'
```

Default ref is origin's default branch (`origin/HEAD`), so the branch under test never
supplies its own gate image; pass `--ref` to pin another reviewed ref. The initial
standard-library image needs project-specific dependencies before it can run an
application's checks. New Dockerfiles,
dependencies or runtimes require review and fresh checks. Container operations
must target a demonstrably local disposable endpoint under the task's authorization.
