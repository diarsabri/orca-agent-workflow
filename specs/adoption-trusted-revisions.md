---
title: Explain the revisions used for first adoption
status: implemented
---

An adopter can commit the workflow on a feature branch while its default branch
still predates adoption. A coordinator must distinguish the commit a new workspace
inherits from the commits trusted by the Docker gate and by a worker.

- Show the three local revisions and availability of their policy in installer
  preview and status. A missing default branch or policy must remain visible.
- Explain how to verify an explicitly reviewed bootstrap revision and how to check
  both default revisions after integration, preserving existing work and sessions.
- Exercise the uncommitted, committed pre-integration and integrated states.
  Default operations must keep using their original trusted refs.

## Routing

GPT-6.2 Astra wrote the initial implementation. After the maintainer merged
the Sol policy, GPT-6.2 Sol took up the task and revised the plan and behavior for
missing default refs and explicit reviewed revisions. The gate and worker keep
the same trusted-ref selection. The new base and head require a fresh review.

```agent-task
{
  "tier": "full",
  "implementer": {"read": [], "write": [], "sensitive": []},
  "review": {"read": ["src/orca_agent_workflow/run_gates.py", "src/orca_agent_workflow/task_plan.py"]}
}
```
