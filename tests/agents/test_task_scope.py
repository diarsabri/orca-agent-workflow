"""Semantic boundary, revision, protocol, and owned-client lifecycle tests."""

import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# The runtime under test: the kit's src/, or a vendored or installed copy.
sys.path.insert(
    0,
    os.environ.get("ORCA_AGENT_WORKFLOW_RUNTIME")
    or str(Path(__file__).resolve().parents[2] / "src"),
)
from orca_agent_workflow import __version__
from orca_agent_workflow import task_scope as module

# The checkout these tests run in: the kit, or a project whose runtime they test.
CHECKOUT = Path(__file__).resolve().parents[2]


class TaskScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "repo"
        self.root.mkdir()
        for name, text in [
            ("read.txt", "read only"),
            ("write.txt", "before"),
            ("private.txt", "synthetic private"),
        ]:
            (self.root / name).write_text(text)
        self.manifest = self.base / "manifest.json"
        self.data = {
            "version": 3,
            "root": str(self.root),
            "head": "a" * 40,
            "role": "implementer",
            "approval_reference": "user-approved synthetic test",
            "expires_at": time.time() + 1800,
            "read": ["read.txt"],
            "write": ["write.txt", "new.txt"],
            "sensitive": [],
            "commands": {},
            "runtime_read": [],
            "infrastructure": [],
            "policy_base": "b" * 40,
            "sensitive_extra": [],
        }
        self.policy = {
            "version": 2,
            "roles": {
                "reviewer": [{"agent": "claude", "model": "claude-opus-5-5", "enabled": True}],
                "implementer": [
                    {"agent": "claude", "model": "claude-sonnet-5-5", "enabled": True},
                    {"agent": "codex", "model": None, "enabled": False},
                ],
            },
        }
        self.git = patch.object(module, "git_bytes", side_effect=self.git_result)
        self.git.start()
        self.addCleanup(self.git.stop)
        self.ignored = set()
        self.check_ignore = patch.object(
            module,
            "git_ignored",
            # Like the real repository: everything under .tmp/ is ignored.
            side_effect=lambda root, values: {
                v for v in values if v in self.ignored or v.startswith(".tmp/")
            },
        )
        self.check_ignore.start()
        self.addCleanup(self.check_ignore.stop)

    def config(self, roles=None):
        """A committed .agents/workflow.json around a roles policy."""
        return {
            "version": 1,
            "runtime": {"package": "orca-agent-workflow", "version": __version__},
            "project": {"name": "Example", "repository": "example/project", "checks": []},
            "reviewer_provider_differs_from_planner": "preferred",
            "roles": roles or self.policy["roles"],
        }

    def git_result(self, root, *args):
        if args[0] == "show" and args[1] == "b" * 40 + ":.agents/workflow.json":
            return json.dumps(self.config()).encode()
        if args[0] == "rev-parse":
            return b"a" * 40
        if args[0] == "diff":
            return b""
        if args[0] == "cat-file":
            return b"read only"
        raise AssertionError(args)

    def scope(self, bundle=None):
        self.manifest.write_text(json.dumps(self.data))
        return module.Scope(self.manifest, bundle)

    def prepared(self, reviewer=False):
        if reviewer:
            self.data.update(role="reviewer", write=[])
        client = self.base / "claude"
        client.write_text("synthetic executable")
        bundle = self.base / "bundle"
        with patch.object(module, "claude_executable", return_value=str(client)):
            module.prepare(
                self.scope(), bundle, "claude-opus-5-5" if reviewer else "claude-sonnet-5-5"
            )
        scope = module.Scope(bundle / "manifest.json", bundle)
        module.atomic_json(bundle / "probe.json", module.probe(scope, bundle))
        return scope, bundle, client

    def test_only_declared_files_are_readable_and_writable(self):
        scope = self.scope()
        self.assertEqual(scope.call("read_file", {"path": "read.txt"})["text"], "read only")
        for value in ("private.txt", "../manifest.json", str(self.root / "read.txt")):
            with self.assertRaises((ValueError, PermissionError)):
                scope.call("read_file", {"path": value})
        with self.assertRaises(PermissionError):
            scope.call("write_file", {"path": "read.txt", "content": "bad"})
        scope.call("write_file", {"path": "write.txt", "content": "after"})
        scope.call("write_file", {"path": "new.txt", "content": "new"})
        self.assertEqual((self.root / "write.txt").read_text(), "after")
        self.assertEqual((self.root / "new.txt").read_text(), "new")

    def test_large_unicode_inputs_are_paged_without_losing_content(self):
        text = 'quote " / Swedish å / emoji 🐋\n' * 4000
        (self.root / "read.txt").write_text(text, encoding="utf-8", newline="\n")
        scope = self.scope()
        offset = 0
        parts = []
        while offset is not None:
            page = scope.call("read_file", {"path": "read.txt", "offset": offset, "limit": 12000})
            self.assertLessEqual(len(json.dumps(page, ensure_ascii=False).encode()), 16000)
            parts.append(page["text"])
            offset = page["next_offset"]
        self.assertEqual("".join(parts), text)
        for values in ({"offset": -1}, {"offset": True}, {"limit": 0}, {"limit": 20000}):
            with self.assertRaises(ValueError):
                scope.call("read_file", {"path": "read.txt", **values})

    def test_expiry_revocation_and_manifest_change_end_authority(self):
        scope = self.scope()
        with patch.object(module.time, "time", return_value=self.data["expires_at"] + 1):
            with self.assertRaises(module.ScopeEnded):
                scope.call("read_file", {"path": "read.txt"})
        self.manifest.with_suffix(".revoked").touch()
        with self.assertRaises(module.ScopeEnded):
            scope.call("read_file", {"path": "read.txt"})
        self.manifest.with_suffix(".revoked").unlink()
        self.manifest.write_text("{}")
        with self.assertRaises(module.ScopeEnded):
            scope.call("read_file", {"path": "read.txt"})

    def test_advanced_head_and_dirty_reviewer_checkout_are_rejected(self):
        scope = self.scope()
        with patch.object(module, "git_bytes", return_value=b"b" * 40):
            with self.assertRaisesRegex(module.ScopeEnded, "head changed"):
                scope.call("read_file", {"path": "read.txt"})
        self.data.update(role="reviewer", write=[])

        def dirty(root, *args):
            if args[0] == "diff":
                raise subprocess.CalledProcessError(1, ["git", "diff"])
            return b"a" * 40

        with patch.object(module, "git_bytes", side_effect=dirty):
            with self.assertRaisesRegex(module.ScopeEnded, "clean tracked"):
                self.scope()

    def test_review_reads_frozen_committed_bytes_and_detects_snapshot_tampering(self):
        scope, bundle, _ = self.prepared(reviewer=True)
        (self.root / "read.txt").write_text("later working-tree content")
        # Even if a status check missed a race, the actual read uses committed bytes.
        self.assertEqual(scope.call("read_file", {"path": "read.txt"})["text"], "read only")
        item = scope.inputs["read.txt"]
        (bundle / "inputs" / item["file"]).write_text("tampered")
        with self.assertRaisesRegex(module.ScopeEnded, "Frozen review input changed"):
            scope.call("read_file", {"path": "read.txt"})

    def test_link_swaps_and_hardlinks_do_not_escape(self):
        scope = self.scope()
        target = self.root / "write.txt"
        target.unlink()
        try:
            target.symlink_to(self.root / "private.txt")
        except OSError:
            self.skipTest("Creating symlinks needs Windows Developer Mode or admin rights")
        with self.assertRaises(OSError):
            scope.call("write_file", {"path": "write.txt", "content": "bad"})
        target.unlink()
        os.link(self.root / "private.txt", target)
        with self.assertRaises(PermissionError):
            scope.call("write_file", {"path": "write.txt", "content": "bad"})
        self.assertEqual((self.root / "private.txt").read_text(), "synthetic private")

    def test_parent_directory_swap_is_rejected(self):
        folder = self.root / "folder"
        folder.mkdir()
        (folder / "input.txt").write_text("safe")
        self.data["read"].append("folder/input.txt")
        scope = self.scope()
        folder.rename(self.root / "old")
        try:
            folder.symlink_to(self.root / "old", target_is_directory=True)
        except OSError:
            self.skipTest("Creating symlinks needs Windows Developer Mode or admin rights")
        with self.assertRaises(OSError):
            scope.call("read_file", {"path": "folder/input.txt"})

    def test_workflow_controls_are_case_insensitively_refused(self):
        for path in (
            ".Claude/settings.json",
            "SPECS/approval.md",
            ".GiThUb/workflows/ci.yml",
            ".githooks/pre-push",
            ".tmp/Agent-Reviews/evidence.json",
            "Scripts/Agents/task_scope.py",
            "src/Orca_Agent_Workflow/review_gate.py",
            "Tests/Agents/test_task_scope.py",
            "Docs/Agents/task-permissions.md",
            "src/AGENTS.md",
            "AGENTS.override.md",
            "packages/api/AGENTS.Override.md",
            "CLAUDE.local.md",
            "AGENTS-local.md",
            "nested/CLAUDE-extra.md",
            "nested/agentsGuide.MD",
            "nested/ClAuDeNotes.md",
            ".MCP.JSON",
            "OPENCODE.JSONC",
            "packages/x/.codex/config.toml",
        ):
            self.data["write"] = [path]
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "workflow controls"):
                self.scope()

    def test_instruction_prefixes_leave_non_markdown_files_writable(self):
        for path in ("src/agents_helpers.py", "docs/claude-notes.txt"):
            with self.subTest(path=path):
                self.assertEqual(module.relative(path, write=True), path)

    def test_root_level_python_modules_are_refused(self):
        for path in ("unittest.py", "PyTest.py", "yaml.py"):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "root-level"):
                module.relative(path, write=True)
        for path in ("packages/api/yaml_utils.py", "tests/api/test_unittest.py"):
            self.assertEqual(module.relative(path, write=True), path)

    def test_sensitive_files_require_spec_marking(self):
        for path in (
            "pyproject.toml",
            "uv.lock",
            "MAKEFILE",
            "tests/conftest.py",
            "packages/backend/Dockerfile",
            "packages/ingest/Dockerfile.worker",
            "Docker-Compose.Sandbox.YML",
            "compose.override.yml",
            "fly.toml",
            "fly/api.toml",
            "deploy/worker/process-job",
            "packages/service/runtime-assets.sha256",
            "scripts/ci_release_gate.py",
            "scripts/ci_gate_check.py",
            "tests/service/test_ci_release_gate.py",
            "tests/service/test_ci_gate_check.py",
            ".pre-commit-config.yaml",
            ".vscode/settings.json",
            "packages/ui/package.json",
            "packages/ui/next.config.js",
            ".gitignore",
        ):
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)
            self.data.update(write=[path], sensitive=[])
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "not marked"):
                self.scope()
            self.data["sensitive"] = [path]
            with self.subTest(path=path, marked=True):
                self.assertIn(path, self.scope().sensitive)
        self.data.update(write=["write.txt"], sensitive=["read.txt"])
        with self.assertRaisesRegex(ValueError, "also approved writes"):
            self.scope()

    def test_application_paths_need_no_marking(self):
        for path in (
            "packages/ui/lib/settings-store.ts",
            "flyers/notes.md",
            "dockerfiles-notes/readme.md",
            "tests/api/test_agents_page.py",
            "packages/api/example_service/routes.py",
        ):
            with self.subTest(path=path):
                self.assertEqual(module.relative(path, write=True), path)
                self.assertFalse(module.is_sensitive(path, module.sensitive_patterns()))

    def test_git_ignored_paths_are_refused_except_frozen_review_evidence(self):
        (self.root / "node_modules").mkdir()
        (self.root / "node_modules/x.js").write_text("ignored")
        self.ignored = {"node_modules/x.js", "build.log"}
        for field, path in (("read", "node_modules/x.js"), ("write", "build.log")):
            self.data[field] = self.data[field] + [path]
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "Git-ignored"):
                self.scope()
            self.data[field] = self.data[field][:-1]
        evidence = self.root / ".tmp/agent-reviews/h"
        evidence.mkdir(parents=True)
        (evidence / "report.md").write_text("evidence")
        self.ignored = {".tmp/agent-reviews/h/report.md"}
        self.data["read"] = ["read.txt", ".tmp/agent-reviews/h/report.md"]
        with self.assertRaisesRegex(ValueError, "Git-ignored"):
            self.scope()
        self.data.update(role="reviewer", write=[])
        self.assertIn(".tmp/agent-reviews/h/report.md", self.scope().read)

    def test_write_path_that_becomes_ignored_ends_the_grant(self):
        scope = self.scope()
        self.ignored = {"write.txt"}
        with self.assertRaisesRegex(module.ScopeEnded, "became Git-ignored"):
            scope.call("write_file", {"path": "write.txt", "content": "hidden"})
        self.assertEqual((self.root / "write.txt").read_text(), "before")

    def test_tracked_census_keeps_application_files_and_marks_configs(self):
        repo = CHECKOUT
        try:
            tracked = subprocess.check_output(
                ["git", "-C", str(repo), "ls-files", "-z"], stderr=subprocess.DEVNULL
            )
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("Not a Git checkout")
        files = [p for p in tracked.decode().split("\0") if p]
        patterns = module.sensitive_patterns()
        for path in files:
            parts = tuple(s.casefold() for s in Path(path).parts)
            if path.startswith("packages/"):
                with self.subTest(path=path):
                    self.assertFalse(module.is_workflow_control(parts))
        for path in (
            "pyproject.toml",
            "uv.lock",
            "Makefile",
            "docker-compose.yml",
            "packages/service/runtime-assets.sha256",
            "scripts/ci_release_gate.py",
        ):
            if path in files:
                with self.subTest(sensitive=path):
                    self.assertTrue(module.is_sensitive(path, patterns))
                    parts = tuple(s.casefold() for s in Path(path).parts)
                    self.assertFalse(module.is_workflow_control(parts))

    def test_credential_paths_are_refused_for_read_and_write(self):
        for path in (
            ".env.local",
            "packages/web/.ENV",
            ".npmrc",
            "home/.netrc",
            ".pgpass",
            "keys/id_rsa",
            "keys/id_ed25519.pub",
            "certs/server.PEM",
            "certs/tls.key",
            "certs/client.p12",
            "certs/client.pfx",
            "config.json.bak",
            "project.backup",
            "prod.sql.bz2",
            "project.dump",
            "prod.sql.gz",
            "data/corpus.jsonl",
            "Backups/latest.sql",
            "dumps/x.txt",
            ".aws/credentials",
            ".ssh/config",
        ):
            for write in (False, True):
                with (
                    self.subTest(path=path, write=write),
                    self.assertRaisesRegex(ValueError, "Credential"),
                ):
                    module.relative(path, write=write)
        for path in (
            "scripts/maintenance/backfill_widget_keys.sql",
            "packages/api/data_utils.py",
            "packages/api/example_service/data/loader.py",
        ):
            with self.subTest(path=path):
                self.assertEqual(module.relative(path, write=True), path)

    def test_credential_denylist_refuses_no_new_tracked_file(self):
        repo = CHECKOUT
        try:
            tracked = subprocess.check_output(
                ["git", "-C", str(repo), "ls-files", "-z"], stderr=subprocess.DEVNULL
            )
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("Not a Git checkout")
        refused = []
        for path in tracked.decode().split("\0"):
            parts = tuple(s.casefold() for s in Path(path).parts)
            if parts and module.is_credential(parts):
                refused.append(path)
        legacy = [
            p for p in refused if any(s.casefold().startswith(".env") for s in Path(p).parts)
        ]
        self.assertEqual(refused, legacy)

    def test_commands_infrastructure_and_unknown_manifest_fields_are_rejected(self):
        for field, value in [
            ("commands", {"test": {}}),
            ("runtime_read", ["/usr"]),
            ("infrastructure", ["database"]),
            ("expires_at", time.time() + 90000),
            ("head", "b" * 40),
        ]:
            old = self.data[field]
            self.data[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.scope()
            self.data[field] = old
        self.data["unexpected"] = True
        with self.assertRaises(ValueError):
            self.scope()

    def test_reviewer_has_no_write_or_execution_interface(self):
        self.data.update(role="reviewer", write=[])
        scope = self.scope()
        self.assertEqual(
            {t["name"] for t in module.tools(scope)},
            {"read_file", "request_scope", "mailbox", "report"},
        )
        with self.assertRaises(PermissionError):
            scope.call("run_check", {"id": "anything"})
        self.data["write"] = ["write.txt"]
        with self.assertRaises(ValueError):
            self.scope()

    def own_orca(self, *args):
        if args[0] == "worker-show":
            return {
                "terminal": "term_fixture",
                "workspace": "repo::" + str(self.root),
                "taskId": "task_abc",
            }
        if args[0] == "check":
            return {
                "messages": [{"id": "msg_reply", "type": "reply", "body": "guidance " * 12000}]
            }
        return {"messageId": "msg_report"}

    def test_malformed_orca_receipts_are_refused(self):
        self.enterContext(patch.object(module, "orca_executable", return_value="orca"))
        scope = self.scope()
        owned = {"terminal": "term_fixture", "workspace": "repo::" + str(self.root)}
        with patch.dict(os.environ, {"ORCA_TERMINAL_HANDLE": "term_fixture"}):
            for state in (
                {"terminal": "term_fixture", "workspace": None},
                {"terminal": "term_fixture", "workspace": 7},
                {"terminal": "term_fixture"},
            ):
                with self.subTest(state=state), patch.object(module, "orca", return_value=state):
                    with self.assertRaises(PermissionError):
                        scope.call("mailbox", {"dispatch_id": "ctx_abc"})
            replies = {"worker-show": owned, "check": {"messages": "x"}}
            with patch.object(module, "orca", side_effect=lambda *a: replies[a[0]]):
                with self.assertRaisesRegex(ValueError, "mailbox shape"):
                    scope.call("mailbox", {"dispatch_id": "ctx_abc"})
        for stdout in ('{"ok": true, "result": [1]}', '{"ok": true, "result": null}'):
            completed = subprocess.CompletedProcess([], 0, stdout=stdout, stderr="")
            with (
                self.subTest(stdout=stdout),
                patch.object(module.subprocess, "run", return_value=completed),
            ):
                with self.assertRaisesRegex(ValueError, "result shape"):
                    module.orca("worker-show", "--dispatch", "ctx_abc")

    def test_windows_broker_refuses_batch_orca_launchers_before_any_call(self):
        with patch.object(module, "WINDOWS", True), patch.object(module.subprocess, "run") as run:
            for launcher in (
                r"C:\Orca\orca.cmd",
                r"C:\Orca\orca.BAT",
                r"C:\Orca\orca.cmd.",
                "orca.exe",
            ):
                environment = {"ORCA_CLI": launcher}
                with self.subTest(launcher=launcher), patch.dict(os.environ, environment):
                    with self.assertRaisesRegex(ValueError, "native orca.exe"):
                        module.orca("report", "--body", "& calc.exe")
            run.assert_not_called()
            with patch.dict(os.environ, {"ORCA_CLI": r"C:\Orca\orca.exe"}):
                self.assertEqual(module.orca_executable(), r"C:\Orca\orca.exe")

    def test_host_programs_never_resolve_inside_the_checkout_or_relative_path(self):
        planted = self.root / "bin"
        outside = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        for folder in (planted, outside):
            folder.mkdir(exist_ok=True)
            (folder / "docker.exe").write_bytes(b"")
        search = os.pathsep.join(["bin", str(planted), str(outside)])
        with patch.dict(os.environ, {"PATH": search}):
            self.assertEqual(
                module.host_executable("docker", self.root), str(outside / "docker.exe")
            )
        with patch.dict(os.environ, {"PATH": os.pathsep.join(["bin", str(planted)])}):
            with self.assertRaises(FileNotFoundError):
                module.host_executable("docker", self.root)

    def test_mailbox_reads_only_owned_dispatch_and_pages_long_replies(self):
        scope = self.scope()
        with (
            patch.dict(os.environ, {"ORCA_TERMINAL_HANDLE": "term_fixture"}),
            patch.object(module, "orca", side_effect=self.own_orca) as orca,
        ):
            listing = scope.call("mailbox", {"dispatch_id": "ctx_abc"})
            self.assertEqual(listing["messages"][0]["id"], "msg_reply")
            offset, parts = 0, []
            while offset is not None:
                page = scope.call(
                    "mailbox",
                    {"dispatch_id": "ctx_abc", "message_id": "msg_reply", "offset": offset},
                )
                parts.append(page["text"])
                offset = page["next_offset"]
            self.assertEqual("".join(parts), "guidance " * 12000)
            checks = [c.args for c in orca.call_args_list if c.args[0] == "check"]
            self.assertEqual(checks, [("check", "--terminal", "term_fixture")])
            with self.assertRaises(PermissionError):
                scope.call("mailbox", {"dispatch_id": "ctx_abc", "message_id": "other"})
        with (
            patch.dict(os.environ, {"ORCA_TERMINAL_HANDLE": "different"}),
            patch.object(module, "orca", side_effect=self.own_orca),
        ):
            with self.assertRaises(PermissionError):
                scope.call("mailbox", {"dispatch_id": "ctx_abc"})

    def test_report_is_bound_to_own_task_and_revokes_access(self):
        scope = self.scope()
        with (
            patch.dict(os.environ, {"ORCA_TERMINAL_HANDLE": "term_fixture"}),
            patch.object(module, "orca", side_effect=self.own_orca) as orca,
        ):
            with self.assertRaises(PermissionError):
                scope.call(
                    "report",
                    {
                        "outcome": "succeeded",
                        "body": "test",
                        "task_id": "task_other",
                        "dispatch_id": "ctx_abc",
                    },
                )
            scope.call(
                "report",
                {
                    "outcome": "succeeded",
                    "body": "test",
                    "task_id": "task_abc",
                    "dispatch_id": "ctx_abc",
                },
            )
            argv = orca.call_args.args
            self.assertNotIn("--from", argv)
            self.assertNotIn("--to", argv)
        with self.assertRaises(module.ScopeEnded):
            scope.call("read_file", {"path": "read.txt"})

    def test_report_rejects_non_text_ids_and_revokes_after_any_send_attempt(self):
        scope = self.scope()
        report = {"outcome": "succeeded", "body": "x", "task_id": None, "dispatch_id": "ctx_abc"}
        with (
            patch.dict(os.environ, {"ORCA_TERMINAL_HANDLE": "term_fixture"}),
            patch.object(module, "orca", side_effect=self.own_orca) as orca,
        ):
            with self.assertRaisesRegex(ValueError, "Invalid report"):
                scope.call("report", report)
            orca.assert_not_called()

        def malformed(*args):
            if args[0] == "send":
                raise ValueError("Orca returned an invalid result shape")
            return self.own_orca(*args)

        with (
            patch.dict(os.environ, {"ORCA_TERMINAL_HANDLE": "term_fixture"}),
            patch.object(module, "orca", side_effect=malformed),
        ):
            with self.assertRaisesRegex(ValueError, "result shape"):
                scope.call("report", dict(report, task_id="task_abc"))
        with self.assertRaises(module.ScopeEnded):
            scope.call("read_file", {"path": "read.txt"})

    def test_lone_surrogate_request_id_does_not_end_broker(self):
        scope = self.scope()
        requests = (
            b'{"jsonrpc": "2.0", "id": "\\ud800", "method": "ping"}\n'
            b'{"jsonrpc": "2.0", "id": 2, "method": "ping"}\n'
        )
        raw = io.BytesIO()
        output = io.TextIOWrapper(raw, encoding="utf-8", errors="strict", write_through=True)
        with (
            patch.object(module.sys, "stdin", Mock(buffer=io.BytesIO(requests))),
            patch.object(module.sys, "stdout", output),
        ):
            module.serve(scope)
        responses = [json.loads(line) for line in raw.getvalue().decode().splitlines()]
        self.assertEqual([r["id"] for r in responses], ["\ud800", 2])

    def test_scope_question_does_not_expand_file_authority(self):
        scope = self.scope()
        with (
            patch.dict(os.environ, {"ORCA_TERMINAL_HANDLE": "term_fixture"}),
            patch.object(module, "orca", return_value={"messageId": "msg_question"}),
        ):
            scope.call("request_scope", {"question": "Need extra context"})
        with self.assertRaises(PermissionError):
            scope.call("read_file", {"path": "private.txt"})

    def test_invalid_protocol_and_argument_types_do_not_crash_broker(self):
        scope = self.scope()
        requests = [
            b"not json\n",
            b"[]\n",
            b"null\n",
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "write_file",
                        "arguments": {"path": "write.txt", "content": None},
                    },
                }
            ).encode()
            + b"\n",
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "read_file", "arguments": {"path": "read.txt"}},
                }
            ).encode()
            + b"\n",
            b"[" * 100_000 + b"]" * 100_000 + b"\n",
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "mailbox", "arguments": {"dispatch_id": "ctx_abc"}},
                }
            ).encode()
            + b"\n",
            json.dumps({"jsonrpc": "2.0", "id": 4, "method": "ping"}).encode() + b"\n",
        ]
        incoming = Mock(buffer=io.BytesIO(b"".join(requests)))
        output = io.StringIO()
        with (
            patch.object(module.sys, "stdin", incoming),
            patch.object(module.sys, "stdout", output),
            patch.dict(os.environ, {"ORCA_TERMINAL_HANDLE": "term_fixture"}),
            patch.object(module, "orca", side_effect=AttributeError("synthetic receipt")),
        ):
            module.serve(scope)
        responses = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(len(responses), 8)
        self.assertEqual(responses[0]["error"]["code"], -32700)
        self.assertTrue(responses[3]["result"]["isError"])
        self.assertIn("read only", responses[4]["result"]["content"][0]["text"])
        # Newer parsers accept this deep valid array; the request is still invalid.
        self.assertIn(responses[5]["error"]["code"], (-32700, -32600))
        self.assertTrue(responses[6]["result"]["isError"])
        self.assertEqual(responses[7], {"jsonrpc": "2.0", "id": 4, "result": {}})
        self.assertEqual((self.root / "write.txt").read_text(), "before")

    def test_models_match_enabled_role_profiles_without_aliases(self):
        module.validate_model("implementer", "claude-sonnet-5-5", self.policy)
        module.validate_model("reviewer", "claude-opus-5-5", self.policy)
        for role, model in [
            ("implementer", "opus"),
            ("implementer", "claude-opus-5-5"),
            ("reviewer", "opus"),
            ("reviewer", "claude-sonnet-5-5"),
        ]:
            with self.assertRaises(ValueError):
                module.validate_model(role, model, self.policy)
        with self.assertRaises(ValueError):
            module.require_supported_harness("codex")

    def test_mcp_interpreter_ignores_project_pythonpath_injection(self):
        _, bundle, _ = self.prepared()
        mcp = json.loads((bundle / "mcp.json").read_text())["mcpServers"]["task"]
        self.assertEqual(mcp["args"][0], "-I")
        poison = self.base / "poison"
        poison.mkdir()
        (poison / "json.py").write_text('raise RuntimeError("POISONED")')
        env = dict(os.environ, PYTHONPATH=str(poison))
        result = subprocess.run(
            [mcp["command"], *mcp["args"], "--help"],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("POISONED", result.stderr)

    def test_probe_covers_real_allowed_write_and_inside_checkout_denials(self):
        scope, bundle, _ = self.prepared()
        receipt = json.loads((bundle / "probe.json").read_text())
        self.assertTrue(receipt["passed"])
        self.assertEqual(
            receipt["checks"],
            [
                "approved_read",
                "approved_write",
                "denied_unlisted_sibling_read",
                "denied_read_only_write",
                "denied_traversal",
                "denied_execution",
            ],
        )
        self.assertEqual((self.root / "write.txt").read_text(), "before")
        self.assertEqual(list((self.root / ".tmp").iterdir()), [])

    def test_missing_argv_hash_changed_bundle_and_same_version_binary_are_blocked(self):
        scope, bundle, client = self.prepared()
        with patch.object(module, "SELF", bundle / "task_scope.py"):
            self.assertEqual(module.verify_bundle(bundle, scope)[0], str(client))
            receipt = json.loads((bundle / "probe.json").read_text())
            saved = receipt["bundle_hashes"].pop("claude-argv.json")
            module.atomic_json(bundle / "probe.json", receipt)
            with self.assertRaisesRegex(ValueError, "Incomplete"):
                module.verify_bundle(bundle, scope)
            receipt["bundle_hashes"]["claude-argv.json"] = saved
            module.atomic_json(bundle / "probe.json", receipt)
            client.write_text("same version, different executable")
            with self.assertRaisesRegex(ValueError, "executable changed"):
                module.verify_bundle(bundle, scope)

    def test_target_policy_cannot_authorize_an_unapproved_model(self):
        target = self.root / ".agents"
        target.mkdir()
        unapproved = {
            "implementer": [{"agent": "claude", "model": "claude-unapproved", "enabled": True}]
        }
        # The branch's own workflow.json is never read: policy comes from the base commit.
        (target / "workflow.json").write_text(json.dumps(self.config(unapproved)))
        with self.assertRaisesRegex(ValueError, "enabled exact role profile"):
            module.prepare(self.scope(), self.base / "blocked", "claude-unapproved")
        trusted = self.base / "trusted-workflow.json"
        trusted.write_text(json.dumps(self.config()))
        with self.assertRaisesRegex(ValueError, "enabled exact role profile"):
            module.prepare(self.scope(), self.base / "blocked", "claude-unapproved", trusted)
        self.assertFalse((self.base / "blocked").exists())

    def test_policy_base_and_project_sensitive_patterns_are_enforced(self):
        self.data["policy_base"] = "main"
        with self.assertRaisesRegex(ValueError, "policy_base"):
            self.scope()
        self.data["policy_base"] = "b" * 40
        self.data["sensitive_extra"] = ["*.tf"]
        (self.root / "infra").mkdir()
        self.data["write"] = ["write.txt", "infra/main.tf"]
        with self.assertRaisesRegex(ValueError, "Sensitive path not marked"):
            self.scope()
        self.data["sensitive"] = ["infra/main.tf"]
        self.assertIn("infra/main.tf", self.scope().sensitive)

    def test_ended_grant_never_starts_a_client(self):
        scope = self.scope()
        self.manifest.with_suffix(".revoked").touch()
        with patch.object(module.subprocess, "Popen") as popen:
            with self.assertRaises(module.ScopeEnded):
                module.supervise(self.base, scope, ["/synthetic/client"])
        popen.assert_not_called()

    def test_supervisor_signals_only_its_own_new_child_on_revocation(self):
        scope = self.scope()
        bundle = self.base / "controller"
        bundle.mkdir()
        (bundle / "work").mkdir()
        child = Mock(pid=123456)
        child.poll.side_effect = [None, 0]
        child.wait.return_value = -15

        def started(*args, **kwargs):
            self.manifest.with_suffix(".revoked").touch()
            return child

        job = object()
        with (
            patch.object(module.subprocess, "Popen", side_effect=started) as popen,
            patch.object(module, "kill_on_close_job", return_value=job) as attach,
            patch.object(module, "close_job") as close,
        ):
            self.assertEqual(module.supervise(bundle, scope, ["/synthetic/client"]), -15)
        child.terminate.assert_called_once()
        child.kill.assert_not_called()
        if module.WINDOWS:
            attach.assert_called_once_with(child)
            close.assert_called_once_with(job)
        else:
            attach.assert_not_called()
        self.assertNotIn("shell", popen.call_args.kwargs)
        status = module.controller_status(bundle)
        self.assertEqual(
            (status["state"], status["pid"], status["reason"]), ("exited", 123456, "grant_ended")
        )


def junction(link, target):
    """Directory junctions need no symlink privilege, so any Windows user can make one."""
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True
    )


