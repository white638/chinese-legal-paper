#!/usr/bin/env python3
"""Focused regression tests for the strict raw-review v2 contract."""

from __future__ import annotations

import tempfile
from types import SimpleNamespace
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import structured_review


ROLE_PREFIX = {"methods": "MET", "contribution": "CON", "clarity": "CLR"}


def rubric_dimension_table(role: str, *, venue: str = "BLOCKED") -> str:
    rows = [
        "| Dimension ID | Applicability | Score | Reason | Manuscript Location |",
        "|---|---|---:|---|---|",
    ]
    for dimension_id, label in structured_review.REVIEW_RUBRICS[role]:
        if dimension_id == "CON-VENUE-FIT" and venue != "APPLICABLE":
            rows.append(
                f"| {dimension_id} | {venue} | N/A | The verified venue contract declares this dimension {venue.lower()} for this review run. | N/A |"
            )
        else:
            rows.append(
                f"| {dimension_id} | APPLICABLE | 4 | The manuscript provides enough material to assess {label} with a concrete diagnostic judgment. | Methods section, paragraph 2 |"
            )
    return "\n".join(rows)


def pass_review(role: str, *, common: str = "") -> str:
    return f"""# Isolated Review

Review Verdict: PASS

## Rubric Dimension Scores

{rubric_dimension_table(role)}

## Findings

{common}

Recommendation: Accept
"""


def finding_review(
    role: str,
    *,
    quote: str = "The baseline comparison is omitted.",
    severity: str = "MAJOR",
    repair_kind: str = "RERUN_ANALYSIS",
    owner_stage: str = "execution",
    text_action: str = "REPLACE",
    delta: int = -12,
    recommended_action: str = "Run and report the missing comparison, then calibrate every propagated claim to the new result.",
) -> str:
    prefix = ROLE_PREFIX[role]
    return f"""# Isolated Review

Review Verdict: FINDINGS

## Rubric Dimension Scores

{rubric_dimension_table(role)}

## Findings

### Finding 1
Finding ID: REV-{prefix}-001
Severity: {severity}
Confidence: HIGH
Category: method_validity
Location: Methods section, paragraph 2
Quoted Span: {quote}
Issue: The manuscript omits a necessary comparison and therefore does not establish the stated empirical contrast.
Reader Consequence: Readers cannot distinguish the reported pattern from a general time trend or reproduce the central comparison.
Repair Kind: {repair_kind}
Owner Stage: {owner_stage}
Text Action: {text_action}
Recommended Action: {recommended_action}
Net Word Delta: {delta}

Recommendation: Major Revision
"""


