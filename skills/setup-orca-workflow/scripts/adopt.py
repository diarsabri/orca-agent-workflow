#!/usr/bin/env python3
"""Discover and bootstrap Orca for workflow adoption."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def prerequisites(check_runtime: bool = False) -> dict:
    executable = shutil.which("orca")
    runtime = "not_checked" if executable else "not_installed"
    app_running = None
    if executable and check_runtime:
        try:
            result = subprocess.run(
                [executable, "status", "--json"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            status = json.loads(result.stdout)
            details = status.get("result", {})
            app = details.get("app", {}).get("running")
            app_running = app if isinstance(app, bool) else None
            state = details.get("runtime", {})
            runtime = (
                "ready"
                if (
                    result.returncode == 0
                    and status.get("ok") is True
                    and state.get("state") == "ready"
                    and state.get("reachable") is True
                )
                else "unavailable"
            )
        except (OSError, ValueError, AttributeError, subprocess.TimeoutExpired):
            runtime = "unavailable"
    return {
        "orca": {
            "required": True,
            "installed": executable is not None,
            "runtime": runtime,
            "app_running": app_running,
            "repository": "https://github.com/stablyai/orca",
            "installation": "https://www.onorca.dev/docs/install",
            "macos_install_command": "brew install --cask stablyai/orca/orca",
            "next": (
                "Orca runtime is reachable; continue project and worker checks."
                if runtime == "ready"
                else (
                    "Open Orca if needed; check CLI registration/runtime access and recheck."
                    if executable
                    else "Install Orca from the official instructions, open it, and make its CLI available on PATH."
                )
            ),
        },
        "ready_for_orca_tasks": runtime == "ready",
        "note": "This checks Orca only; model access, worker qualification and project gates are separate.",
    }


def macos_app_present() -> bool:
    return sys.platform == "darwin" and any(
        path.is_dir()
        for path in (Path("/Applications/Orca.app"), Path.home() / "Applications/Orca.app")
    )


def bootstrap(apply: bool = False) -> dict:
    report = {
        "applied": apply,
        "actions": [],
        "remaining_steps": [],
        "prerequisites": prerequisites(True),
        "ready_for_orca_tasks": False,
    }

    def finish(message: str | None = None) -> dict:
        report["ready_for_orca_tasks"] = report["prerequisites"]["ready_for_orca_tasks"]
        if message:
            report["remaining_steps"].append(message)
        report["next"] = (
            "Continue repository adoption in this agent."
            if report["ready_for_orca_tasks"]
            else (
                "Resolve the listed setup steps with the agent, recheck, and continue independent repository preparation."
                if report["remaining_steps"]
                else "Run bootstrap --apply to perform the planned dependency setup."
            )
        )
        return report

    def perform(command: list[str], timeout: int) -> bool:
        action = {"command": command, "status": "planned"}
        report["actions"].append(action)
        if not apply:
            return True
        print("Bootstrap: " + " ".join(command), file=sys.stderr, flush=True)
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=timeout
            )
            if result.returncode:
                action.update(status="failed", returncode=result.returncode)
                detail = (result.stderr or result.stdout or "").strip()
                if detail:
                    action["detail"] = detail[-2000:]
                return False
        except (OSError, subprocess.TimeoutExpired):
            action["status"] = "unconfirmed"
            return False
        action["status"] = "completed"
        return True

    state = report["prerequisites"]
    if state["ready_for_orca_tasks"]:
        return finish()
    installed_now = False
    if not state["orca"]["installed"]:
        # An existing app with an unregistered CLI needs registration, not another install.
        if macos_app_present():
            return finish(
                "Orca is already installed. Register its CLI in Settings > General > Orca CLI, then recheck."
            )
        brew = shutil.which("brew") if sys.platform == "darwin" else None
        if not brew:
            return finish(
                "Use the official Orca installer for this platform: https://www.onorca.dev/docs/install . The agent can run the appropriate installer within the requested setup; user interaction may be required."
            )
        if not perform([brew, "install", "--cask", "stablyai/orca/orca"], 600):
            report["prerequisites"] = prerequisites(True)
            return finish(
                "Orca installation was not confirmed. Inspect the installer and complete any system permission step; recheck before retrying. Do not force reinstall."
            )
        if not apply:
            perform(["orca", "open", "--json"], 60)
            return finish()
        installed_now = True
        state = report["prerequisites"] = prerequisites(True)
        if not state["orca"]["installed"]:
            return finish(
                "The installer completed but orca is not on PATH. Check the official CLI registration guidance; do not reinstall the app."
            )
    if state["ready_for_orca_tasks"]:
        return finish()
    if state["orca"]["app_running"] is False or installed_now:
        executable = shutil.which("orca")
        if not perform([executable, "open", "--json"], 60):
            report["prerequisites"] = prerequisites(True)
            return finish(
                "Orca startup was not confirmed. Inspect the app and any first-launch/system permission dialogs before retrying; no automatic retry was made."
            )
        if apply:
            report["prerequisites"] = prerequisites(True)
            if not report["prerequisites"]["ready_for_orca_tasks"]:
                return finish(
                    "Complete Orca's first-launch choices or runtime-access permissions, then recheck. No agents have been started."
                )
        return finish()
    return finish(
        "Orca is installed but runtime access is not confirmed. Inspect the existing app and CLI/sandbox permissions; do not restart an active runtime or reinstall."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    boot = commands.add_parser(
        "bootstrap", help="Plan Orca dependency setup from an existing coding agent"
    )
    boot.add_argument(
        "--apply",
        action="store_true",
        help="Install missing Orca with macOS Homebrew and open it when needed; system prompts remain interactive",
    )
    check = commands.add_parser(
        "prerequisites", help="Check required Orca installation and optionally its runtime"
    )
    check.add_argument(
        "--check-runtime",
        action="store_true",
        help="Read orca status; no installation or agent launch",
    )
    args = parser.parse_args()
    try:
        if sys.version_info < (3, 11):
            raise ValueError("Python 3.11 or newer is required")
        if args.command == "bootstrap":
            report = bootstrap(args.apply)
            print(json.dumps(report, indent=2))
            return int(args.apply and not report["ready_for_orca_tasks"])
        report = prerequisites(args.check_runtime)
        print(json.dumps(report, indent=2))
        return int(
            not report["orca"]["installed"]
            or (args.check_runtime and not report["ready_for_orca_tasks"])
        )
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"adoption: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
