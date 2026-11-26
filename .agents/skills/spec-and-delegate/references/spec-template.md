---
title: Describe the intended change
status: draft
---

# Task brief

## Routing

Record the exact enabled implementer and independent reviewer profiles selected
from `.agents/workflow.json`, and the coordinator/project worktree.

```agent-task
{
  "tier": "light",
  "implementer": {"read": [], "write": [], "sensitive": []},
  "review": {"read": []}
}
```

## Goal and acceptance

Describe observable behavior, exact inputs/outputs and how success will be checked.

## Context

List exact files the worker/reviewer should read; they cannot list directories.

## Changes and scope

List exact file changes. Workers create/overwrite approved files only. Assign
directory creation, renames, deletions and command execution to the coordinator.

## Sensitive files

None. For a full-tier task, replace this with each sensitive file and its reason.

## Verification and operational permissions

List actual coordinator gate commands, trusted dependencies and expected outputs.
Infrastructure/network/credentials/service operations: none unless separately
approved with an exact target, action, purpose and expiry. Workers get none.

## Out of scope

Record explicit task boundaries and decisions the worker must not expand.
