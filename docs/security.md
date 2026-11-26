# Scope and security model

The primary control is the exact file scope from a user-approved committed spec.
The fixed backstop protects credentials, workflow controls, ignored paths and
root-level Python modules that could shadow test tools. Gate/build/deploy inputs
are sensitive: the spec names them with a reason, the manifest marks them, and
the reviewer explicitly covers their complete diff.

The Claude adapter removes the normal tool surface and exposes the scoped file
broker. It is an experimental capability arrangement, not a claim of a universal
operating-system sandbox. Recheck flags and the effective client configuration on
each supported client version. Never fall back to an unrestricted session when
preparation, probing, model selection or lifecycle checks fail.

On Windows the broker cannot open files relative to a directory handle. It refuses
reparse points (symlinks, junctions, mount points) at every path component, refuses
names Windows reinterprets (alternate data streams, drive-relative paths, device
names, trailing dots or spaces), then reads the real path of the handle it actually
opened (`GetFinalPathNameByHandleW`) and refuses unless it is exactly the approved
path, so a swap between the checks and the open cannot redirect a read or write.
One residual differs from POSIX: if another local process swaps a junction in that
window during a *new-file* write, an empty file may be left at the swapped target
before the refusal; no content is written and no existing file is read or changed.
Workers cannot create reparse points themselves. The supervisor places the client
in a kill-on-close Job Object so revocation also ends the broker process it started.
The client is assigned just after it starts, so a child it spawns in that instant
can outlive the job; that only affects cleanup, because a broker refuses every call
once the scope is revoked. The broker calls only a native `orca.exe`, never a batch
launcher, because `cmd.exe` re-parses arguments that carry worker-written text.
On Windows a bare program name is searched in the current folder first, which is
often the branch under test, so Git, Docker and Claude are resolved only from absolute
PATH entries outside the checkout. `prepare` pins and hashes the `claude` it finds;
with an npm `claude.cmd` shim that is the shim, not the client code, so prefer the
native `claude.exe` install.

Codex review uses a separate named filesystem permission profile and frozen inputs.
The adapter checks its saved local qualification against the installed binary,
profile and adapter. The probes sample important denials and do not establish
complete native-client isolation. Keep implementation disabled until separately
qualified. Reviewer inputs remain untrusted text even when copied into a snapshot.

The gate container runs without runtime network, bind mounts, forwarded host
environment, privileges or a writable root filesystem. It receives regular files
from a Git-selected snapshot; ignored files, credentials and local data roots are
omitted. Symlink snapshots are refused. The trusted image **build** may use network;
review that Dockerfile and its declared inputs before building it. Do not use an
unreviewed worker-edited build definition as authority.

Dependency bootstrap runs in the user's existing setup agent, before any confined
worker dispatch. Only explicit `bootstrap --apply` performs its supported app
installation/startup; preview and file adoption remain separate. It uses the
upstream Homebrew cask on supported hosts, preserves existing installations, and
reports uncertain outcomes without automatic retries. OS permissions, first-launch
choices and account access are not bypassed or inferred from a successful install.

Policy is read from a reviewed commit, not the working tree. Each manifest records
`policy_base`, and `scope prepare` reads `.agents/workflow.json` with
`git show <policy_base>:` before freezing the roles policy into the bundle; the review
gate reads it at `--base` and refuses unless its own version equals that commit's
runtime pin. A branch that edits `.agents/workflow.json` or `.agents/workflow.py`
therefore gains no authority until the edit is reviewed and merged. The launcher in
the checkout is the coordinator's convenience, not a trust anchor: run the review
gate at the base's pinned version. The runtime lives outside the checkout (or in
`.agents/runtime/`, which workers cannot write), so workers do not see the broker.
`uvx` resolves the pinned version from PyPI, which never reuses a version number;
it does not pin a hash. Teams that must review every line vendor the runtime.

This kit is intended for a trusted local coordinator operating a reviewed project.
It is not a multi-tenant service or a guarantee against hostile native clients,
malicious local users, compromised tools or a dishonest coordinator. Records and
hashes are operator-controlled. `review-gate` checks consistency and successful
completion; it does not authenticate model authorship or enforce GitHub settings.

Keep `.tmp/`, provider histories, credentials and qualification receipts local.
Neither a passing test nor a review grants deployment, data migration, provider
activation or permission expansion. Reviewers and workers cannot grant those rights.

To report an issue, avoid attaching transcripts or credentials to a public issue.
Use the repository's private vulnerability reporting channel when it is available.
