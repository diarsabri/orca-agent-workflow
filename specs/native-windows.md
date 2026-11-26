---
title: Run the workflow natively on Windows
status: implemented
---

# Task brief

## Routing

Planner/coordinator: Claude `claude-opus-5-5`, implemented directly in this
repository on `feat/native-windows`. There is no implementation worker: the scoped
implementer broker is the component being ported, so it cannot confine a worker on
the Windows host until this lands. Reviewer: a fresh Claude `claude-opus-5-5` session,
the only enabled reviewer profile in the trusted base policy. The user approved
this spec in the coordinator session on 2026-11-09.

```agent-task
{
  "tier": "full",
  "implementer": {"read": [], "write": [], "sensitive": []},
  "review": {"read": [
    "specs/native-windows.md",
    "scripts/agents/task_scope.py",
    "scripts/agents/task_plan.py",
    "scripts/agents/review_gate.py",
    "scripts/agents/codex_review.py",
    "scripts/agents/gate_sandbox/run_gates.py",
    "skills/setup-orca-workflow/scripts/adopt.py",
    "scaffold.py",
    "workflow.py",
    ".github/workflows/ci.yml",
    ".gitattributes",
    "tests/agents/test_task_scope.py",
    "tests/agents/test_task_plan.py",
    "tests/agents/test_codex_review.py",
    "tests/kit/test_gate_runner.py",
    "tests/kit/test_setup_skill.py",
    "tests/kit/test_scaffold.py",
    "README.md",
    "INSTALL.md",
    "docs/compatibility.md",
    "docs/security.md",
    "docs/validation.md",
    "skills/setup-orca-workflow/SKILL.md"
  ]}
}
```

## Goal and acceptance

Make the kit's own runtime work on native Windows (no WSL), with the same safety
guarantees as on macOS/Linux, so adopting and using the workflow on Windows needs
only Git for Windows, Python 3.11+, Orca, Docker Desktop and the provider CLIs.

Acceptance:

1. `python -m unittest discover -s tests` passes on `windows-latest` in CI for
   Python 3.11 and 3.13, alongside the existing Ubuntu and macOS jobs. Tests that
   are inherently POSIX-only are skipped on Windows with a stated reason, never
   silently weakened; every security property they cover has a Windows test.
2. The scoped file broker on Windows refuses everything it refuses on POSIX:
   unlisted paths, traversal, writes to read-only paths, symlinks, junctions and
   other reparse points at any path component, swaps of a parent directory during
   an open, hardlinked files and non-regular files. It allows exactly the approved
   reads and writes. `task_scope.py probe` passes on Windows.
3. `adopt.py prepare`/`apply`, `workflow.py setup/status/start --dry-run`,
   `run_gates.py` and the offline demo work from a native Windows shell. Generated
   files are written byte-for-byte with LF line endings regardless of `core.autocrlf`.
4. Gate snapshots carry executable bits from Git's index, so `./scripts/test.sh`-style
   checks run in the Linux gate container from a Windows checkout.
5. Docs state Windows as supported and give the Windows form of commands
   (`py -3` / `python` where docs say `python3`).

## Context

