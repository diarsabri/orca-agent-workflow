"""Behavioral checks for token-free transcript recovery, with synthetic history."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / ".agents/skills/session-recover/scripts/session_context.py"
)
spec = importlib.util.spec_from_file_location("session_context", SCRIPT)
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cwd = str(self.root / "project")

    def write(self, items, name="session.jsonl"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(item) + "\n" for item in items))
        return path

    def codex(self, source="cli", cwd=None):
        return {
            "type": "session_meta",
            "payload": {"id": "session-id", "cwd": cwd or self.cwd, "source": source},
        }

    def message(self, role, text):
        return {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": role,
                "content": [{"type": "input_text", "text": text}],
            },
        }

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)

    def test_codex_keeps_conversation_and_tool_evidence_without_reasoning(self):
        path = self.write(
            [
                self.codex(),
                self.message("system", "SYSTEM SECRET"),
                self.message("user", "fix the crash"),
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "channel": "analysis",
                        "content": [{"type": "output_text", "text": "HIDDEN ANALYSIS"}],
                    },
                },
                {
                    "type": "response_item",
                    "payload": {"type": "reasoning", "text": "HIDDEN REASONING"},
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell",
                        "arguments": "run checks",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {"type": "function_call_output", "output": "3 tests failed"},
                },
            ]
        )
        output = list(reader.events(path, "codex", path.stat().st_size))
        self.assertEqual([role for role, text in output], ["user", "tool call", "tool result"])
        self.assertEqual(output[-1][1], "3 tests failed")

    def test_claude_uses_latest_main_branch_not_abandoned_or_sidechain(self):
        def msg(uuid, parent, text, side=False):
            return {
                "uuid": uuid,
                "parentUuid": parent,
                "type": "user",
                "isSidechain": side,
                "cwd": self.cwd,
                "sessionId": "session-id",
                "message": {"content": text},
            }

        path = self.write(
            [
                msg("a", None, "original goal"),
                msg("abandoned", "a", "obsolete direction"),
                msg("b", "a", "revised direction"),
                msg("child", "b", "unrelated side work", True),
            ]
        )
        self.assertEqual(
            list(reader.events(path, "claude", path.stat().st_size)),
            [("user", "original goal"), ("user", "revised direction")],
        )

    def test_claude_tool_results_are_retained(self):
        path = self.write(
            [
                {
                    "uuid": "a",
                    "parentUuid": None,
                    "type": "user",
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "content": [{"type": "text", "text": "exit 1"}],
                            }
                        ]
                    },
                }
            ]
        )
        self.assertEqual(
            list(reader.events(path, "claude", path.stat().st_size)), [("tool result", "exit 1")]
        )

    def test_partial_final_record_is_ignored_but_interior_corruption_fails(self):
        path = self.write([self.codex()])
        with path.open("a") as stream:
            stream.write('{"unfinished":')
        self.assertEqual(len(list(reader.records(path))), 1)
        path.write_text("{broken}\n" + json.dumps(self.codex()) + "\n")
        with self.assertRaises(ValueError):
            list(reader.records(path))

    def test_fixed_prefix_excludes_concurrent_append(self):
        path = self.write([self.codex(), self.message("user", "before")])
        size = path.stat().st_size
        with path.open("a") as stream:
            stream.write(json.dumps(self.message("user", "after")) + "\n")
        self.assertEqual(list(reader.events(path, "codex", size)), [("user", "before")])

    def test_wrong_project_or_subagent_refused(self):
        for metadata in [
            self.codex(cwd="/unrelated/project"),
            self.codex(source={"subagent": {"other": "guardian"}}),
        ]:
            path = self.write([metadata, self.message("user", "private content")])
            result = self.cli("read", "--agent", "codex", "--cwd", self.cwd, "--file", str(path))
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")

    def test_list_filters_project_and_subagents_without_exposing_prompts(self):
        self.write(
            [self.codex(), self.message("user", "PRIVATE PROMPT")], "history/2026/11/03/main.jsonl"
        )
        self.write([self.codex(cwd="/elsewhere")], "history/2026/11/03/elsewhere.jsonl")
        self.write([self.codex(source={"subagent": {}})], "history/2026/11/03/child.jsonl")
        result = self.cli(
            "list", "--agent", "codex", "--cwd", self.cwd, "--root", str(self.root / "history")
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), 1)
        self.assertNotIn("PRIVATE PROMPT", result.stdout)

    def test_bounded_read_reports_loss_and_does_not_modify_source(self):
        path = self.write(
            [
                self.codex(),
                self.message("user", "original request"),
                *[self.message("assistant", "x" * 100) for _ in range(5)],
            ]
        )
        before = path.read_bytes()
        result = self.cli(
            "read",
            "--agent",
            "codex",
            "--cwd",
            self.cwd,
            "--file",
            str(path),
            "--events",
            "2",
            "--chars",
            "20",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"omitted_events": 4', result.stdout)
        self.assertIn("original request", result.stdout)
        self.assertIn("[EVENT TRUNCATED]", result.stdout)
        self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
