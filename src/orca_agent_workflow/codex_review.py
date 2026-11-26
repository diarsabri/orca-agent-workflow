#!/usr/bin/env python3
"""Read-only Codex reviewer: qualification probe and confined review runs.

``qualify`` proves, on the installed Codex CLI, that the review permission profile
denies reads outside the review folder (home, the checkout, /tmp, $TMPDIR), denies
all writes and denies network. ``run`` refuses unless a passing qualification
matches the current Codex binary, then reviews frozen copies of exactly the inputs a
reviewer manifest lists. Evidence is local and operator-controlled.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import shlex
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from orca_agent_workflow import task_scope

CACHE = Path.home() / ".cache/orca-agent-workflow/codex-review"
QUALIFICATION = Path(".tmp/agent-qualification/codex-reviewer.json")
WINDOWS_UNSUPPORTED = (
    "Codex review qualification is not supported on Windows yet: its probes target the "
    "macOS/Linux sandbox. Use the Claude reviewer profile on Windows."
)


def require_posix() -> None:
    if task_scope.WINDOWS:
        raise ValueError(WINDOWS_UNSUPPORTED)


def codex_binary() -> Path:
    found = shutil.which("codex")
    if not found:
        raise ValueError("Codex CLI is not installed")
    return Path(found).resolve(strict=True)


def install_root(binary: Path) -> Path:
    """The Codex version folder (for example .../Caskroom/codex/0.166.0), never a whole prefix."""
    root = binary.parent.parent if binary.parent.name == "bin" else binary.parent
    if not re.fullmatch(r"\d+(?:\.\d+)+", root.name):
        raise ValueError(
            f"Unsupported Codex install layout ({binary}); the read grant would be {root}, "
            "not a versioned install folder"
        )
    return root


def profile_args(review: Path, binary: Path) -> list[str]:
    """Named Codex permission profile: system basics, the Codex install and one review folder."""
    filesystem = {
        ":minimal": "read",
        install_root(binary).as_posix(): "read",
        review.as_posix(): "read",
        "/tmp": "none",
        "/private/tmp": "none",
        "/var/folders": "none",
        "/private/var/folders": "none",
    }
    entries = ", ".join(f"{json.dumps(k)}={json.dumps(v)}" for k, v in filesystem.items())
    return [
        "-c",
        'default_permissions="review"',
        "-c",
        f"permissions.review.filesystem={{{entries}}}",
        "-c",
        "permissions.review.network={enabled=false}",
        "-c",
        'web_search="disabled"',
    ]


def profile_digest(binary: Path) -> str:
    """Binds a qualification to the exact profile shape (review folder abstracted)."""
    return task_scope.sha(json.dumps(profile_args(Path("/REVIEW"), binary)).encode())


def sandboxed(review: Path, binary: Path, *command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(binary), "sandbox", *profile_args(review, binary), "--", *command],
        cwd=review,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def denied(result: subprocess.CompletedProcess[str]) -> bool:
    return result.returncode != 0 and "CANARY" not in result.stdout


def qualify(checkout: Path) -> dict[str, Any]:
    """Probe the profile with canaries; outputs of real-secret probes are never kept."""
    require_posix()
    binary = codex_binary()
    CACHE.mkdir(parents=True, exist_ok=True)
    review = Path(tempfile.mkdtemp(prefix="qual-", dir=CACHE)).resolve()
    canaries = {
        "home": CACHE / f"canary-{os.getpid()}.txt",
        "tmp": Path(tempfile.mkstemp(prefix="codex-canary-", dir="/tmp")[1]),
        "tmpdir": Path(tempfile.mkstemp(prefix="codex-canary-")[1]),
    }
    outside_write = CACHE / f"written-{os.getpid()}.txt"
    results: dict[str, bool] = {}
    absent: list[str] = []
    try:
        (review / "in.txt").write_text("REVIEW-INPUT", encoding="utf-8", newline="\n")
        for path in canaries.values():
            path.write_text("CANARY", encoding="utf-8", newline="\n")
        inside = sandboxed(review, binary, "/bin/cat", str(review / "in.txt"))
        results["reads_review_folder"] = inside.returncode == 0 and "REVIEW-INPUT" in inside.stdout
        for name, path in canaries.items():
            results[f"denies_{name}_read"] = denied(
                sandboxed(review, binary, "/bin/cat", str(path))
            )
        for name, path in (
            ("checkout", checkout / "AGENTS.md"),
            ("codex_auth", Path.home() / ".codex"),
            ("ssh", Path.home() / ".ssh"),
            ("homebrew_var", Path("/opt/homebrew/var")),
        ):
            if not path.exists():
                absent.append(name)  # a probe of a missing path would pass vacuously
                continue
            probe = (
                ["/bin/ls", str(path)]
                if path.is_dir()
                else ["/usr/bin/head", "-c", "1", str(path)]
            )
            results[f"denies_{name}_read"] = sandboxed(review, binary, *probe).returncode != 0
        inner = sandboxed(review, binary, "/bin/sh", "-c", "echo x > written.txt")
        outer = sandboxed(
            review, binary, "/bin/sh", "-c", f"echo x > {shlex.quote(str(outside_write))}"
        )
        results["denies_write"] = (
            inner.returncode != 0
            and outer.returncode != 0
            and not (review / "written.txt").exists()
            and not outside_write.exists()
        )
        net = sandboxed(review, binary, "/usr/bin/curl", "-sS", "-m", "5", "https://example.com")
        # 6: cannot resolve, 7: cannot connect, 28: timed out; anything else proves nothing.
        results["denies_network"] = net.returncode in (6, 7, 28)
    finally:
        shutil.rmtree(review, ignore_errors=True)
        outside_write.unlink(missing_ok=True)
        for path in canaries.values():
            path.unlink(missing_ok=True)
    version = subprocess.run(
        [str(binary), "--version"], capture_output=True, text=True, check=False
    ).stdout.strip()
    return {
        "passed": all(results.values()) and "checkout" not in absent,
        "results": results,
        "not_present": absent,
        "install_root": str(install_root(binary)),
        "codex_path": str(binary),
        "codex_sha256": task_scope.digest(binary),
        "codex_version": version,
        "profile_sha256": profile_digest(binary),
        "adapter_sha256": task_scope.digest(Path(__file__).resolve()),
        "checked_at": time.time(),
    }


def session_models(thread: str | None) -> set[str]:
    """Models Codex recorded for the thread (client-side turn context, not a server echo)."""
    if not thread:
        return set()
    models = set()
    for path in (Path.home() / ".codex/sessions").glob(f"*/*/*/*{thread}*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("type") == "turn_context":
                model = event.get("payload", {}).get("model")
                if isinstance(model, str):
                    models.add(model)
    return models


def run(
    manifest: Path,
    brief: Path,
    policy: Path | None,
    model: str,
    out: Path,
    qualification: Path,
) -> dict[str, Any]:
    manifest, brief, out, qualification = (
        path.resolve() for path in (manifest, brief, out, qualification)
    )
    policy = policy.resolve() if policy else None
    require_posix()
    binary = codex_binary()
    qual = json.loads(qualification.read_text(encoding="utf-8"))
    if (
        qual.get("passed") is not True
        or qual.get("codex_sha256") != task_scope.digest(binary)
        or qual.get("profile_sha256") != profile_digest(binary)
        or qual.get("adapter_sha256") != task_scope.digest(Path(__file__).resolve())
    ):
        raise ValueError(
            "No passing qualification for this Codex binary, profile and adapter; run qualify"
        )
    # Refuse a disabled profile before touching the manifest, when a policy copy is given.
    config = task_scope.load_config(policy.read_bytes()) if policy else None
    scope = None
    if config is None:
        scope = task_scope.Scope(manifest)
        _, config = task_scope.base_config(scope.root, scope.data["policy_base"])
    if not task_scope.enabled_profile(task_scope.roles_policy(config), "reviewer", "codex", model):
        raise ValueError("Codex reviewer profile is not enabled in the trusted policy")
    scope = scope or task_scope.Scope(manifest)
    if scope.data["role"] != "reviewer":
        raise ValueError("A reviewer manifest is required")
    out.mkdir(parents=True, exist_ok=False)
    CACHE.mkdir(parents=True, exist_ok=True)
    review = Path(tempfile.mkdtemp(prefix=scope.data["head"][:12] + "-", dir=CACHE)).resolve()
    inputs = {}
    try:
        for path in sorted(scope.read):
            if path.startswith(".tmp/"):
                with os.fdopen(scope.open_file(path), "rb") as f:
                    data = f.read()
            else:
                data = task_scope.git_bytes(
                    scope.root, "cat-file", "blob", scope.data["head"] + ":" + path
                )
            target = review / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            inputs[path] = task_scope.sha(data)
        prompt = (
            brief.read_text(encoding="utf-8")
            + "\n\nEvery readable path is copied into your current directory under the same"
            " relative path. Other paths are blocked by the sandbox. Reply with only the"
            " complete review report.\n"
        )
        argv = [
            str(binary),
            "exec",
            "-m",
            model,
            "--skip-git-repo-check",
            "--ignore-user-config",
            "--ignore-rules",
            "--json",
            *profile_args(review, binary),
            "-C",
            str(review),
            "-o",
            str(out / "report.md"),
            "-",
        ]
        ended = None
        with (out / "events.jsonl").open("w", encoding="utf-8", newline="\n") as events:
            # Own exactly this child and stop it when the grant ends, as the Claude launcher does.
            process = subprocess.Popen(
                argv, stdin=subprocess.PIPE, stdout=events, stderr=subprocess.STDOUT, text=True
            )
            try:
                assert process.stdin is not None
                process.stdin.write(prompt)
                process.stdin.close()
                while process.poll() is None:
                    try:
                        scope.live()
                    except task_scope.ScopeEnded as exc:
                        ended = str(exc)
                        break
                    time.sleep(1)
            finally:
                # Never leave the child running, whatever ended the loop.
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
            returncode = process.wait()
        thread = None
        for line in (out / "events.jsonl").read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("type") == "thread.started":
                thread = event.get("thread_id")
        changed = [p for p, h in inputs.items() if task_scope.digest(review / p) != h]
    finally:
        shutil.rmtree(review, ignore_errors=True)
    models = session_models(thread)
    receipt = {
        "agent": "codex",
        "requested_model": model,
        "session_models": sorted(models),
        "model_evidence": "codex-session-turn-context",
        "returncode": returncode,
        "grant_ended": ended,
        "thread_id": thread,
        "codex_sha256": qual["codex_sha256"],
        "codex_version": qual["codex_version"],
        "qualification_sha256": task_scope.digest(qualification),
        "manifest_sha256": scope.sha,
        "head": scope.data["head"],
        "inputs": inputs,
        "inputs_changed": changed,
        "argv": argv[:-1],
    }
    task_scope.atomic_json(out / "launch.json", receipt)
    if ended or returncode or changed or not (out / "report.md").is_file():
        raise ValueError("Codex review did not complete cleanly; see events.jsonl and launch.json")
    if models != {model}:
        raise ValueError("Codex session did not record exactly the requested model")
    scope.live()
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["qualify", "run"])
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--brief", type=Path)
    parser.add_argument(
        "--policy",
        type=Path,
        help="A saved copy of the base's .agents/workflow.json; default: the manifest's policy_base",
    )
    parser.add_argument("--model", default="gpt-6.1-sol")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--qualification", type=Path, default=QUALIFICATION)
    args = parser.parse_args()
    if args.action == "qualify":
        checkout = task_scope.project_root()
        record = qualify(checkout)
        args.qualification.parent.mkdir(parents=True, exist_ok=True)
        task_scope.atomic_json(args.qualification, record)
        print(json.dumps(record, indent=2))
        return 0 if record["passed"] else 1
    if not (args.manifest and args.brief and args.out):
        parser.error("run needs --manifest, --brief and --out")
    print(
        json.dumps(
            run(args.manifest, args.brief, args.policy, args.model, args.out, args.qualification)
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
