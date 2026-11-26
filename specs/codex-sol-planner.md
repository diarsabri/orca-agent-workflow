---
title: Select GPT-6.2 Sol for Codex planning
status: implemented
---

The maintainer selected the exact Codex planner model `gpt-6.2-sol` for cost.
The coordinator applied that choice to this repository and the new-project
template. Existing project installations keep their local policy until upgraded.
The reviewer and implementer roles retain their current settings.

## Acceptance

- Both enabled Codex planner entries name `gpt-6.2-sol`.
- A new project installed with `--coordinator codex` uses that model in its
  task launch preview.
- Preserve the actual planner recorded for earlier tasks.

```agent-task
{
  "tier": "full",
  "implementer": {"read": [], "write": [], "sensitive": []},
  "review": {"read": []}
}
```