@unittest.skipUnless(os.name == "nt", "Windows broker path")
class WindowsBrokerTests(unittest.TestCase):
    setUp = TaskScopeTests.setUp
    git_result = TaskScopeTests.git_result
    scope = TaskScopeTests.scope

    def outside_folder(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "input.txt").write_text("synthetic private")
        return outside

    def test_junction_component_is_refused(self):
        folder = self.root / "folder"
        folder.mkdir()
        (folder / "input.txt").write_text("safe")
        self.data["read"].append("folder/input.txt")
        scope = self.scope()
        folder.rename(self.root / "old")
        junction(folder, self.outside_folder())
        with self.assertRaises(PermissionError):
            scope.call("read_file", {"path": "folder/input.txt"})

    def test_swap_after_the_walk_is_caught_by_the_opened_handle(self):
        # Simulate losing the race: the walk sees no reparse point, the open follows one.
        folder = self.root / "folder"
        folder.mkdir()
        (folder / "input.txt").write_text("safe")
        self.data["read"].append("folder/input.txt")
        self.data["write"].append("folder/out.txt")
        scope = self.scope()
        folder.rename(self.root / "old")
        outside = self.outside_folder()
        junction(folder, outside)
        with patch.object(module, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            with self.assertRaises(PermissionError):
                scope.call("read_file", {"path": "folder/input.txt"})
            with self.assertRaises(OSError):
                scope.call("write_file", {"path": "folder/out.txt", "content": "bad"})
        self.assertEqual((outside / "input.txt").read_text(), "synthetic private")
        # A created file is refused after opening, so only an empty file can remain.
        leftover = outside / "out.txt"
        self.assertTrue(not leftover.exists() or leftover.read_bytes() == b"")

    def test_names_windows_reinterprets_are_refused(self):
        for value in (
            "read.txt:secret",
            "C:read.txt",
            "CON",
            "nul.txt",
            "folder/aux.md",
            "COM1.log",
            "read.txt.",
            "read.txt ",
            "bad|name.txt",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.relative(value)

    def test_short_names_cannot_alias_an_unlisted_file(self):
        import ctypes

        buffer = ctypes.create_unicode_buffer(512)
        ctypes.windll.kernel32.GetShortPathNameW(str(self.root / "private.txt"), buffer, 512)
        short = Path(buffer.value).name
        if short.casefold() == "private.txt":
            self.skipTest("8.3 short names are disabled on this volume")
        self.data["read"].append(short)
        with self.assertRaises(ValueError):
            self.scope()

    def test_job_object_ends_the_clients_children(self):
        script = (
            "import subprocess, sys, time\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
            "print(child.pid, flush=True)\n"
            "time.sleep(60)\n"
        )
        client = subprocess.Popen(
            [sys_executable(), "-c", script], stdout=subprocess.PIPE, text=True
        )
        job = module.kill_on_close_job(client)
        grandchild = int(client.stdout.readline())
        module.close_job(job)
        client.wait(timeout=10)
        client.stdout.close()
        deadline = time.time() + 10
        while running(grandchild) and time.time() < deadline:
            time.sleep(0.1)
        self.assertFalse(running(grandchild))


def sys_executable():
    import sys

    return sys.executable


def running(pid):
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32")
    kernel32.OpenProcess.restype = ctypes.c_void_p
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        kernel32.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code))
        return code.value == 259  # STILL_ACTIVE
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(handle))


if __name__ == "__main__":
    unittest.main()
