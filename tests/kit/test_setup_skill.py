"""Keep install instructions aligned with the version the launcher will request."""

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, os.environ.get("ORCA_AGENT_WORKFLOW_RUNTIME") or str(ROOT / "src"))
from orca_agent_workflow import __version__


class SetupSkillTests(unittest.TestCase):
    def test_entry_points_use_the_runtime_version(self):
        for name in ("README.md", "INSTALL.md", "docs/getting-started.md", "skills/setup-orca-workflow/SKILL.md"):
            with self.subTest(name=name):
                self.assertIn(f"uvx orca-agent-workflow@{__version__} init", (ROOT / name).read_text(encoding="utf-8"))
