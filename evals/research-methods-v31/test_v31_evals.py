#!/usr/bin/env python3
"""Static acceptance checks for the v3.1 textbook/method evaluation assets."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def load_json(name: str):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


blind_eval = load_module("blind_eval_v31_tests", HERE / "blind_eval.py")


class V31EvalAssetsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.coverage = load_json("textbook_coverage.json")
        cls.sources = load_json("authoritative-method-sources.json")
        cls.fixtures = load_json("fixture_manifest.json")
        cls.rules = load_json("rules.json")
        cls.registry = json.loads(
            (
                REPO
                / "skills"
                / "empirical-research"
                / "references"
                / "method-adapter-registry.json"
            ).read_text(encoding="utf-8")
        )

    def test_textbook_has_all_19_chapters_and_80_toc_sections(self) -> None:
        chapters = self.coverage["chapters"]
        self.assertEqual(list(range(1, 20)), [chapter["chapter"] for chapter in chapters])
        sections = [section for chapter in chapters for section in chapter["sections"]]
        self.assertEqual(80, len(sections))
        self.assertEqual(80, self.coverage["source"]["toc_sections"])
        self.assertEqual(len(sections), len({section["id"] for section in sections}))

    def test_every_section_has_a_disposition_basis_entry_and_reason(self) -> None:
        allowed = set(self.coverage["classifications"])
        source_ids = {source["id"] for source in self.sources["sources"]}
        for chapter in self.coverage["chapters"]:
            for section in chapter["sections"]:
                with self.subTest(section=section["id"]):
                    self.assertIn(section["classification"], allowed)
                    self.assertRegex(section["pages"], r"^\d+(?:-\d+)?$")
                    self.assertTrue(section["external_basis"])
                    self.assertTrue(set(section["external_basis"]) <= source_ids)
                    self.assertTrue(section["entry_points"])
                    self.assertGreaterEqual(len(section["transformation"]), 12)
                    self.assertGreaterEqual(len(section["rationale"]), 8)
                    self.assertNotIn("quote", section)
                    for entry in section["entry_points"]:
                        file_part = entry.split("#", 1)[0]
                        self.assertTrue((REPO / file_part).is_file(), file_part)

    def test_authoritative_sources_have_stable_identity_and_scope(self) -> None:
        sources = self.sources["sources"]
        self.assertGreaterEqual(len(sources), 20)
        self.assertEqual(len(sources), len({source["id"] for source in sources}))
        for source in sources:
            with self.subTest(source=source["id"]):
                self.assertRegex(source["id"], r"^AUTH-[A-Z0-9-]+$")
                self.assertTrue(source["url"].startswith("https://"))
                self.assertTrue(source["supports"])

    def test_every_active_method_family_has_six_fixture_classes(self) -> None:
        active = set(self.registry["families"]) - {"unresolved"}
        task_families = {
            task["family"]
            for task in self.fixtures["hidden_evaluation"]["tasks"]
        }
        self.assertEqual(
            active - {"congruence_analysis"},
            task_families - {"governance-migration", "multi-route"},
        )
        self.assertEqual(
            {
                "positive",
                "keyword-gaming",
                "single-field-mutation",
                "design-execution-drift",
                "inference-overreach",
                "legal-non-applicability",
            },
            set(self.fixtures["automated_variants_per_family"]),
        )

    def test_design_answer_protocol_covers_every_route_and_requires_completeness(self) -> None:
        protocol = (
            REPO
            / "skills"
            / "empirical-research"
            / "references"
            / "design-answer-protocol.md"
        ).read_text(encoding="utf-8")
        for family in set(self.registry["families"]) - {"unresolved"}:
            with self.subTest(family=family):
                self.assertIn(f"| {family} |", protocol)
        self.assertIn("路线完整性复核", protocol)
        self.assertIn("依据什么结果改变决定", protocol)
        self.assertIn("cnki-paper 7.1.0", protocol)
        self.assertIn("cnki-research-design/v4", protocol)
        self.assertIn("cnki-method-execution/v3", protocol)

    def test_design_answer_protocol_preserves_context_and_decision_boundaries(self) -> None:
        protocol = (
            REPO
            / "skills"
            / "empirical-research"
            / "references"
            / "design-answer-protocol.md"
        ).read_text(encoding="utf-8")
        required_codes = {
            "AQ.CONTEXT.FACT_BOUNDARY",
            "AQ.SALIENCE.DECISION_FIRST",
            "AQ.COVERAGE.ROUTE_CLOSURE",
            "AQ.EXECUTION.DEPLOYMENT_MATCH",
            "AQ.DECISION.CONDITIONAL_AUDIT",
            "AQ.REPAIR.OBJECT_PRESERVED",
            "AQ.INFERENCE.EVIDENCE_LADDER",
        }
        self.assertEqual(
            required_codes,
            {
                rule["code"]
                for rule in self.rules["answer_quality_review_rules"]
            },
        )
        for phrase in (
            "守住题面事实边界",
            "未核验风险使用条件式裁决",
            "修复必须保留答案对象",
            "证据组合写成推断阶梯",
            "不得把内部版本注入题面",
            "理想修复失败后还能诚实交付什么",
            "决策优先只改变组织顺序",
            "角色覆盖矩阵",
            "跨案例匹配只在真实比较问题",
            "多臂或多结局实验",
            "沉默主张",
            "标签形成时点",
            "实体与时间",
            "固定节点面板",
            "簇数较少",
            "研究家族",
            "参与者自主反馈",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, protocol)

    def test_method_adapter_contract_does_not_recreate_markdown_truth_tables(self) -> None:
        contract = (
            REPO
            / "skills"
            / "empirical-research"
            / "references"
            / "host-method-adapter.source.md"
        ).read_text(encoding="utf-8")
        self.assertIn("research_design.json", contract)
        self.assertIn("method_execution.json", contract)
        self.assertIn("不再是每条路线必须新建的统一骨架", contract)
        self.assertNotIn("Required Artifact Skeleton", contract)
        self.assertNotIn("paper_rewriting_output/empirical/\n  design_protocol.md", contract)

    def test_hidden_pair_arithmetic_and_release_thresholds_are_locked(self) -> None:
        hidden = self.fixtures["hidden_evaluation"]
        self.assertEqual(20, hidden["task_count"])
        self.assertEqual(20, len(hidden["tasks"]))
        self.assertEqual(2, hidden["repeats_per_task"])
        self.assertEqual(
            hidden["task_count"] * hidden["repeats_per_task"],
            hidden["anonymous_pairs"],
        )
        self.assertEqual(3, hidden["reviewers"])
        self.assertEqual("plurality_non_tie", hidden["preference_aggregation"])
        thresholds = self.fixtures["release_thresholds"]
        self.assertEqual(1.0, thresholds["hard_failure_detection"])
        self.assertEqual(27, thresholds["blind_wins_min"])
        self.assertEqual(5, thresholds["blind_losses_max"])

    def test_rule_codes_are_implemented_and_no_fixed_threshold_is_hard(self) -> None:
        scripts = "\n".join(
            (
                (
                    REPO
                    / "skills"
                    / "cnki-paper"
                    / "scripts"
                    / "research_design.py"
                ).read_text(encoding="utf-8"),
                (
                    REPO
                    / "skills"
                    / "cnki-paper"
                    / "scripts"
                    / "research_design_v2.py"
                ).read_text(encoding="utf-8"),
                (
                    REPO
                    / "skills"
                    / "cnki-paper"
                    / "scripts"
                    / "research_design_v3.py"
                ).read_text(encoding="utf-8"),
                (
                    REPO
                    / "skills"
                    / "empirical-research"
                    / "scripts"
                    / "method_execution.py"
                ).read_text(encoding="utf-8"),
            )
        )
        section_ids = {
            section["id"]
            for chapter in self.coverage["chapters"]
            for section in chapter["sections"]
        }
        source_ids = {source["id"] for source in self.sources["sources"]}
        for rule in self.rules["hard_rules"]:
            self.assertIn(rule["code"], scripts)
            self.assertTrue(rule["objectively_checkable"])
            self.assertTrue(set(rule["textbook_basis"]) <= section_ids)
            self.assertTrue(set(rule["external_basis"]) <= source_ids)
            self.assertTrue(rule["external_basis"])
            if rule["basis_type"] != "contract-safety":
                self.assertTrue(rule["textbook_basis"])
        hard_text = " ".join(rule["risk"].casefold() for rule in self.rules["hard_rules"])
        for prohibited in ("fixed sample size", "fixed p-value", "fixed qca", "fixed theoretical saturation"):
            self.assertNotIn(prohibited, hard_text)

    def test_schema_assets_and_registry_are_version_locked(self) -> None:
        design_schema = json.loads(
            (
                REPO
                / "skills"
                / "cnki-paper"
                / "references"
                / "schemas"
                / "cnki-research-design-v4.schema.json"
            ).read_text(encoding="utf-8")
        )
        execution_schema = json.loads(
            (
                REPO
                / "skills"
                / "empirical-research"
                / "references"
                / "schemas"
                / "cnki-method-execution-v3.schema.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            "cnki-research-design/v4",
            design_schema["properties"]["schema_version"]["const"],
        )
        self.assertEqual(
            "cnki-method-execution/v3",
            execution_schema["properties"]["schema_version"]["const"],
        )
        self.assertEqual("5.1.0", self.registry["registry_version"])
        self.assertEqual("1.4.0", self.registry["answer_protocol_version"])
        for family in (
            "quantitative",
            "experiment",
            "case_study",
            "process_tracing",
            "qca",
            "discourse_analysis",
            "comparative",
            "historical",
            "grounded_theory",
            "review",
        ):
            with self.subTest(family=family):
                expected_versions = {
                    "quantitative": "2.0.0",
                    "experiment": "2.0.0",
                    "case_study": "1.1.1",
                    "process_tracing": "2.0.0",
                    "qca": "1.1.0",
                    "discourse_analysis": "1.2.0",
                    "comparative": "1.2.0",
                    "historical": "1.2.0",
                    "grounded_theory": "1.1.0",
                    "review": "1.2.0",
                }
                self.assertEqual(
                    expected_versions[family],
                    self.registry["families"][family]["adapter_version"],
                )
        for family, version in {
            "text_as_data": "2.0.0",
            "social_network": "2.0.0",
            "content_analysis": "1.1.0",
            "interpretive": "1.2.0",
        }.items():
            with self.subTest(family=family):
                self.assertEqual(version, self.registry["families"][family]["adapter_version"])
        for profile, specification in self.registry["method_contracts"].items():
            with self.subTest(profile=profile):
                self.assertTrue(
                    (REPO / "skills" / "empirical-research" / specification["asset"]).is_file()
                )
                self.assertTrue(specification["validator"])

    def test_blind_eval_packages_40_pairs_and_scores_three_isolated_reviews(self) -> None:
        tasks = {
            "schema_version": blind_eval.TASK_SCHEMA,
            "tasks": [
                {
                    "id": f"N{number:02d}",
                    "family": f"family-{number:02d}",
                    "prompt": f"Synthetic hidden task {number}",
                }
                for number in range(1, 21)
            ],
        }
        records = [
            {
                "task_id": f"N{number:02d}",
                "repeat": repeat,
                "output": ("bounded design response with evidence and inference " * 8)
                + f"{number}/{repeat}",
            }
            for number in range(1, 21)
            for repeat in (1, 2)
        ]
        candidate = {
            "schema_version": blind_eval.OUTPUT_SCHEMA,
            "outputs": [
                {
                    "task_id": record["task_id"],
                    "repeat": record["repeat"],
                    "text": record["output"],
                }
                for record in records
            ],
        }
        baseline = {
            "schema_version": blind_eval.OUTPUT_SCHEMA,
            "records": [
                {**record, "output": record["output"] + " baseline comparison"}
                for record in records
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            paths = {
                "tasks": base / "tasks.json",
                "candidate": base / "candidate.json",
                "baseline": base / "baseline.json",
                "package": base / "package.json",
                "decode": base / "decode.json",
            }
            for key in ("tasks", "candidate", "baseline"):
                paths[key].write_text(
                    json.dumps(locals()[key], ensure_ascii=False),
                    encoding="utf-8",
                )
            packed = blind_eval.pack(
                paths["tasks"],
                paths["baseline"],
                paths["candidate"],
                paths["package"],
                paths["decode"],
                seed=17,
            )
            self.assertEqual(40, packed["pair_count"])
            package = json.loads(paths["package"].read_text(encoding="utf-8"))
            decode = json.loads(paths["decode"].read_text(encoding="utf-8"))
            labels = {row["pair_id"]: row["candidate_label"] for row in decode["rows"]}

            reviews: list[Path] = []
            for reviewer_number in range(1, 4):
                review = {
                    "schema_version": blind_eval.REVIEW_SCHEMA,
                    "reviewer_id": f"R{reviewer_number}",
                    "isolation_declaration": {
                        field: False for field in blind_eval.FORBIDDEN_REVIEW_METADATA
                    },
                    "entries": [
                        {
                            "pair_id": pair["pair_id"],
                            "scores": {
                                label: {
                                    dimension: (
                                        3
                                        if label == labels[pair["pair_id"]]
                                        else (
                                            0
                                            if dimension
                                            in {
                                                "question_answer_match",
                                                "inference_calibration",
                                            }
                                            else 2
                                        )
                                    )
                                    for dimension in blind_eval.DIMENSIONS
                                }
                                for label in ("A", "B")
                            },
                            "preference": (
                                "tie"
                                if reviewer_number in {2, 3}
                                and pair["pair_id"] == package["pairs"][0]["pair_id"]
                                else labels[pair["pair_id"]]
                            ),
                            "findings": [
                                {
                                    "location": f"{labels[pair['pair_id']]}: paragraph {index}",
                                    "text": "The preferred output states a usable design boundary.",
                                }
                                for index in range(1, 4)
                            ],
                        }
                        for pair in package["pairs"]
                    ],
                }
                review_path = base / f"review-{reviewer_number}.json"
                review_path.write_text(
                    json.dumps(review, ensure_ascii=False),
                    encoding="utf-8",
                )
                reviews.append(review_path)

            summary = blind_eval.score(paths["package"], paths["decode"], reviews)
            self.assertEqual("PASS", summary["status"])
            self.assertEqual("plurality_non_tie", summary["preference_aggregation"])
            self.assertEqual(40, summary["counts"]["wins"])
            self.assertEqual(0, summary["counts"]["losses"])
            self.assertEqual([], summary["zero_score_events"])
            self.assertEqual(
                3.0,
                summary["score_averages"]["candidate"]["question_answer_match"],
            )
            self.assertEqual(
                0.0,
                summary["score_averages"]["baseline"]["question_answer_match"],
            )

            contaminated = json.loads(reviews[0].read_text(encoding="utf-8"))
            first_pair_id = package["pairs"][0]["pair_id"]
            first_candidate_label = labels[first_pair_id]
            contaminated["entries"][0]["scores"][first_candidate_label][
                "inference_calibration"
            ] = 0
            reviews[0].write_text(
                json.dumps(contaminated, ensure_ascii=False),
                encoding="utf-8",
            )
            failed = blind_eval.score(paths["package"], paths["decode"], reviews)
            self.assertEqual("FAIL", failed["status"])
            self.assertFalse(failed["checks"]["no_zero_question_or_inference_score"])


if __name__ == "__main__":
    unittest.main()
