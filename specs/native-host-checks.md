---
title: Verify native Apple app tests on the coordinator host
status: implemented
---

The coordinator previews a new adopter's shared Xcode schemes, test targets,
test plans and dependency locks. The coordinator reviews the app's build
steps and chooses the scheme, simulator and required local artifacts. The host
check records its own evidence alongside the portable Docker checks.

## Acceptance

- Preview discovers native project metadata without running Xcode or changing
  the adopter's portable check settings.
- The coordinator can run simulator tests from a clean committed checkout. A
  successful result identifies the revision, Xcode, simulator and test counts.
- Report missing required artifacts, unavailable native tooling or destination,
  failing builds or tests, and zero executed tests as failures.
- Exercise a disposable iOS app and an existing portable adopter.

GPT-6.2 Sol planned and implemented the change directly in the coordinator
session. The scoped reviewer receives the diff and the coordinator's results.

```agent-task
{
  "tier": "full",
  "implementer": {"read": [], "write": [], "sensitive": []},
  "review": {"read": ["src/orca_agent_workflow/run_gates.py"]}
}
```
