"""Spec-to-manifest planning in a real throwaway Git repository; no providers."""

import os
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# The runtime under test: the kit's src/, or a vendored or installed copy.
sys.path.insert(
    0,
    os.environ.get("ORCA_AGENT_WORKFLOW_RUNTIME")
    or str(Path(__file__).resolve().parents[2] / "src"),
)
from orca_agent_workflow import task_plan

SPEC = """---
status: approved
---
# Example

## Sensitive files
- `pyproject.toml`: the task adds a dependency.

```agent-task
{
  "tier": "full",
  "implementer": {
    "read": ["docs/guide.md"],
    "write": ["docs/new.md", "pyproject.toml"],
    "sensitive": ["pyproject.toml"]
  },
  "review": {"read": ["docs/guide.md"]}
}
```
"""


class TaskPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        files = {
            "AGENTS.md": "# Contract\n",
            "CLAUDE.md": "@AGENTS.md\n",
            ".agents/skills/review-pr/SKILL.md": "review\n",
            ".agents/skills/review-pr/references/reviewer.md": "reviewer\n",
            ".agents/docs/roles/implementer.md": "implementer\n",
            "docs/guide.md": "guide\n",
            "pyproject.toml": "[project]\n",
            "specs/example.md": SPEC,
            ".gitignore": ".tmp/\n",
            ".agents/workflow.json": json.dumps(
                {
                    "version": 1,
                    "runtime": {"package": "orca-agent-workflow", "version": "0.0.0"},
                    "project": {"name": "Example", "repository": "example/app"},
                    "roles": {},
                    "sensitive_patterns": ["docs/secret-*.md"],
                }
            ),
        }
        for name, text in files.items():
            (self.root / name).parent.mkdir(parents=True, exist_ok=True)
            (self.root / name).write_text(text)
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-qm", "base")
        self.base = self.git("rev-parse", "HEAD").strip()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True)

    def test_implementer_manifest_and_brief_list_every_path(self):
        block = task_plan.load_block(self.root / "specs/example.md")
        with self.assertRaisesRegex(ValueError, "origin/HEAD"):
            task_plan.plan_implementer(self.root, "specs/example.md", block, 1)
        out = task_plan.plan_implementer(self.root, "specs/example.md", block, 1, self.base)
        data = json.loads((out / "scope.json").read_text())
        # The trusted policy and project patterns come from the named reviewed commit.
        self.assertEqual(data["policy_base"], self.base)
        self.assertEqual(data["sensitive_extra"], ["docs/secret-*.md"])
        self.assertEqual(
            data["read"],
            ["AGENTS.md", "specs/example.md", ".agents/docs/roles/implementer.md", "docs/guide.md"],
        )
        self.assertEqual(data["write"], ["docs/new.md", "pyproject.toml"])
        self.assertEqual(data["sensitive"], ["pyproject.toml"])
        brief = (out / "brief.md").read_text()
        self.assertIn("existing ones are readable too", brief)
        for path in data["read"] + data["write"]:
            self.assertIn(f"`{path}`", brief)
        self.assertEqual(self.git("status", "--porcelain"), "")

    def commit(self, message="x"):
        self.git("-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-qam", message)

    def test_spec_must_be_approved_and_committed(self):
        spec = self.root / "specs/example.md"
        block = task_plan.load_block(spec)
        spec.write_text(SPEC.replace("status: approved", "status: draft"))
        self.commit()
        with self.assertRaisesRegex(ValueError, "status approved"):
            task_plan.plan_implementer(self.root, "specs/example.md", block, 1, self.base)
        spec.write_text(SPEC + "\nUncommitted edit.\n")
        with self.assertRaisesRegex(ValueError, "Commit the approved spec"):
            task_plan.plan_implementer(self.root, "specs/example.md", block, 1, self.base)

    def test_malformed_blocks_are_refused(self):
        spec = self.root / "specs/bad.md"
        for bad, message in (
            (SPEC.replace('"write":', '"writes":'), "exactly read, write and sensitive"),
            (SPEC.replace('"tier": "full"', '"tier": "huge"'), "tier light or full"),
            (SPEC.replace('"tier": "full"', '"tier": "light"'), "require tier full"),
            (SPEC.replace("- `pyproject.toml`: the task", "- The task"), "Name each sensitive"),
            (SPEC.replace('"review": {"read":', '"review": {"reads":'), "review needs exactly"),
            (SPEC.replace('"tier": "full",', '"tier": "full", "extra": 1,'), "keys are"),
        ):
            spec.write_text(bad)
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                task_plan.load_block(spec)

    def test_unmarked_sensitive_write_is_refused_at_planning(self):
        spec = self.root / "specs/example.md"
        spec.write_text(SPEC.replace('"sensitive": ["pyproject.toml"]', '"sensitive": []'))
        self.git("-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-qam", "x")
        block = task_plan.load_block(spec)
        with self.assertRaisesRegex(ValueError, "not marked"):
            task_plan.plan_implementer(self.root, "specs/example.md", block, 1, self.base)

    def test_deleted_sensitive_files_are_flagged_for_review(self):
        self.git("rm", "-q", "pyproject.toml")
        self.commit("delete")
        block = task_plan.load_block(self.root / "specs/example.md")
        task_plan.plan_reviewer(self.root, "specs/example.md", block, 1, self.base)
        head = self.git("rev-parse", "HEAD").strip()
        listed = (self.root / f".tmp/agent-reviews/{head}/sensitive-paths.txt").read_text()
        self.assertIn("pyproject.toml (deleted)", listed)

    def test_reviewer_evidence_and_brief_cover_the_change(self):
        (self.root / "docs/new.md").write_text("new\n")
        (self.root / "pyproject.toml").write_text("[project]\nname = 'x'\n")
        self.git("add", ".")
        self.git("-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-qm", "change")
        block = task_plan.load_block(self.root / "specs/example.md")
        out = task_plan.plan_reviewer(self.root, "specs/example.md", block, 1, self.base)
        data = json.loads((out / "scope.json").read_text())
        head = self.git("rev-parse", "HEAD").strip()
        evidence = f".tmp/agent-reviews/{head}"
        for path in (
            "docs/new.md",
            "pyproject.toml",
            f"{evidence}/full.diff",
            f"{evidence}/base-AGENTS.md",
            f"{evidence}/sensitive-paths.txt",
        ):
            self.assertIn(path, data["read"])
        self.assertEqual(data["write"], [])
        brief = (out / "brief.md").read_text()
        self.assertIn("Sensitive files changed", brief)
        self.assertIn("- `pyproject.toml`", brief.split("Readable paths:")[0])
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_spec_without_exactly_one_block_is_refused(self):
        spec = self.root / "specs/none.md"
        spec.write_text("# No block\n")
        with self.assertRaisesRegex(ValueError, "exactly one"):
            task_plan.load_block(spec)
        spec.write_text(SPEC + SPEC.split("# Example")[1])
        with self.assertRaisesRegex(ValueError, "exactly one"):
            task_plan.load_block(spec)


if __name__ == "__main__":
    unittest.main()
