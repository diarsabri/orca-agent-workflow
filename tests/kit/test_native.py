"""Exercise native verification discovery and outcome handling without Xcode."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, os.environ.get("ORCA_AGENT_WORKFLOW_RUNTIME") or str(ROOT / "src"))
from orca_agent_workflow import native

DESTINATION = "platform=iOS Simulator,id=01234567-89AB-CDEF-0123-456789ABCDEF"
SUCCESS = {
    "totalTestCount": 2, "passedTests": 1, "failedTests": 0, "skippedTests": 1,
    "devicesAndConfigurations": [{"device": {"modelName": "Fixture iPhone"}}],
}


class NativeCheckTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.base = Path(folder.name).resolve()
        self.root = self.base / "checkout"
        self.project = self.root / "App.xcodeproj"
        self.project.mkdir(parents=True)
        self.results = self.base / "results"
        self.results.mkdir()
        self.args = argparse.Namespace(
            container="App.xcodeproj", scheme="App", destination=DESTINATION, requires=[], timeout=42,
        )

    def test_preview_lists_native_metadata_without_running_commands(self):
        schemes = self.project / "xcshareddata/xcschemes"
        schemes.mkdir(parents=True)
        (schemes / "App.xcscheme").write_text(
            '<Scheme><TestAction><Testables><TestableReference>'
            '<BuildableReference BlueprintName="AppTests" />'
            '</TestableReference></Testables><TestPlans>'
            '<TestPlanReference reference="container:AppTests.xctestplan" />'
            '</TestPlans></TestAction></Scheme>', encoding="utf-8",
        )
        (schemes / "Invalid.xcscheme").write_text("<invalid", encoding="utf-8")
        lock = self.project / "project.xcworkspace/xcshareddata/swiftpm/Package.resolved"
        lock.parent.mkdir(parents=True)
        lock.touch()
        with patch.object(native.subprocess, "run") as run:
            report = native.preview(self.root)
            self.assertIsNone(native.preview(self.base))
            run.assert_not_called()
        self.assertEqual(report["containers"], ["App.xcodeproj"])
        self.assertEqual(report["shared_schemes"][0], {
            "container": "App.xcodeproj", "scheme": "App", "test_targets": ["AppTests"],
            "test_plans": ["container:AppTests.xctestplan"],
        })
        self.assertIn("problem", report["shared_schemes"][1])
        self.assertEqual(report["dependency_locks"], [lock.relative_to(self.root).as_posix()])

    def test_destination_requires_a_simulator_id(self):
        self.assertTrue(native.simulator_destination(DESTINATION))
        for value in ("platform=iOS,id=01234567-89AB-CDEF-0123-456789ABCDEF",
                      "platform=iOS Simulator,name=Fixture", "platform=iOS Simulator,id=invalid"):
            with self.subTest(value=value):
                self.assertFalse(native.simulator_destination(value))

    def test_invalid_paths_and_dirty_checkout_stop_before_xcode(self):
        scenarios = (
            ("../App.xcodeproj", [], b"", "traversal"),
            ("Absent.xcodeproj", [], b"", "existing .xcodeproj"),
            ("App.xcodeproj", ["../Vendor"], b"", "traversal"),
            ("App.xcodeproj", ["Vendor/Missing.xcframework"], b"", "Missing required"),
            ("App.xcodeproj", [], b" M App.swift\n", "clean, committed"),
        )
        for container, requires, status, error in scenarios:
            with (
                self.subTest(error=error),
                patch.object(native.sys, "platform", "darwin"),
                patch.object(native.task_scope, "git_bytes", side_effect=[b"fixture-revision", status]),
                patch.object(native, "checked_output") as xcode,
            ):
                self.args.container, self.args.requires = container, requires
                with self.assertRaisesRegex(ValueError, error):
                    native.run(self.root, self.args, {})
                xcode.assert_not_called()

    def test_result_counts_and_build_failures(self):
        scenarios = (
            ("pass", SUCCESS, 0, None),
            ("no bundle", None, 70, "no result bundle"),
            ("zero tests", dict(SUCCESS, totalTestCount=0, passedTests=0), 0, "zero tests"),
            ("invalid counts", dict(SUCCESS, passedTests="1"), 0, "valid test counts"),
            ("failure", dict(SUCCESS, passedTests=0, failedTests=1), 0, "test or build failures"),
            ("nonzero exit", SUCCESS, 65, "test or build failures"),
        )
        for case, summary, exit_code, error in scenarios:
            with self.subTest(case=case), tempfile.TemporaryDirectory(dir=self.results) as directory:
                output = Path(directory)
                if summary is not None:
                    (output / "Tests.xcresult").mkdir()
                with (
                    patch.object(native.sys, "platform", "darwin"),
                    patch.object(native.task_scope, "git_bytes", side_effect=[b"fixture-revision", b""] * 2),
                    patch.object(native.tempfile, "mkdtemp", return_value=str(output)),
                    patch.object(native, "checked_output", side_effect=["Xcode fixture", json.dumps(summary)]),
                    patch.object(native.subprocess, "run", return_value=subprocess.CompletedProcess([], exit_code)) as run,
                ):
                    report = {}
                    if error:
                        with self.assertRaisesRegex(ValueError, error):
                            native.run(self.root, self.args, report)
                    else:
                        native.run(self.root, self.args, report)
                        self.assertEqual(report["passedTests"], 1)
                        self.assertEqual(report["skippedTests"], 1)
                        self.assertEqual(report["devices"], [{"modelName": "Fixture iPhone"}])
                    command = run.call_args.args[0]
                    self.assertEqual(command, [
                        "/usr/bin/xcodebuild", "-project", str(self.project), "-scheme", "App",
                        "-destination", DESTINATION, "-derivedDataPath", str(output / "DerivedData"),
                        "-resultBundlePath", str(output / "Tests.xcresult"),
                        "-disableAutomaticPackageResolution", "-parallel-testing-enabled", "NO",
                        "CODE_SIGN_IDENTITY=-", "test",
                    ])
                    self.assertEqual(report["revision"], "fixture-revision")
