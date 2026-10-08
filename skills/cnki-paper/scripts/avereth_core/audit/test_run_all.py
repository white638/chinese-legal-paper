from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from avereth_core.artifacts import sha256_file
from avereth_core.models import GateResult

run_all = importlib.import_module("avereth_core.audit.run_all")


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class AuditCompletionOrderTests(unittest.TestCase):
    def _fixture(self, outdir: Path) -> tuple[dict[str, object], object]:
        manuscript = outdir / "final_paper" / "main.md"
        manuscript.parent.mkdir(parents=True)
        manuscript.write_text("Canonical audited manuscript.\n", encoding="utf-8")
        active: dict[str, object] = {
            "scene": "report_review",
            "page_evidence_required": False,
            "canonical_manuscript": "final_paper/main.md",
        }
        canonical = {
            "path": "final_paper/main.md",
            "sha256": sha256_file(manuscript),
        }
        selection = mock.Mock()
        selection.as_dict.return_value = canonical

        skills_dir = Path(run_all.__file__).resolve().parents[4]
        actions = run_all._actions(outdir, skills_dir, active, manuscript)
        action_by_name = {action.name: action for action in actions}
        expected_order = [
            "artifact_consistency",
            "integrity",
            *(action.name for action in actions),
            "review_postcondition",
            "audit_postcondition",
            "review_assurance_postcondition",
            "upstream_postcondition",
        ]
        implementation = {
            "artifact_consistency": sha256_file(Path(run_all.__file__).with_name("artifacts.py")),
            "integrity": sha256_file(Path(run_all.__file__).with_name("integrity.py")),
            "review_postcondition": sha256_file(Path(run_all.__file__).with_name("reviewers.py")),
            "audit_postcondition": sha256_file(Path(run_all.__file__).resolve().parents[1] / "stages.py"),
            "review_assurance_postcondition": sha256_file(
                Path(run_all.__file__).resolve().parents[1] / "cli.py"
            ),
            "upstream_postcondition": sha256_file(
                Path(run_all.__file__).resolve().parents[1] / "cli.py"
            ),
            **{
                action.name: sha256_file(action.script) if action.script.is_file() else ""
                for action in actions
            },
        }
        input_digests = {
            "artifact_consistency": run_all._digest_payload({"config": active, "action": "artifact_consistency"}),
            "integrity": run_all._digest_payload({"canonical_sha256": canonical["sha256"], "config": active, "action": "integrity"}),
            "review_postcondition": run_all._digest_payload({"canonical_sha256": canonical["sha256"], "action": "review_postcondition"}),
            "audit_postcondition": run_all._digest_payload({"config": active, "action": "audit_postcondition"}),
            "review_assurance_postcondition": run_all._digest_payload({"action": "review_assurance_postcondition", "issues": []}),
            "upstream_postcondition": run_all._digest_payload({"action": "upstream_postcondition", "issues": []}),
            **{
                name: run_all._action_input_digest(action, outdir, manuscript)
                for name, action in action_by_name.items()
            },
        }
        page_report = outdir / "page_evidence_audit.md"
        page_report.write_text("Status: NOT_APPLICABLE\n", encoding="utf-8")
        write_json(
            outdir / run_all.RUN_LOG_REL,
            {
                "schema_version": "avereth-audit-run/v1",
                "status": "PASS",
                "canonical_manuscript": canonical,
                "invocations": {name: 1 for name in expected_order},
                "actions": [
                    {
                        "name": name,
                        "returncode": 0,
                        "execution": "EXECUTED",
                        "input_digest": input_digests[name],
                        "implementation_sha256": implementation[name],
                        "revision_impact_sha256": "",
                        "output_artifacts": [{"path": page_report.name, "sha256": sha256_file(page_report)}] if name == "page_evidence" else [],
                    }
                    for name in expected_order
                ],
                "findings": [],
            },
        )
        return active, selection

    def _validate(self, outdir: Path, active: dict[str, object], selection: object) -> GateResult:
        with (
            mock.patch.object(run_all, "select_manuscript", return_value=selection),
            mock.patch.object(run_all, "inspect_stage", return_value=GateResult.pass_("audit")),
            mock.patch.object(
                run_all,
                "validate_review_outputs",
                return_value=GateResult.pass_("audit"),
            ),
        ):
            return run_all.validate_completion(outdir, config=active)

    def _assert_order_failure(self, result: GateResult) -> None:
        order_findings = [item for item in result.findings if item.code == "AUDIT.ACTION_ORDER"]
        self.assertFalse(result.ok)
        self.assertEqual(1, len(order_findings))
        self.assertIn("expected=", order_findings[0].message)
        self.assertIn("actual=", order_findings[0].message)

    def test_swapped_review_compile_order_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            outdir = Path(raw)
            active, selection = self._fixture(outdir)
            self.assertTrue(self._validate(outdir, active, selection).ok)
            payload = json.loads((outdir / run_all.RUN_LOG_REL).read_text(encoding="utf-8"))
            records = payload["actions"]
            left = next(i for i, row in enumerate(records) if row["name"] == "structured_review")
            right = next(
                i for i, row in enumerate(records) if row["name"] == "review_finding_compile"
            )
            records[left], records[right] = records[right], records[left]
            write_json(outdir / run_all.RUN_LOG_REL, payload)
            result = self._validate(outdir, active, selection)
        self._assert_order_failure(result)

    def test_upstream_postcondition_cannot_be_moved_before_actions(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            outdir = Path(raw)
            active, selection = self._fixture(outdir)
            payload = json.loads((outdir / run_all.RUN_LOG_REL).read_text(encoding="utf-8"))
            records = payload["actions"]
            upstream = records.pop(
                next(i for i, row in enumerate(records) if row["name"] == "upstream_postcondition")
            )
            records.insert(2, upstream)
            write_json(outdir / run_all.RUN_LOG_REL, payload)
            result = self._validate(outdir, active, selection)
        self._assert_order_failure(result)

    def test_action_cache_binds_inputs_implementation_and_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            outdir = Path(raw)
            manuscript = outdir / "final_paper" / "main.md"
            manuscript.parent.mkdir(parents=True)
            manuscript.write_text("Manuscript A\n", encoding="utf-8")
            script = outdir / "check.py"
            script.write_text("print('ok')\n", encoding="utf-8")
            output = outdir / "academic_prose_check.md"
            output.write_text("Status: PASS\n", encoding="utf-8")
            action = run_all.Action("academic_prose", script, (str(outdir),))
            previous = {
                "status": "PASS",
                "actions": [
                    {
                        "name": action.name,
                        "returncode": 0,
                        "execution": "EXECUTED",
                        "input_digest": run_all._action_input_digest(action, outdir, manuscript),
                        "implementation_sha256": sha256_file(script),
                        "revision_impact_sha256": "",
                        "output_artifacts": [
                            {"path": output.name, "sha256": sha256_file(output)}
                        ],
                    }
                ],
            }
            reused = run_all._cached_action_record(previous, action, outdir, manuscript)
            self.assertIsNotNone(reused)
            self.assertEqual("REUSED", reused["execution"])
            manuscript.write_text("Manuscript B\n", encoding="utf-8")
            self.assertIsNone(run_all._cached_action_record(previous, action, outdir, manuscript))
            manuscript.write_text("Manuscript A\n", encoding="utf-8")
            script.write_text("print('changed')\n", encoding="utf-8")
            self.assertIsNone(run_all._cached_action_record(previous, action, outdir, manuscript))
            script.write_text("print('ok')\n", encoding="utf-8")
            write_json(
                outdir / "revision_impact.json",
                {"schema_version": "avereth-revision-impact/v1", "change_classes": ["surface"]},
            )
            self.assertIsNone(run_all._cached_action_record(previous, action, outdir, manuscript))


if __name__ == "__main__":
    unittest.main()
