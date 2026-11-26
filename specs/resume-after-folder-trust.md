---
title: Resume the initial scoped dispatch after Claude folder trust
status: implemented
---

On a local macOS Orca host, the coordinator can arm one initial dispatch for a
prepared Claude implementer or reviewer. The user makes the trust decision in
the provider UI. The coordinator observes readiness and sends the approved
brief only after the expected terminal and scope match.

## Acceptance

- A trust prompt does not deliver a brief. Confirm readiness in the captured
  terminal and scope after the user approves. Stop on exit, other blockers or
  an identity mismatch.
- Keep the intent across an interrupted wait. Preserve the attempt before
  sending and require Orca recovery if the result is uncertain.
- Test the interruption and duplicate-delivery conditions for both role
  labels. Record which roles were exercised live separately.

GPT-6.2 Sol planned and implemented the change directly in the coordinator
session. The scoped reviewer receives the diff and the coordinator's results.

```agent-task
{
  "tier": "full",
  "implementer": {"read": [], "write": [], "sensitive": []},
  "review": {"read": ["src/orca_agent_workflow/task_scope.py"]}
}
```
