"""Check that an interrupted wait can resume without resending an ambiguous launch."""

import os
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, os.environ.get("ORCA_AGENT_WORKFLOW_RUNTIME") or str(ROOT / "src"))
from orca_agent_workflow import resume_dispatch as resume


class ResumeDispatchTests(unittest.TestCase):
    def test_trust_wait_can_resume_for_implementer_and_reviewer(self):
        for role in ("implementer", "reviewer"):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                brief = root / "brief.md"
                brief.write_text("Fixture task")
                args = Namespace(bundle=root, terminal="term_worker", run="run_fixture",
                                 title="Fixture", timeout=5, brief=brief)
                identity = {"terminal": args.terminal, "incarnation": "incarnation", "pid": 1}
                ready = (0, {"ok": True, "result": {"wait": {
                    "handle": args.terminal, "satisfied": True,
                }}})
                blocked = (1, {"ok": True, "result": {"wait": {
                    "handle": args.terminal, "satisfied": False,
                    "blockedReason": "agent-trust-workspace",
                }}})
                fake_scope = SimpleNamespace(root=root, data={"role": role})
                with (
                    patch.object(resume.sys, "platform", "darwin"),
                    patch.dict(resume.os.environ, ORCA_TERMINAL_HANDLE="term_coordinator"),
                    patch.object(resume.shutil, "which", return_value="/usr/bin/orca"),
                    patch.object(resume.task_scope, "Scope", return_value=fake_scope),
                    patch.object(resume.task_scope, "project_root", return_value=root),
                    patch.object(resume, "exact_client", return_value=identity),
                    patch.object(resume, "orca", side_effect=[
                        blocked, KeyboardInterrupt, ready,
                        subprocess.TimeoutExpired("worker-start", 90),
                    ]) as cli,
                ):
                    with self.assertRaises(KeyboardInterrupt):
                        resume.dispatch(args)
                    self.assertFalse((root / "dispatch-attempt.json").exists())
                    with self.assertRaisesRegex(ValueError, "outcome uncertain"):
                        resume.dispatch(args)
                    self.assertTrue((root / "dispatch-attempt.json").exists())
                    with self.assertRaisesRegex(ValueError, "already started"):
                        resume.dispatch(args)
                    self.assertEqual(sum(
                        call.args[1:3] == ("orchestration", "worker-start")
                        for call in cli.call_args_list
                    ), 1)
