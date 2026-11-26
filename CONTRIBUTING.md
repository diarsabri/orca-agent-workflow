# Contributing

Keep the adopter-facing interface small: ask the existing coding agent to follow
`INSTALL.md`, arrange missing dependencies and adopt the workflow, then start a
task. Skills CLI installation remains optional. Keep the package CLI and automation
interfaces available. Preserve custom instructions and unrelated work; avoid
duplicating policy across providers.

Use a feature branch, preserve existing files, and include relevant tests and
documentation. Run the commands in [validation](docs/validation.md). Do not add
host credentials, provider receipts or real conversation histories to fixtures.
Use synthetic data and redact values from diagnostics.

Changes to scope, lifecycle, gate execution or adoption behavior need meaningful
behavioral coverage. Update the compatibility record when adding a runtime or
client; executable presence and a few denied commands do not prove a full native
capability restriction. Never enable an unqualified implementation profile as a
convenience fallback.

Contributions are under the repository's [MIT license](LICENSE). Please keep pull
requests focused and describe observed behavior, checks and their limitations.

The standalone setup skill lives under `skills/setup-orca-workflow`. Its helper
bootstraps Orca and its instructions install the pinned package. Update the
documented version alongside the runtime. Exercise the wheel built from the
sdist, including adoption in a disposable project. Check all wheel-test jobs
before tagging the release.

For the first release, configure the PyPI pending publisher for project
`orca-agent-workflow`, repository `diarsabri/orca-agent-workflow`, workflow
`release.yml` and GitHub environment `pypi`. Restrict that environment to
release tags and configure maintainer approval. After merging the reviewed PR,
tag the release commit with `v` followed by the package version. The workflow
checks the tag, tests the wheel and publishes the tested artifacts.
