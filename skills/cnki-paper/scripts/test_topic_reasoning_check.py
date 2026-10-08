#!/usr/bin/env python3
"""Regression tests for the topic induction-deduction gate."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent


def load_module():
    path = HERE / "topic_reasoning_check.py"
    spec = importlib.util.spec_from_file_location("topic_reasoning_check", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


topic = load_module()


def gap_contract(
    *,
    locus: str = "theory-explanation",
    obstruction: str = "inconsistent-or-incomparable",
) -> str:
    return (
        f"Status=corroborated；Primary Locus={locus}；Obstruction={obstruction}；"
        "Gap Claim=在相同制度压力下，现有理论仍不能区分资源约束何时改变项目选择机制；"
        "Evidence Basis=SYN-GAP-1 综合了支持、负例与可比性判断；"
        "Rival Explanations=已检查发表时滞、术语错配、相邻覆盖及仅因对象新而低命中；"
        "Research Responsibility=比较同一结果并检验两种解释的区分性预期；"
        "Withdrawal Condition=若差异完全由统计口径或不可比时期造成则撤回该空白"
    )


def ledger_rows() -> list[tuple[str, str, str, str, str]]:
    return [
        ("PE01", "practice-experience", "用户提供的地方项目选择材料显示相似压力下出现不同投资偏好。", "user-provided context", "用户本轮题面与本地材料路径"),
        ("ME01", "memory-experience", "记忆线索显示部分地方在考核压力下偏好大型可见项目。", "hypothesis-only", "model memory; unverified"),
        ("WE01", "web-experience", "某省公开预算与项目清单显示大型项目占比在考核期上升。", "traceable-context", "https://example.gov/data；某省政府；项目清单；2026-07-10"),
        ("MT01", "memory-theory", "激励理论认为考核指标会改变行动者资源配置。", "theory-candidate", "model memory; verify via CT01"),
        ("MT02", "memory-theory", "可见性理论认为行动者偏好容易展示绩效的政策工具。", "theory-candidate", "model memory; verify via CT02"),
        ("CT01", "cnki-theory", "知网文献将晋升激励与地方投资偏好联系起来并限定制度条件。", "verified-literature", "S01；CNKI detail；2026-07-10"),
        ("CT02", "cnki-theory", "知网文献讨论政策绩效可见性及其在项目选择中的作用。", "verified-literature", "S02；知网摘要；2026-07-10"),
    ]


def candidate_rows(count: int = 3) -> list[tuple[str, ...]]:
    rows = []
    for index in range(1, count + 1):
        rows.append(
            (
                f"O{index}",
                "PO-01",
                "解释相同制度压力下的异质选择，能够检验并修正激励必然产生同质反应的常识判断。",
                "PE01, ME01, WE01, MT01, CT01, MT02, CT02",
                "公开材料与记忆线索共同指向考核期大型可见项目增加，但部分地区并未出现该模式。",
                "先验上关注晋升激励与政策可见性，因此主动登记未出现大型项目偏好的负例。",
                "激励理论假定考核改变收益结构；可见性理论假定行动者重视可展示绩效。",
                "如果晋升考核更强调短期增长，则大型且可见项目的投资倾向将提高。",
                "考核权重上升后，大型项目立项和预算占比同步增加。",
                "考核权重上升但项目结构不变，或低权重地区同样大幅增加大型项目。",
                "经验负例与单一激励解释存在张力，提示资源约束或公众监督可能构成边界。",
                "保留激励机制，但修正为受财政资源与监督强度约束的条件性命题。",
                "S01、S02；CNKI detail/摘要；2026-07-10；同机制未被完全写尽。",
                "可取得跨地区考核文件、预算数据与项目清单，并形成跨期比较。",
                f"增长考核何以塑造地方大型项目投资偏好——基于条件性激励机制的研究{index}",
                "question-led；标题只压缩研究问题，不预断机制成立、结果方向或概念创新。",
                "在2012—2025年间，增长考核为何会在资源约束下塑造地方大型项目投资偏好？",
                "解释性",
                "O=地方政府项目选择；T=2012—2025年；I=地方公共投资；P=制度激励与政策可见性；R=强关系：增长考核在资源约束下通过可见性激励影响大型项目偏好",
                "只解释所观察制度和财政条件下的项目选择，不外推为所有地方政府的一般规律。",
                gap_contract(),
                "以地方项目选择为单一结果，以同类地方政策过程为分析单位；核心案例提供过程证据，对照案例提供反事实比较。",
            )
        )
    return rows


def write_cnki_registry(base: Path) -> None:
    registry = {
        "schema_version": "cnki-acquisition/v2",
        "publication_track": "cnki-cn",
        "queries": [
            {
                "query_id": "Q-COLLISION",
                "channel": "CNKI",
                "purpose": "collision",
                "query": "主题=增长考核 项目选择",
                "result_count": 12,
                "url": "https://kns.cnki.net/kns8s/search?kw=collision",
                "collected_at": "2026-07-10",
                "status": "complete",
            }
        ],
        "sources": [
            {
                "source_id": source_id,
                "channel": "CNKI",
                "roles": ["theory"],
                "title": f"Registered CNKI theory {source_id}",
                "url": f"https://kns.cnki.net/kcms2/article/abstract?id={source_id}",
                "state": "content-verified",
                "verification": {
                    "method": "abstract",
                    "verified_at": "2026-07-10",
                    "support_claim": "The registered CNKI abstract verifies a concrete theoretical mechanism and boundary condition.",
                },
            }
            for source_id in ("S01", "S02")
        ],
    }
    path = base / "reference_materials" / "literature_registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry), encoding="utf-8")


def write_international_registry(base: Path) -> None:
    registry = {
        "schema_version": "cnki-acquisition/v2",
        "publication_track": "international-ssci",
        "queries": [
            {
                "query_id": "Q-I-COLLISION",
                "channel": "OpenAlex",
                "purpose": "collision",
                "query": "promotion incentives visible investment choices",
                "result_count": 9,
                "url": "https://openalex.org/works/W1",
                "collected_at": "2026-08-14",
                "status": "complete",
            }
        ],
        "sources": [
            {
                "source_id": "INTL-S001",
                "channel": "publisher-official",
                "roles": ["theory"],
                "title": "Promotion Incentives and Visible Investment",
                "doi": "10.1162/isec_a_00499",
                "url": "https://direct.mit.edu/isec/article/49/1/1/000001",
                "state": "content-verified",
                "verification": {
                    "method": "full-text",
                    "verified_at": "2026-08-14",
                    "support_claim": "The registered publisher article verifies the theoretical mechanism and its institutional boundary.",
                    "content_url": "https://direct.mit.edu/isec/article-pdf/49/1/1/000001",
                },
            },
            {
                "source_id": "INTL-S002",
                "channel": "lawful-oa",
                "roles": ["theory"],
                "title": "Fiscal Constraints and Visibility Mechanisms",
                "doi": "10.1234/example.2026.001",
                "url": "https://repository.university.edu/articles/INTL-S002",
                "state": "content-verified",
                "verification": {
                    "method": "pdf",
                    "verified_at": "2026-08-14",
                    "support_claim": "The registered lawful repository copy verifies a competing explanation and observable implications.",
                    "content_url": "https://repository.university.edu/articles/INTL-S002.pdf",
                },
            },
        ],
    }
    path = base / "reference_materials" / "literature_registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry), encoding="utf-8")


def write_matrix(path: Path, ledger: list[tuple[str, ...]], candidates: list[tuple[str, ...]]) -> None:
    if not (path.parent / "reference_materials" / "literature_registry.json").exists():
        write_cnki_registry(path.parent)
    (path.parent / "problem_orientation.md").write_text(
        """# Problem Orientation

