"""Wait for a prepared local Claude client and dispatch its brief once."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from orca_agent_workflow import task_scope


def orca(cli: str, *args: str, timeout: float = 30) -> tuple[int, dict]:
    result = subprocess.run(
        [cli, *args, "--environment", "local", "--json"],
        capture_output=True, text=True, timeout=timeout,
    )
    try:
        return result.returncode, json.loads(result.stdout)
    except ValueError as exc:
        raise ValueError("Orca did not return a JSON receipt.") from exc


def exact_client(bundle: Path, scope: task_scope.Scope, args: argparse.Namespace, cli: str) -> dict:
    scope.live()
    controller = task_scope.controller_status(bundle)
    if (
        controller.get("state") != "running"
        or controller.get("terminal") != args.terminal
        or controller.get("manifest_sha256") != scope.sha
        or controller.get("head") != scope.data["head"]
        or controller.get("bundle") != str(bundle)
    ):
        raise ValueError("The intended scoped client has exited or its launch record no longer matches.")
    pid = controller.get("pid")
    if type(pid) is not int or pid <= 0:
        raise ValueError("Missing scoped client PID.")
    os.kill(pid, 0)
    code, reply = orca(cli, "terminal", "show", "--terminal", args.terminal)
    terminal = reply.get("result", {}).get("terminal", {})
    if (
        code or reply.get("ok") is not True
        or terminal.get("handle") != args.terminal
        or terminal.get("agentIdentity") != "claude"
        or terminal.get("connected") is not True
        or terminal.get("writable") is not True
        or not terminal.get("incarnationId")
        or Path(terminal.get("worktreePath") or "/").resolve() != scope.root
    ):
        raise ValueError("Orca cannot identify the expected live Claude terminal. Inspect the original tab.")
    return {
        "terminal": args.terminal,
        "incarnation": terminal["incarnationId"],
        "started_at": controller["started_at"],
        "pid": pid,
        "manifest_sha256": scope.sha,
    }


def exclusive_json(path: Path, data: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


def dispatch(args: argparse.Namespace) -> None:
    if sys.platform != "darwin":
        raise ValueError("This helper currently supports local macOS Claude terminals.")
    cli = shutil.which("orca")
    if not cli:
        raise ValueError("Install the local Orca CLI.")
    coordinator = os.environ.get("ORCA_TERMINAL_HANDLE")
    if not coordinator or coordinator == args.terminal:
        raise ValueError("Run from the owning Orca coordinator terminal.")
    bundle = args.bundle.resolve(strict=True)
    scope = task_scope.Scope(bundle / "manifest.json")
    if scope.root != task_scope.project_root():
        raise ValueError("Run from the scoped task checkout.")
    brief = args.brief.resolve(strict=True)
    state = bundle / "dispatch-intent.json"
    attempted = bundle / "dispatch-attempt.json"
    receipt = bundle / "dispatch-receipt.json"
    if attempted.exists():
        raise ValueError(f"A dispatch already started. Inspect {receipt} and the original Orca run before recovery.")
    identity = exact_client(bundle, scope, args, cli)
    intent = {
        **identity, "run": args.run, "coordinator": coordinator,
        "brief": str(brief), "brief_sha256": task_scope.digest(brief),
        "title": args.title,
    }
    try:
        exclusive_json(state, intent)
    except FileExistsError:
        if json.loads(state.read_text(encoding="utf-8")) != intent:
            raise ValueError("The original dispatch intent differs. Check the exact client and brief.")
    deadline = time.monotonic() + args.timeout
    print(f"Waiting for Claude readiness in {args.terminal}. Confirm trust in that tab if prompted.", file=sys.stderr)
    while time.monotonic() < deadline:
        if exact_client(bundle, scope, args, cli) != identity:
            raise ValueError("The scoped terminal changed while waiting.")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("Timed out before dispatch. Inspect the original tab.")
        code, reply = orca(
            cli, "terminal", "wait", "--terminal", args.terminal, "--for", "tui-idle",
            "--timeout-ms", str(max(1, min(int(remaining * 1000), 2000))),
        )
        wait = reply.get("result", {}).get("wait", {})
        if wait.get("satisfied") is True and reply.get("ok") is True and code == 0:
            if wait.get("handle") != args.terminal or wait.get("blockedReason"):
                raise ValueError("Orca returned a readiness receipt for a different or blocked terminal.")
            break
        if wait.get("blockedReason") not in (None, "agent-trust-workspace"):
            raise ValueError(f"Claude is waiting for {wait['blockedReason']}. Inspect the original tab.")
        if not wait and reply.get("error", {}).get("code") != "timeout":
            raise ValueError(f"Orca readiness could not be verified: {reply.get('error')}")
    else:
        raise ValueError("Timed out before dispatch. Inspect the original tab and rerun this command if it is still live.")
    if exact_client(bundle, scope, args, cli) != identity or task_scope.digest(brief) != intent["brief_sha256"]:
        raise ValueError("The terminal or brief changed while waiting.")
    # Reserve the one attempt before contacting Orca. Keep it even on an interrupted reply.
    try:
        exclusive_json(attempted, intent)
    except FileExistsError as exc:
        raise ValueError("Another invocation reserved the dispatch. Inspect the original Orca run.") from exc
    try:
        code, reply = orca(
            cli, "orchestration", "worker-start", "--run", args.run, "--from", coordinator,
            "--terminal", args.terminal, "--spec-file", str(brief), "--task-title", args.title,
            timeout=90,
        )
        task_scope.atomic_json(receipt, reply)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise ValueError(f"Dispatch outcome uncertain. Inspect the original Orca run before retrying: {exc}") from exc
    print(json.dumps(reply))
    if code or reply.get("ok") is not True:
        raise ValueError(f"Orca did not confirm the dispatch. Follow the recovery steps in {receipt}.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--terminal", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--brief", type=Path, required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    if args.timeout < 1:
        parser.error("--timeout must be positive")
    try:
        dispatch(args)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"resume-dispatch: {exc}\n")
    return 0
