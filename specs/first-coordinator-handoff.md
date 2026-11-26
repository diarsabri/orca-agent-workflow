---
title: Hand a newly adopted project to its first coordinator
status: implemented
---

## Scope

After committing adoption, the setup agent can open the configured coordinator
before the user has chosen a task. The user supplies the first goal in that session. Setup directs the user
to a coordinator that is already open. The explicit launcher creates a worktree
on each invocation. Existing typed-task and interactive launches continue to work.

## Routing

GPT-6.2 Astra implemented the first handoff and pilot. After the maintainer
merged the Sol policy, GPT-6.2 Sol took up the task, clarified which session
users should open or reuse, and planned validation of the updated installer
against the merged coordinator default. The new base and head require review.

```agent-task
{
  "tier": "full",
  "implementer": {"read": [], "write": [], "sensitive": []},
  "review": {"read": []}
}
```

## Acceptance

- Install a candidate wheel in a fresh application and verify that the configured
  coordinator asks for the first task and waits.
- Report the workspace and session that Orca created. Exercise reuse and recovery
  from a missing reply without opening a duplicate coordinator.
- Verify typed-task launches and document the installation procedure for the
  runtime actually used. Obtain independent review of the committed change.