Findings 1–4, 10–12 in #6 (first external install on Windows 10). Current failures
on Windows: 15 errors and 4 failures in `tests/agents`, `prepare` crash (fixed in #6),
`run_gates.py` `[WinError 2]`, exec bits lost in gate snapshots.

## Changes and scope

- **`scripts/agents/task_scope.py`: broker file opens.** Keep the POSIX `dir_fd` +
  `O_NOFOLLOW` walk unchanged. Add a Windows path:
  - walk each component with `os.lstat` and refuse any component with
    `FILE_ATTRIBUTE_REPARSE_POINT` (symlinks, junctions, mount points);
  - open the final file with `O_BINARY | O_NOINHERIT` (`O_CREAT | O_EXCL` for new writes);
  - after opening, read the handle's real path with `GetFinalPathNameByHandleW`
    (`ctypes`, standard library), and close and refuse the handle unless that path equals
    the resolved `root / value`, compared case-insensitively as NTFS does. This check
    runs on what was actually opened, so a swap between the walk and the open cannot
    redirect it;
  - keep the existing `fstat` regular-file and `st_nlink == 1` checks.
- **`task_scope.py`: Git and processes.**
  - Resolve Git once to an absolute executable outside the checkout: `/usr/bin/git`
    on POSIX as today; on Windows `shutil.which("git")` with the checkout excluded,
    failing if the result is inside the checkout.
  - Use `os.devnull` for `core.hooksPath`.
  - Build relative paths with `as_posix()` (the probe currently produces backslashes).
  - On Windows, `supervise` places the client in a Job Object with
    `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, so revocation also ends the MCP broker
    child it started. It still never signals processes it did not create.
- **`scripts/agents/task_plan.py`, `review_gate.py`:** POSIX relative paths via
  `as_posix()`; evidence files written as bytes/`newline="\n"`.
- **`scripts/agents/gate_sandbox/run_gates.py`:** shared Git resolution; snapshot
  file modes taken from `git ls-files -s` (0755 for mode 100755, else 0644), not from
  the working tree; `--ref` defaults to `HEAD` instead of `origin/main` (finding 7);
  errors name the missing executable.
- **`scripts/agents/codex_review.py`:** Codex review qualification stays POSIX-only
  for now. On Windows it fails fast with a clear "Codex review qualification is not
  supported on Windows yet" error, and the profile stays disabled. Profile path
  formatting uses `as_posix()` where paths are POSIX by construction.
- **`skills/setup-orca-workflow/scripts/adopt.py`, `scaffold.py`, `workflow.py`:**
  all generated text written with `newline="\n"`; console output that may contain
  non-ASCII is encoded safely (`errors="replace"` or ASCII only).
- **`.gitattributes`** (new, kit and generated projects via `kit-files.json`):
  `* text=auto eol=lf` plus `*.sh` and `*.py` `eol=lf`.
- **`.github/workflows/ci.yml`:** add `windows-latest` to the OS matrix.
- **Tests:** new Windows tests for junction/symlink/reparse refusal, parent swap,
  hardlink refusal, final-path mismatch and Job Object cleanup. Mark the existing
  POSIX-only tests (`dir_fd`, `/bin/sh` canaries) `skipUnless(os.name == "posix")`
  with reasons.
- **Docs:** README platform paragraph, INSTALL.md step 3 (Windows Python form),
  `docs/compatibility.md` (Windows supported; Codex review qualification POSIX-only),
  `docs/security.md` (Windows broker mechanism and its threat model),
  `docs/validation.md` (record the Windows runs), setup skill platform notes.

## Sensitive files

- `scripts/agents/task_scope.py`: the security boundary for workers; every changed
  line needs review.
- `scripts/agents/gate_sandbox/run_gates.py`: builds trusted gate inputs.
- `.github/workflows/ci.yml`: changes what CI proves.
- `.gitattributes`: changes the bytes Git stores and checks out.

## Verification and operational permissions

- On this Windows 10 host: `python -m unittest discover -s tests -q`,
  `python scripts/agents/check_sync.py`, `python scripts/check_docs.py`,
  `python scripts/scan_public.py`, `python examples/offline_demo.py`,
  `task_scope.py probe` against a disposable checkout, and a fresh
  `adopt.py prepare/apply` into a disposable application followed by its installed
  suite.
- The same suite on Linux in the Docker gate image, so POSIX behaviour is unchanged.
- CI on GitHub across Ubuntu, macOS and Windows after the PR is pushed.
- Network: none beyond GitHub for push/CI. No model calls, no credentials, no
  changes to Orca, Docker or system settings.

## Out of scope

- Native Codex review qualification on Windows (needs Codex's Windows sandbox model).
- WSL support or detection.
- `workflow.py start` selecting a remote/SSH host (finding 22; separate task).
- Changes to Orca itself.

## Implementation notes

Deliberate differences from the plan above, recorded for review:

- `run_gates.py --ref` defaults to origin's default branch (`origin/HEAD`), not
  `HEAD`. Gate build inputs must come from a reviewed ref; `HEAD` would let the
  branch under test supply its own image. This still fixes `master` repositories.
- `workflow.py` refuses `.cmd`/`.bat` Orca launchers on Windows: `cmd.exe`
  re-parses their arguments, so user task text could run as commands. Orca ships
  a native `orca.exe`. The Windows test fakes are real `.exe` files built with
  pip's console-script launcher.
- Generated projects receive a `.gitattributes` scoped to workflow files, not the
  kit's global LF rule; an existing file gets only the missing lines appended.
- Executable bits travel with the exported kit (`.kit-modes.json`) because Windows
  file modes lose them; `apply` lists the files to stage with `--chmod=+x`.
- Residual on Windows: a lost race during a new-file write can leave an empty
  file at a junction target swapped in by another local process. Documented in
  `docs/security.md`.
- `git_executable` skips a Git found inside the checkout and keeps searching PATH
  rather than failing. `run_gates.py` resolves Git before it knows the checkout
  root, so that first `rev-parse` relies on skipping relative PATH entries only.
- The broker refuses a non-native Orca launcher (anything but an absolute
  `orca.exe`) on Windows for the same reason as `workflow.py`: report and question
  text is written by the worker. Docker (gate runner) and Claude (`prepare`) are
  resolved like Git, from absolute PATH entries outside the checkout, so a branch
  cannot plant its own `docker.exe` or `claude.cmd`. Both found in independent review.
