#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""repro_pack 单测（仅标准库）。运行：python test_repro_pack.py"""
import sys
import tempfile
import unittest
import json
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import repro_pack as rp  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        rp.main(["init", str(self.tmp)])

    def _csv(self, name, rows, cols=3):
        p = self.tmp / "data" / "raw" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        header = ",".join("c%d" % i for i in range(cols))
        body = "\n".join(",".join(str(r) for _ in range(cols)) for r in range(rows))
        p.write_text(header + "\n" + body + "\n", encoding="utf-8")
        return p


class TestInit(Base):
    def test_scaffold_and_meta(self):
        for sub in rp.SCAFFOLD:
            self.assertTrue((self.tmp / sub).is_dir(), sub)
        self.assertTrue(rp.meta_path(self.tmp, rp.PROVENANCE).exists())
        self.assertTrue(rp.meta_path(self.tmp, rp.MANIFEST_MD).exists())


class TestProvenance(Base):
    def test_hash_and_csv_shape(self):
        self._csv("survey.csv", rows=42, cols=4)
        rec = rp.add_source(self.tmp, "data/raw/survey.csv",
                            source_url="http://x", access_date="2026-06-14")
        self.assertEqual(rec["n_rows"], 42)
        self.assertEqual(rec["n_cols"], 4)
        self.assertEqual(len(rec["sha256"]), 64)

    def test_same_file_updates_not_duplicates(self):
        self._csv("survey.csv", rows=10)
        rp.add_source(self.tmp, "data/raw/survey.csv")
        rp.add_source(self.tmp, "data/raw/survey.csv")  # 二次登记
        pv = rp.load_json(rp.meta_path(self.tmp, rp.PROVENANCE), {"sources": []})
        self.assertEqual(len(pv["sources"]), 1, "同名来源应更新而非重复")

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            rp.add_source(self.tmp, "data/raw/nope.csv")


