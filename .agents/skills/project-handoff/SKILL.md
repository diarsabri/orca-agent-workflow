---
name: project-handoff
description: Preserve a task checkpoint and transfer an identified project session between clients when the user requests a handoff or client switch.
---

# Hand off a project task

Follow the project's instructions and any repository-specific handover policy.
Record the objective, acceptance criteria, exact worktree/branch/HEAD, changed and
unrelated files, verification with revision provenance, decisions, authorizations,
known owned processes and one concrete next action under `docs/handovers/`.
Reference durable specs and evidence rather than copying transcripts or secrets.

A checkpoint alone does not transfer ownership or prove exit. For an actual
client switch, identify the precise source and receiving session, capture final
state and verify the old writer stopped before the receiver edits. Use Orca's
installed handoff/recovery procedure, preserve supervised dispatch fences and
retain the existing checkout when work is uncommitted. Never use workspace-wide
agent closure or start another writer merely because a model is unavailable.

If the source has already hit a usage limit, use `session-recover` in the receiver;
do not ask the exhausted client for another model turn. A request to save a
checkpoint alone does not authorize closing a live session or launching another.