class StructuredReviewIntegrityTests(unittest.TestCase):
    def _write_outputs(self, review_dir: Path, texts: tuple[str, str, str]) -> None:
        for name, text in zip(
            (
                "methods_review_output.md",
                "contribution_review_output.md",
                "clarity_review_output.md",
            ),
            texts,
            strict=True,
        ):
            (review_dir / name).write_text(text, encoding="utf-8")

    def _write_contracts(self, outdir: Path) -> None:
        (outdir / "confirmed_motivation.md").write_text(
            "Question: why does the comparison differ? Claim CLM-SECRET remains internal.\n"
            "Schema Version: controller-only\n"
            "Claim IDs: CLM-DROP-ME\n",
            encoding="utf-8",
        )
        (outdir / "confirmed_contribution.md").write_text(
            "Contribution: identify the boundary. Evidence EVD-SECRET remains internal.\n"
            "| Field | Content |\n"
            "|---|---|\n"
            "| Execution IDs | EXE-DROP-ME |\n",
            encoding="utf-8",
        )

    def test_pass_with_zero_findings_is_valid(self) -> None:
        findings, metrics = structured_review._validate_reviewer_output(
            "methods_review_output.md", pass_review("methods")
        )
        self.assertEqual([], findings)
        self.assertEqual("PASS", metrics["review_verdict"])
        self.assertFalse(metrics["score_found"])
        self.assertEqual(0, metrics["located_substantive_findings"])

    def test_one_material_finding_is_valid_without_a_quota(self) -> None:
        findings, metrics = structured_review._validate_reviewer_output(
            "methods_review_output.md", finding_review("methods")
        )
        self.assertEqual([], findings)
        self.assertEqual(1, metrics["located_substantive_findings"])

    def test_text_edit_add_is_argument_build_bridge_or_define_only(self) -> None:
        valid = finding_review(
            "clarity",
            severity="MINOR",
            repair_kind="TEXT_EDIT",
            owner_stage="build",
            text_action="ADD",
            delta=12,
            recommended_action=(
                "Add a BRIDGE only if the build expression budget binds it to an existing warrant."
            ),
        )
        findings, _ = structured_review._validate_reviewer_output(
            "clarity_review_output.md", valid
        )
        self.assertEqual([], findings)

        missing_anchor_action = valid.replace("Add a BRIDGE", "Add explanatory prose")
        findings, _ = structured_review._validate_reviewer_output(
            "clarity_review_output.md", missing_anchor_action
        )
        self.assertTrue(any("REPAIR_ACTION_MISMATCH" in item for item in findings))

        wrong_owner = valid.replace("Owner Stage: build", "Owner Stage: research")
        findings, _ = structured_review._validate_reviewer_output(
            "clarity_review_output.md", wrong_owner
        )
        self.assertTrue(any("REPAIR_ACTION_MISMATCH" in item for item in findings))

    def test_internal_ids_are_forbidden_in_raw_review(self) -> None:
        review = finding_review("methods").replace(
            "Recommended Action: Run",
            "Recommended Action: Update CLM-001 using EVD-002 and run",
        )
        findings, _ = structured_review._validate_reviewer_output(
            "methods_review_output.md", review
        )
        self.assertTrue(any("[RD.REVIEW.INTERNAL_ID_FORBIDDEN]" in item for item in findings))

    def test_mixed_finding_and_concern_headings_cannot_hide_raw_finding(self) -> None:
        review = finding_review("methods").replace(
            "\nRecommendation: Major Revision",
            "\n### Concern 2\n"
            "Location: Conclusion, paragraph 1\n"
            "Issue: A second substantive concern would otherwise be swallowed into Finding 1.\n"
            "Reader Consequence: The canonical registry would omit a source objection.\n"
            "\nRecommendation: Major Revision",
        )
        findings, metrics = structured_review._validate_reviewer_output(
            "methods_review_output.md", review
        )
        self.assertTrue(any("[RD.REVIEW.FINDING_HEADING_INVALID]" in item for item in findings))
        self.assertEqual(1, metrics["finding_candidates"])

    def test_renamed_findings_section_cannot_disable_strict_heading_coverage(self) -> None:
        review = finding_review("methods").replace("## Findings", "## Detailed Objections")
        review = review.replace(
            "\nRecommendation: Major Revision",
            "\n### Concern 2\n"
            "Location: Conclusion, paragraph 1\n"
            "Issue: This second objection must not be swallowed by the first Finding.\n"
            "Reader Consequence: A raw source objection would disappear.\n"
            "\nRecommendation: Major Revision",
        )
        findings, metrics = structured_review._validate_reviewer_output(
            "methods_review_output.md", review
        )
        self.assertTrue(
            any("[RD.REVIEW.FINDINGS_SECTION_INVALID]" in item for item in findings)
        )
        self.assertEqual(1, metrics["finding_candidates"])

    def test_pass_cannot_hide_substantive_plain_prose_in_findings_region(self) -> None:
        review = pass_review(
            "methods",
            common=(
                "The manuscript omits a baseline comparison, so the central empirical "
                "contrast cannot be reproduced or distinguished from a time trend."
            ),
        )
        findings, _ = structured_review._validate_reviewer_output(
            "methods_review_output.md", review
        )
        self.assertTrue(
            any("[RD.REVIEW.FINDING_REGION_UNPROJECTED]" in item for item in findings)
        )

    def test_location_must_be_valid_in_its_own_field(self) -> None:
        review = finding_review("methods").replace(
            "Location: Methods section, paragraph 2",
            "Location: nowhere",
        ).replace(
            "Issue: The manuscript",
            "Issue: In the Methods section, paragraph 2, the manuscript",
        )
        findings, _ = structured_review._validate_reviewer_output(
            "methods_review_output.md", review
        )
        self.assertTrue(
            any("[RD.REVIEW.FINDING_LOCATION_INVALID]" in item for item in findings)
        )

    def test_add_requires_material_anchor_and_positive_delta(self) -> None:
        # v2 moves stable material identities to the internal mapper; the raw
        # reviewer still has to declare the scientific repair and positive delta.
        review = finding_review(
            "methods",
            repair_kind="ADD_EVIDENCE",
            owner_stage="research",
            text_action="ADD",
            delta=0,
        )
        findings, _ = structured_review._validate_reviewer_output(
            "methods_review_output.md", review
        )
        self.assertTrue(any("[RD.REVIEW.NET_GROWTH_INVALID]" in item for item in findings))

    def test_applicability_controls_score_and_location(self) -> None:
        valid = pass_review("contribution")
        findings, _ = structured_review._validate_reviewer_output(
            "contribution_review_output.md", valid
        )
        self.assertEqual([], findings)
        invalid = valid.replace(
            "| CON-VENUE-FIT | BLOCKED | N/A |",
            "| CON-VENUE-FIT | APPLICABLE | N/A |",
        )
        findings, _ = structured_review._validate_reviewer_output(
            "contribution_review_output.md", invalid
        )
        self.assertTrue(any("[RD.REVIEW.RUBRIC_SCORE_INVALID]" in item for item in findings))

    def test_score_verdict_and_locations_are_required(self) -> None:
        # Overall Score is intentionally optional in v2; verdict, locator, and
        # the machine-readable Finding fields remain hard requirements.
        review = finding_review("clarity").replace("Review Verdict: FINDINGS\n", "")
        review = review.replace("Severity: MAJOR\n", "")
        review = review.replace("Location: Methods section, paragraph 2\n", "")
        findings, _ = structured_review._validate_reviewer_output(
            "clarity_review_output.md", review
        )
        joined = "\n".join(findings)
        self.assertIn("[RD.REVIEW.VERDICT_INVALID]", joined)
        self.assertIn("[RD.REVIEW.FIELD_MISSING]", joined)
        self.assertIn("[RD.REVIEW.FINDING_LOCATION_MISSING]", joined)

    def test_finding_location_is_required(self) -> None:
        review = finding_review("clarity").replace(
            "Location: Methods section, paragraph 2\n", ""
        )
        findings, _ = structured_review._validate_reviewer_output(
            "clarity_review_output.md", review
        )
        self.assertTrue(any("[RD.REVIEW.FINDING_LOCATION_MISSING]" in item for item in findings))

    def test_distinct_chinese_reviews_pass(self) -> None:
        methods = finding_review("methods").replace(
            "The manuscript omits a necessary comparison and therefore does not establish the stated empirical contrast.",
            "稿件省略必要的基准比较，因此当前结果不能建立文中声称的经验差异。",
        ).replace(
            "Readers cannot distinguish the reported pattern from a general time trend or reproduce the central comparison.",
            "读者无法区分报告的模式与一般时间趋势，也无法复现核心比较。",
        )
        with tempfile.TemporaryDirectory() as tmp:
            review_dir = Path(tmp)
            self._write_outputs(
                review_dir,
                (methods, pass_review("contribution"), pass_review("clarity")),
            )
            result = structured_review.validate_independence(review_dir)
        self.assertTrue(result["ok"], result["findings"])

    def test_english_reviews_remain_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            review_dir = Path(tmp)
            self._write_outputs(
                review_dir,
                (
                    finding_review("methods"),
                    finding_review("contribution", severity="MINOR", repair_kind="TEXT_EDIT", owner_stage="build"),
                    finding_review("clarity", severity="OBSERVATION", repair_kind="NO_ACTION", owner_stage="build", text_action="NO_ACTION", delta=0),
                ),
            )
            result = structured_review.validate_independence(review_dir)
        self.assertTrue(result["ok"], result["findings"])

    def test_textual_overlap_is_diagnostic_not_independence(self) -> None:
        common = " ".join(
            f"shared diagnostic token {index} carries distinct common wording"
            for index in range(1200)
        )
        with tempfile.TemporaryDirectory() as tmp:
            review_dir = Path(tmp)
            self._write_outputs(
                review_dir,
                (
                    pass_review("methods") + "\n## Diagnostic Note\n\n" + common,
                    pass_review("contribution") + "\n## Diagnostic Note\n\n" + common,
                    pass_review("clarity") + "\n## Diagnostic Note\n\n" + common,
                ),
            )
            result = structured_review.validate_independence(review_dir)
        self.assertTrue(result["ok"], result["findings"])
        self.assertTrue(any("RD.REVIEW.TEXTUAL_OVERLAP" in item for item in result["warnings"]))
        self.assertNotIn("independence_score", result)

    def test_rubric_dimension_contract_rejects_missing_duplicate_and_unknown_ids(self) -> None:
        text = pass_review("methods")
        first, second, third = (
            item[0] for item in structured_review.REVIEW_RUBRICS["methods"][:3]
        )
        text = text.replace(f"| {second} |", f"| {first} |", 1)
        text = text.replace(f"| {third} |", "| MET-UNKNOWN |", 1)
        findings, _ = structured_review._validate_reviewer_output(
            "methods_review_output.md", text
        )
        joined = "\n".join(findings)
        self.assertIn("[RD.REVIEW.RUBRIC_DIMENSION_DUPLICATE]", joined)
        self.assertIn("[RD.REVIEW.RUBRIC_DIMENSION_MISSING]", joined)
        self.assertIn("[RD.REVIEW.RUBRIC_DIMENSION_UNKNOWN]", joined)

    def test_rubric_dimension_rows_require_score_reason_and_location(self) -> None:
        text = pass_review("methods")
        first = structured_review.REVIEW_RUBRICS["methods"][0][0]
        line = next(row for row in text.splitlines() if row.startswith(f"| {first} |"))
        text = text.replace(
            line,
            f"| {first} | APPLICABLE | 6 | weak | nowhere |",
            1,
        )
        findings, _ = structured_review._validate_reviewer_output(
            "methods_review_output.md", text
        )
        joined = "\n".join(findings)
        self.assertIn("[RD.REVIEW.RUBRIC_SCORE_INVALID]", joined)
        self.assertIn("[RD.REVIEW.RUBRIC_REASON_WEAK]", joined)
        self.assertIn("[RD.REVIEW.RUBRIC_LOCATION_MISSING]", joined)

    def test_legacy_single_score_without_dimension_table_is_rejected(self) -> None:
        text = "# Review\n\nOverall Score: 4/5\n\nReview Verdict: PASS\n\n## Findings\n"
        findings, _ = structured_review._validate_reviewer_output(
            "methods_review_output.md", text
        )
        self.assertTrue(any("[RD.REVIEW.RUBRIC_TABLE_MISSING]" in item for item in findings))

    def test_short_manuscript_does_not_seed_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            manuscript = outdir / "manuscript.md"
            manuscript.write_text("# Result\n\nA concise supported result.", encoding="utf-8")
            report = structured_review.generate_structured_review(outdir, manuscript)
        self.assertEqual(0, report.total_findings)

    def test_dispatch_embeds_complete_manuscript_and_isolates_planning_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            manuscript = outdir / "manuscript.md"
            manuscript.write_text("# Methods\n\nThe baseline comparison is omitted.", encoding="utf-8")
            self._write_contracts(outdir)
            result = structured_review.dispatch_review(outdir, manuscript)
            prompts = outdir / "review_prompts"
            methods = (prompts / "methods_reviewer.md").read_text(encoding="utf-8")
            contribution = (prompts / "contribution_reviewer.md").read_text(encoding="utf-8")
            clarity = (prompts / "clarity_reviewer.md").read_text(encoding="utf-8")
        self.assertRegex(result["review_run_id"], r"^REV-[A-F0-9]{16}$")
        self.assertNotIn("CLM-SECRET", contribution)
        self.assertNotIn("EVD-SECRET", contribution)
        self.assertIn("INTERNAL_CLAIM_ID_WITHHELD", contribution)
        self.assertNotIn("controller-only", contribution)
        self.assertNotIn("DROP-ME", contribution)
        self.assertIn("Sanitized Confirmed Motivation Semantic Context", contribution)
        self.assertNotIn("Complete Confirmed Motivation Contract", contribution)
        self.assertNotIn("Contribution: identify the boundary", methods)
        self.assertNotIn("Contribution: identify the boundary", clarity)
        self.assertIn("not a mandated sentence order", clarity)
        self.assertIn("a clear long sentence", clarity)
        self.assertIn("analogy is not independent corroboration", clarity)
        self.assertIn("adds, revises, rejects, or reorganizes", contribution)
        for prompt in (methods, contribution, clarity):
            self.assertIn(
                "| Dimension ID | Applicability | Score | Reason | Manuscript Location |",
                prompt,
            )
            self.assertNotIn("changed Claim ID", prompt)

    def test_dispatch_blocks_unverified_venue_fit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            manuscript = outdir / "manuscript.md"
            manuscript.write_text("# Methods\n\nThe baseline comparison is omitted.", encoding="utf-8")
            self._write_contracts(outdir)
            structured_review.dispatch_review(outdir, manuscript)
            prompt = (outdir / "review_prompts" / "contribution_reviewer.md").read_text(
                encoding="utf-8"
            )
        self.assertIn("Applicability: BLOCKED", prompt)

    def test_venue_contract_requires_validation_ok_not_only_example_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            (outdir / "workflow_config.json").write_text(
                '{"scene":"journal","target_name":"Verified Journal"}',
                encoding="utf-8",
            )
            invalid = SimpleNamespace(ok=False, stats={"target_examples": 3})
            with patch("cnki_acquisition.validate_registry", return_value=invalid):
                state = structured_review.venue_contract_state(outdir)
        self.assertEqual("BLOCKED", state["applicability"])

    def test_venue_contract_accepts_role_valid_verified_target_example(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            (outdir / "workflow_config.json").write_text(
                '{"scene":"journal","target_name":"Verified Journal"}',
                encoding="utf-8",
            )
            valid = SimpleNamespace(ok=True, stats={"target_examples": 1})
            with patch("cnki_acquisition.validate_registry", return_value=valid):
                state = structured_review.venue_contract_state(outdir)
        self.assertEqual("APPLICABLE", state["applicability"])

    def test_contribution_prompt_scopes_direct_checks_and_full_paper_obligations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            manuscript = outdir / "manuscript.md"
            manuscript.write_text("# Introduction\n\nThe baseline comparison is omitted.", encoding="utf-8")
            self._write_contracts(outdir)
            structured_review.dispatch_review(outdir, manuscript)
            prompt = (outdir / "review_prompts" / "contribution_reviewer.md").read_text(
                encoding="utf-8"
            )
        for marker in (
            "response increment over fairly represented prior positions",
            "Material reader update",
            "Zero activated manuscript countervoices is valid",
            "Statistical claim ownership when comparison/inference is present",
            "Do not infer novelty from novelty words",
            "Review Verdict: PASS",
            "Severity: CRITICAL|MAJOR|MINOR|OBSERVATION",
        ):
            self.assertIn(marker, prompt)
        self.assertNotIn("CLM-SECRET", prompt)
        self.assertNotIn("EVD-SECRET", prompt)

    def test_clarity_prompt_isolatedly_recovers_voice_response_and_payoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            manuscript = outdir / "manuscript.md"
            manuscript.write_text("# Introduction\n\nThe baseline comparison is omitted.", encoding="utf-8")
            self._write_contracts(outdir)
            structured_review.dispatch_review(outdir, manuscript)
            prompt = (outdir / "review_prompts" / "clarity_reviewer.md").read_text(
                encoding="utf-8"
            )
        for marker in (
            "Use only the manuscript text embedded below",
            "four answers: what happened",
            "how the evidence supports that explanation",
            "what understanding changes",
            "Apply the paragraph object test",
            "Object-first writing clarity",
            "Positive formulation",
            "Revision cleanliness",
            "objection-concession-reply-qualification sequence",
            "without revealing the sequence of comments",
            "AP.ARC.CATALOGUE_ONLY",
            "AP.ARC.FALSE_TELEOLOGY",
            "AP.MOTION.NO_ADVANCE",
            "AP.HOOK.ARTIFICIAL",
            "AP.HOOK.NO_DEEPENING",
            "AP.QUOTE.DECORATIVE",
            "AP.VOICE.SOURCE_DOMINATED",
            "AP.CLOSURE.REPETITION_ONLY",
            "AP.CLOSURE.UNGROUNDED_ELEVATION",
            "require a body passage that explains",
            "AP.FOCUS.DRIFT",
            "AP.FOCUS.WARRANT_GAP",
            "AP.FOCUS.ORPHAN",
            "AP.FOCUS.OVERPRUNED",
            "allowing an unresolved or negative answer",
            "Do not invent an opponent",
            "section deletion test",
            "preserve necessary context",
        ):
            self.assertIn(marker, prompt)
        self.assertNotIn("Contribution: identify the boundary", prompt)

    def test_clarity_rubric_covers_explanation_formulation_and_clean_revision(self) -> None:
        dimension_ids = {item[0] for item in structured_review.REVIEW_RUBRICS["clarity"]}
        self.assertTrue(
            {
                "CLR-SUBSTANTIVE-EXPLANATION",
                "CLR-POSITIVE-FORMULATION",
                "CLR-REVISION-CLEANLINESS",
            }.issubset(dimension_ids)
        )

    def test_dispatch_embeds_complete_manuscript_and_sanitized_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            manuscript = outdir / "manuscript.md"
            manuscript.write_text(
                "# Introduction\n\n" + ("A" * 3500) + "MANUSCRIPT_END_SENTINEL",
                encoding="utf-8",
            )
            self._write_contracts(outdir)
            structured_review.dispatch_review(outdir, manuscript)
            prompts = [
                (outdir / "review_prompts" / name).read_text(encoding="utf-8")
                for name in (
                    "methods_reviewer.md",
                    "contribution_reviewer.md",
                    "clarity_reviewer.md",
                )
            ]
        self.assertTrue(all("MANUSCRIPT_END_SENTINEL" in prompt for prompt in prompts))
        self.assertIn("Contribution: identify the boundary", prompts[1])
        self.assertNotIn("CLM-SECRET", prompts[1])
        self.assertNotIn("Contribution: identify the boundary", prompts[0])
        self.assertNotIn("Contribution: identify the boundary", prompts[2])

    def test_dispatch_refuses_missing_confirmed_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            manuscript = outdir / "manuscript.md"
            manuscript.write_text("# Manuscript\n\nComplete text.", encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                structured_review.dispatch_review(outdir, manuscript)

    def test_dispatch_refuses_to_overwrite_an_existing_raw_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            manuscript = outdir / "manuscript.md"
            manuscript.write_text("# Manuscript\n\nComplete text.", encoding="utf-8")
            self._write_contracts(outdir)
            first = structured_review.dispatch_review(outdir, manuscript)
            (outdir / "review_prompts" / "methods_review_output.md").write_text(
                pass_review("methods"), encoding="utf-8"
            )
            with self.assertRaisesRegex(FileExistsError, "refusing to overwrite"):
                structured_review.dispatch_review(outdir, manuscript)
        self.assertRegex(first["review_run_id"], r"^REV-[A-F0-9]{16}$")

    def test_redispatch_of_incomplete_prompt_set_gets_a_new_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            manuscript = outdir / "manuscript.md"
            manuscript.write_text("# Manuscript\n\nComplete text.", encoding="utf-8")
            self._write_contracts(outdir)
            first = structured_review.dispatch_review(outdir, manuscript)
            second = structured_review.dispatch_review(outdir, manuscript)
        self.assertNotEqual(first["review_run_id"], second["review_run_id"])


if __name__ == "__main__":
    unittest.main()
