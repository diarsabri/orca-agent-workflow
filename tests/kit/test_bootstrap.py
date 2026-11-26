"""Exercise dependency setup with controlled installers; never mutate the host."""

import importlib.util
import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "bootstrap_helper", ROOT / "skills/setup-orca-workflow/scripts/adopt.py"
)
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


def state(installed=False, ready=False, running=None):
    return {
        "orca": {"installed": installed, "app_running": running},
        "ready_for_orca_tasks": ready,
    }


def executable(name):
    return {"brew": "/example/brew", "orca": "/example/orca"}.get(name)


class BootstrapTests(unittest.TestCase):
    def test_ready_runtime_is_reused_without_install_or_start(self):
        with (
            patch.object(helper, "prerequisites", return_value=state(True, True, True)),
            patch.object(helper.subprocess, "run") as run,
        ):
            result = helper.bootstrap(True)
        self.assertTrue(result["ready_for_orca_tasks"])
        self.assertEqual(result["actions"], [])
        run.assert_not_called()

    def test_missing_macos_install_is_only_planned_by_default(self):
        with (
            patch.object(helper, "prerequisites", return_value=state()),
            patch.object(helper, "macos_app_present", return_value=False),
            patch.object(helper.sys, "platform", "darwin"),
            patch.object(helper.shutil, "which", side_effect=executable),
            patch.object(helper.subprocess, "run") as run,
        ):
            result = helper.bootstrap()
        self.assertFalse(result["ready_for_orca_tasks"])
        self.assertEqual([x["status"] for x in result["actions"]], ["planned", "planned"])
        self.assertEqual(
            result["actions"][0]["command"],
            ["/example/brew", "install", "--cask", "stablyai/orca/orca"],
        )
        self.assertEqual(result["actions"][1]["command"], ["orca", "open", "--json"])
        run.assert_not_called()

    def test_apply_installs_missing_orca_opens_and_verifies_runtime(self):
        complete = subprocess.CompletedProcess([], 0, "", "")
        with (
            patch.object(
                helper,
                "prerequisites",
                side_effect=[state(), state(True, False, False), state(True, True, True)],
            ) as probe,
            patch.object(helper, "macos_app_present", return_value=False),
            patch.object(helper.sys, "platform", "darwin"),
            patch.object(helper.shutil, "which", side_effect=executable),
            patch.object(helper.subprocess, "run", return_value=complete) as run,
        ):
            result = helper.bootstrap(True)
        self.assertTrue(result["ready_for_orca_tasks"])
        self.assertEqual(probe.call_count, 3)
        self.assertEqual(
            [call.args[0] for call in run.call_args_list],
            [
                ["/example/brew", "install", "--cask", "stablyai/orca/orca"],
                ["/example/orca", "open", "--json"],
            ],
        )
        self.assertEqual([x["status"] for x in result["actions"]], ["completed", "completed"])
        self.assertEqual(result["remaining_steps"], [])

    def test_existing_app_without_registered_cli_is_not_reinstalled(self):
        with (
            patch.object(helper, "prerequisites", return_value=state()),
            patch.object(helper, "macos_app_present", return_value=True),
            patch.object(helper.subprocess, "run") as run,
        ):
            result = helper.bootstrap(True)
        self.assertFalse(result["ready_for_orca_tasks"])
        self.assertEqual(result["actions"], [])
        self.assertIn("Register its CLI", result["remaining_steps"][0])
        run.assert_not_called()

    def test_existing_stopped_app_is_opened_without_reinstall(self):
        complete = subprocess.CompletedProcess([], 0, "", "")
        with (
            patch.object(
                helper,
                "prerequisites",
                side_effect=[state(True, False, False), state(True, True, True)],
            ),
            patch.object(helper.shutil, "which", side_effect=executable),
            patch.object(helper.subprocess, "run", return_value=complete) as run,
        ):
            result = helper.bootstrap(True)
        self.assertTrue(result["ready_for_orca_tasks"])
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], ["/example/orca", "open", "--json"])

    def test_active_or_unknown_runtime_is_not_restarted(self):
        for running in (True, None):
            with (
                self.subTest(running=running),
                patch.object(helper, "prerequisites", return_value=state(True, False, running)),
                patch.object(helper.subprocess, "run") as run,
            ):
                result = helper.bootstrap(True)
                self.assertFalse(result["ready_for_orca_tasks"])
                self.assertEqual(result["actions"], [])
                self.assertIn("do not restart", result["remaining_steps"][0])
                run.assert_not_called()

    def test_failed_installer_stops_without_open_or_automatic_retry(self):
        failure = subprocess.CompletedProcess([], 1, "", "System permission needed")
        with (
            patch.object(helper, "prerequisites", return_value=state()),
            patch.object(helper, "macos_app_present", return_value=False),
            patch.object(helper.sys, "platform", "darwin"),
            patch.object(helper.shutil, "which", side_effect=executable),
            patch.object(helper.subprocess, "run", return_value=failure) as run,
        ):
            result = helper.bootstrap(True)
        self.assertFalse(result["ready_for_orca_tasks"])
        self.assertEqual(run.call_count, 1)
        self.assertEqual(result["actions"][0]["status"], "failed")
        self.assertIn("System permission needed", result["actions"][0]["detail"])
        self.assertTrue(result["remaining_steps"])

    def test_installer_success_with_missing_cli_stays_unready(self):
        complete = subprocess.CompletedProcess([], 0, "", "")
        with (
            patch.object(helper, "prerequisites", return_value=state()),
            patch.object(helper, "macos_app_present", return_value=False),
            patch.object(helper.sys, "platform", "darwin"),
            patch.object(helper.shutil, "which", side_effect=executable),
            patch.object(helper.subprocess, "run", return_value=complete) as run,
        ):
            result = helper.bootstrap(True)
        self.assertFalse(result["ready_for_orca_tasks"])
        self.assertEqual(run.call_count, 1)
        self.assertIn("not on PATH", result["remaining_steps"][0])

    def test_uncertain_start_never_retries_or_launches_an_agent(self):
        with (
            patch.object(
                helper,
                "prerequisites",
                side_effect=[state(True, False, False), state(True, False, True)],
            ),
            patch.object(helper.shutil, "which", side_effect=executable),
            patch.object(
                helper.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired(["orca", "open"], 60),
            ) as run,
        ):
            result = helper.bootstrap(True)
        self.assertFalse(result["ready_for_orca_tasks"])
        self.assertEqual(run.call_count, 1)
        self.assertEqual(result["actions"][0]["status"], "unconfirmed")
        self.assertEqual(run.call_args.args[0], ["/example/orca", "open", "--json"])

    def test_platform_without_supported_automatic_install_stays_actionable(self):
        with (
            patch.object(helper, "prerequisites", return_value=state()),
            patch.object(helper, "macos_app_present", return_value=False),
            patch.object(helper.sys, "platform", "linux"),
            patch.object(helper.subprocess, "run") as run,
        ):
            result = helper.bootstrap(True)
        self.assertFalse(result["ready_for_orca_tasks"])
        self.assertIn("https://www.onorca.dev/docs/install", result["remaining_steps"][0])
        run.assert_not_called()

    def test_cli_plan_succeeds_but_incomplete_apply_returns_failure(self):
        for apply, code in ((False, 0), (True, 1)):
            output = io.StringIO()
            args = ["adopt.py", "bootstrap"] + (["--apply"] if apply else [])
            with (
                self.subTest(apply=apply),
                patch.object(sys, "argv", args),
                patch.object(
                    helper, "bootstrap", return_value={"ready_for_orca_tasks": False}
                ) as bootstrap,
                redirect_stdout(output),
            ):
                self.assertEqual(helper.main(), code)
                bootstrap.assert_called_once_with(apply)
                self.assertFalse(json.loads(output.getvalue())["ready_for_orca_tasks"])


if __name__ == "__main__":
    unittest.main()
