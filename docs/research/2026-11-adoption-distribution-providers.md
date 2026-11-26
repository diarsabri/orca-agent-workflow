# Adoption, distribution and provider neutrality: research notes

Status: research and proposal, 2026-11-09. Nothing here is implemented except where
marked. It records the first adoption of the kit outside its originating pilot,
the decision to support Windows natively, and the analysis behind a smaller,
provider-neutral distribution. Decisions still open are listed at the end.

## 1. Evidence

- **First external adoption:** a private Lua 5.1 game-addon repository with its own
  agent baseline and a `master` default branch, adopted from Windows 10 by a Claude
  Code setup agent. Every step of `INSTALL.md` and the setup skill was followed and
  each friction point recorded.
- **Native Windows port:** spec [`specs/native-windows.md`](../../specs/native-windows.md),
  validated on Windows 10 and in the Linux gate image ([validation](../validation.md)).
- **Distribution research:** official Claude Code, Codex, Gemini CLI and Mistral Vibe
  documentation and comparable open-source kits (sources in section 8).

## 2. First external install: findings and status

The adoption ended configured, with every gate passing in Docker: the application's
193 offline tests and the installed workflow tests. Reaching that took four
workarounds, and the scoped implementer could not run on the Windows host.

| # | Finding | Status |
|---|---|---|
| 1 | `adopt.py prepare` crashed on Windows (`os.O_NOFOLLOW`) | Fixed (#6) |
| 2 | The scoped broker used POSIX-only APIs (`dir_fd`, `O_DIRECTORY`); workers could not run on Windows | Fixed (native Windows port) |
| 3 | Gate runner hard-coded `/usr/bin/git` and failed with an unnamed `[WinError 2]` | Fixed (port) |
| 4 | Gate snapshots lost executable bits from Windows working trees | Fixed (port: modes come from the Git index) |
| 5 | Runtime pin lagged `main`, so adopters missed newer runtime changes | Fixed (#7); a CI staleness check is still open |
| 6 | `--source/--revision` records an unpushed commit as provenance without warning | Open |
| 7 | `run_gates.py --ref` defaulted to `origin/main`; `master` repositories failed | Fixed (port: defaults to `origin/HEAD`, keeping a reviewed ref) |
| 8 | `sensitive.json` ships pilot-specific paths, and installed tests assert them | Open |
| 9 | Example model IDs are enabled planners without an availability check | Open |
| 10 | Provenance and rendered files were written with CRLF on Windows | Fixed (port: explicit UTF-8/LF everywhere) |
| 11 | Git for Windows `core.autocrlf` turned kit files into CRLF | Fixed (port: `.gitattributes`, scoped for adopters) |
| 12 | Docs said `python3`, a Microsoft Store placeholder on Windows | Fixed (port: docs give `py -3`/`python`) |
| 13 | `bootstrap` reported Orca missing after install: CLI not on PATH until registered | Open |
| 14 | Docs never mentioned winget | Fixed (port: INSTALL step 3) |
| 15 | Docker Desktop's WSL2, UAC and licence prompts are not mentioned up front | Open |
| 16 | `claude`/`codex` installed but off PATH; doctor only checks PATH | Open |
| 17 | The same guidance is repeated across README, INSTALL, SKILL and adoption notes | Open |
| 18 | 56–57 installed files, scattered through the application's tree | Open, see section 4 |
| 19 | Merge detection is path-only and missed an overlapping existing workflow doc | Open |
| 20 | `adopt.py prepare --help` lacks option descriptions | Open |
| 21 | Setup ends with instructions instead of an open, ready coordinator session in Orca | Open |
| 22 | `workflow.py start` always targets the local checkout, not a remote/SSH Orca host | Open |

The port also fixed two problems not found in that install: `workflow.py` now refuses
`.cmd`/`.bat` Orca launchers, because `cmd.exe` would re-parse task text as commands;
and `apply` reports which installed files must be committed as executable, because
Windows file modes cannot record it.

## 3. Windows: native port rather than WSL

Orca itself supports Windows; the gaps were all in this kit. Two routes were weighed:

- **WSL:** run the POSIX-only parts in an Ubuntu distribution, reached from Orca as an
  SSH target or a paired `orca serve` runtime. No kit changes, but every Windows
  adopter would need to install and sign in to a Linux environment first.
- **Native:** port the broker and gate runner. More work, and a second implementation
  of security-sensitive code, but Windows works like the other platforms.

The kit is meant to be public, so the native port was chosen: asking adopters to set up
WSL first is the kind of friction the kit exists to remove. The Windows broker refuses
reparse points at every component and Windows-reinterpreted names, then trusts only
the real path of the handle it opened (`GetFinalPathNameByHandleW`). One residual
differs from POSIX and is documented in [security](../security.md): a lost race during
a new-file write can leave an empty file at a junction swapped in by another local
process. CI now runs on Windows alongside Ubuntu and macOS.

## 4. Install footprint

The current install copies 57 files into the application:

| Group | Files | Needs to be in the application repository? |
|---|---|---|
| Runtime code (broker, planner, gate runner, review gate, launcher) | 14 | No: tooling, installable per machine |
| Kit docs and licence | 10 | No: link to the kit's documentation |
| Client adapters (`.claude`, `.opencode`) | 10 | Only for clients that cannot read `.agents/skills` |
| Skills | 8 | As one skill, or delivered by plugins |
| Configuration (project, roles, gates, sensitive paths) | 4 | Yes, as one file |
| Kit tests | 5 | No: they test the kit, not the application |
| `AGENTS.md`, `CLAUDE.md`, ignore/attribute rules, hook, spec template | 6 | A few merged lines; hook and template unnecessary |

Why teams would decline it as it stands: the diff is large; `tests/agents` is collected
by the application's own test runner; linters and doc checks pick up kit files; the team
becomes owner of a security-sensitive broker it did not write; and every kit upgrade is
a large re-review.

What must stay in the repository is what the security model relies on being reviewed:
committed, approved **specs**; the **role policy and gate configuration**, read from the
reviewed base; and the **routing block** in `AGENTS.md`. Moving the runtime out of the
checkout strengthens isolation, because workers can no longer see the broker. It needs
one change: the broker must read its trusted policy explicitly from the base commit
(`git show <base>:…`) instead of locating it beside its own file.

## 5. How comparable kits are distributed

| Kit | Mechanism | Footprint in the project |
|---|---|---|
| GitHub Spec Kit | CLI run from a pinned git tag (`uvx --from git+…@vX.Y.Z specify init`) | One contained `.specify/` folder plus per-agent command files |
| BMAD Method | `npx bmad-method install`; re-run to update | One contained `_bmad/` folder plus tool folders |
| Agent OS | Base install in the home directory plus a per-project install | Project standards and specs only |
| Superpowers | Pure Claude Code plugin from its own marketplace | None |
| Agent Skills / `npx skills` | Vendor-neutral `SKILL.md` standard and installer | Skills only, if project-scoped |

Kits that support several agents vendor files into **one contained folder** through a CLI
pinned to a release; single-vendor kits use plugins and leave the repository untouched.
None spreads files through the application tree as this kit currently does.

Official channels:

- **Claude Code** plugins come from any self-hosted marketplace (a git repository with
  `.claude-plugin/marketplace.json`), can be pinned by `ref`/`sha`, and can carry skills,
  hooks, MCP servers and scripts. A project can register a marketplace for teammates by
  committing `.claude/settings.json`; it applies once each person trusts the folder.
- **Codex** plugins (`.codex-plugin/plugin.json`) also come from self-hosted marketplaces,
  including a repository-scoped one at `.agents/plugins/marketplace.json`. Project-level
  enablement has been reported as unreliable in some versions, so per-user installation
  is the safe default.

Cross-vendor concern: a workflow built on one provider reviewing another is a poor fit
for any single vendor's curated directory. No published rule forbids it, and cross-vendor
plugins exist, but the kit should not depend on a vendor promoting it. Self-hosted
marketplaces need no approval, and Orca, which is explicitly multi-agent and ships
version-matched skills and plugins, is the natural neutral listing.

## 6. Provider neutrality

The goal is to support providers beyond Anthropic and OpenAI (Google, Mistral and
others). The building blocks have converged:

- `AGENTS.md` is read by Codex, OpenCode and Mistral Vibe, can be configured in Gemini
  CLI, and reaches Claude through the `@AGENTS.md` import in `CLAUDE.md`.
- `.agents/skills/` with `SKILL.md` is discovered by Codex, Gemini CLI and Mistral Vibe;
  Claude Code reads `.claude/skills`, hence one adapter.
- Every candidate client supports MCP, which is how the broker is exposed.
- Disabling native tools, which confinement needs, exists beyond Claude: Gemini CLI has
  a `coreTools` allowlist and per-server `includeTools`/`excludeTools`; Mistral Vibe has
  per-tool permissions and per-agent configuration.
- Orca launches agents generically (`--agent <id> --model <id>`).

The repository-side formats the kit already uses are the neutral ones. Provider
specificity lives in the runtime: the implementer launch in `task_scope.py` is Claude's
command line, `codex_review.py` is Codex-only, and the launcher, review gate and scaffold
accept only `claude` or `codex`.

Proposed: a **provider adapter interface** inside the runtime, with support declared per
role. Each adapter declares how Orca launches the agent, how it is confined, and its
qualification probe. The role policy names providers by free identifiers matched to
installed adapters, and the existing cross-provider reviewer preference carries over.

| Role | Requirement | Expected availability |
|---|---|---|
| Coordinator | Reads `AGENTS.md` and skills, runs `orca` and the kit CLI | Almost any agent, immediately |
| Reviewer | Native tools off; reads only frozen inputs through the broker | Providers with a qualified confinement adapter |
| Implementer | Native tools off; broker is the only file access; model pinned | Providers with a qualified adapter and passing probes |

## 7. Recommendation

1. **Phase 1, trim (no packaging work):** stop installing kit tests, kit docs, the spec
   template, the pre-push hook and OpenCode adapters unless requested; merge the four
   configuration files; move the runtime into one folder (`.agents/orca/`) and working
   state out of the checkout. About 57 files become about 15, nearly all in one folder.
2. **Phase 2, provider adapters:** move Claude and Codex behind the interface without
   behaviour changes, then add a third provider (proposed: Gemini CLI) as coordinator
   and reviewer first, implementer once its confinement passes the probes.
3. **Phase 3, distribution:** runtime installed from pinned release tags, refusing to run
   on a version mismatch; in the repository only `.agents/workflow.json`, the `AGENTS.md`
   block, Claude's one adapter and specs as tasks create them; optional Claude Code,
   Codex and Gemini packages generated from the same skill source; an Orca listing later.
   A contained vendored mode remains for teams that cannot install per-user tools.

Adoption ladder: **try** with nothing committed (configuration in a Git-excluded file),
**team** with the two files committed, **enforced** with an optional CI check of review
records.

## 8. Open decisions

1. Confirm the target: runtime from release tags, self-hosted optional plugins, an Orca
   listing pursued later.
2. Keep a contained vendored mode for teams that cannot install per-user tools?
3. Third provider to prove the adapter interface (proposed: Gemini CLI).
4. Accept coordinator/reviewer support before implementer support for new providers?
5. Depth of OpenCode support: Agent Skills installation only, or more.

## 9. Sources

- [Claude Code: create a marketplace](https://code.claude.com/docs/en/plugin-marketplaces)
- [Claude Code: host and maintain a marketplace](https://code.claude.com/docs/en/plugins/host-marketplace.md)
- [OpenAI Codex: package your plugin](https://developers.openai.com/codex/plugins/build)
- [openai/codex issue 18115: repository-scoped marketplace configuration](https://github.com/openai/codex/issues/18115)
- [Gemini CLI configuration](https://geminicli.com/docs/cli/configuration)
- [Gemini CLI Agent Skills](https://geminicli.com/docs/cli/skills/)
- [Gemini CLI extensions](https://www.geminicli.com/docs/extensions/writing-extensions)
- [Mistral Vibe MCP servers](https://docs.mistral.ai/vibe/code/cli/mcp-servers)
- [Spec Kit installation](https://github.github.com/spec-kit/installation.html)
- [Spec Kit agent integrations](https://github.github.io/spec-kit/reference/integrations.html)
- [BMAD: install](https://www.mintlify.com/bmad-code-org/BMAD-METHOD/guides/install-bmad)
- [Agent OS installation](https://buildermethods.com/agent-os/installation)
- [Superpowers for Claude Code](https://www.mintlify.com/obra/superpowers/installation/claude-code)
- [vercel-labs/skills](https://cdn.jsdelivr.net/gh/vercel-labs/skills@main/README.md)
- [Orca: ways to run Orca](https://www.onorca.dev/docs/ways-to-run)
