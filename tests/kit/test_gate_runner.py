"""Check trusted input selection and concrete runtime isolation arguments."""

import io
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
from orca_agent_workflow import run_gates as runner  # noqa: E402


def committed(gates):
    """The trusted ref's .agents/workflow.json with this gate section."""
    return json.dumps(
        {
            "version": 1,
            "runtime": {"package": "orca-agent-workflow", "version": "0.0.0"},
            "project": {"name": "Example", "repository": "example/app"},
            "roles": {},
            "gates": gates,
        }
    ).encode()


class GateRunnerTests(unittest.TestCase):
    def test_configuration_and_build_inputs_come_from_one_frozen_ref(self):
        calls = []
        data = {
            "dockerfile": "Dockerfile",
            "inputs": ["requirements.txt"],
            "timeout_seconds": 30,
            "memory": "1g",
        }

        def git(root, *args):
            calls.append(args)
            if args[0] == "rev-parse":
                return ("a" * 40).encode()
            if args[-1].endswith(":.agents/workflow.json"):
                return committed(data)
            return b"trusted bytes"

        with patch.object(runner.task_scope, "git_bytes", side_effect=git):
            config, files = runner.trusted_config(Path("/example"), "origin/main")
            self.assertEqual(config, data)
            self.assertEqual(
                set(files), {".agents/workflow.json", "Dockerfile", "requirements.txt"}
            )
            self.assertTrue(all(args[1].startswith("a" * 40 + ":") for args in calls[1:]))
            # No dockerfile: the pinned runtime's own image, never a file from the branch.
            data = {"dockerfile": None, "inputs": []}
            config, files = runner.trusted_config(Path("/example"), "origin/main")
            self.assertEqual(files["Dockerfile"], runner.DEFAULT_DOCKERFILE.read_bytes())
            self.assertEqual(config["dockerfile"], "Dockerfile")
            # A runtime inside the checkout (kit source, vendored copy) is the branch's own:
            # its image is read from the trusted ref, never from the working tree.
            with tempfile.TemporaryDirectory() as folder:
                checkout = Path(folder).resolve()
                inside = checkout / ".agents/runtime/orca_agent_workflow/gate.Dockerfile"
                inside.parent.mkdir(parents=True)
                inside.write_bytes(b"FROM branch-controlled")
                with patch.object(runner, "DEFAULT_DOCKERFILE", inside):
                    _, files = runner.trusted_config(checkout, "origin/main")
                self.assertEqual(files["Dockerfile"], b"trusted bytes")
                self.assertIn(
                    ("show", "a" * 40 + ":.agents/runtime/orca_agent_workflow/gate.Dockerfile"),
                    calls,
                )
            data = {"dockerfile": None, "inputs": ["Dockerfile"]}
            with self.assertRaisesRegex(ValueError, "gates.dockerfile"):
                runner.trusted_config(Path("/example"), "origin/main")

    def test_build_path_traversal_and_unbounded_timeout_are_refused(self):
        for changes in (
            {"inputs": ["../outside"]},
            {"timeout_seconds": 0},
            {"timeout_seconds": True},
            {"memory": "unlimited"},
        ):
            data = {"dockerfile": "Dockerfile", "inputs": [], **changes}

            def git(root, *args):
                if args[0] == "rev-parse":
                    return ("a" * 40).encode()
                return committed(data) if args[-1].endswith(":.agents/workflow.json") else b"x"

            with self.subTest(changes=changes), patch.object(
                runner.task_scope, "git_bytes", side_effect=git
            ):
                with self.assertRaises(ValueError):
                    runner.trusted_config(Path("/example"), "main")

    @staticmethod
    def listing(names, executable=()):
        """Fake `git ls-files`: plain names, or index entries for `-s`."""

        def git(root, *args):
            if "-s" in args:
                return b"".join(
                    f"{'100755' if n in executable else '100644'} {'0' * 40} 0\t{n}\0".encode()
                    for n in names
                )
            return b"".join(n.encode() + b"\0" for n in names)

        return git

    def test_snapshot_omits_credentials_and_refuses_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "code.py").write_text("safe")
            (root / ".env").write_text("synthetic secret")
            with patch.object(runner, "git", side_effect=self.listing(["code.py", ".env"])):
                data = runner.checkout_archive(root)
            with runner.tarfile.open(fileobj=io.BytesIO(data)) as archive:
                self.assertEqual(archive.getnames(), ["code.py"])
            try:
                (root / "link").symlink_to(root / "code.py")
            except OSError:
                self.skipTest("Creating symlinks needs Windows Developer Mode or admin rights")
            with patch.object(runner, "git", side_effect=self.listing(["link"])):
                with self.assertRaisesRegex(ValueError, "regular files"):
                    runner.checkout_archive(root)

    def test_snapshot_takes_executable_bits_from_the_git_index(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "test.sh").write_text("#!/bin/sh\n")
            (root / "notes.md").write_text("notes\n")
            (root / "test.sh").chmod(0o644)  # what a Windows working tree reports
            git = self.listing(["test.sh", "notes.md"], executable={"test.sh"})
            with patch.object(runner, "git", side_effect=git):
                data = runner.checkout_archive(root)
            with runner.tarfile.open(fileobj=io.BytesIO(data)) as archive:
                modes = {m.name: m.mode for m in archive.getmembers()}
        self.assertEqual(modes, {"test.sh": 0o755, "notes.md": 0o644})

    def test_default_ref_is_the_remotes_default_branch(self):
        with patch.object(runner, "git", return_value=b"origin/master\n"):
            self.assertEqual(runner.default_ref(Path("/example")), "origin/master")
        missing = subprocess.CalledProcessError(128, ["git"])
        with patch.object(runner, "git", side_effect=missing):
            with self.assertRaisesRegex(ValueError, "pass --ref"):
                runner.default_ref(Path("/example"))

    def test_gate_has_no_mounts_or_env_forwarding_and_cleans_owned_name_on_timeout(self):
        calls = []

        def run(argv, **kwargs):
            calls.append((argv, kwargs))
            if argv[1] == "run":
                raise subprocess.TimeoutExpired(argv, 1)
            return subprocess.CompletedProcess(argv, 0)

        with patch.object(runner.subprocess, "run", side_effect=run):
            with self.assertRaises(subprocess.TimeoutExpired):
                runner.run_gate("image", b"snapshot", "check", {"timeout_seconds": 1})
        argv, kwargs = calls[0]
        self.assertEqual(argv[argv.index("--network") + 1], "none")
        self.assertIn("--read-only", argv)
        self.assertEqual(argv[argv.index("--cap-drop") + 1], "ALL")
        self.assertFalse(set(argv) & {"--mount", "-v", "--volume", "-e", "--env", "--env-file"})
        self.assertEqual(kwargs["input"], b"snapshot")
        self.assertEqual(calls[1][0], ["docker", "rm", "--force", argv[argv.index("--name") + 1]])

    def test_remote_docker_endpoint_is_refused(self):
        with patch.dict(runner.os.environ, {"DOCKER_HOST": "tcp://example.invalid:2375"}):
            with self.assertRaisesRegex(ValueError, "local Docker"):
                runner.ensure_local_docker()


if __name__ == "__main__":
    unittest.main()
