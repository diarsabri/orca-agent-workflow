---
title: Release and distribute the pinned runtime
status: implemented
---

# Task brief

PR B implements criteria 9–11 of the [approved packaging spec](package-runtime.md).
Claude Opus planned the two-PR split. The receiving Codex coordinator implements
PR B directly because it changes the publishing workflow. The trusted base enables
Claude Opus 5.5 for independent review.

```agent-task
{
  "tier": "full",
  "implementer": {"read": [], "write": [], "sensitive": []},
  "review": {"read": ["specs/package-runtime.md", ".github/workflows/release.yml", "pyproject.toml", "src/orca_agent_workflow/install.py", "skills/setup-orca-workflow/SKILL.md"]}
}
```

## Acceptance

- Build the source distribution and its wheel once. Exercise the installed wheel
  on Linux, macOS and Windows. Pull requests run the build and tests.
- A version-matching tag can publish those tested files after every matrix job passes.
  Limit OIDC credentials to the publish job and attach PyPI publish attestations.
- Keep Orca bootstrap and use version-pinned package commands for adoption. Explain
  the tagged Git fallback, vendoring, artifact identity and the version pin.
- Verify the wheel locally through uvx. Leave PyPI configuration, first tag and
  merge to the maintainer.