class TestCheck(Base):
    def setUp(self):
        super().setUp()
        self.eligibility = mock.patch.object(
            rp.method_execution_authority,
            "downstream_eligibility",
            side_effect=self._eligible_projection,
        )
        self.eligibility_mock = self.eligibility.start()
        self.addCleanup(self.eligibility.stop)

    @staticmethod
    def _eligible_projection(_root, payload=None):
        results = {}
        for run in (payload or {}).get("runs") or []:
            for result in run.get("results") or []:
                if isinstance(result, dict) and result.get("id"):
                    results[str(result["id"]).upper()] = {
                        "result_id": str(result["id"]).upper(),
                        "allowed_uses": ["claim_support"],
                    }
        return {
            "schema_version": "cnki-method-downstream-eligibility/v1",
            "status": "PASS",
            "issues": [],
            "results": results,
        }

    def _execution(self, *, artifact_path="output/results.json", artifact_id="ART-001"):
        output = self.tmp / artifact_path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('{"beta": 0.12}\n', encoding="utf-8")
        payload = {
            "schema_version": "cnki-method-execution/v3",
            "runs": [
                {
                    "id": "RUN-001",
                    "artifacts": [
                        {
                            "id": artifact_id,
                            "path": artifact_path,
                            "sha256": rp.sha256_of(output),
                            "role": "model-output",
                        }
                    ],
                    "results": [
                        {
                            "id": "RES-001",
                            "numeric_values": [
                                {
                                    "id": "t2_beta",
                                    "value": 0.12,
                                    "evidence_id": "E-001",
                                    "artifact_id": artifact_id,
                                    "locator": "json:/beta",
                                    "reproduction_command": "python scripts/main.py",
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        (self.tmp / rp.METHOD_EXECUTION).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return payload

    def _make_clean(self):
        # 来源
        self._csv("survey.csv", rows=10)
        rp.add_source(self.tmp, "data/raw/survey.csv")
        # 落稿数字只存在于 canonical method_execution.json。
        self._execution()
        # 环境冻结
        rp.meta_path(self.tmp, rp.ENVIRONMENT).write_text("python 3.13\n", encoding="utf-8")

    def test_clean_passes(self):
        self._make_clean()
        self.assertEqual(rp.run_check(self.tmp), [])

    def test_missing_source_file_flagged(self):
        self._make_clean()
        (self.tmp / "data" / "raw" / "survey.csv").unlink()
        issues = rp.run_check(self.tmp)
        self.assertTrue(any("来源文件缺失" in i for i in issues))

    def test_hash_mismatch_flagged(self):
        self._make_clean()
        # 篡改数据文件 → 哈希不符
        (self.tmp / "data" / "raw" / "survey.csv").write_text("tampered\n", encoding="utf-8")
        issues = rp.run_check(self.tmp)
        self.assertTrue(any("哈希不符" in i for i in issues))

    def test_number_with_unknown_artifact_flagged(self):
        self._make_clean()
        payload = json.loads((self.tmp / rp.METHOD_EXECUTION).read_text(encoding="utf-8"))
        payload["runs"][0]["results"][0]["numeric_values"][0]["artifact_id"] = "ART-MISSING"
        (self.tmp / rp.METHOD_EXECUTION).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        issues = rp.run_check(self.tmp)
        self.assertTrue(any("未知 Artifact ID" in i for i in issues))

    def test_numbers_view_is_derived_from_execution(self):
        self._make_clean()
        rp.run_check(self.tmp)
        rows = rp.read_jsonl(rp.meta_path(self.tmp, rp.NUMBERS))
        self.assertEqual(rows[0]["generated_from"], rp.METHOD_EXECUTION)
        self.assertEqual(rows[0]["artifact_id"], "ART-001")
        self.assertEqual(len(rows[0]["execution_sha256"]), 64)

    def test_v3_number_requires_reciprocal_accepted_action(self):
        payload = self._execution()
        payload["schema_version"] = "cnki-method-execution/v3"
        payload["runs"][0]["actions"] = [
            {"id": "ACT-001", "status": "accepted", "result_ids": ["RES-001"]}
        ]
        payload["runs"][0]["results"][0]["action_ids"] = ["ACT-001"]
        (self.tmp / rp.METHOD_EXECUTION).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        rows, issues = rp.execution_numbers(self.tmp)
        self.assertEqual(issues, [])
        self.assertEqual([row["id"] for row in rows], ["t2_beta"])
        self.eligibility_mock.assert_called()

    def test_v3_number_from_failed_or_unchecked_action_is_excluded(self):
        for status in ("failed", "superseded", "unchecked"):
            with self.subTest(status=status):
                payload = self._execution()
                payload["schema_version"] = "cnki-method-execution/v3"
                payload["runs"][0]["actions"] = [
                    {"id": "ACT-001", "status": status, "result_ids": ["RES-001"]}
                ]
                payload["runs"][0]["results"][0]["action_ids"] = ["ACT-001"]
                (self.tmp / rp.METHOD_EXECUTION).write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                blocked = {
                    "schema_version": "cnki-method-downstream-eligibility/v1",
                    "status": "BLOCKED",
                    "issues": [
                        {
                            "code": "ME.RESULT.ACTION_NOT_ACCEPTED",
                            "message": "result is not bound to an accepted action",
                        }
                    ],
                    "results": {},
                }
                with mock.patch.object(
                    rp.method_execution_authority,
                    "downstream_eligibility",
                    return_value=blocked,
                ):
                    rows, issues = rp.execution_numbers(self.tmp)
                self.assertEqual(rows, [])
                self.assertTrue(any("ME.RESULT.ACTION_NOT_ACCEPTED" in issue for issue in issues))

    def test_canonical_projection_failure_is_fail_closed(self):
        self._execution()
        blocked = {
            "schema_version": "cnki-method-downstream-eligibility/v1",
            "status": "BLOCKED",
            "issues": [
                {
                    "code": "ME.ARTIFACT.HASH_MISMATCH",
                    "message": "artifact digest does not match",
                }
            ],
            "results": {},
        }
        with mock.patch.object(
            rp.method_execution_authority,
            "downstream_eligibility",
            return_value=blocked,
        ):
            rows, issues = rp.execution_numbers(self.tmp)
        self.assertEqual(rows, [])
        self.assertTrue(any("ME.ARTIFACT.HASH_MISMATCH" in issue for issue in issues))

    def test_deprecated_number_command_cannot_write_second_truth(self):
        code = rp.main([
            "number", "--id", "x", "--value", "1", "--script", "scripts/x.py"
        ])
        self.assertEqual(code, 2)
        self.assertFalse(rp.meta_path(self.tmp, rp.NUMBERS).exists())

    def test_unfrozen_env_flagged(self):
        self._csv("s.csv", rows=5)
        rp.add_source(self.tmp, "data/raw/s.csv")
        self._execution()
        # 不创建 environment.txt
        issues = rp.run_check(self.tmp)
        self.assertTrue(any("环境未冻结" in i for i in issues))

    def test_missing_execution_contract_flagged(self):
        self._csv("s.csv", rows=5)
        rp.add_source(self.tmp, "data/raw/s.csv")
        rp.meta_path(self.tmp, rp.ENVIRONMENT).write_text("python 3.13\n", encoding="utf-8")
        issues = rp.run_check(self.tmp)
        self.assertTrue(any("缺少 method_execution.json" in i for i in issues))


class TestSampleLogAndManifest(Base):
    def test_exclude_and_manifest(self):
        sl = rp.load_json(rp.meta_path(self.tmp, rp.SAMPLE_LOG), {"steps": []})
        sl["steps"].append({"step": "删缺失", "n_before": 100, "n_after": 90, "dropped": 10})
        rp.save_json(rp.meta_path(self.tmp, rp.SAMPLE_LOG), sl)
        rp._write_manifest(self.tmp)
        md = rp.meta_path(self.tmp, rp.MANIFEST_MD).read_text(encoding="utf-8")
        self.assertIn("删缺失", md)
        self.assertIn("100 → 90", md)


class TestCanonicalV3Integration(unittest.TestCase):
    def test_real_v4_v3_projection_releases_recomputable_number(self):
        import test_method_execution_v3 as fixtures

        temporary, base, _, payload = fixtures.v3_workspace()
        try:
            run = payload["runs"][0]
            result = run["results"][0]
            artifact = next(item for item in run["artifacts"] if item["id"] == "ART-001")
            artifact_path = base / artifact["path"]
            artifact_path.write_text("0.12\n", encoding="utf-8")
            artifact["sha256"] = rp.sha256_of(artifact_path)
            result["numeric_values"] = [
                {
                    "id": "registered_beta",
                    "value": 0.12,
                    "evidence_id": result["evidence_ids"][0],
                    "artifact_id": "ART-001",
                    "locator": "text:line=1",
                    "reproduction_command": "python scripts/reproduce_registered_beta.py",
                }
            ]
            (base / rp.METHOD_EXECUTION).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            rows, issues = rp.execution_numbers(base)
            self.assertEqual([], issues)
            self.assertEqual(["registered_beta"], [row["id"] for row in rows])
            self.assertEqual("ART-001", rows[0]["artifact_id"])
            self.assertEqual(64, len(rows[0]["execution_sha256"]))
        finally:
            temporary.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
