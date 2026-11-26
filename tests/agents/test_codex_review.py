"""Codex reviewer adapter refusal rules; no provider or sandbox calls."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# The runtime under test: the kit's src/, or a vendored or installed copy.
sys.path.insert(
    0,
    os.environ.get("ORCA_AGENT_WORKFLOW_RUNTIME")
    or str(Path(__file__).resolve().parents[2] / "src"),
)
from orca_agent_workflow import codex_review


class CodexReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.binary = self.base / "codex/1.2.3/bin/codex"
        self.binary.parent.mkdir(parents=True)
        self.binary.write_text("synthetic codex")
        self.qualification = self.base / "qualification.json"
        self.policy = self.base / "policy.json"
        self.write_policy(enabled=True)
        self.write_qualification(passed=True)
        self.which = patch.object(codex_review, "codex_binary", return_value=self.binary)
        self.which.start()
        self.addCleanup(self.which.stop)
        # Refusal logic is platform-independent; the Windows guard has its own test.
        self.posix = patch.object(codex_review.task_scope, "WINDOWS", False)
        self.posix.start()
        self.addCleanup(self.posix.stop)

    def write_policy(self, enabled):
        reviewer = [{"agent": "codex", "model": "gpt-6.1-sol", "enabled": enabled}]
        config = {
            "version": 1,
            "runtime": {"package": "orca-agent-workflow", "version": "0.0.0"},
            "project": {"name": "Example", "repository": "example/app"},
            "roles": {"reviewer": reviewer},
        }
        self.policy.write_text(json.dumps(config))

    def write_qualification(self, passed, digest=None):
        record = {
            "passed": passed,
            "codex_sha256": digest or codex_review.task_scope.digest(self.binary),
            "codex_version": "codex-cli test",
            "profile_sha256": codex_review.profile_digest(self.binary),
            "adapter_sha256": codex_review.task_scope.digest(
                Path(codex_review.__file__).resolve()
            ),
        }
        self.qualification.write_text(json.dumps(record))

    def attempt(self):
        return codex_review.run(
            self.base / "manifest.json",
            self.base / "brief.md",
            self.policy,
            "gpt-6.1-sol",
            self.base / "out",
            self.qualification,
        )

    def test_failed_or_stale_qualification_refuses_to_run(self):
        self.write_qualification(passed=False)
        with self.assertRaisesRegex(ValueError, "qualification"):
            self.attempt()
        self.write_qualification(passed=True, digest="0" * 64)
        with self.assertRaisesRegex(ValueError, "qualification"):
            self.attempt()

    def test_qualification_for_another_profile_or_adapter_refuses_to_run(self):
        record = json.loads(self.qualification.read_text())
        for field in ("profile_sha256", "adapter_sha256"):
            changed = dict(record, **{field: "0" * 64})
            self.qualification.write_text(json.dumps(changed))
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "qualification"):
                self.attempt()

    def test_unversioned_install_layout_is_refused(self):
        for layout in ("usr/local/bin/codex", "opt/codex"):
            binary = self.base / layout
            with self.subTest(layout=layout), self.assertRaisesRegex(ValueError, "Unsupported"):
                codex_review.install_root(binary)
        self.assertEqual(codex_review.install_root(self.binary), self.base / "codex/1.2.3")

    def test_disabled_or_unknown_profile_refuses_to_run(self):
        self.write_policy(enabled=False)
        with self.assertRaisesRegex(ValueError, "not enabled"):
            self.attempt()
        self.write_policy(enabled=True)
        with self.assertRaisesRegex(ValueError, "not enabled"):
            codex_review.run(
                self.base / "manifest.json",
                self.base / "brief.md",
                self.policy,
                "gpt-6.1-terra",
                self.base / "out",
                self.qualification,
            )

    def test_profile_grants_only_review_folder_and_denies_temp_and_network(self):
        args = codex_review.profile_args(Path("/home/example/.cache/review"), self.binary)
        joined = " ".join(args)
        self.assertIn('"/home/example/.cache/review"="read"', joined)
        for path in ("/tmp", "/private/tmp", "/var/folders", "/private/var/folders"):
            self.assertIn(f'"{path}"="none"', joined)
        self.assertIn("permissions.review.network={enabled=false}", joined)
        self.assertIn('web_search="disabled"', joined)
        self.assertNotIn('"write"', joined)
        self.assertNotIn('"/opt/homebrew"=', joined)

    def test_windows_refuses_qualification_and_runs_before_touching_codex(self):
        with (
            patch.object(codex_review.task_scope, "WINDOWS", True),
            patch.object(codex_review, "sandboxed") as sandboxed,
        ):
            with self.assertRaisesRegex(ValueError, "not supported on Windows"):
                codex_review.qualify(self.base)
            with self.assertRaisesRegex(ValueError, "not supported on Windows"):
                self.attempt()
        sandboxed.assert_not_called()
        self.assertFalse((self.base / "out").exists())

    @unittest.skipIf(os.name == "nt", "Probes create canaries in /tmp; qualification is POSIX-only")
    def test_qualification_fails_if_any_probe_is_not_denied(self):
        (self.base / "AGENTS.md").write_text("checkout file")

        def fake(review, binary, *command):
            target = command[-1]
            if target.endswith("in.txt"):
                code, out = 0, "REVIEW-INPUT"
            elif target.endswith("AGENTS.md"):
                code, out = 0, ""  # the checkout is readable: the failure under test
            elif command[0].endswith("curl"):
                code, out = 6, ""
            else:
                code, out = 1, ""
            return codex_review.subprocess.CompletedProcess(command, code, out, "")

        version = codex_review.subprocess.CompletedProcess([], 0, "codex-cli test", "")
        with (
            patch.object(codex_review, "sandboxed", side_effect=fake),
            patch.object(codex_review, "CACHE", self.base / "cache"),
            patch.object(codex_review.subprocess, "run", return_value=version),
        ):
            record = codex_review.qualify(self.base)
        self.assertFalse(record["passed"])
        self.assertFalse(record["results"]["denies_checkout_read"])
        self.assertTrue(record["results"]["denies_network"])

    @unittest.skipIf(os.name == "nt", "Probes create canaries in /tmp; qualification is POSIX-only")
    def test_missing_checkout_target_cannot_qualify(self):
        def fake(review, binary, *command):
            ok = command[-1].endswith("in.txt")
            code = 0 if ok else (6 if command[0].endswith("curl") else 1)
            out = "REVIEW-INPUT" if ok else ""
            return codex_review.subprocess.CompletedProcess(command, code, out, "")

        version = codex_review.subprocess.CompletedProcess([], 0, "codex-cli test", "")
        with (
            patch.object(codex_review, "sandboxed", side_effect=fake),
            patch.object(codex_review, "CACHE", self.base / "cache"),
            patch.object(codex_review.subprocess, "run", return_value=version),
        ):
            record = codex_review.qualify(self.base / "no-checkout")
        self.assertIn("checkout", record["not_present"])
        self.assertFalse(record["passed"])


if __name__ == "__main__":
    unittest.main()
