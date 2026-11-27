"""Test init/start through user commands; no model calls or Orca server."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

try:
    import pty
except ImportError:  # Windows: no pseudo-terminal module
    pty = None

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = os.environ.get("ORCA_AGENT_WORKFLOW_RUNTIME") or str(ROOT / "src")


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.base = Path(self.folder.name).resolve()
        self.target = self.base / "my-app"
        self.tools = self.base / "bin"
        self.tools.mkdir()
        self.log = self.base / "calls.jsonl"
        self.env = dict(
            os.environ,
            PYTHONDONTWRITEBYTECODE="1",
            PYTHONSAFEPATH="1",
            PATH=str(self.tools) + os.pathsep + os.environ["PATH"],
            WORKFLOW_TEST_LOG=str(self.log),
            # The installed launcher runs the kit's source instead of fetching a release.
            ORCA_AGENT_WORKFLOW_RUNTIME=RUNTIME,
            PYTHONPATH=RUNTIME,
        )
        for name in ("claude", "codex"):
            self.fake_command(name, "import sys\nsys.exit(99)\n")
        self.fake_command("orca", r"""
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with Path(os.environ["WORKFLOW_TEST_LOG"]).open("a") as log:
    log.write(json.dumps(args) + "\n")
mode = os.environ.get("WORKFLOW_TEST_MODE", "registered")
if args[:2] == ["repo", "show"]:
    if mode == "transport":
        print(json.dumps({"ok": False, "error": {"code": "runtime_access_denied"}}))
        sys.exit(1)
    if mode in ("unregistered", "registration-failed"):
        print(json.dumps({"ok": False, "error": {"code": "repo_not_found"}}))
        sys.exit(1)
if args[:2] == ["repo", "add"] and mode == "registration-failed":
    print(json.dumps({"ok": False, "error": {"code": "refused"}}))
    sys.exit(1)
if args[:2] == ["worktree", "create"]:
    if mode == "launch-failed":
        print(json.dumps({"ok": False, "error": {"operationId": "synthetic-retry-id"}}))
        sys.exit(1)
    if mode == "launch-unknown":
        print("reply interrupted")
        sys.exit(1)
    prompt_outcome = "unknown" if mode == "launch-incomplete" else "journaled"
    workspace = {} if mode == "launch-missing-workspace" else {"path": "/fixture/first-task-2"}
    print(json.dumps({"ok": True, "result": {
        "worktree": workspace,
        "launch": {"outcome": {"kind": "structured", "handle": "synthetic-agent"},
                   "prompt": {"outcome": prompt_outcome}},
    }}))
else:
    print(json.dumps({"ok": True, "result": {"fixture": True}}))
