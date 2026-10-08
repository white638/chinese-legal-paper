"""Tests for the pairwise taste judge (emit, collect, probes, validation)."""

from __future__ import annotations

import json
import copy
import io
from contextlib import redirect_stdout
import tempfile
import unittest
from pathlib import Path

import taste_cards
import taste_judge

MODEL = "test-judge-model"


def _candidate(candidate_id: str, question: str, contribution: str, maturity: str = "screened") -> dict:
    return {
        "id": candidate_id,
        "topic_option_id": candidate_id.replace("CAND-", "O"),
        "status": "alternate",
        "provisional_title": f"{candidate_id} 的工作标题",
        "orientation_ids": ["PO-01"],
        "focus_rationale": "测试候选",
        "maturity": maturity,
        "candidate_family": f"{candidate_id} 家族",
        "research_question": question,
        "potential_contribution": contribution,
        "question_versions": [],
        "active_question_version_id": None,
    }


def write_workspace(base: Path, *, field: str = "比较政治") -> None:
    (base / "workflow_config.json").write_text(
        json.dumps(
            {
                "task_profile": "topic_selection",
                "direction_contract": {"field": field},
                "topic_selection": {
                    "origin_mode": "direction_first",
                    "brainstorm_depth": "broad",
                    "workspace_policy": "quarantine_until_divergence",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (base / "research_decision.json").write_text(
        json.dumps(
            {
                "candidates": [
                    _candidate(
                        "CAND-01",
                        "在全球南方国家，为何同类反腐机构在某些国家强化了威权韧性而在另一些国家削弱了它？",
                        "识别反腐机构改变威权韧性的范围条件，并给出条件两侧的反面观察。",
                    ),
                    _candidate(
                        "CAND-02",
                        "地方立法机关的议程设置权在何种财政条件下会实际约束行政部门？",
                        "提出财政依赖度作为议程约束的机制条件。",
                    ),
                    _candidate("CAND-03", "已撤回的问题", "无", maturity="seed"),
                    {**_candidate("CAND-04", "撤回", "撤回"), "status": "withdrawn"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def write_packet(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "literature_reconnaissance": [
                    {
                        "query": "威权韧性 反腐",
                        "source": "cnki",
                        "title": "反腐运动与威权体制的自我修复",
                        "year": 2023,
                        "claim": "反腐运动通过更换地方精英提高了体制的短期稳定，但没有改变长期的合法性来源。",
                        "identifier": "https://example.org/cnki/1",
                    },
                    {
                        "query": "legislature agenda",
                        "source": "openalex",
                        "title": "Fiscal dependence and legislative agenda control",
                        "year": 2022,
                        "claim": "Provinces that depend on central transfers show weaker legislative agenda control over budgets.",
                        "identifier": "10.1000/agenda.2022",
                    },
                    {
                        "query": "state capacity",
                        "source": "openalex",
                        "title": "State capacity as information",
                        "year": 2024,
                        "claim": "States that collect finer-grained information about local conditions tax more effectively.",
                        "identifier": "10.1000/info.2024",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def proposal_provenance() -> dict:
    """Synthetic declaration for contract tests, not a real original proposal."""
    return {
        "source_id": "SYN-PROPOSAL-01",
        "locator": "synthetic-fixture:original-proposal",
        "recorded_at": "2026-09-01T00:00:00Z",
        "verification_basis": "SYNTHETIC fixture: the declared proposal text was inspected for this contract test.",
        "permission_basis": "SYNTHETIC fixture created locally for automated testing and authorized for reuse.",
        "information_basis": "SYNTHETIC fixture uses the same proposal fields and evidence budget as its candidate.",
    }


def write_proposals(path: Path) -> None:
    path.write_text(json.dumps([
        {
            "identifier": f"SYN-PROPOSAL-{index:02d}",
            "title": f"SYNTHETIC proposal fixture {index}",
            "claim": "Synthetic expected knowledge update, not an actual research finding.",
            "comparison_view": {
                "maturity": "proposal",
                "origin": "contemporaneous",
                "question": f"SYNTHETIC: when does allocation rule {index} change recorded compliance?",
                "update": "Separate compliance and recording explanations under comparable information conditions.",
                "provenance": {**proposal_provenance(), "source_id": f"SYN-PROPOSAL-{index:02d}"},
            },
        }
        for index in (1, 2)
    ], ensure_ascii=False), encoding="utf-8")


def teaching_exemplar(identifier: str = "SYN-MOVE-01", *, level: str = "synthetic") -> dict:
    """Explicitly invented teaching content for structure and boundary regressions."""
    content = "SYNTHETIC: a fictional recording index mixes rule compliance with inspection frequency; disaggregation separates the two processes."
    return {
        "identifier": identifier,
        "title": "SYNTHETIC measurement distinction for contract testing",
        "why": "Historical selection wording; this field is not a verified teaching breakdown.",
        "research_move": {
            "schema_version": taste_cards.RESEARCH_MOVE_SCHEMA,
            "version": "synthetic-fixture-v1",
            "source": {
                "identifier": identifier,
                "level": level,
                "origin": "synthetic" if level == "synthetic" else "published_result",
                "content": content,
                "content_sha256": taste_judge.sha256_text(content),
                "locator": "synthetic-fixture:measurement-distinction",
                "verification": {"status": "content-verified", "basis": "SYNTHETIC fixture content checked against its locally constructed text."},
                "permission": {"status": "permitted", "basis": "SYNTHETIC fixture authored for local regression tests with reuse permitted."},
            },
            "prior_understanding": "SYNTHETIC baseline treats the mixed index as a single behavior.",
            "move": "SYNTHETIC move separates compliance from the process that records compliance.",
            "support": {"basis": "synthetic" if level == "synthetic" else "author_claim", "text": "SYNTHETIC source describes how the components represent distinct processes."},
            "without_move": {"kind": "synthetic_ablation", "text": "SYNTHETIC ablation merges the components and loses the distinction between behavior and recording."},
            "limits": "SYNTHETIC teaching example only; it establishes no empirical finding or publication history.",
        },
    }


def _assessment_fixture(pair_ids: list[str], preferred: str, *, risk: str = "low") -> dict:
    return {
        "pairs": [
            {
                "pair_id": pair_id,
                "preferred": preferred,
                "reader_default_changed": "读者不再默认反腐机构必然强化威权体制。",
                "rationale": "候选提出了条件两侧的反面观察，厚味与趣味俱在。",
            }
            for pair_id in pair_ids
        ],
        "flavors": {"clear": "present", "thick": "present", "elegant": "unclear", "interesting": "present"},
        "flavor_evidence": {
            "clear": "问题来自机制失效的反常案例",
            "thick": "给出范围条件与反面观察",
            "elegant": "变量数尚未可见",
            "interesting": "同类机构相反结果",
        },
        "mediocrity_risk": risk,
        "mediocrity_path": "只换国家不论证条件，退化成多国描述并列。",
        "best_case_paper": "以最不可能案例识别反腐机构改变威权韧性的条件。",
        "smell_hits": [],
    }


def _response(pair_ids, preferred, *, risk="low"):
    import copy
    fixture = _assessment_fixture(pair_ids, preferred, risk=risk)
    analysis = {key: value for key, value in fixture.items() if key != "pairs"}
    return {"pairs": [{**pair, "one_analysis": copy.deepcopy(analysis), "two_analysis": copy.deepcopy(analysis)} for pair in fixture["pairs"]]}


def answer_prompts(directory: Path, chooser, *, context_prefix: str) -> list[str]:
    """Answer every emitted prompt in one capture directory with a fake isolated subagent."""

    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    plan_file = next(directory.glob(f"*.{taste_judge.PLAN_NAME}"))
    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    prefix = f"taste-{plan['variant']}-"
    steps = []
    for step, entry in manifest["steps"].items():
        candidate_id = step[len(prefix):]
        item = next(entry for entry in plan["items"] if entry["candidate_id"] == candidate_id)
        payload = chooser(item)
        (directory / entry["response_path"]).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        (directory / entry["context_path"]).write_text(f"{context_prefix}-{step}", encoding="utf-8")
        steps.append(step)
    return steps


def prefer_candidate(item: dict) -> dict:
    """Answer so the candidate wins every pair regardless of its shuffled position."""

    pairs = item["pairs"]
    payload = _response([pair["pair_id"] for pair in pairs], "one")
    for entry, pair in zip(payload["pairs"], pairs):
        entry["preferred"] = pair["candidate_position"] if pair["comparable"] else "not_comparable"
    return payload


def prefer_reference(item: dict) -> dict:
    pairs = item["pairs"]
    payload = _response([pair["pair_id"] for pair in pairs], "two", risk="high")
    for entry, pair in zip(payload["pairs"], pairs):
        entry["preferred"] = ("two" if pair["candidate_position"] == "one" else "one") if pair["comparable"] else "not_comparable"
    return payload


class PlanTests(unittest.TestCase):
    def test_pair_positions_are_deterministic_and_mixed(self) -> None:
        positions = {taste_judge.pair_position(f"CAND-{i:02d}", "REF-01") for i in range(40)}
        self.assertEqual({"one", "two"}, positions)
        self.assertEqual(taste_judge.pair_position("CAND-01", "REF-01"), taste_judge.pair_position("CAND-01", "REF-01"))

    def test_hot_strip_replaces_registered_terms_longest_first(self) -> None:
        registry = taste_cards.load_registry()
        card = taste_cards.card_by_slug(registry, "international-politics")
        text, replaced = taste_judge.strip_hot_terms(
            "在百年未有之大变局下，一带一路与中美关系如何互动？", taste_cards.hot_terms_for(registry, card)
        )
        self.assertNotIn("一带一路", text)
        self.assertIn(taste_judge.HOT_PLACEHOLDER, text)
        self.assertEqual({"百年未有之大变局", "一带一路", "中美关系"}, set(replaced))

    def test_reference_selection_is_shared_deterministic_and_pinnable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_workspace(base)
            packet = base / "packet.json"
            write_packet(packet)
            origin, pool = taste_judge.load_reference_pool(base, packet=packet)
            self.assertEqual("packet", origin)
            first = taste_judge.select_references(pool, count=2)
            second = taste_judge.select_references(pool, count=2)
            self.assertEqual(first, second)
            pinned = taste_judge.select_references(pool, count=2, pinned=["10.1000/info.2024"])
            self.assertEqual("10.1000/info.2024", pinned[0]["identifier"])
            self.assertEqual("REF-01", pinned[0]["ref_id"])
            with self.assertRaises(ValueError):
                taste_judge.select_references(pool, count=2, pinned=["missing"])

    def test_workspace_without_card_keeps_judge_off(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_workspace(base, field="政治学")
            packet = base / "packet.json"
            write_packet(packet)
            code = taste_judge.main(
                ["emit", str(base), "--model-revision", MODEL, "--packet", str(packet), "--out", str(base / "cap")]
            )
            self.assertEqual(1, code)
            self.assertFalse((base / "cap").exists())


class RoundTripTests(unittest.TestCase):
    def _emit(self, base: Path, packet: Path, variant: str = "base", extra: list[str] | None = None) -> Path:
        out = base / "capture"
        argv = [
            "emit",
            str(base),
            "--model-revision",
            MODEL,
            "--references",
            str(packet),
            "--out",
            str(out),
            "--variant",
            variant,
        ] + (extra or [])
        self.assertEqual(0, taste_judge.main(argv))
        return out

    def test_emit_collect_retains_opinions_and_unshuffles_positions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_workspace(base)
            packet = base / "packet.json"
            write_proposals(packet)
            out = self._emit(base, packet)
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual({"taste-base-CAND-01", "taste-base-CAND-02"}, set(manifest["steps"]))
            prompt = (out / "taste-base-CAND-01.prompt.md").read_text(encoding="utf-8")
            self.assertNotIn("CAND-01", prompt.split("SHA-256")[1])
            self.assertNotIn("https://example.org/cnki/1", prompt)
            self.assertNotIn("openalex", prompt)
            self.assertIn("清味", prompt)
            self.assertIn("【文本一】", prompt)

            def chooser(item: dict) -> dict:
                return prefer_candidate(item) if item["candidate_id"] == "CAND-01" else prefer_reference(item)

            answer_prompts(out, chooser, context_prefix="ctx")
            self.assertEqual(
                0,
                taste_judge.main(
                    ["collect", str(base), "--model-revision", MODEL, "--references", str(packet), "--responses", str(out), "--write"]
                ),
            )
            judgement = json.loads((base / taste_judge.JUDGEMENT_JSON).read_text(encoding="utf-8"))
            self.assertEqual(taste_judge.SCHEMA_VERSION, judgement["schema_version"])
            self.assertEqual("signal-not-gate", judgement["authority"])
            self.assertEqual("comparative-politics", judgement["card_slug"])
            self.assertEqual([], judgement["ranking"])
            by_id = {item["candidate_id"]: item for item in judgement["judgements"]}
            self.assertEqual(2.0, by_id["CAND-01"]["wins"])
            self.assertEqual(0.0, by_id["CAND-02"]["wins"])
            self.assertTrue(all(pair["preferred"] == "candidate" for pair in by_id["CAND-01"]["pairs"]))
            self.assertTrue(all(pair["preferred"] == "reference" for pair in by_id["CAND-02"]["pairs"]))
            self.assertNotEqual(by_id["CAND-01"]["context_id"], by_id["CAND-02"]["context_id"])
            markdown = (base / taste_judge.JUDGEMENT_MD).read_text(encoding="utf-8")
            self.assertIn("signal-not-gate", markdown)
            self.assertIn("### CAND-01", markdown)
            self.assertEqual(0, taste_judge.main(["validate", str(base)]))

    def test_reused_context_or_bad_response_fails_collect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_workspace(base)
            packet = base / "packet.json"
            write_proposals(packet)
            out = self._emit(base, packet)
            answer_prompts(out, prefer_candidate, context_prefix="same")
            for path in out.glob("*.context.txt"):
                path.write_text("same-context", encoding="utf-8")
            self.assertEqual(
                1,
                taste_judge.main(
                    ["collect", str(base), "--model-revision", MODEL, "--references", str(packet), "--responses", str(out)]
                ),
            )
            answer_prompts(out, prefer_candidate, context_prefix="fresh")
            bad = json.loads((out / "taste-base-CAND-01.response.json").read_text(encoding="utf-8"))
            bad["pairs"][0]["preferred"] = "three"
            (out / "taste-base-CAND-01.response.json").write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(
                1,
                taste_judge.main(
                    ["collect", str(base), "--model-revision", MODEL, "--references", str(packet), "--responses", str(out)]
                ),
            )

    def test_hot_strip_does_not_treat_abstention_as_style_bias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_workspace(base)
            packet = base / "packet.json"
            write_proposals(packet)
            out = self._emit(base, packet)
            answer_prompts(out, prefer_candidate, context_prefix="base")
            probe_dir = base / "probe"
            argv = [
                "emit",
                str(base),
                "--model-revision",
                MODEL,
                "--references",
                str(packet),
                "--out",
                str(probe_dir),
                "--variant",
                "hot-strip",
            ]
            self.assertEqual(0, taste_judge.main(argv))
            probe_manifest = json.loads((probe_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual({"taste-hot-strip-CAND-01"}, set(probe_manifest["steps"]))
            probe_prompt = (probe_dir / "taste-hot-strip-CAND-01.prompt.md").read_text(encoding="utf-8")
            self.assertIn(taste_judge.HOT_PLACEHOLDER, probe_prompt)
            self.assertNotIn("全球南方", probe_prompt.split("SHA-256")[1])
            answer_prompts(probe_dir, lambda item: _response([pair["pair_id"] for pair in item["pairs"]], "uncertain"), context_prefix="probe")
            self.assertEqual(
                0,
                taste_judge.main(
                    [
                        "collect",
                        str(base),
                        "--model-revision",
                        MODEL,
                        "--references",
                        str(packet),
                        "--responses",
                        str(out),
                        "--probe",
                        "hot-strip",
                        str(probe_dir),
                        "--write",
                    ]
                ),
            )
            judgement = json.loads((base / taste_judge.JUDGEMENT_JSON).read_text(encoding="utf-8"))
            probe = judgement["probes"]["hot-strip"]
            self.assertEqual(0, probe["pairs_compared"])
            self.assertEqual(0, probe["flips"])
            self.assertEqual(0.0, probe["flip_rate"])
            self.assertFalse(probe["shortcut_suspected"])
            self.assertEqual(["全球南方"], probe["candidates"][0]["replaced_terms"])
            self.assertEqual(0, taste_judge.main(["validate", str(base)]))
            judgement["probes"]["hot-strip"]["flip_rate"] = 1.0
            (base / taste_judge.JUDGEMENT_JSON).write_text(json.dumps(judgement, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(1, taste_judge.main(["validate", str(base)]))

    def test_plain_rewrite_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_workspace(base)
            packet = base / "packet.json"
            write_proposals(packet)
            rewrite_dir = base / "rewrite"
            self.assertEqual(
                0,
                taste_judge.main(
                    ["emit-rewrite", str(base), "--model-revision", MODEL, "--references", str(packet), "--out", str(rewrite_dir)]
                ),
            )
            rewrite_prompt = (rewrite_dir / "taste-rewrite.prompt.md").read_text(encoding="utf-8")
            self.assertIn("CAND-01", rewrite_prompt)
            rewritten = {
                "CAND-01": {
                    "research_question": "同类反腐机构为何在有的国家巩固政权、在有的国家削弱政权？",
                    "potential_contribution": "说明反腐机构效果取决于哪些条件，并给出反例。",
                },
                "CAND-02": {
                    "research_question": "地方人大何时能真正约束政府预算？",
                    "potential_contribution": "把财政依赖度作为约束条件。",
                },
            }
            rewritten_path = rewrite_dir / "taste-rewrite.response.json"
            rewritten_path.write_text(json.dumps(rewritten, ensure_ascii=False), encoding="utf-8")
            out = self._emit(base, packet)
            answer_prompts(out, prefer_candidate, context_prefix="base")
            probe_dir = base / "plain"
            self.assertEqual(
                0,
                taste_judge.main(
                    [
                        "emit",
                        str(base),
                        "--model-revision",
                        MODEL,
                        "--references",
                        str(packet),
                        "--out",
                        str(probe_dir),
                        "--variant",
                        "plain-rewrite",
                        "--rewritten",
                        str(rewritten_path),
                    ]
                ),
            )
            self.assertIn("同类反腐机构为何", (probe_dir / "taste-plain-rewrite-CAND-01.prompt.md").read_text(encoding="utf-8"))
            answer_prompts(probe_dir, prefer_candidate, context_prefix="plain")
            self.assertEqual(
                0,
                taste_judge.main(
                    [
                        "collect",
                        str(base),
                        "--model-revision",
                        MODEL,
                        "--references",
                        str(packet),
                        "--responses",
                        str(out),
                        "--probe",
                        "plain-rewrite",
                        str(probe_dir),
                        "--rewritten",
                        str(rewritten_path),
                        "--write",
                    ]
                ),
            )
            judgement = json.loads((base / taste_judge.JUDGEMENT_JSON).read_text(encoding="utf-8"))
            probe = judgement["probes"]["plain-rewrite"]
            self.assertEqual(4, probe["pairs_compared"])
            self.assertEqual(0, probe["flips"])
            self.assertFalse(probe["shortcut_suspected"])


class TeachingProjectionTests(unittest.TestCase):
    def setUp(self):
        self.card = copy.deepcopy(taste_cards.card_by_slug(taste_cards.load_registry(), "comparative-politics"))
        self.card["exemplars"] = {"positive": [teaching_exemplar(f"SYN-MOVE-{index:02d}") for index in range(4)], "negative": []}

    def test_teaching_is_optional_bounded_and_has_no_selection_quota(self):
        self.assertEqual([], taste_cards.teaching_projection(self.card)["examples"])
        self.assertEqual([], taste_cards.teaching_projection(self.card, enabled=True, limit=0)["examples"])
        self.assertEqual(2, len(taste_cards.teaching_projection(self.card, enabled=True)["examples"]))
        self.assertEqual(3, len(taste_cards.teaching_projection(self.card, enabled=True, limit=3)["examples"]))
        with self.assertRaises(ValueError):
            taste_cards.teaching_projection(self.card, enabled=True, limit=4)
        self.card["exemplars"] = {"positive": [teaching_exemplar()], "negative": []}
        self.assertEqual(1, len(taste_cards.teaching_projection(self.card, enabled=True)["examples"]))
        self.assertEqual("exemplars-registered", taste_cards.card_status(self.card))
        self.assertEqual("legacy-unreviewed", taste_cards.exemplar_calibration_status(self.card))

    def test_historical_praise_is_excluded_without_becoming_a_failure_gate(self):
        entry = teaching_exemplar()
        del entry["research_move"]
        self.card["exemplars"] = {"positive": [entry], "negative": []}
        projection = taste_cards.teaching_projection(self.card, enabled=True)
        self.assertEqual([], projection["examples"])
        self.assertEqual(["research_move_missing"], projection["excluded"][0]["reasons"])
        self.assertEqual([], taste_cards.teaching_projection(self.card)["excluded"])

    def test_abstract_can_only_support_author_claims(self):
        entry = teaching_exemplar(level="abstract")
        self.assertEqual([], taste_cards.research_move_issues(entry))
        entry["research_move"]["support"]["basis"] = "inspected_argument"
        self.assertIn("support_exceeds_source_level", taste_cards.research_move_issues(entry))
        entry["research_move"]["source"]["level"] = "metadata"
        self.assertIn("source_level_insufficient", taste_cards.research_move_issues(entry))

    def test_missing_verification_permission_hash_and_synthetic_label_are_rejected(self):
        changes = (
            (lambda e: e["research_move"]["source"]["verification"].update(status="metadata-only"), "source_verification_missing"),
            (lambda e: e["research_move"]["source"]["permission"].update(status="unknown"), "source_permission_missing"),
            (lambda e: e["research_move"]["source"].update(content="Edited source text without updating its original recorded source hash."), "source_content_hash_mismatch"),
            (lambda e: e["research_move"]["source"].update(identifier="another-source"), "source_identity_mismatch"),
            (lambda e: e["research_move"].update(version=""), "research_move_version_missing"),
            (lambda e: e["research_move"]["without_move"].update(kind="actual_result"), "ablation_must_be_synthetic"),
        )
        for mutate, expected in changes:
            with self.subTest(expected=expected):
                entry = teaching_exemplar()
                mutate(entry)
                self.assertIn(expected, taste_cards.research_move_issues(entry))

    def test_projection_has_bounded_fields_and_does_not_copy_extra_material(self):
        entry = self.card["exemplars"]["positive"][0]
        entry["research_move"]["source"]["unrequested_content"] = "PRIVATE_CANARY"
        entry["research_move"]["support"]["unrequested_content"] = "PRIVATE_CANARY"
        projected = taste_cards.teaching_projection(self.card, enabled=True, limit=1)
        self.assertNotIn("PRIVATE_CANARY", taste_judge.canonical_json(projected))
        entry["research_move"]["move"] = "x" * (taste_cards.MAX_MOVE_FIELD_CHARS + 1)
        self.assertIn("move_outside_budget", taste_cards.research_move_issues(entry))

    def test_shipped_teaching_records_retain_abstract_scope_and_valid_snapshots(self):
        records = [entry for card in taste_cards.cards(taste_cards.load_registry()) for role in ("positive", "negative") for entry in card["exemplars"][role] if entry.get("research_move")]
        self.assertGreaterEqual(len(records), 2)
        for entry in records:
            self.assertEqual([], taste_cards.research_move_issues(entry))
            self.assertEqual("abstract", entry["research_move"]["source"]["level"])
            self.assertEqual("author_claim", entry["research_move"]["support"]["basis"])


class PreflightAndBindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        write_workspace(self.base)
        self.references = self.base / "references.json"
        write_proposals(self.references)
        self.registry_path = self.base / "cards.json"
        self.registry = taste_cards.load_registry()
        self.card = next(c for c in self.registry["cards"] if c["slug"] == "comparative-politics")
        self.card["exemplars"] = {"positive": [teaching_exemplar()], "negative": []}
        self.save_registry()

    def save_registry(self):
        self.registry_path.write_text(json.dumps(self.registry, ensure_ascii=False), encoding="utf-8")

    def common(self):
        return [str(self.base), "--model-revision", MODEL, "--references", str(self.references), "--registry", str(self.registry_path)]

    def run_cli(self, command, *options):
        with redirect_stdout(io.StringIO()):
            return taste_judge.main([command] + self.common() + list(options))

    def emit(self, enabled="on"):
        out = self.base / "capture"
        self.assertEqual(0, self.run_cli("emit", "--out", str(out), "--teaching-exemplars", enabled))
        return out

    def test_actual_prompt_and_capture_bind_research_move_version_content_and_source_level(self):
        before = {name: (self.base / name).read_bytes() for name in ("workflow_config.json", "research_decision.json")}
        out = self.emit()
        plan = json.loads((out / f"base.{taste_judge.PLAN_NAME}").read_text(encoding="utf-8"))
        prompt = (out / "taste-base-CAND-01.prompt.md").read_text(encoding="utf-8")
        move = self.card["exemplars"]["positive"][0]["research_move"]
        for value in (move["version"], move["move"], move["source"]["content"], move["source"]["content_sha256"], "synthetic_ablation", "teaching-only", plan["input_sha256"], plan["teaching_projection_sha256"]):
            self.assertIn(value, prompt)
        self.assertNotIn(self.card["exemplars"]["positive"][0]["why"], prompt)
        self.assertNotIn("cohort_percentile", prompt)
        self.assertIn("全文论证厚度仍未知", prompt)
        answer_prompts(out, prefer_candidate, context_prefix="synthetic-test")
        self.assertEqual(0, self.run_cli("collect", "--responses", str(out), "--teaching-exemplars", "on", "--write"))
        judgement = json.loads((self.base / taste_judge.JUDGEMENT_JSON).read_text(encoding="utf-8"))
        self.assertEqual(plan["teaching_projection"], judgement["teaching_projection"])
        self.assertEqual("signal-not-gate", judgement["authority"])
        self.assertEqual("opinions-only", judgement["decision_policy"])
        self.assertEqual([], judgement["ranking"])
        self.assertEqual(before, {name: (self.base / name).read_bytes() for name in before})

    def test_disabling_teaching_preserves_symmetric_baseline_and_rejects_flag_drift(self):
        out = self.emit("off")
        prompt = (out / "taste-base-CAND-01.prompt.md").read_text(encoding="utf-8")
        self.assertNotIn("SYN-MOVE-01", prompt)
        self.assertIn("symmetric-assessment/v2", prompt)
        answer_prompts(out, prefer_candidate, context_prefix="synthetic-off")
        self.assertEqual(0, self.run_cli("collect", "--responses", str(out), "--teaching-exemplars", "off"))
        self.assertEqual(1, self.run_cli("collect", "--responses", str(out), "--teaching-exemplars", "on"))

    def test_source_content_version_and_source_level_drift_reject_old_capture(self):
        out = self.emit()
        answer_prompts(out, prefer_candidate, context_prefix="synthetic-drift")
        original = copy.deepcopy(self.card["exemplars"]["positive"][0]["research_move"])
        for change in ("version", "content", "source_level", "permission", "verification"):
            with self.subTest(change=change):
                move = copy.deepcopy(original)
                if change == "version":
                    move["version"] = "synthetic-fixture-v2"
                elif change == "content":
                    move["source"]["content"] += " The fictional record is revised."
                    move["source"]["content_sha256"] = taste_judge.sha256_text(move["source"]["content"])
                elif change == "source_level":
                    move["source"].update(level="abstract", origin="published_result")
                    move["support"]["basis"] = "author_claim"
                else:
                    move["source"][change]["basis"] += " Revised source review declaration."
                self.card["exemplars"]["positive"][0]["research_move"] = move
                self.save_registry()
                self.assertEqual(1, self.run_cli("collect", "--responses", str(out), "--teaching-exemplars", "on"))

    def test_proposal_provenance_change_rejects_old_capture(self):
        out = self.emit("off")
        answer_prompts(out, prefer_candidate, context_prefix="synthetic-source")
        data = json.loads(self.references.read_text(encoding="utf-8"))
        data[0]["comparison_view"]["provenance"]["information_basis"] += " Changed information conditions."
        self.references.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(1, self.run_cli("collect", "--responses", str(out)))

    def test_plan_reports_missing_and_published_references_without_judge_calls(self):
        for kind in ("empty", "published"):
            with self.subTest(kind=kind):
                data = [] if kind == "empty" else [{"identifier": "SYN-RESULT-01", "title": "SYNTHETIC published result", "claim": "Synthetic retrospective finding, not an original proposal."}]
                self.references.write_text(json.dumps(data), encoding="utf-8")
                plan_file = self.base / f"{kind}.plan.json"
                self.assertEqual(0, self.run_cli("plan", "--out", str(plan_file)))
                plan = json.loads(plan_file.read_text(encoding="utf-8"))
                self.assertEqual(0, plan["dispatch_count"])
                self.assertEqual("no_comparable_pairs", plan["comparison_status"])
                if kind == "empty":
                    self.assertIn("reference_pool_empty", plan["reference_availability"]["reasons"])
                else:
                    self.assertIn("reference_is_not_proposal", plan["reference_availability"]["excluded"][0]["reasons"])
                out = self.base / kind
                self.assertEqual(0, self.run_cli("emit", "--out", str(out)))
                self.assertFalse((out / "manifest.json").exists())
                self.assertEqual([], list(out.glob("*.prompt.md")))
                self.assertEqual(0, self.run_cli("collect", "--responses", str(out), "--write"))
                judgement = json.loads((self.base / taste_judge.JUDGEMENT_JSON).read_text(encoding="utf-8"))
                self.assertEqual([], judgement["judgements"])
                self.assertEqual([], judgement["ranking"])
                self.assertEqual(2, len(judgement["unavailable_candidates"]))
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(0, taste_judge.main(["validate", str(self.base), "--registry", str(self.registry_path)]))

    def test_changed_inputs_cannot_overwrite_or_restore_old_capture(self):
        out = self.emit("off")
        answer_prompts(out, prefer_candidate, context_prefix="synthetic-old-capture")
        self.assertEqual(0, self.run_cli("collect", "--responses", str(out), "--write"))
        before = {path.name: path.read_bytes() for path in out.iterdir() if path.is_file()}
        self.references.write_text("[]", encoding="utf-8")
        self.assertEqual(1, self.run_cli("emit", "--out", str(out)))
        self.assertEqual(before, {path.name: path.read_bytes() for path in out.iterdir() if path.is_file()})
        self.assertEqual(1, self.run_cli("collect", "--responses", str(out), "--write"))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(1, taste_judge.main(["validate", str(self.base), "--registry", str(self.registry_path)]))
        fresh = self.base / "fresh-empty"
        self.assertEqual(0, self.run_cli("emit", "--out", str(fresh)))
        self.assertEqual(0, self.run_cli("collect", "--responses", str(fresh), "--write"))
        judgement = json.loads((self.base / taste_judge.JUDGEMENT_JSON).read_text(encoding="utf-8"))
        self.assertEqual([], judgement["judgements"])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(0, taste_judge.main(["validate", str(self.base), "--registry", str(self.registry_path)]))

    def test_one_verified_declaration_is_usable_without_a_two_reference_quota(self):
        data = json.loads(self.references.read_text(encoding="utf-8"))
        data[1].pop("comparison_view")
        self.references.write_text(json.dumps(data), encoding="utf-8")
        out = self.emit()
        plan = json.loads((out / f"base.{taste_judge.PLAN_NAME}").read_text(encoding="utf-8"))
        self.assertEqual(1, plan["reference_availability"]["eligible_count"])
        self.assertEqual(2, plan["dispatch_count"])
        self.assertTrue(all(len(item["pairs"]) == 1 for item in plan["items"]))

    def test_contemporaneous_label_without_provenance_is_not_comparable(self):
        data = json.loads(self.references.read_text(encoding="utf-8"))
        data[0]["comparison_view"].pop("provenance")
        data[1]["comparison_view"]["origin"] = "retrospective"
        self.references.write_text(json.dumps(data), encoding="utf-8")
        out = self.emit()
        plan = json.loads((out / f"base.{taste_judge.PLAN_NAME}").read_text(encoding="utf-8"))
        self.assertEqual(0, plan["dispatch_count"])
        reasons = {reason for entry in plan["reference_availability"]["excluded"] for reason in entry["reasons"]}
        self.assertIn("proposal_provenance_missing", reasons)
        self.assertIn("contemporaneous_origin_missing", reasons)

    def test_explicit_empty_inputs_do_not_fall_back_to_workspace_literature(self):
        registry_file = self.base / "reference_materials" / "literature_registry.json"
        registry_file.parent.mkdir()
        registry_file.write_text(json.dumps({"sources": [{"source_id": "SYN-REGISTRY-01", "title": "SYNTHETIC registered result", "metadata": {"abstract": "SYNTHETIC existing workspace abstract must not replace an explicitly empty reference input."}}]}), encoding="utf-8")
        self.references.write_text("[]", encoding="utf-8")
        packet = self.base / "empty-packet.json"
        packet.write_text('{"literature_reconnaissance": []}', encoding="utf-8")
        self.assertEqual(("references", []), taste_judge.load_reference_pool(self.base, references=self.references))
        self.assertEqual(("packet", []), taste_judge.load_reference_pool(self.base, packet=packet))
        origin, pool = taste_judge.load_reference_pool(self.base)
        self.assertEqual("registry", origin)
        self.assertEqual(1, len(pool))
        out = self.emit("off")
        plan = json.loads((out / f"base.{taste_judge.PLAN_NAME}").read_text(encoding="utf-8"))
        self.assertEqual(0, plan["reference_availability"]["pool_count"])
        self.assertNotIn(str(registry_file.resolve()), [binding["path"] for binding in plan["input_files"]])

    def test_missing_candidate_content_is_reported_before_dispatch(self):
        path = self.base / "research_decision.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["candidates"][0]["potential_contribution"] = ""
        path.write_text(json.dumps(data), encoding="utf-8")
        out = self.emit("off")
        plan = json.loads((out / f"base.{taste_judge.PLAN_NAME}").read_text(encoding="utf-8"))
        self.assertEqual(1, plan["dispatch_count"])
        item = next(item for item in plan["items"] if item["candidate_id"] == "CAND-01")
        self.assertIn("candidate_potential_contribution_missing", item["reasons"])
        self.assertFalse((out / "taste-base-CAND-01.prompt.md").exists())


if __name__ == "__main__":
    unittest.main()
