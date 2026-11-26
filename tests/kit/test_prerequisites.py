"""Check Orca readiness without installing software or starting any sessions."""

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
    "prerequisite_helper", ROOT / "skills/setup-orca-workflow/scripts/adopt.py"
)
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


class PrerequisiteTests(unittest.TestCase):
    def test_missing_orca_reports_required_dependency_and_install_guidance(self):
        with (
            patch.object(helper.shutil, "which", return_value=None),
            patch.object(helper.subprocess, "run") as run,
        ):
            result = helper.prerequisites(True)
        self.assertFalse(result["ready_for_orca_tasks"])
        self.assertTrue(result["orca"]["required"])
        self.assertEqual(result["orca"]["runtime"], "not_installed")
        self.assertIn("stablyai/orca", result["orca"]["repository"])
        self.assertIn("stablyai/orca/orca", result["orca"]["macos_install_command"])
        run.assert_not_called()

    def test_installed_binary_is_not_treated_as_runtime_readiness(self):
        with (
            patch.object(helper.shutil, "which", return_value="/example/orca"),
            patch.object(helper.subprocess, "run") as run,
        ):
            result = helper.prerequisites()
        self.assertTrue(result["orca"]["installed"])
        self.assertEqual(result["orca"]["runtime"], "not_checked")
        self.assertFalse(result["ready_for_orca_tasks"])
        run.assert_not_called()

    def test_ready_runtime_requires_success_and_explicit_reachability(self):
        response = {
            "ok": True,
            "result": {
                "runtime": {"state": "ready", "reachable": True, "private_extra": "do-not-echo"}
            },
        }
        complete = subprocess.CompletedProcess([], 0, json.dumps(response), "")
        with (
            patch.object(helper.shutil, "which", return_value="/example/orca"),
            patch.object(helper.subprocess, "run", return_value=complete) as run,
        ):
            result = helper.prerequisites(True)
        self.assertTrue(result["ready_for_orca_tasks"])
        self.assertNotIn("do-not-echo", json.dumps(result))
        self.assertEqual(run.call_args.args[0], ["/example/orca", "status", "--json"])
        self.assertEqual(run.call_args.kwargs["timeout"], 15)

    def test_unavailable_failed_and_malformed_status_never_report_ready(self):
        responses = [
            subprocess.CompletedProcess(
                [],
                0,
                json.dumps(
                    {"ok": True, "result": {"runtime": {"state": "ready", "reachable": False}}}
                ),
                "",
            ),
            subprocess.CompletedProcess(
                [],
                1,
                json.dumps(
                    {"ok": True, "result": {"runtime": {"state": "ready", "reachable": True}}}
                ),
                "",
            ),
            subprocess.CompletedProcess([], 0, json.dumps({"ok": False}), ""),
            subprocess.CompletedProcess([], 0, "[]", ""),
            subprocess.CompletedProcess([], 0, "not JSON", ""),
        ]
        for complete in responses:
            with (
                self.subTest(status=complete.stdout),
                patch.object(helper.shutil, "which", return_value="/example/orca"),
                patch.object(helper.subprocess, "run", return_value=complete),
            ):
                result = helper.prerequisites(True)
                self.assertFalse(result["ready_for_orca_tasks"])
                self.assertEqual(result["orca"]["runtime"], "unavailable")

    def test_timeout_or_process_failure_reports_action_without_mutation(self):
        for error in (subprocess.TimeoutExpired(["orca"], 15), OSError("synthetic failure")):
            with (
                self.subTest(error=error),
                patch.object(helper.shutil, "which", return_value="/example/orca"),
                patch.object(helper.subprocess, "run", side_effect=error) as run,
            ):
                result = helper.prerequisites(True)
                self.assertFalse(result["ready_for_orca_tasks"])
                self.assertIn("Open Orca", result["orca"]["next"])
                self.assertEqual(run.call_count, 1)

    def test_cli_returns_failure_for_missing_prerequisite(self):
        output = io.StringIO()
        with (
            patch.object(sys, "argv", ["adopt.py", "prerequisites", "--check-runtime"]),
            patch.object(helper.shutil, "which", return_value=None),
            redirect_stdout(output),
        ):
            code = helper.main()
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(output.getvalue())["ready_for_orca_tasks"])


if __name__ == "__main__":
    unittest.main()
