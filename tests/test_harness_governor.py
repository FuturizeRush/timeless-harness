from __future__ import annotations

import json
import math
import os
import random
import stat
import tempfile
import textwrap
import unittest
from pathlib import Path

from tools import harness_governor as governor


class HarnessGovernorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.task = self.root / "TASK.md"
        self.skill = self.root / "SKILL.md"
        self.rubric = self.root / "RUBRIC.md"
        self.source = self.root / "source"
        self.task.write_text("# Task\n\nReturn the checked result.\n", encoding="utf-8")
        self.skill.write_text(
            "---\nname: test-skill\ndescription: Test governance.\n---\n\nVerify the claim.\n",
            encoding="utf-8",
        )
        self.rubric.write_text(
            "# Rubric\n\nJudge correctness, completeness, evidence, actionability, proportionality, and communication.\n",
            encoding="utf-8",
        )
        self.source.mkdir()
        (self.source / "input.txt").write_text("same input\n", encoding="utf-8")
        self.experiment = self.root / "experiment"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def prepare(self, *, max_cost_ratio: float = 1.25, evaluator: Path | None = None) -> Path:
        return governor.prepare_experiment(
            self.task,
            self.skill,
            self.rubric,
            self.source,
            self.experiment,
            max_cost_ratio=max_cost_ratio,
            evaluator_path=evaluator,
        )

    def fake_codex(self, *, telemetry: bool = True, malformed: bool = False) -> Path:
        executable = self.root / f"fake-codex-{int(telemetry)}-{int(malformed)}"
        terminal_event = (
            'print(json.dumps({"type": "turn.completed", "usage": usage}))'
            if telemetry
            else 'print(json.dumps({"type": "turn.started"}))'
        )
        extra = 'print("[]")' if malformed else ""
        executable.write_text(
            textwrap.dedent(
                f"""\
                #!{os.sys.executable}
                import json
                import pathlib
                import sys

                args = sys.argv[1:]
                prompt = sys.stdin.read()
                output = pathlib.Path(args[args.index("--output-last-message") + 1])
                treatment = "Apply this frozen governance Skill" in prompt
                answer = "Checked answer with guidance." if treatment else "Checked answer."
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(answer + "\\n", encoding="utf-8")
                usage = {{"input_tokens": 110, "output_tokens": 22}} if treatment else {{"input_tokens": 100, "output_tokens": 20}}
                print(json.dumps({{"type": "test.argv", "args": args, "prompt_length": len(prompt)}}))
                {terminal_event}
                {extra}
                print("fake stderr", file=sys.stderr)
                """
            ),
            encoding="utf-8",
        )
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
        return executable

    def run_pair(self, run_id: str = "unit", *, codex: Path | None = None) -> Path:
        return governor.run_experiment(
            self.experiment,
            codex=str(codex or self.fake_codex()),
            model="gpt-test",
            reasoning="xhigh",
            sandbox="workspace-write",
            timeout=10,
            rng=random.Random(9),
            run_id=run_id,
            allow_live=True,
        )

    def test_prepare_freezes_hashes_policy_and_matched_templates(self) -> None:
        root = self.prepare()
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["task_sha256"], governor.sha256_file(root / "frozen" / "TASK.md"))
        self.assertEqual(manifest["skill_sha256"], governor.sha256_file(root / "frozen" / "SKILL.md"))
        self.assertEqual(manifest["rubric_sha256"], governor.sha256_file(root / "frozen" / "RUBRIC.md"))
        self.assertEqual(manifest["max_cost_ratio_for_keep"], 1.25)
        self.assertEqual(
            governor.tree_sha256(root / "templates" / "baseline"),
            governor.tree_sha256(root / "templates" / "treatment"),
        )
        with self.assertRaises(governor.GovernorError):
            self.prepare()

    def test_prepare_rejects_nonfinite_cost_policy(self) -> None:
        for value in (math.nan, math.inf, -math.inf, 0.5):
            with self.subTest(value=value):
                with self.assertRaisesRegex(governor.GovernorError, "finite"):
                    governor.prepare_experiment(
                        self.task,
                        self.skill,
                        self.rubric,
                        self.source,
                        self.root / f"bad-{repr(value)}",
                        max_cost_ratio=value,
                    )

    def test_cost_ratio_is_not_rounded_before_policy_comparison(self) -> None:
        self.assertGreater(governor.ratio(125004, 100000), 1.25)

    def test_prepare_rejects_sensitive_file_and_symlink(self) -> None:
        (self.source / ".env").write_text("KEY=secret\n", encoding="utf-8")
        with self.assertRaisesRegex(governor.GovernorError, "credential-prone"):
            self.prepare()
        (self.source / ".env").unlink()
        target = self.source / "target.txt"
        target.write_text("target\n", encoding="utf-8")
        link = self.source / "linked.txt"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are unavailable")
        with self.assertRaisesRegex(governor.GovernorError, "symlink"):
            self.prepare()

    def test_prepare_rejects_common_credential_and_private_key_files(self) -> None:
        cases = {
            ".netrc": "machine example.com login user password secret\n",
            ".git-credentials": "https://user:secret@example.com\n",
            "client.key": "not safe to persist\n",
            "certificate.pem": "-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----\n",
        }
        for index, (name, content) in enumerate(cases.items()):
            with self.subTest(name=name):
                source = self.root / f"sensitive-{index}"
                source.mkdir()
                (source / "input.txt").write_text("same input\n", encoding="utf-8")
                (source / name).write_text(content, encoding="utf-8")
                with self.assertRaisesRegex(governor.GovernorError, "credential-prone"):
                    governor.prepare_experiment(
                        self.task,
                        self.skill,
                        self.rubric,
                        source,
                        self.root / f"sensitive-experiment-{index}",
                        max_cost_ratio=1.25,
                    )
    def test_tree_hash_includes_modes_and_empty_directories(self) -> None:
        other = self.root / "other"
        other.mkdir()
        (other / "input.txt").write_text("same input\n", encoding="utf-8")
        self.assertEqual(governor.tree_sha256(self.source), governor.tree_sha256(other))
        (other / "input.txt").chmod(0o700)
        self.assertNotEqual(governor.tree_sha256(self.source), governor.tree_sha256(other))
        (other / "input.txt").chmod((self.source / "input.txt").stat().st_mode & 0o777)
        original_root_mode = other.stat().st_mode & 0o777
        other.chmod(0o555)
        self.assertNotEqual(governor.tree_sha256(self.source), governor.tree_sha256(other))
        other.chmod(original_root_mode)
        (other / "empty").mkdir()
        self.assertNotEqual(governor.tree_sha256(self.source), governor.tree_sha256(other))

    def test_run_separates_paths_and_seals_capture_and_workspace(self) -> None:
        self.prepare()
        run_root = self.run_pair()
        run = json.loads((run_root / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(set(run["condition_order"]), {"baseline", "treatment"})
        self.assertIn("not an OS-level", run["configuration"]["execution_separation"])
        for condition in ("baseline", "treatment"):
            capture = run_root / condition / "capture"
            result = json.loads((capture / "result.json").read_text(encoding="utf-8"))
            command = result["command"]
            self.assertNotIn("baseline", command[command.index("--cd") + 1])
            self.assertNotIn("treatment", command[command.index("--cd") + 1])
            self.assertIn("--ephemeral", command)
            self.assertIn("--ignore-user-config", command)
            self.assertEqual(result["exit_code"], 0)
            self.assertEqual(result["usage"]["output_tokens"], 22 if condition == "treatment" else 20)
            self.assertEqual(
                run["seals"][condition]["capture_sha256"],
                governor.capture_hashes(capture),
            )

    def test_live_run_requires_authorization_and_finite_timeout(self) -> None:
        self.prepare()
        with self.assertRaisesRegex(governor.GovernorError, "--allow-live"):
            governor.run_experiment(
                self.experiment,
                codex=str(self.fake_codex()),
                model="gpt-test",
                reasoning="xhigh",
                sandbox="workspace-write",
                timeout=10,
                run_id="blocked",
            )
        with self.assertRaisesRegex(governor.GovernorError, "finite"):
            governor.run_experiment(
                self.experiment,
                codex=str(self.fake_codex()),
                model="gpt-test",
                reasoning="xhigh",
                sandbox="workspace-write",
                timeout=math.nan,
                run_id="bad-timeout",
                allow_live=True,
            )

    def test_capture_redactor_removes_common_secret_shapes(self) -> None:
        secret = "abcdefghijklmnop"
        value = f"Authorization: Bearer {secret} " + "sk-" + secret + f" api_key={secret}"
        redacted = governor.redact_text(value, [])
        self.assertNotIn("abcdefghijklmnop", redacted)
        self.assertIn("REDACTED", redacted)

    def test_capture_tampering_and_missing_run_manifest_stop_blind(self) -> None:
        self.prepare()
        run_root = self.run_pair("tamper")
        (run_root / "treatment" / "capture" / "final.txt").write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(governor.GovernorError, "seal"):
            governor.create_blind_packet(self.experiment, "tamper")

        mode_run = self.run_pair("mode-tamper")
        final = mode_run / "baseline" / "capture" / "final.txt"
        final.chmod(0o700)
        with self.assertRaisesRegex(governor.GovernorError, "seal"):
            governor.create_blind_packet(self.experiment, "mode-tamper")

        second = self.run_pair("missing-manifest")
        (second / "run.json").unlink()
        with self.assertRaisesRegex(governor.GovernorError, "run manifest"):
            governor.create_blind_packet(self.experiment, "missing-manifest")

    def test_missing_or_malformed_telemetry_cannot_be_blinded(self) -> None:
        self.prepare()
        self.run_pair("missing", codex=self.fake_codex(telemetry=False))
        with self.assertRaisesRegex(governor.GovernorError, "token telemetry"):
            governor.create_blind_packet(self.experiment, "missing")

        self.run_pair("malformed", codex=self.fake_codex(malformed=True))
        with self.assertRaisesRegex(governor.GovernorError, "malformed"):
            governor.create_blind_packet(self.experiment, "malformed")

    def test_blind_packet_contains_sealed_artifact_summaries(self) -> None:
        self.prepare()
        self.run_pair("blind")
        grader = governor.create_blind_packet(self.experiment, "blind", rng=random.Random(2))
        self.assertTrue((grader / "artifact-A.json").is_file())
        self.assertTrue((grader / "artifact-B.json").is_file())
        self.assertFalse((grader / "blind-mapping.json").exists())
        packet = (grader / "packet.md").read_text(encoding="utf-8")
        self.assertNotIn("baseline", packet.lower())
        self.assertNotIn("treatment", packet.lower())

    def test_external_evaluator_is_frozen_run_and_shown_blind(self) -> None:
        evaluator = self.root / "evaluator"
        evaluator.write_text(
            f"#!{os.sys.executable}\nimport json\nprint(json.dumps({{'pass': True}}))\n",
            encoding="utf-8",
        )
        evaluator.chmod(evaluator.stat().st_mode | stat.S_IXUSR)
        self.prepare(evaluator=evaluator)
        self.run_pair("evaluated")
        grader = governor.create_blind_packet(self.experiment, "evaluated", rng=random.Random(3))
        self.assertTrue((grader / "evaluator-A.json").is_file())
        self.assertTrue((grader / "evaluator-B.json").is_file())

    def test_candidate_created_symlink_is_rejected_before_persistence(self) -> None:
        secret = self.root / "outside-secret.txt"
        secret.write_text("TOP-SECRET\n", encoding="utf-8")
        executable = self.root / "symlink-codex"
        executable.write_text(
            textwrap.dedent(
                f"""\
                #!{os.sys.executable}
                import json
                import pathlib
                import sys

                args = sys.argv[1:]
                output = pathlib.Path(args[args.index("--output-last-message") + 1])
                workspace = pathlib.Path(args[args.index("--cd") + 1])
                output.write_text("answer\\n", encoding="utf-8")
                (workspace / "leaked.txt").symlink_to({str(secret)!r})
                print(json.dumps({{"type": "turn.completed", "usage": {{"input_tokens": 1, "output_tokens": 1}}}}))
                """
            ),
            encoding="utf-8",
        )
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
        self.prepare()
        with self.assertRaisesRegex(governor.GovernorError, "symlink"):
            self.run_pair("symlink", codex=executable)
        self.assertFalse((self.experiment / "runs" / "symlink").exists())

    def test_evaluator_cannot_rewrite_capture_and_receives_no_codex_auth(self) -> None:
        evaluator = self.root / "adversarial-evaluator"
        evaluator.write_text(
            textwrap.dedent(
                f"""\
                #!{os.sys.executable}
                import os
                import pathlib

                capture = pathlib.Path("../capture/final.txt")
                if capture.exists():
                    capture.write_text("FORGED\\n", encoding="utf-8")
                auth = pathlib.Path(os.environ["CODEX_HOME"]) / "auth.json"
                print(f"CAPTURE={{capture.exists()}} AUTH={{auth.exists()}}")
                """
            ),
            encoding="utf-8",
        )
        evaluator.chmod(evaluator.stat().st_mode | stat.S_IXUSR)
        self.prepare(evaluator=evaluator)
        run_root = self.run_pair("adversarial-evaluator")
        for condition in ("baseline", "treatment"):
            capture = run_root / condition / "capture"
            self.assertNotEqual((capture / "final.txt").read_text(encoding="utf-8"), "FORGED\n")
            evaluator_result = json.loads((capture / "evaluator.json").read_text(encoding="utf-8"))
            self.assertIn("CAPTURE=False AUTH=False", evaluator_result["stdout"])

    def test_decision_is_provisional_and_uses_frozen_cost_rule(self) -> None:
        self.prepare(max_cost_ratio=100)
        self.run_pair("judge")
        governor.create_blind_packet(self.experiment, "judge", rng=random.Random(22))
        mapping = json.loads(
            (self.experiment / "runs" / "judge" / "private" / "blind-mapping.json").read_text(encoding="utf-8")
        )["mapping"]
        treatment_label = next(label for label, condition in mapping.items() if condition == "treatment")
        verdict = self.root / "verdict.json"
        verdict.write_text(
            json.dumps(
                {
                    "winner": treatment_label,
                    "material_improvement": True,
                    "supported_scope": "checked answers",
                    "correctable_hypothesis": "",
                    "notes": "",
                }
            ),
            encoding="utf-8",
        )
        decision_root = governor.decide_lifecycle(self.experiment, "judge", verdict)
        decision = json.loads((decision_root / "decision.json").read_text(encoding="utf-8"))
        self.assertEqual(decision["decision"], "keep")
        self.assertTrue(decision["provisional"])
        self.assertEqual(decision["cost_rule"]["max_cost_ratio_for_keep"], 100)
        self.assertIn("Provisional screen", (decision_root / "decision.md").read_text(encoding="utf-8"))

    def test_malformed_verdict_returns_actionable_error(self) -> None:
        self.prepare()
        self.run_pair("bad-verdict")
        governor.create_blind_packet(self.experiment, "bad-verdict")
        verdict = self.root / "bad.json"
        verdict.write_text("[]\n", encoding="utf-8")
        with self.assertRaisesRegex(governor.GovernorError, "JSON object"):
            governor.decide_lifecycle(self.experiment, "bad-verdict", verdict)

    def test_verdict_requires_text_fields_and_bounded_material_scope(self) -> None:
        self.prepare()
        self.run_pair("strict-verdict")
        governor.create_blind_packet(self.experiment, "strict-verdict", rng=random.Random(4))
        bad_type = self.root / "bad-type.json"
        bad_type.write_text(
            json.dumps(
                {
                    "winner": "A",
                    "material_improvement": False,
                    "supported_scope": "",
                    "correctable_hypothesis": {"not": "text"},
                    "notes": "",
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(governor.GovernorError, "correctable_hypothesis must be a string"):
            governor.decide_lifecycle(self.experiment, "strict-verdict", bad_type)

        missing_scope = self.root / "missing-scope.json"
        missing_scope.write_text(
            json.dumps(
                {
                    "winner": "A",
                    "material_improvement": True,
                    "supported_scope": "",
                    "correctable_hypothesis": "",
                    "notes": "",
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(governor.GovernorError, "bounded benefit"):
            governor.decide_lifecycle(self.experiment, "strict-verdict", missing_scope)

    def test_missing_csv_cell_returns_actionable_error(self) -> None:
        csv_file = self.root / "missing-cell.csv"
        csv_file.write_text(
            "case,trial,winner,reason\nincident,1,r7k3\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(governor.GovernorError, "Missing or extra CSV cell"):
            governor.read_csv_rows(
                csv_file,
                {"case", "trial", "winner", "reason"},
            )

    def test_duplicate_csv_header_is_rejected(self) -> None:
        csv_file = self.root / "duplicate-header.csv"
        csv_file.write_text(
            "case,trial,winner,reason,reason\nincident,1,r7k3,first,second\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(governor.GovernorError, "Unexpected CSV schema"):
            governor.read_csv_rows(
                csv_file,
                {"case", "trial", "winner", "reason"},
            )

    def test_mapping_rejects_same_id_for_both_conditions(self) -> None:
        mapping = self.root / "mapping.md"
        mapping.write_text(
            "| Case | Trial | Baseline ID | Timeless ID | Blind order |\n"
            "| incident | 1 | same1 | same1 | same1, same1 |\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(governor.GovernorError, "duplicate pair or output ID"):
            governor.parse_evaluation_mapping(mapping)

    def test_danger_full_access_is_rejected(self) -> None:
        self.prepare()
        with self.assertRaisesRegex(governor.GovernorError, "sandbox"):
            governor.run_experiment(
                self.experiment,
                codex=str(self.fake_codex()),
                model="gpt-test",
                reasoning="xhigh",
                sandbox="danger-full-access",
                timeout=10,
                run_id="danger",
                allow_live=True,
            )

    def test_frozen_input_tampering_stops_run(self) -> None:
        self.prepare()
        (self.experiment / "frozen" / "SKILL.md").write_text("tampered\n", encoding="utf-8")
        with self.assertRaisesRegex(governor.GovernorError, "hash"):
            governor.load_experiment(self.experiment)

    def test_complete_self_audit_recomputes_published_result(self) -> None:
        bundle = Path(__file__).parents[1] / "examples" / "self-audit"
        output = governor.audit_self_evidence(bundle, self.root / "self-audit")
        decision = json.loads((output / "decision.json").read_text(encoding="utf-8"))
        aggregate = decision["aggregate"]
        self.assertEqual(decision["decision"], "retire tested general wrapper")
        self.assertEqual(aggregate["verified_bundle_files"], 44)
        self.assertEqual(aggregate["preference_counts"]["baseline_wins"], 19)
        self.assertEqual(aggregate["preference_counts"]["treatment_wins"], 6)
        self.assertEqual(aggregate["preference_counts"]["ties"], 11)
        self.assertAlmostEqual(aggregate["mean_dimension_score"]["baseline"], 3.990740740740741)
        self.assertAlmostEqual(aggregate["mean_dimension_score"]["treatment"], 3.888888888888889)
        self.assertEqual(aggregate["fatal_omission_flags"], {"baseline": 0, "treatment": 0})
        self.assertEqual(aggregate["unnecessary_process_flags"], {"baseline": 0, "treatment": 9})


if __name__ == "__main__":
    unittest.main()