""")

    def fake_command(self, name, source):
        """A fake CLI on PATH: a shebang script on POSIX; on Windows a real .exe built
        like pip's console scripts (launcher + shebang + zipped __main__.py), because
        workflow.py refuses batch launchers."""
        if os.name != "nt":
            path = self.tools / name
            path.write_text("#!" + sys.executable + "\n" + source)
            path.chmod(0o755)
            return
        try:
            from pip._vendor import distlib
        except ImportError:
            self.skipTest("Building fake Windows CLIs needs pip's bundled launcher")
        launcher = (Path(distlib.__file__).parent / "t64.exe").read_bytes()
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w") as archive:
            archive.writestr("__main__.py", source)
        shebang = f'#!"{sys.executable}"\r\n'.encode()
        (self.tools / f"{name}.exe").write_bytes(launcher + shebang + payload.getvalue())

    def command(self, script, *args):
        return subprocess.run(
            [sys.executable, str(script), *args],
            cwd=self.base,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=20,
        )

    def init(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "orca_agent_workflow", "init", "--target", str(self.target),
             "--coordinator", "codex", *args],
            cwd=self.base,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=20,
        )

    def setup_project(self, *args):
        return self.init("--apply", *args)

    def config(self):
        return json.loads((self.target / ".agents/workflow.json").read_text())

    def app(self, *args):
        return self.command(self.target / ".agents/workflow.py", *args)

    def commit(self):
        for args in (
            ["init", "-q"],
            ["add", "."],
            [
                "-c",
                "user.name=Example",
                "-c",
                "user.email=example@example.invalid",
                "-c",
                "core.hooksPath=/dev/null",
                "commit",
                "-qm",
                "synthetic app",
            ],
        ):
            subprocess.run(["git", "-C", str(self.target), *args], check=True, capture_output=True)

    def require_executable_fixtures(self):
        if os.name != "nt" and not os.access(self.tools / "orca", os.X_OK):
            self.skipTest("Temporary mount is noexec; fake CLI launch coverage runs on host/CI.")

    def calls(self):
        return (
            [json.loads(x) for x in self.log.read_text().splitlines()] if self.log.exists() else []
        )

    def test_preview_is_write_free_and_does_not_require_github(self):
        result = self.init("--stack", "node")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Nothing written", result.stdout)
        self.assertFalse(self.target.exists())
        self.assertEqual(self.calls(), [])

    def test_optional_files_are_installed_only_on_request(self):
        self.assertEqual(self.setup_project().returncode, 0)
        self.assertFalse((self.target / ".opencode").exists())
        self.assertFalse((self.target / ".githooks").exists())
        result = self.setup_project("--opencode", "--pre-push-hook")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.target / ".opencode/commands/start-task.md").is_file())
        self.assertTrue((self.target / ".githooks/pre-push").is_file())

    def test_adoption_revisions_before_commit_on_branch_and_after_integration(self):
        self.target.mkdir()
        (self.target / "README.md").write_text("Existing app")
        self.commit()

        def git(*args):
            return subprocess.check_output(
                ["git", "-C", str(self.target), *args], text=True
            ).strip()

        initial = git("rev-parse", "HEAD")
        no_default = json.loads(self.init().stdout)["current_revisions"]
        self.assertEqual(no_default["gate (origin default branch)"], "origin/HEAD unavailable")
        self.assertEqual(no_default["worker (merge base with origin/HEAD)"], "origin/HEAD unavailable")
        git("update-ref", "refs/remotes/origin/main", initial)
        git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
        git("switch", "-qc", "adoption")
        preview = json.loads(self.init().stdout)["current_revisions"]
        self.assertEqual(set(preview.values()), {f"{initial} (policy unavailable)"})
        self.assertEqual(self.setup_project().returncode, 0)
        uncommitted = self.app("status")
        self.assertNotEqual(uncommitted.returncode, 0)
        self.assertIn(f"{initial} (policy unavailable)", uncommitted.stdout)

        self.commit()
        adopted = git("rev-parse", "HEAD")
        branch = self.app("status")
        self.assertIn(f"workspace (committed HEAD): {adopted} (policy present)", branch.stdout)
        self.assertIn(f"gate (origin default branch): {initial} (policy unavailable)", branch.stdout)
        self.assertIn(f"worker (merge base with origin/HEAD): {initial} (policy unavailable)", branch.stdout)
        git("update-ref", "refs/remotes/origin/main", adopted)
        integrated = self.app("status")
        self.assertEqual(integrated.stdout.count(f"{adopted} (policy present)"), 3)

    def test_detects_node_checks_preserves_application_and_never_runs_checks(self):
        self.target.mkdir()
        (self.target / "package.json").write_text(
            json.dumps(
                {
                    "packageManager": "pnpm@10.0.0",
                    "scripts": {"test": "touch model-was-called", "check": "tsc --noEmit"},
                }
            )
        )
        (self.target / "README.md").write_text("My application\n")
        result = self.setup_project()
        self.assertEqual(result.returncode, 0, result.stderr)
        project = self.config()["project"]
        self.assertEqual(project["stack"], "node")
        self.assertEqual(project["checks"], ["pnpm run check", "pnpm run test"])
        self.assertEqual(project["repository"], "local/my-app")
        self.assertEqual(project["coordinator"]["agent"], "codex")
        self.assertEqual((self.target / "README.md").read_text(), "My application\n")
        self.assertFalse((self.target / "model-was-called").exists())
        self.assertFalse((self.target / ".git").exists())
        self.assertIsNone(self.config()["gates"]["dockerfile"])  # the standard-library image
        policy = self.config()
        self.assertFalse(policy["roles"]["implementer"][1]["enabled"])
        self.assertFalse(policy["roles"]["reviewer"][1]["enabled"])
        self.assertEqual(self.calls(), [])

    def test_setup_detects_origin_and_is_idempotent(self):
        self.target.mkdir()
        subprocess.run(["git", "init", "-q", str(self.target)], check=True, capture_output=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.target),
                "remote",
                "add",
                "origin",
                "git@github.com:example/my-app.git",
            ],
            check=True,
        )
        result = self.setup_project(
            "--stack", "python", "--check", "python3 -m unittest discover -s tests"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.config()["project"]["repository"],
            "example/my-app",
        )
        result = self.setup_project()
        self.assertEqual(result.returncode, 0, result.stderr)
        actions = {f["action"] for f in json.loads(result.stdout)["files"]}
        self.assertEqual(actions, {"unchanged"})

    def test_custom_instructions_are_kept_with_a_candidate_to_merge(self):
        self.target.mkdir()
        (self.target / "AGENTS.md").write_text("Custom rules")
        result = self.setup_project()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["requires_merge"], ["AGENTS.md"])
        self.assertEqual((self.target / "AGENTS.md").read_text(), "Custom rules")
        candidate = self.target / ".tmp/orca-agent-workflow/merge/AGENTS.md"
        self.assertIn("start-task", candidate.read_text())
        self.assertEqual(self.calls(), [])

    def interactive(self, responses, *args, script):
        if pty is None:
            self.skipTest("Interactive prompts need a POSIX pseudo-terminal to drive")
        master, slave = pty.openpty()
        try:
            with subprocess.Popen(
                [sys.executable, str(script), *args],
                stdin=slave,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=self.env,
            ) as process:
                os.write(master, responses)
                try:
                    output, errors = process.communicate(timeout=20)
                except subprocess.TimeoutExpired:
                    process.kill()
                    output, errors = process.communicate()
                    self.fail("Interactive command timed out: " + output + errors)
                return process.returncode, output, errors
        finally:
            os.close(master)
            os.close(slave)

    def test_start_without_a_task_asks_for_one_and_opens_coordinator(self):
        self.require_executable_fixtures()
        self.assertEqual(self.setup_project().returncode, 0)
        self.commit()
        code, output, errors = self.interactive(
            b"Build a small feature\n", "start", script=self.target / ".agents/workflow.py"
        )
        self.assertEqual(code, 0, errors)
        self.assertIn("What would you like", output)
        self.assertIn("Continue in Orca", output)
        self.assertEqual([x[:2] for x in self.calls()], [["repo", "show"], ["worktree", "create"]])

    def test_adoption_handoff_waits_for_first_task_and_identifies_session(self):
        self.require_executable_fixtures()
        self.assertEqual(self.setup_project().returncode, 0)
        blocked = self.app("start", "--wait-for-task")
        self.assertNotEqual(blocked.returncode, 0)
        self.commit()
        conflict = self.app("start", "--wait-for-task", "An existing task")
        self.assertNotEqual(conflict.returncode, 0)
        preview = self.app("start", "--wait-for-task", "--dry-run")
        self.assertEqual(preview.returncode, 0, preview.stderr)
        command = json.loads(preview.stdout)["command"]
        self.assertIn("ask the user for their first task and wait", command[command.index("--prompt") + 1])
        self.assertEqual(self.calls(), [])
        result = self.app("start", "--wait-for-task")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Orca workspace: /fixture/first-task-2", result.stdout)
        self.assertIn("Session: synthetic-agent", result.stdout)
        self.assertEqual([x[:2] for x in self.calls()], [["repo", "show"], ["worktree", "create"]])

    def test_generated_entrypoint_works_without_starter_and_helps_uncommitted_user(self):
        self.assertEqual(self.setup_project().returncode, 0)
        self.assertFalse((self.target / "scripts").exists())
        result = self.app("start", "Build a small feature", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertFalse(plan["ready_for_planning"])
        self.assertEqual(plan["model_calls"], 0)
        self.assertIn("commit", " ".join(plan["before_starting"]))
        self.assertEqual(self.calls(), [])
        result = self.app("start", "Build a feature")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_dry_run_and_real_launch_use_committed_base_and_safe_arguments(self):
        self.require_executable_fixtures()
        self.assertEqual(self.setup_project().returncode, 0)
        self.commit()
        task = "Build a page; $(touch should-not-exist)"
        result = self.app("start", task, "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertTrue(plan["ready_for_planning"])
        self.assertEqual(self.calls(), [])
        result = self.app("start", task)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([x[:2] for x in self.calls()], [["repo", "show"], ["worktree", "create"]])
        command = self.calls()[-1]
        self.assertEqual(
            command[command.index("--base-branch") + 1],
            subprocess.check_output(
                ["git", "-C", str(self.target), "rev-parse", "HEAD"], text=True
            ).strip(),
        )
        self.assertEqual(command[command.index("--setup") + 1], "skip")
        self.assertEqual(command[command.index("--agent") + 1], "codex")
        prompt = command[command.index("--prompt") + 1]
        self.assertIn(task, prompt)
        self.assertIn("Use start-task", prompt)
        self.assertIn("\n\nUser goal:\n", prompt)
        self.assertNotIn("\\n", prompt)
        self.assertIn("explicit user approval", prompt)
        self.assertIn("before any implementation worker dispatch", prompt)
        self.assertIn("--no-parent", command)
        self.assertFalse((self.base / "should-not-exist").exists())

    def test_linked_worktree_uses_main_repo_path_and_its_own_commit(self):
        self.require_executable_fixtures()
        self.assertEqual(self.setup_project().returncode, 0)
        self.commit()
        linked = self.base / "linked checkout"
        subprocess.run(["git", "-C", str(self.target), "worktree", "add", "--detach", str(linked)],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(linked), "-c", "user.name=Example",
                        "-c", "user.email=example@example.invalid", "-c", "core.hooksPath=/dev/null",
                        "commit", "--allow-empty", "-qm", "linked worktree only"],
                       check=True, capture_output=True)
        head = subprocess.check_output(["git", "-C", str(linked), "rev-parse", "HEAD"], text=True).strip()
        launcher = linked / ".agents/workflow.py"
        preview = self.command(launcher, "start", "--wait-for-task", "--dry-run")
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertEqual(self.calls(), [])
        plan = json.loads(preview.stdout)
        self.assertTrue(plan["ready_for_planning"], plan["before_starting"])
        command = plan["command"]
        self.assertEqual(command[command.index("--repo") + 1], f"path:{self.target}")
        self.assertEqual(command[command.index("--base-branch") + 1], head)

        self.env["WORKFLOW_TEST_MODE"] = "unregistered"
        launch = self.command(launcher, "start", "--wait-for-task")
        self.assertEqual(launch.returncode, 0, launch.stderr)
        self.assertEqual(self.calls(), [
            ["repo", "show", "--repo", f"path:{self.target}", "--json"],
            ["repo", "add", "--path", str(self.target), "--json"],
            command[1:],
        ])

    def test_start_registers_missing_project_once(self):
        self.require_executable_fixtures()
        self.assertEqual(self.setup_project().returncode, 0)
        self.commit()
        self.env["WORKFLOW_TEST_MODE"] = "unregistered"
        result = self.app("start", "Add a feature")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            [x[:2] for x in self.calls()],
            [["repo", "show"], ["repo", "add"], ["worktree", "create"]],
        )

    def test_unencodable_task_text_does_not_fail_a_finished_launch(self):
        self.require_executable_fixtures()
        self.assertEqual(self.setup_project().returncode, 0)
        self.commit()
        self.env["PYTHONIOENCODING"] = "ascii"
        result = self.app("start", "Übersetze die Startseite — 日本語")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([x[:2] for x in self.calls()], [["repo", "show"], ["worktree", "create"]])

    @unittest.skipUnless(os.name == "nt", "Batch launchers exist only on Windows")
    def test_batch_orca_launcher_is_refused_before_any_call(self):
        self.assertEqual(self.setup_project().returncode, 0)
        self.commit()
        batch = self.base / "batch-bin"
        batch.mkdir()
        (batch / "orca.cmd").write_text(
            f'@"{sys.executable}" -c "open(r\'{self.log}\', \'a\').write(\'ran\\n\')"\r\n',
            encoding="utf-8",
        )
        self.env["PATH"] = str(batch) + os.pathsep + self.env["PATH"]
        result = self.app("start", "Add a feature & echo injected")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("batch launcher", result.stderr)
        self.assertFalse(self.log.exists())

    def test_dirty_project_or_disabled_coordinator_cannot_start(self):
        self.assertEqual(self.setup_project().returncode, 0)
        self.commit()
        (self.target / "scratch.txt").write_text("Work in progress")
        result = self.app("start", "Add a feature")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])
        (self.target / "scratch.txt").unlink()
        path = self.target / ".agents/workflow.json"
        policy = json.loads(path.read_text())
        for profile in policy["roles"]["planner"]:
            profile["enabled"] = False
        path.write_text(json.dumps(policy))
        self.commit()
        result = self.app("start", "Add a feature")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("enabled exact coordinator", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_transport_registration_and_launch_failures_never_retry(self):
        self.require_executable_fixtures()
        self.assertEqual(self.setup_project().returncode, 0)
        self.commit()
        for mode, expected in (
            ("transport", [["repo", "show"]]),
            ("registration-failed", [["repo", "show"], ["repo", "add"]]),
            ("launch-failed", [["repo", "show"], ["worktree", "create"]]),
            ("launch-unknown", [["repo", "show"], ["worktree", "create"]]),
            ("launch-incomplete", [["repo", "show"], ["worktree", "create"]]),
            ("launch-missing-workspace", [["repo", "show"], ["worktree", "create"]]),
        ):
            with self.subTest(mode=mode):
                if self.log.exists():
                    self.log.unlink()
                self.env["WORKFLOW_TEST_MODE"] = mode
                result = self.app("start", "Add a feature")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual([x[:2] for x in self.calls()], expected)
                if mode.startswith("launch"):
                    self.assertIn("do not retry as a fresh launch", result.stderr)
                if mode == "launch-failed":
                    self.assertIn("synthetic-retry-id", result.stdout)


if __name__ == "__main__":
    unittest.main()
