---
title: Prepare source files for a fresh public snapshot
status: implemented
---

Generalize the starter kit's pilot references and CI gate naming patterns.
Existing literal protections must remain covered by the general patterns.
Adopters can record additional project-specific paths in their own policy.

## Acceptance

- The reviewed source no longer names private adopters or their individual CI
  gate paths. Default protections still cover the previously matched paths.
- A rehearsal export contains only the reviewed Git tree as one root commit.
  Sources and distributions retain the MIT license.
- Check paths and text in the export, wheel and source distribution with the
  publication guard and the private audit. Keep the denylist and audit evidence
  out of the exported repository.
- Run the installed wheel tests and inspect normal and vendored adoption in
  disposable projects.

The rehearsal is local. Final release also requires selecting and inspecting
the hosting destination and preserving access for deployments pinned to
commits in the private history.

GPT-6.2 Sol planned and implemented the source changes in the coordinator
session.

```agent-task
{
  "tier": "full",
  "implementer": {"read": [], "write": [], "sensitive": []},
  "review": {"read": ["scripts/scan_public.py"]}
}
```