| Field | Content |
|---|---|
| Orientation ID | PO-01 |
| Practical encounter | 相似财政与考核压力下出现了不同项目投资选择。 |
| Affected actors | 地方决策者、公共服务使用者和承担财政风险的居民。 |
| Tension or unknown | 单一激励解释无法说明同一制度下的异质选择。 |
| Why it matters | 这关系到能否准确理解考核改革如何改变治理行为。 |
| Common-sense or imported frame at risk | 激励会自动产生一致政策反应的常识判断可能失效。 |
| What could change our mind | 若差异完全由统计口径造成，就撤回或改写当前定向。 |
| Origin | user-provided and practice-observation |
| Epistemic status | provisional user-provided context |
| Researcher position and access | 可接近公开预算材料，但缺少内部决策记录。 |
| Method/data role | feasibility-only；方法和数据服从问题。 |
| Confirmation source | 用户本轮题面。 |
""",
        encoding="utf-8",
    )
    (path.parent / "literature_analysis.json").write_text(
        json.dumps(
            {
                "schema_version": "cnki-literature-analysis/v2",
                "syntheses": [{"synthesis_id": "SYN-GAP-1"}],
            }
        ),
        encoding="utf-8",
    )
    lines = [
        "# Topic Induction-Deduction Matrix",
        "",
        "| Input ID | Source Layer | Content | Epistemic Status | Trace |",
        "|---|---|---|---|---|",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in ledger)
    lines.extend(
        [
            "",
            "| Option | Problem Orientation IDs | Problem Warrant | Input IDs | Inductive Pattern/Anomaly | Prior Lens Disclosed | Theory & Assumptions | Deductive Proposition | Confirming Observation | Disconfirming Observation | Empirical-Theory Tension | Iteration/Revision | CNKI Collision Trace | Data Feasibility | Provisional Title | Title Function / Claim Boundary | Provisional Research Question | Primary Question Type | O-T-I-P-R | Inference Boundary | Gap Reality Check | Outcome Unit & Comparison Design |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    lines.extend("| " + " | ".join(row) + " |" for row in candidates)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TopicReasoningTests(unittest.TestCase):
    def test_complete_inductive_deductive_loop_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topic_induction_deduction_matrix.md"
            write_matrix(path, ledger_rows(), candidate_rows())
            self.assertEqual([], topic.check_topic_reasoning(path))

    def test_international_track_uses_verified_international_theory_and_collision(self) -> None:
        ledger = [
            row
            for row in ledger_rows()
            if row[1] not in {"cnki-theory", "memory-theory"}
        ]
        ledger.extend(
            [
                (
                    "IT01",
                    "international-theory",
                    "International research links promotion incentives to visible investment choices under bounded institutional conditions.",
                    "verified-literature",
                    "INTL-S001；publisher full-text；https://publisher.example/a；2026-08-14",
                ),
                (
                    "IT02",
                    "international-theory",
                    "A competing international account explains when fiscal constraints interrupt the visibility mechanism.",
                    "verified-literature",
                    "10.1234/example.2026.001；lawful-OA PDF；https://repository.example/b；2026-08-14",
                ),
            ]
        )
        candidates = []
        for row in candidate_rows():
            updated = list(row)
            updated[3] = "PE01, ME01, WE01, IT01, IT02"
            updated[12] = (
                "OpenAlex and publisher collision search；https://openalex.org/works/W1；"
                "2026-08-14；the conditional mechanism remains unresolved."
            )
            updated[20] = gap_contract()
            candidates.append(tuple(updated))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topic_induction_deduction_matrix.md"
            (path.parent / "workflow_config.json").write_text(
                json.dumps({"publication_track": "international-ssci"}),
                encoding="utf-8",
            )
            write_international_registry(path.parent)
            write_matrix(path, ledger, candidates)
            self.assertEqual([], topic.check_topic_reasoning(path))

    def test_international_theory_and_collision_reject_unregistered_source_id(self) -> None:
        ledger = [
            row
            for row in ledger_rows()
            if row[1] not in {"cnki-theory", "memory-theory"}
        ]
        ledger.append(
            (
                "IT01",
                "international-theory",
                "An asserted international theory sentence has no registered source behind it.",
                "verified-literature",
                "INTL-S999；full-text；2026-08-14",
            )
        )
        candidates = []
        for row in candidate_rows():
            updated = list(row)
            updated[3] = "PE01, ME01, WE01, IT01"
            updated[12] = (
                "INTL-S999；collision search；2026-08-14；"
                "a conditional mechanism remains unresolved."
            )
            candidates.append(tuple(updated))
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "workflow_config.json").write_text(
                '{"publication_track":"international-ssci"}', encoding="utf-8"
            )
            write_international_registry(base)
            path = base / "topic_induction_deduction_matrix.md"
            write_matrix(path, ledger, candidates)
            issues = topic.check_topic_reasoning(path)
            self.assertTrue(any("does not resolve" in issue for issue in issues), issues)
            self.assertTrue(any("lacks a dated collision trace" in issue for issue in issues), issues)

    def test_cnki_theory_rejects_generic_web_trace_even_when_marked_verified(self) -> None:
        ledger = ledger_rows()
        first = list(ledger[5])
        first[4] = "https://example.org/blog-post；abstract；2026-08-14"
        ledger[5] = tuple(first)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topic_induction_deduction_matrix.md"
            write_matrix(path, ledger, candidate_rows())
            issues = topic.check_topic_reasoning(path)
            self.assertTrue(
                any("does not resolve to a content-verified registered CNKI source" in issue for issue in issues),
                issues,
            )

    def test_cnki_collision_rejects_unregistered_source_id(self) -> None:
        candidates = []
        for row in candidate_rows():
            updated = list(row)
            updated[12] = (
                "S999；collision search；2026-08-14；"
                "the conditional mechanism remains unresolved."
            )
            candidates.append(tuple(updated))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topic_induction_deduction_matrix.md"
            write_matrix(path, ledger_rows(), candidates)
            issues = topic.check_topic_reasoning(path)
            self.assertTrue(any("lacks a dated collision trace" in issue for issue in issues), issues)

    def test_international_theory_rejects_a_generic_web_url_as_scholarly_identity(self) -> None:
        ledger = [
            row
            for row in ledger_rows()
            if row[1] not in {"cnki-theory", "memory-theory"}
        ]
        ledger.append(
            (
                "IT01",
                "international-theory",
                "A generic page repeats a theoretical claim without a scholarly publication identity.",
                "verified-literature",
                "https://example.com/article；full-text；2026-08-14",
            )
        )
        candidates = []
        for row in candidate_rows():
            updated = list(row)
            updated[3] = "PE01, ME01, WE01, IT01"
            updated[12] = "OpenAlex W12345 collision search；2026-08-14；mechanism boundary unresolved."
            candidates.append(tuple(updated))
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "workflow_config.json").write_text(
                '{"publication_track":"international-ssci"}', encoding="utf-8"
            )
            write_international_registry(base)
            path = base / "topic_induction_deduction_matrix.md"
            write_matrix(path, ledger, candidates)
            issues = topic.check_topic_reasoning(path)
            self.assertTrue(
                any("international theory lacks a DOI/publisher" in issue for issue in issues)
            )

    def test_international_collision_rejects_a_generic_dated_web_search(self) -> None:
        ledger = [
            row
            for row in ledger_rows()
            if row[1] not in {"cnki-theory", "memory-theory"}
        ]
        ledger.append(
            (
                "IT01",
                "international-theory",
                "Publisher research verifies a bounded international mechanism and its assumptions.",
                "verified-literature",
                "INTL-S001；publisher full-text；https://publisher.example/a；2026-08-14",
            )
        )
        candidates = []
        for row in candidate_rows():
            updated = list(row)
            updated[3] = "PE01, ME01, WE01, IT01"
            updated[12] = "international web search；https://example.com/results；2026-08-14"
            candidates.append(tuple(updated))
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "workflow_config.json").write_text(
                '{"publication_track":"international-ssci"}', encoding="utf-8"
            )
            write_international_registry(base)
            path = base / "topic_induction_deduction_matrix.md"
            write_matrix(path, ledger, candidates)
            issues = topic.check_topic_reasoning(path)
            self.assertTrue(any("lacks a dated collision trace" in issue for issue in issues))

    def test_international_track_does_not_accept_cnki_anchor_as_its_only_theory_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topic_induction_deduction_matrix.md"
            (path.parent / "workflow_config.json").write_text(
                json.dumps({"publication_track": "international-ssci"}),
                encoding="utf-8",
            )
            write_matrix(path, ledger_rows(), candidate_rows())
            issues = topic.check_topic_reasoning(path)
            self.assertTrue(
                any("international theory anchor" in issue for issue in issues), issues
            )

    def test_candidate_count_is_evidence_driven_without_a_fixed_quota(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topic_induction_deduction_matrix.md"
            for count in (1, 2, 7):
                with self.subTest(count=count):
                    write_matrix(path, ledger_rows(), candidate_rows(count))
                    self.assertEqual([], topic.check_topic_reasoning(path))

    def test_zero_usable_candidates_still_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topic_induction_deduction_matrix.md"
            write_matrix(path, ledger_rows(), [])
            issues = topic.check_topic_reasoning(path)
            self.assertTrue(any("no usable candidate" in issue for issue in issues))

    def test_memory_experience_cannot_be_marked_verified_fact(self) -> None:
        ledger = ledger_rows()
        row = ledger[1]
        ledger[1] = (row[0], row[1], row[2], "verified fact", row[4])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topic_induction_deduction_matrix.md"
            write_matrix(path, ledger, candidate_rows())
            issues = topic.check_topic_reasoning(path)
            self.assertTrue(any("memory experience must remain" in issue for issue in issues))

    def test_model_memory_is_optional_when_grounded_anchors_exist(self) -> None:
        candidates = candidate_rows()
        candidates = [tuple([*row[:3], "PE01, WE01, CT01", *row[4:]]) for row in candidates]
        ledger = [row for row in ledger_rows() if row[1] not in {"memory-experience", "memory-theory"}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topic_induction_deduction_matrix.md"
            write_matrix(path, ledger, candidates)
            self.assertEqual([], topic.check_topic_reasoning(path))

    def test_memory_only_candidate_cannot_replace_grounded_experience_and_verified_theory(self) -> None:
        candidates = candidate_rows()
        first = list(candidates[0])
        first[3] = "ME01, MT01, MT02"
        candidates[0] = tuple(first)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topic_induction_deduction_matrix.md"
            write_matrix(path, ledger_rows(), candidates)
            issues = topic.check_topic_reasoning(path)
            self.assertTrue(any("no traceable practice/web" in issue for issue in issues))
            self.assertTrue(any("no content-verified CNKI theory" in issue for issue in issues))

    def test_candidate_must_retain_problem_orientation_identity(self) -> None:
        candidates = candidate_rows()
        first = list(candidates[0])
        first[1] = "PO-99"
        candidates[0] = tuple(first)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topic_induction_deduction_matrix.md"
            write_matrix(path, ledger_rows(), candidates)
            issues = topic.check_topic_reasoning(path)
            self.assertTrue(any("unknown problem orientations" in issue for issue in issues))

    def test_support_and_falsification_cannot_be_identical(self) -> None:
        candidates = candidate_rows()
        first = list(candidates[0])
        first[9] = first[8]
        candidates[0] = tuple(first)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topic_induction_deduction_matrix.md"
            write_matrix(path, ledger_rows(), candidates)
            issues = topic.check_topic_reasoning(path)
            self.assertTrue(any("same observation" in issue for issue in issues))

    def test_object_novelty_or_few_papers_is_not_a_true_gap(self) -> None:
        candidates = candidate_rows()
        first = list(candidates[0])
        first[20] = "以这个新机构为主题的论文数量很少，因此属于鲜有研究的空白。"
        candidates[0] = tuple(first)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topic_induction_deduction_matrix.md"
            write_matrix(path, ledger_rows(), candidates)
            issues = topic.check_topic_reasoning(path)
            self.assertTrue(any("missing field" in issue for issue in issues), issues)

    def test_all_seven_labels_without_evidence_cannot_game_the_gap_gate(self) -> None:
        candidates = candidate_rows()
        first = list(candidates[0])
        first[20] = (
            "知识、概念、理论、实证、方法、群体和实践空白全部存在；"
            "并且已经排除发表时滞、术语错配和低贡献。"
        )
        candidates[0] = tuple(first)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topic_induction_deduction_matrix.md"
            write_matrix(path, ledger_rows(), candidates)
            issues = topic.check_topic_reasoning(path)
            self.assertTrue(any("missing field" in issue for issue in issues), issues)

    def test_gap_must_link_a_current_synthesis_identity(self) -> None:
        candidates = candidate_rows()
        first = list(candidates[0])
        first[20] = gap_contract().replace("SYN-GAP-1", "SYN-INVENTED")
        candidates[0] = tuple(first)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topic_induction_deduction_matrix.md"
            write_matrix(path, ledger_rows(), candidates)
            issues = topic.check_topic_reasoning(path)
            self.assertTrue(any("unknown synthesis identities" in issue for issue in issues), issues)

    def test_some_versus_some_question_requires_comparative_design(self) -> None:
        candidates = candidate_rows()
        first = list(candidates[0])
        first[16] = "为什么有些治理倡议停留在平台，有些跨越为国际组织？"
        first[21] = "以组织创设为单一结果，以世界人工智能合作组织为一个案例进行过程追踪。"
        candidates[0] = tuple(first)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topic_induction_deduction_matrix.md"
            write_matrix(path, ledger_rows(), candidates)
            issues = topic.check_topic_reasoning(path)
            self.assertTrue(any("without a comparative design" in issue for issue in issues))

    def test_explanatory_question_requires_strong_relation(self) -> None:
        candidates = candidate_rows()
        first = list(candidates[0])
        first[18] = "O=地方政府项目选择；T=2012—2025年；I=地方公共投资；P=制度激励；R=弱关系：只描述项目偏好"
        candidates[0] = tuple(first)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topic_induction_deduction_matrix.md"
            write_matrix(path, ledger_rows(), candidates)
            issues = topic.check_topic_reasoning(path)
            self.assertTrue(any("without a strong relation" in issue for issue in issues))

    def test_otipr_requires_all_five_elements(self) -> None:
        candidates = candidate_rows()
        first = list(candidates[0])
        first[18] = "O=地方政府项目选择；T=2012—2025年；I=地方公共投资；R=强关系：增长考核影响项目偏好"
        candidates[0] = tuple(first)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topic_induction_deduction_matrix.md"
            write_matrix(path, ledger_rows(), candidates)
            issues = topic.check_topic_reasoning(path)
            self.assertTrue(any("lacks a substantive perspective" in issue for issue in issues))

    def test_descriptive_weak_relation_does_not_require_a_fake_outcome(self) -> None:
        candidates = candidate_rows()
        first = list(candidates[0])
        first[16] = "2012—2025年地方大型项目选择呈现怎样的结构与演变特征？"
        first[17] = "描述性"
        first[18] = "O=地方政府项目选择；T=2012—2025年；I=地方公共投资；P=公共管理的制度分类；R=弱关系：还原项目选择的结构与演变"
        first[21] = "以地方项目选择为还原对象和分析单位，按统一分类规则做跨地区、跨时段比较。"
        candidates[0] = tuple(first)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topic_induction_deduction_matrix.md"
            write_matrix(path, ledger_rows(), candidates)
            issues = topic.check_topic_reasoning(path)
            self.assertFalse(any("does not define one common outcome" in issue for issue in issues))
            self.assertFalse(any("without a strong relation" in issue for issue in issues))

    def test_pre_evidence_title_cannot_be_result_led(self) -> None:
        candidates = candidate_rows()
        first = list(candidates[0])
        first[15] = "result-led；标题先宣布财政约束机制已经得到证实。"
        candidates[0] = tuple(first)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topic_induction_deduction_matrix.md"
            write_matrix(path, ledger_rows(), candidates)
            issues = topic.check_topic_reasoning(path)
            self.assertTrue(any("before evidence exists" in issue for issue in issues))

    def test_pre_evidence_title_must_state_claim_boundary(self) -> None:
        candidates = candidate_rows()
        first = list(candidates[0])
        first[15] = "question-led；标题突出研究吸引力。"
        candidates[0] = tuple(first)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topic_induction_deduction_matrix.md"
            write_matrix(path, ledger_rows(), candidates)
            issues = topic.check_topic_reasoning(path)
            self.assertTrue(any("claim boundary" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
