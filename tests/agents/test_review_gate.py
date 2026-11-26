"""Semantic rejection tests for review readiness; no providers or services."""

import copy
import json
import os
import shutil
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
from orca_agent_workflow import __version__
from orca_agent_workflow import review_gate as gate

# The gate as the coordinator runs it: the package's command, in a fresh interpreter.
GATE = [sys.executable, "-m", "orca_agent_workflow", "review-gate"]
GATE_ENV = dict(os.environ, PYTHONPATH=str(Path(gate.__file__).resolve().parents[1]))


def workflow_config(policy, version=__version__):
    """The base commit's .agents/workflow.json holding a roles policy."""
    return {
        "version": 1,
        "runtime": {"package": "orca-agent-workflow", "version": version},
        "project": {"name": "Example", "repository": policy["repository"]},
        "reviewer_provider_differs_from_planner": policy.get(
            "reviewer_provider_differs_from_planner"
        ),
        "roles": policy["roles"],
    }


class ReviewGateTests(unittest.TestCase):
    def setUp(self):
        self.policy = {
            "version": 2,
            "repository": "example/project",
            "reviewer_provider_differs_from_planner": "preferred",
            "roles": {
                "planner": [
                    {"agent": "claude", "model": "claude-opus-5-5", "enabled": True},
                    {"agent": "codex", "model": "gpt-6.1-sol", "enabled": True},
                ],
                "reviewer": [
                    {"agent": "claude", "model": "claude-opus-5-5", "enabled": True},
                    {"agent": "codex", "model": "gpt-6.1-sol", "enabled": False},
                ]
            },
        }
        self.record = {
            "version": 1,
            "repository": "example/project",
            "head_sha": "a" * 40,
            "base_sha": "b" * 40,
            "policy_sha256": "c" * 64,
            "planner": {"agent": "claude", "model": "claude-opus-5-5"},
            "verdict": "pass",
            "implementation_authorship": "agent",
            "implementer_session_id": "writer-session",
            "reviewer": {
                "agent": "claude",
                "requested_model": "claude-opus-5-5",
                "effective_model": "claude-opus-5-5",
                "session_id": "review-session",
                "dispatch_id": "review-dispatch",
                "fresh_session": True,
            },
            "coverage": {
                "complete_diff": True,
                "acceptance_criteria": True,
                "test_evidence": True,
            },
            "findings": [],
            "sensitive_files_reviewed": [],
            "summary": "No blocking findings.",
            "launch_receipt_sha256": "d" * 64,
            "review_report_sha256": "e" * 64,
        }

    def errors(self, record=None):
        return gate.validate_review(
            self.record if record is None else record,
            self.policy,
            head="a" * 40,
            base="b" * 40,
            policy_digest="c" * 64,
        )

    def test_complete_independent_review_passes(self):
        self.assertEqual(self.errors(), [])

    def test_unknown_author_cannot_pass_as_independent(self):
        for author in (None, "", 42):
            record = copy.deepcopy(self.record)
            record["implementer_session_id"] = author
            self.assertTrue(self.errors(record))
        self.record["implementation_authorship"] = "unknown"
        self.assertTrue(self.errors())
        self.record["implementation_authorship"] = "human"
        self.record["implementer_session_id"] = None
        self.assertEqual(self.errors(), [])

    def test_head_base_policy_and_repository_changes_invalidate_review(self):
        for field in ("head_sha", "base_sha", "policy_sha256", "repository"):
            record = copy.deepcopy(self.record)
            record[field] = "changed"
            with self.subTest(field=field):
                self.assertTrue(self.errors(record))

    def test_wrong_model_unknown_model_and_alias_fail(self):
        for model in (None, "opus", "claude-sonnet-5-5", "gpt-6.1-terra"):
            record = copy.deepcopy(self.record)
            record["reviewer"]["effective_model"] = model
            with self.subTest(model=model):
                self.assertTrue(self.errors(record))

    def test_reviewer_must_be_an_enabled_policy_profile(self):
        for agent, model in (
            ("claude", "claude-sonnet-5-5"),
            ("codex", "gpt-6.1-sol"),
            ("codex", "claude-opus-5-5"),
        ):
            record = copy.deepcopy(self.record)
            record["reviewer"].update(agent=agent, requested_model=model, effective_model=model)
            with self.subTest(agent=agent, model=model):
                self.assertIn(
                    "reviewer is not an enabled exact policy profile", self.errors(record)
                )

    def test_enabled_cross_provider_reviewer_passes_with_disclosed_evidence(self):
        self.policy["roles"]["reviewer"][1]["enabled"] = True
        self.record["reviewer"].update(
            agent="codex", requested_model="gpt-6.1-sol", effective_model="gpt-6.1-sol"
        )
        self.assertIn(
            "Codex reviewer needs codex-session-turn-context model evidence", self.errors()
        )
        self.record["reviewer"].update(
            model_evidence="codex-session-turn-context", qualification_sha256="f" * 64
        )
        self.assertEqual(self.errors(), [])

    def test_single_provider_policy_reviews_same_provider_without_fallback(self):
        self.assertEqual(self.errors(), [])
        self.record["cross_provider_fallback"] = {"reason": "unqualified"}
        self.assertIn(
            "cross_provider_fallback is only valid for a same-provider review", self.errors()
        )

    def test_same_provider_review_needs_disclosed_fallback_when_other_is_enabled(self):
        self.policy["roles"]["reviewer"][1]["enabled"] = True
        expected = "same-provider review needs a cross_provider_fallback reason"
        self.assertIn(expected, self.errors())
        for reason in ("preference", None, ""):
            self.record["cross_provider_fallback"] = {"reason": reason}
            with self.subTest(reason=reason):
                self.assertIn(expected, self.errors())
        for reason in sorted(gate.FALLBACK_REASONS):
            self.record["cross_provider_fallback"] = {"reason": reason}
            with self.subTest(reason=reason):
                self.assertEqual(self.errors(), [])

    def test_codex_planner_reviewing_codex_needs_fallback_when_claude_is_enabled(self):
        self.policy["roles"]["reviewer"][1]["enabled"] = True
        self.record["planner"] = {"agent": "codex", "model": "gpt-6.1-sol"}
        self.record["reviewer"].update(
            agent="codex",
            requested_model="gpt-6.1-sol",
            effective_model="gpt-6.1-sol",
            model_evidence="codex-session-turn-context",
            qualification_sha256="f" * 64,
        )
        self.assertIn(
            "same-provider review needs a cross_provider_fallback reason", self.errors()
        )
        self.record["cross_provider_fallback"] = {"reason": "quota_exhausted"}
        self.assertEqual(self.errors(), [])

    def test_malformed_fallback_is_reported_not_raised(self):
        self.policy["roles"]["reviewer"][1]["enabled"] = True
        for fallback in (
            "quota_exhausted",
            ["quota_exhausted"],
            {"reason": ["quota_exhausted"]},
            {"reason": {"quota_exhausted": True}},
        ):
            self.record["cross_provider_fallback"] = fallback
            with self.subTest(fallback=fallback):
                self.assertIn(
                    "same-provider review needs a cross_provider_fallback reason",
                    self.errors(),
                )

    def test_disabled_planner_profile_is_rejected(self):
        self.policy["roles"]["planner"][1]["enabled"] = False
        self.record["planner"] = {"agent": "codex", "model": "gpt-6.1-sol"}
        self.assertIn("planner is not an enabled exact policy profile", self.errors())

    def test_human_planner_rejects_fallback(self):
        self.policy["roles"]["reviewer"][1]["enabled"] = True
        self.record["planner"] = {"agent": "human"}
        self.record["cross_provider_fallback"] = {"reason": "unqualified"}
        self.assertIn(
            "cross_provider_fallback is only valid for a same-provider review", self.errors()
        )

    def test_cross_provider_review_needs_no_fallback(self):
        self.record["planner"] = {"agent": "codex", "model": "gpt-6.1-sol"}
        self.policy["roles"]["reviewer"][1]["enabled"] = True
        self.assertEqual(self.errors(), [])
        self.record["cross_provider_fallback"] = {"reason": "quota_exhausted"}
        self.assertIn(
            "cross_provider_fallback is only valid for a same-provider review", self.errors()
        )

    def test_planner_must_be_recorded_policy_profile_or_human(self):
        expected = "planner is not an enabled exact policy profile"
        for planner in (None, {}, {"agent": "codex", "model": "gpt-6.1-terra"}, "claude"):
            record = copy.deepcopy(self.record)
            record["planner"] = planner
            with self.subTest(planner=planner):
                self.assertIn(expected, self.errors(record))
        self.policy["roles"]["reviewer"][1]["enabled"] = True
        self.record["planner"] = {"agent": "human"}
        self.assertEqual(self.errors(), [])

    def test_policy_without_preference_skips_planner_checks(self):
        del self.policy["reviewer_provider_differs_from_planner"]
        del self.record["planner"]
        self.assertEqual(self.errors(), [])

    def test_alias_profiles_and_missing_sensitive_list_fail(self):
        self.policy["roles"]["reviewer"][0]["model"] = "opus"
        self.record["reviewer"].update(requested_model="opus", effective_model="opus")
        self.assertIn("trusted policy has no enabled reviewer profile", self.errors())
        record = copy.deepcopy(self.record)
        del record["sensitive_files_reviewed"]
        self.assertIn(
            "sensitive_files_reviewed must be an explicit list, including when empty",
            self.errors(record),
        )

    def test_policy_without_enabled_reviewer_or_old_shape_fails(self):
        for policy in (
            {"version": 2, "repository": "example/project", "roles": {"reviewer": []}},
            {
                "version": 1,
                "repository": "example/project",
                "reviewer": {"agent": "claude", "model": "claude-opus-5-5"},
            },
        ):
            self.policy = policy
            self.assertIn("trusted policy has no enabled reviewer profile", self.errors())

    def test_same_session_or_reused_reviewer_fails(self):
        self.record["reviewer"]["session_id"] = "writer-session"
        self.assertTrue(self.errors())
        self.record["reviewer"]["session_id"] = "other"
        self.record["reviewer"]["fresh_session"] = False
        self.assertTrue(self.errors())

    def test_unresolved_blockers_and_malformed_findings_fail(self):
        for findings in (
            None,
            [{"blocking": True, "status": "open"}],
            [{"blocking": "false", "status": "resolved"}],
        ):
            record = copy.deepcopy(self.record)
            record["findings"] = findings
            self.assertTrue(self.errors(record))

    def test_nonblocking_notes_and_resolved_findings_do_not_block(self):
        self.record["findings"] = [
            {"blocking": False, "status": "open"},
            {"blocking": True, "status": "resolved"},
        ]
        self.assertEqual(self.errors(), [])

    def test_incomplete_coverage_and_truthy_strings_fail(self):
        for value in (False, "true", 1, None):
            self.record["coverage"]["complete_diff"] = value
            self.assertTrue(self.errors())

    def test_pending_failed_or_incomplete_reviews_never_pass(self):
        for verdict in (None, "pending", "blocked", "changes_requested", "timeout"):
            self.record["verdict"] = verdict
            self.assertTrue(self.errors())

    def test_cli_checks_real_evidence_hashes_and_rejects_report_replacement(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            receipt = directory / "launch.json"
            report = directory / "report.md"
            record_path = directory / "review.json"
            sensitive = directory / "sensitive-paths.txt"
            sensitive.write_text("")
            policy = directory / "policy.json"
            policy.write_text(json.dumps(workflow_config(self.policy)))
            receipt.write_text('{"fixture": "local receipt, not model authentication"}')
            report.write_text("Fixture review report")
            record = copy.deepcopy(self.record)
            record["policy_sha256"] = gate.digest(policy)
            record["launch_receipt_sha256"] = gate.digest(receipt)
            record["review_report_sha256"] = gate.digest(report)
            record_path.write_text(json.dumps(record))
            argv = [
                *GATE,
                "--policy",
                str(policy),
                "--record",
                str(record_path),
                "--head",
                "a" * 40,
                "--base",
                "b" * 40,
                "--launch-receipt",
                str(receipt),
                "--review-report",
                str(report),
                "--sensitive-paths",
                str(sensitive),
            ]
            result = subprocess.run(argv, capture_output=True, text=True, check=False, env=GATE_ENV, cwd=directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            # Without --policy the gate reads workflow.json as committed at --base.
            repo = directory / "repo"
            (repo / ".agents").mkdir(parents=True)
            (repo / ".agents/workflow.json").write_bytes(policy.read_bytes())
            git = ["git", "-C", str(repo)]
            subprocess.run([*git, "init", "-q"], check=True)
            subprocess.run([*git, "add", "."], check=True)
            subprocess.run(
                [*git, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "b"],
                check=True,
            )
            base = subprocess.check_output([*git, "rev-parse", "HEAD"], text=True).strip()
            (repo / ".agents/workflow.json").write_text("{}")  # the working tree is ignored
            record["base_sha"] = base
            based = directory / "based.json"
            based.write_text(json.dumps(record))
            from_base = [*GATE, "--record", str(based), "--head", "a" * 40, "--base", base]
            from_base += argv[argv.index("--launch-receipt") :]
            result = subprocess.run(
                from_base, capture_output=True, text=True, cwd=repo, check=False, env=GATE_ENV
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            # A different runtime than the base pins is not the trusted validator.
            pinned = directory / "pinned.json"
            pinned.write_text(json.dumps(workflow_config(self.policy, "9.9.9")))
            wrong = [*argv]
            wrong[wrong.index("--policy") + 1] = str(pinned)
            result = subprocess.run(wrong, capture_output=True, text=True, check=False, env=GATE_ENV, cwd=directory)
            self.assertIn("pins 9.9.9", result.stderr)
            self.assertNotEqual(result.returncode, 0)
            omitted = subprocess.run(argv[:-2], capture_output=True, text=True, check=False, env=GATE_ENV, cwd=directory)
            self.assertNotEqual(omitted.returncode, 0)
            self.assertIn("--sensitive-paths", omitted.stderr)
            sensitive.unlink()
            missing = subprocess.run(argv, capture_output=True, text=True, check=False, env=GATE_ENV, cwd=directory)
            self.assertNotEqual(missing.returncode, 0)
            sensitive.write_text("")
            report.write_text("Replaced report")
            result = subprocess.run(argv, capture_output=True, text=True, check=False, env=GATE_ENV, cwd=directory)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing or changed evidence", result.stderr)
            receipt.unlink()
            result = subprocess.run(argv, capture_output=True, text=True, check=False, env=GATE_ENV, cwd=directory)
            self.assertNotEqual(result.returncode, 0)

    def test_validator_inside_the_checkout_must_match_the_reviewed_base(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder)
            runtime = repo / "vendored"
            shutil.copytree(
                Path(gate.__file__).resolve().parent,
                runtime / "orca_agent_workflow",
                ignore=shutil.ignore_patterns("__pycache__"),
            )
            git = ["git", "-C", str(repo)]
            subprocess.run([*git, "init", "-q"], check=True)
            subprocess.run([*git, "add", "."], check=True)
            subprocess.run(
                [*git, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "b"],
                check=True,
            )
            base = subprocess.check_output([*git, "rev-parse", "HEAD"], text=True).strip()
            env = dict(os.environ, PYTHONPATH=str(runtime))
            argv = [sys.executable, "-c", "import os, sys; os.chdir(sys.argv.pop(1)); "
                    "from orca_agent_workflow import review_gate; print(review_gate.validator_problem(sys.argv[1]))",
                    str(repo), base]
            same = subprocess.run(argv, capture_output=True, text=True, env=env, check=True)
            self.assertEqual(same.stdout.strip(), "None", same.stderr)
            gate_file = runtime / "orca_agent_workflow/review_gate.py"
            gate_file.write_text(gate_file.read_text() + "\n# accepts anything\n")
            changed = subprocess.run(argv, capture_output=True, text=True, env=env, check=True)
            self.assertIn("review_gate.py differs from the reviewed base", changed.stdout)

    def test_cli_compares_sensitive_list_and_codex_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            policy = directory / "policy.json"
            self.policy["roles"]["reviewer"][1]["enabled"] = True
            policy.write_text(json.dumps(workflow_config(self.policy)))
            receipt, report = directory / "launch.json", directory / "report.md"
            sensitive = directory / "sensitive-paths.txt"
            sensitive.write_text("Makefile\n")
            receipt.write_text(
                json.dumps(
                    {
                        "qualification_sha256": "f" * 64,
                        "thread_id": "thread-1",
                        "session_models": ["gpt-6.1-sol"],
                        "head": "a" * 40,
                        "returncode": 0,
                        "grant_ended": None,
                        "inputs_changed": [],
                    }
                )
            )
            report.write_text("Fixture review report")
            record = copy.deepcopy(self.record)
            record["reviewer"].update(
                agent="codex",
                requested_model="gpt-6.1-sol",
                effective_model="gpt-6.1-sol",
                session_id="thread-1",
                dispatch_id="thread-1",
                model_evidence="codex-session-turn-context",
                qualification_sha256="f" * 64,
            )
            record.update(
                policy_sha256=gate.digest(policy),
                launch_receipt_sha256=gate.digest(receipt),
                review_report_sha256=gate.digest(report),
                sensitive_files_reviewed=["Makefile"],
            )
            path = directory / "review.json"

            def run(rec):
                path.write_text(json.dumps(rec))
                argv = [*GATE, "--policy", str(policy), "--record", str(path), "--head", "a" * 40]
                argv += ["--base", "b" * 40, "--launch-receipt", str(receipt)]
                argv += ["--review-report", str(report), "--sensitive-paths", str(sensitive)]
                return subprocess.run(argv, capture_output=True, text=True, check=False, env=GATE_ENV, cwd=directory)

            result = run(record)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(
                "sensitive files not reviewed",
                run(dict(record, sensitive_files_reviewed=[])).stderr,
            )
            other = copy.deepcopy(record)
            other["reviewer"]["session_id"] = "thread-2"
            self.assertIn("does not match its launch receipt", run(other).stderr)
            other = copy.deepcopy(record)
            other["reviewer"]["dispatch_id"] = "other-dispatch"
            self.assertIn("does not match its launch receipt", run(other).stderr)

            original = json.loads(receipt.read_text())
            mutations = [
                ("head", "b" * 40),
                ("returncode", 1),
                ("returncode", False),
                ("grant_ended", "grant expired"),
                ("inputs_changed", ["source.py"]),
                ("session_models", ["gpt-6.1-terra"]),
                ("qualification_sha256", "0" * 64),
            ]
            for field, value in mutations + [(key, None) for key in original]:
                changed = dict(original, **{field: value})
                if value is None:
                    del changed[field]
                receipt.write_text(json.dumps(changed))
                updated = dict(record, launch_receipt_sha256=gate.digest(receipt))
                with self.subTest(field=field, value=value):
                    result = run(updated)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("does not match its launch receipt", result.stderr)
            receipt.write_text("[]")
            result = run(dict(record, launch_receipt_sha256=gate.digest(receipt)))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not match its launch receipt", result.stderr)

    def test_missing_evidence_and_malformed_record_fail(self):
        self.assertTrue(self.errors([]))
        for field in ("launch_receipt_sha256", "review_report_sha256"):
            record = copy.deepcopy(self.record)
            del record[field]
            self.assertTrue(self.errors(record))


if __name__ == "__main__":
    unittest.main()
