"""Adoption through the commands a project uses: init, the launcher and migrate."""

import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(os.environ.get("ORCA_AGENT_WORKFLOW_RUNTIME") or ROOT / "src")
sys.path.insert(0, str(SOURCE))
from orca_agent_workflow import __version__, install, task_scope  # noqa: E402

KIT_OWN = {".gitignore", ".gitattributes", ".agents/workflow.json", "AGENTS.md"}


class InitTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.base = Path(self.folder.name).resolve()
        self.target = self.base / "application"
        self.env = dict(os.environ, PYTHONPATH=str(SOURCE), PYTHONDONTWRITEBYTECODE="1")
        self.env.pop("ORCA_AGENT_WORKFLOW_RUNTIME", None)

    def run_cli(self, *args, cwd=None, env=None):
        return subprocess.run(
            [sys.executable, "-m", "orca_agent_workflow", *args],
            cwd=cwd or self.base,
            env=env or self.env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def init(self, *extra):
        return self.run_cli(
            "init",
            "--target",
            str(self.target),
            "--name",
            "Example App",
            "--repository",
            "example/application",
            "--coordinator",
            "claude",
            *extra,
        )

    def launcher(self, *args, env=None):
        return subprocess.run(
            [sys.executable, str(self.target / ".agents/workflow.py"), *args],
            cwd=self.base,
            env=env or dict(self.env, ORCA_AGENT_WORKFLOW_RUNTIME=str(SOURCE)),
            capture_output=True,
            text=True,
            timeout=60,
        )

    def files(self):
        return sorted(
            p.relative_to(self.target).as_posix()
            for p in self.target.rglob("*")
            if p.is_file() and ".git" not in p.relative_to(self.target).parts[:1]
        )

    def test_preview_writes_nothing(self):
        result = self.init()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)["applied"])
        self.assertFalse(self.target.exists())

    def test_install_writes_only_workflow_files_and_keeps_the_application(self):
        self.target.mkdir()
        (self.target / "README.md").write_text("existing application\n")
        (self.target / "LICENSE").write_text("Application license stays unchanged\n")
        result = self.init("--check", "python3 -m unittest discover -s tests", "--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = sorted(install.template_files()) + ["LICENSE", "README.md"]
        self.assertEqual(self.files(), sorted(expected))
        self.assertLess(len(install.template_files()), 30)
        for folder in ("docs", "tests", "specs", "scripts", ".opencode", ".githooks"):
            self.assertFalse((self.target / folder).exists(), folder)
        config = json.loads((self.target / ".agents/workflow.json").read_text())
        self.assertEqual(config["runtime"], {"package": "orca-agent-workflow", "version": __version__})
        self.assertEqual(config["project"]["repository"], "example/application")
        self.assertEqual(config["project"]["checks"], ["python3 -m unittest discover -s tests"])
        self.assertFalse(config["roles"]["reviewer"][1]["enabled"])
        self.assertEqual((self.target / "README.md").read_text(), "existing application\n")
        self.assertEqual(
            (self.target / ".agents/LICENSE").read_bytes(), (ROOT / "LICENSE").read_bytes()
        )
        if os.name == "posix":
            # The isolated gate mounts its temporary directory noexec.
            self.assertTrue((self.target / ".agents/workflow.py").stat().st_mode & stat.S_IXUSR)
        agents = (self.target / "AGENTS.md").read_text()
        self.assertNotIn("starter-kit repository", agents)
        self.assertIn("python3 .agents/workflow.py check", agents)
        # Kit docs are linked as they were for this version, and local links resolve.
        guide = (self.target / ".agents/README.md").read_text()
        self.assertIn(f"orca-agent-workflow/blob/v{__version__}/docs/", guide)
        self.assertNotIn("/blob/main/", guide)
        links = importlib.util.spec_from_file_location("links", ROOT / "scripts/check_docs.py")
        check_docs = importlib.util.module_from_spec(links)
        links.loader.exec_module(check_docs)
        count, errors = check_docs.check(self.target)
        self.assertGreater(count, 0)
        self.assertEqual(errors, [])
        result = self.launcher("check")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_optional_groups_install_on_request_and_stay_checked(self):
        result = self.init("--opencode", "--pre-push-hook", "--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.target / ".opencode/commands/start-task.md").is_file())
        if os.name == "posix":
            self.assertTrue((self.target / ".githooks/pre-push").stat().st_mode & stat.S_IXUSR)
        self.assertEqual(self.launcher("check").returncode, 0)
        (self.target / ".opencode/commands/review-pr.md").unlink()
        result = self.launcher("check")
        self.assertIn("OpenCode command drift: review-pr", result.stderr)
        with self.assertRaisesRegex(ValueError, "Unknown optional"):
            install.template_files(("vim",))

    def test_existing_files_are_kept_and_rerunning_changes_nothing(self):
        self.target.mkdir()
        (self.target / ".gitignore").write_text("local-assets/\n")
        (self.target / "CLAUDE.md").write_text("Custom Claude rules\n")
        result = self.init("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["requires_merge"], ["CLAUDE.md"])
        self.assertEqual((self.target / "CLAUDE.md").read_text(), "Custom Claude rules\n")
        merge = self.target / install.MERGE_FOLDER / "CLAUDE.md"
        self.assertIn("@AGENTS.md", merge.read_text())
        ignore = (self.target / ".gitignore").read_text()
        self.assertTrue(ignore.startswith("local-assets/\n"))
        self.assertIn(".tmp/", ignore)
        before = {p: (self.target / p).read_bytes() for p in self.files()}
        result = self.init("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        actions = {f["path"]: f["action"] for f in json.loads(result.stdout)["files"]}
        self.assertEqual(actions.pop("CLAUDE.md"), "merge")
        self.assertEqual(set(actions.values()), {"unchanged"})
        self.assertEqual(before, {p: (self.target / p).read_bytes() for p in self.files()})

    def test_symlinks_bad_identity_and_non_directory_targets_are_refused(self):
        self.target.mkdir()
        outside = self.base / "outside"
        outside.mkdir()
        (self.target / ".agents").symlink_to(outside, target_is_directory=True)
        result = self.init("--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((self.target / "AGENTS.md").exists())
        shutil.rmtree(self.target)
        result = self.init("--repository", "bad; shell-command", "--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.target.exists())
        self.target.write_text("keep")
        self.assertNotEqual(self.init("--apply").returncode, 0)
        self.assertEqual(self.target.read_text(), "keep")

    def test_launcher_refuses_another_version_and_explains_a_missing_uv(self):
        self.assertEqual(self.init("--apply").returncode, 0)
        subprocess.run(["git", "init", "-q", str(self.target)], check=True)
        path = self.target / ".agents/workflow.json"
        config = json.loads(path.read_text())
        config["runtime"]["version"] = "9.9.9"
        path.write_text(json.dumps(config))
        result = self.launcher("check")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("pins 9.9.9", result.stderr)
        bare = {k: v for k, v in self.env.items() if k != "PYTHONPATH"}
        bare["PATH"] = str(self.base / "no-tools")
        result = self.launcher("check", env=bare)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("orca-agent-workflow@9.9.9", result.stderr)

    def test_vendored_project_passes_the_runtime_suite_on_its_own_copy(self):
        result = self.init("--vendor", "--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        runtime = self.target / ".agents/runtime"
        self.assertTrue((runtime / "orca_agent_workflow/task_scope.py").is_file())
        bare = {k: v for k, v in self.env.items() if k != "PYTHONPATH"}
        result = self.launcher("--version", env=bare)
        self.assertEqual(result.stdout.strip(), __version__, result.stderr)
        # The kit's runtime tests are not installed; run them against the vendored copy.
        shutil.copytree(ROOT / "tests/agents", self.target / "tests/agents")
        for args in (
            ["init", "-q"],
            ["add", "."],
            ["-c", "user.name=Example", "-c", "user.email=example@example.invalid",
             "commit", "-qm", "synthetic bootstrap"],
        ):
            subprocess.run(
                ["git", "-C", str(self.target), *args], check=True, stdout=subprocess.DEVNULL
            )
        result = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests/agents", "-v"],
            cwd=self.target,
            env=dict(bare, ORCA_AGENT_WORKFLOW_RUNTIME=str(runtime)),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(str(runtime), subprocess.run(
            [sys.executable, "-c", "import orca_agent_workflow as m; print(m.__file__)"],
            env=dict(bare, PYTHONPATH=str(runtime)), capture_output=True, text=True,
        ).stdout)
        # Only deliberate platform splits may skip; anything else is lost coverage.
        platform_only = {
            "Windows broker path",
            "Probes create canaries in /tmp; qualification is POSIX-only",
            "8.3 short names are disabled on this volume",
            "Creating symlinks needs Windows Developer Mode or admin rights",
        }
        reasons = set(re.findall(r"skipped '([^']*)'", result.stderr))
        self.assertLessEqual(reasons, platform_only, result.stderr)

    def test_the_kit_runs_on_the_files_it_installs(self):
        """The kit's own project files are the template's, except its own config and rules."""
        for relative, source in install.template_files(("opencode", "pre-push-hook")).items():
            if relative in KIT_OWN:
                continue
            with self.subTest(path=relative):
                self.assertEqual((ROOT / relative).read_bytes(), source.read_bytes())
        template = (install.TEMPLATE / "AGENTS.md").read_text()
        contract = template[: template.index("Run this application's actual checks")]
        self.assertTrue((ROOT / "AGENTS.md").read_text().startswith(contract))
        config = task_scope.load_config((ROOT / ".agents/workflow.json").read_bytes())
        self.assertEqual(config["runtime"]["version"], __version__)


class MigrateTests(unittest.TestCase):
    """A v1 project: runtime and four configuration files copied into the repository."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.target = Path(self.folder.name).resolve() / "old-app"
        roles = json.loads((install.TEMPLATE / "agents/workflow.json").read_text())["roles"]
        files = {
            ".agents/project.json": {
                "version": 1,
                "name": "Old App",
                "repository": "example/old-app",
                "checks": ["make test"],
            },
            ".agents/orchestration.json": {
                "version": 2,
                "repository": "example/old-app",
                "max_fix_rounds": 3,
                "reviewer_provider_differs_from_planner": "preferred",
                "roles": roles,
            },
            ".agents/gates.json": {
                "version": 1,
                "dockerfile": "scripts/agents/gate_sandbox/Dockerfile",
                "inputs": [],
                "timeout_seconds": 600,
                "memory": "2g",
            },
            "scripts/agents/sensitive.json": {
                "patterns": [
                    *json.loads((install.PACKAGE / "sensitive.json").read_text())["patterns"],
                    "terraform/*",
                ]
            },
        }
        for relative, value in files.items():
            path = self.target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value))
        dockerfile = self.target / "scripts/agents/gate_sandbox/Dockerfile"
        dockerfile.parent.mkdir(parents=True)
        dockerfile.write_bytes((install.PACKAGE / "gate.Dockerfile").read_bytes())
        (self.target / "scripts/agents/task_scope.py").write_text("# v1 runtime\n")
        (self.target / "workflow.py").write_text("# v1 launcher\n")
        (self.target / "AGENTS.md").write_text("Custom contract kept by the team\n")
        (self.target / ".opencode/commands").mkdir(parents=True)

    def migrate(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "orca_agent_workflow", "migrate", "--target", str(self.target),
             *args],
            env=dict(os.environ, PYTHONPATH=str(SOURCE)),
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_preview_then_apply_converts_without_deleting(self):
        before = sorted(p for p in self.target.rglob("*") if p.is_file())
        result = self.migrate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, sorted(p for p in self.target.rglob("*") if p.is_file()))
        result = self.migrate("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        config = json.loads((self.target / ".agents/workflow.json").read_text())
        self.assertEqual(config["project"]["checks"], ["make test"])
        self.assertEqual(config["runtime"]["version"], __version__)
        self.assertEqual(config["max_fix_rounds"], 3)
        self.assertIsNone(config["gates"]["dockerfile"])  # the stock image ships with the runtime
        self.assertEqual(config["gates"]["timeout_seconds"], 600)
        self.assertEqual(config["sensitive_patterns"], ["terraform/*"])
        self.assertIn("AGENTS.md", report["requires_merge"])
        self.assertEqual((self.target / "AGENTS.md").read_text(), "Custom contract kept by the team\n")
        self.assertTrue((self.target / ".opencode/commands/start-task.md").is_file())
        for path in (".agents/project.json", "scripts/agents/task_scope.py"):
            self.assertIn(path, report["removable"])
            self.assertTrue((self.target / path).is_file())
        # A generic name may be the project's own file: listed for review, never as removable.
        self.assertIn("workflow.py", report["review_before_removing"])
        self.assertNotIn("workflow.py", report["removable"])
        self.assertTrue((self.target / "workflow.py").is_file())
        self.assertNotEqual(self.migrate().returncode, 0)  # already migrated: use init

    def test_pilot_layout_keeps_custom_gate_image_and_project_scripts(self):
        (self.target / ".agents/project.json").unlink()
        (self.target / ".agents/gates.json").unlink()
        (self.target / "scripts/agents/gate_sandbox/Dockerfile").write_text("FROM custom\n")
        (self.target / "scripts/agents/run_smoke.sh").write_text("# the project's own\n")
        result = self.migrate("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        config = json.loads((self.target / ".agents/workflow.json").read_text())
        self.assertEqual(config["project"]["repository"], "example/old-app")
        self.assertEqual(config["gates"]["dockerfile"], "scripts/agents/gate_sandbox/Dockerfile")
        self.assertIn("set project.name and project.checks", " ".join(report["notes"]))
        self.assertNotIn("scripts/agents/gate_sandbox/Dockerfile", report["removable"])
        self.assertIn("scripts/agents/run_smoke.sh", report["review_before_removing"])
        self.assertNotIn("scripts/agents/run_smoke.sh", report["removable"])


if __name__ == "__main__":
    unittest.main()
