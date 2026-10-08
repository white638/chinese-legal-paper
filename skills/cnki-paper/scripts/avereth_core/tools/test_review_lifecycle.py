#!/usr/bin/env python3
"""Adversarial tests for the JSON-authoritative review lifecycle."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import review_lifecycle
import structured_review
from avereth_core.audit.run_all import _actions
from avereth_core import cli
from avereth_core.version import VERSION
from test_structured_review import finding_review, pass_review


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class ReviewLifecycleTests(unittest.TestCase):
    def _workspace(
        self,
        root: Path,
        *,
        methods: str | None = None,
        contribution: str | None = None,
        clarity: str | None = None,
        mode: str = "independent",
        contexts: tuple[str, str, str] = ("ctx-methods", "ctx-contribution", "ctx-clarity"),
        profile: str = "full_paper",
        claim_ids: tuple[str, ...] = (),
        claim_rows: tuple[tuple[str, str], ...] = (),
    ) -> tuple[Path, Path]:
        outdir = root / "paper_rewriting_output"
        (outdir / "final_paper").mkdir(parents=True)
        manuscript = outdir / "final_paper" / "main.md"
        manuscript.write_text(
            "# Methods\n\nThe baseline comparison is omitted.\n\n# Conclusion\n\nThe claimed contrast is decisive.\n",
            encoding="utf-8",
        )
        write_json(
            outdir / "workflow_config.json",
            {
                "schema_version": "avereth-workflow-config/v1",
                "framework_version": VERSION,
                "workflow": "rewrite_existing",
                "task_profile": profile,
                "publication_track": "cnki-cn",
                "scene": "journal",
                "tier": "pro",
                "output_language": "en",
                "word_output": "none",
                "pdf_output": "none",
                "citation_mode": "author_year",
                "word_font_policy": "default",
                "prose_mode": "clear",
                "canonical_manuscript": "final_paper/main.md",
            },
        )
        (outdir / "confirmed_motivation.md").write_text(
            "Question: which comparison identifies the claimed contrast?", encoding="utf-8"
        )
        (outdir / "confirmed_contribution.md").write_text(
            "Contribution: calibrate the comparison and its boundary.", encoding="utf-8"
        )
        all_claim_rows = [
            *( (claim_id, "The baseline comparison is omitted.") for claim_id in claim_ids ),
            *claim_rows,
        ]
        if all_claim_rows:
            rows = "\n".join(
                f"| {claim_id} | {span} |"
                for claim_id, span in all_claim_rows
            )
            (outdir / "claim_register.md").write_text(
                "| Claim ID | Manuscript span |\n|---|---|\n" + rows + "\n",
                encoding="utf-8",
            )
        analysis = outdir / "artifacts" / "baseline.csv"
        analysis.parent.mkdir(parents=True, exist_ok=True)
        analysis.write_text("group,estimate\ncontrol,0.2\ntreated,0.4\n", encoding="utf-8")
        write_json(
            outdir / "method_execution.json",
            {
                "schema_version": "cnki-method-execution/v2",
                "status": "complete",
                "runs": [
                    {
                        "id": "EXE-001",
                        "artifacts": [
                            {
                                "id": "ART-BASELINE-001",
                                "path": "artifacts/baseline.csv",
                                "sha256": digest(analysis),
                                "role": "registered_analysis_output",
                            }
                        ],
                    }
                ],
            },
        )
        structured_review.dispatch_review(outdir, manuscript)
        review_dir = outdir / "review_prompts"
        outputs = {
            "methods": methods if methods is not None else pass_review("methods"),
            "contribution": contribution if contribution is not None else pass_review("contribution"),
            "clarity": clarity if clarity is not None else pass_review("clarity"),
        }
        for role, text in outputs.items():
            (review_dir / f"{role}_review_output.md").write_text(text, encoding="utf-8")
        manifest = json.loads((review_dir / "review_manifest.json").read_text(encoding="utf-8"))
        reviewers = []
        for role, context in zip(("methods", "contribution", "clarity"), contexts, strict=True):
            prompt = review_dir / f"{role}_reviewer.md"
            output = review_dir / f"{role}_review_output.md"
            reviewers.append(
                {
                    "role": role,
                    "context_id": context,
                    "prompt_path": f"review_prompts/{role}_reviewer.md",
                    "prompt_sha256": digest(prompt),
                    "output_path": f"review_prompts/{role}_review_output.md",
                    "output_sha256": digest(output),
                    "input_scope": (
                        "manuscript_and_sanitized_confirmed_semantics"
                        if role == "contribution"
                        else "manuscript_only"
                    ),
                    "isolation_declared": mode == "independent",
                }
            )
        write_json(
            outdir / "review_assurance.json",
            {
                "schema_version": "cnki-review-assurance/v2",
                "review_run_id": manifest["review_run_id"],
                "mode": mode,
                "manuscript": {
                    "path": manifest["canonical_manuscript"],
                    "sha256": manifest["canonical_sha256"],
                },
                "reviewers": reviewers,
            },
        )
        return outdir, manuscript

    def _compile(self, outdir: Path, manuscript: Path) -> review_lifecycle.LifecycleResult:
        return review_lifecycle.compile_findings(
            outdir,
            outdir / "review_prompts",
            manuscript,
            write=True,
        )

    def _render(self, outdir: Path) -> None:
        registry = json.loads((outdir / "review_findings.json").read_text(encoding="utf-8"))
        resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
        review_lifecycle.render_views(outdir, registry, resolution)

    def _rewrite_post_review_output(self, outdir: Path, resolution: dict) -> None:
        review = resolution["post_revision_review"]
        output = outdir / review["output_path"]
        output.write_text(
            f"Review Run ID: {review['review_run_id']}\n"
            f"Review Mode: {review['mode']}\n"
            f"Before Manuscript SHA-256: {review['before_manuscript_sha256']}\n"
            f"Reviewed Manuscript SHA-256: {review['after_manuscript_sha256']}\n"
            f"Changed Locations: {' | '.join(review['changed_locations'])}\n"
            f"Review Scope: {review['scope']}\n"
            f"Review Result: {review['result']}\n"
            f"Reviewed By: {review['reviewed_by']}\n"
            f"Reviewer Context ID: {review['reviewer_context_id']}\n",
            encoding="utf-8",
        )
        review["output_sha256"] = digest(output)

    def _major_workspace(self, root: Path, *, profile: str = "full_paper") -> tuple[Path, Path]:
        outdir, manuscript = self._workspace(
            root,
            methods=finding_review("methods"),
            profile=profile,
            claim_ids=("CLM-001",),
        )
        result = self._compile(outdir, manuscript)
        self.assertTrue(result.ok, result.findings)
        return outdir, manuscript

    def _authorized_revision_contract(self, registry: dict, outdir: Path | None = None) -> dict:
        contract = {
            "schema_version": "cnki-manuscript-revision/v2",
            "baseline": {
                "kind": "workspace",
                "path": "final_paper/main.md",
                "snapshot_path": "revision_baseline/main.md",
                "sha256": registry["manuscript"]["sha256"],
            },
            "requested_changes": [
                {
                    "change_id": "CH-001",
                    "summary": "rerun and report the missing baseline comparison",
                    "change_class": "execution",
                    "target_finding_keys": [registry["findings"][0]["finding_key"]],
                }
            ],
            "affected_identities": {
                "source_ids": [],
                "claim_ids": ["CLM-001"],
                "design_ids": [],
                "execution_ids": [],
                "manuscript_units": ["final_paper/main.md"],
            },
            "earliest_reopen_stage": "execution",
            "assurance_level": "full",
            "authorization": {
                "status": "confirmed",
                "evidence": "explicit user authorization for REV-MET-001",
            },
            "active_batch_id": None,
            "revision_batches": [],
        }
        if outdir is not None:
            snapshot = outdir / "revision_baseline" / "main.md"
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_text(
                "# Methods\n\nThe baseline comparison is omitted.\n\n"
                "# Conclusion\n\nThe claimed contrast is decisive.\n",
                encoding="utf-8",
            )
            self.assertEqual(registry["manuscript"]["sha256"], digest(snapshot))
        return contract

    def _verified_resolution(self, outdir: Path, manuscript: Path) -> dict:
        registry = json.loads((outdir / "review_findings.json").read_text(encoding="utf-8"))
        before = registry["manuscript"]["sha256"]
        manuscript.write_text(
            "# Methods\n\nThe baseline comparison is now reported with a preregistered control.\n\n"
            "# Conclusion\n\nThe contrast is limited to the registered comparison.\n",
            encoding="utf-8",
        )
        after = digest(manuscript)
        analysis = outdir / "artifacts" / "baseline.csv"
        verification_output = outdir / "review_prompts" / "verifications" / "REV-MET-001.md"
        verification_output.parent.mkdir(parents=True, exist_ok=True)
        verification_output.write_text(
            f"Review Run ID: {registry['review_run_id']}\n"
            "Finding ID: REV-MET-001\n"
            f"Before Manuscript SHA-256: {before}\n"
            f"Verified Manuscript SHA-256: {after}\n"
            "Verification Method: independent_reviewer_recheck\n"
            "Remaining Boundary: Inference remains limited to the registered comparison.\n"
            "Verification Result: PASS\n"
            "Verified By: methods_rechecker\n"
            "Verifier Context ID: ctx-verifier\n\n"
            "The comparison and propagated boundary are present.\n",
            encoding="utf-8",
        )
        cycle_dir = outdir / "review_prompts" / "cycles" / "RC-001"
        cycle_dir.mkdir(parents=True, exist_ok=True)
        reviewer_outputs = []
        for role in ("methods", "contribution", "clarity"):
            output = cycle_dir / f"{role}_review_output.md"
            output.write_text("Review Verdict: PASS\n\n## Findings\n", encoding="utf-8")
            reviewer_outputs.append(
                {
                    "role": role,
                    "path": output.relative_to(outdir).as_posix(),
                    "sha256": digest(output),
                    "context_id": f"ctx-cycle-{role}",
                }
            )
        impact = {
            "schema_version": "avereth-revision-impact/v1",
            "batch_id": "RB-001",
            "before_sha256": before,
            "after_sha256": after,
            "changed_unit_ids": ["MSU-CHANGE"],
            "required_reviewers": ["methods", "contribution", "clarity"],
            "full_review_required": True,
            "preflight_status": "PASS",
        }
        write_json(outdir / "revision_impact.json", impact)
        impact_sha = digest(outdir / "revision_impact.json")
        propagation = [
            {"target": target, "status": "CHECKED", "evidence": f"checked {target}"}
            for target in review_lifecycle.PROPAGATION_TARGETS
        ]
        return {
            "schema_version": review_lifecycle.RESOLUTION_SCHEMA,
            "review_run_id": registry["review_run_id"],
            "findings_sha256": digest(outdir / "review_findings.json"),
            "status": "CLOSED",
            "revision_batches": [
                {
                    "batch_id": "RB-001",
                    "before_manuscript_sha256": before,
                    "after_manuscript_sha256": after,
                    "impact_path": "revision_impact.json",
                    "impact_sha256": impact_sha,
                    "promotion_count": 1,
                    "cycle_ids": ["RC-001"],
                }
            ],
            "review_cycles": [
                {
                    "schema_version": "avereth-review-cycle/v1",
                    "cycle_id": "RC-001",
                    "batch_id": "RB-001",
                    "parent_cycle_id": None,
                    "mode": "FULL",
                    "before_manuscript_sha256": before,
                    "after_manuscript_sha256": after,
                    "impact_path": "revision_impact.json",
                    "impact_sha256": impact_sha,
                    "reviewed_unit_ids": ["MSU-CHANGE"],
                    "required_reviewers": ["methods", "contribution", "clarity"],
                    "dispatched_reviewers": ["methods", "contribution", "clarity"],
                    "reused_reviewers": [],
                    "role_input_digests": {role: "1" * 64 for role in ("methods", "contribution", "clarity")},
                    "role_results": {role: "PASS" for role in ("methods", "contribution", "clarity")},
                    "result": "PASS",
                    "closed_finding_keys": [registry["findings"][0]["finding_key"]],
                    "reopened_finding_keys": [],
                    "new_finding_keys": [],
                    "reviewer_outputs": reviewer_outputs,
                    "block_reason": "",
                }
            ],
            "optional_backlog": [],
            "convergence": {
                "status": "FROZEN",
                "latest_cycle_id": "RC-001",
                "active_blocking_finding_keys": [],
                "root_cause_required_finding_keys": [],
            },
            "resolutions": [
                {
                    "finding_id": "REV-MET-001",
                    "finding_key": registry["findings"][0]["finding_key"],
                    "status": "VERIFIED",
                    "decision": "ACCEPTED",
                    "original_severity": "MAJOR",
                    "final_severity": "MAJOR",
                    "earliest_reopen_stage": "execution",
                    "adjudication": None,
                    "merge_target_finding_id": None,
                    "authorization": None,
                    "change": {
                        "before_manuscript_sha256": before,
                        "after_manuscript_sha256": after,
                        "changed_locations": ["Methods paragraph 1", "Conclusion paragraph 1"],
                        "affected_claim_ids": ["CLM-001"],
                        "affected_evidence_ids": [],
                        "affected_design_ids": [],
                        "affected_execution_ids": ["EXE-001"],
                        "rerun_artifacts": [
                            {
                                "artifact_id": "ART-BASELINE-001",
                                "kind": "execution",
                                "path": "artifacts/baseline.csv",
                                "sha256": digest(analysis),
                            }
                        ],
                        "change_summary": "Added the missing comparison and propagated its bounded result.",
                        "applied_by": "revision_writer",
                        "applier_context_id": "ctx-applier",
                        "propagation_checks": propagation,
                    },
                    "verification": {
                        "method": "independent_reviewer_recheck",
                        "verified_by": "methods_rechecker",
                        "verifier_context_id": "ctx-verifier",
                        "verified_against_sha256": after,
                        "result": "PASS",
                        "remaining_boundary": "Inference remains limited to the registered comparison.",
                        "output_path": "review_prompts/verifications/REV-MET-001.md",
                        "output_sha256": digest(verification_output),
                    },
                    "history": [
                        {"from": "OPEN", "to": "PLANNED", "by": "editor", "at": "2026-08-23T00:00:00Z"},
                        {"from": "PLANNED", "to": "APPLIED", "by": "revision_writer", "at": "2026-08-23T01:00:00Z"},
                        {"from": "APPLIED", "to": "VERIFIED", "by": "methods_rechecker", "at": "2026-08-23T02:00:00Z"},
                    ],
                    "reopen_count": 0,
                    "root_cause_analysis": None,
                }
            ],
        }

    def test_three_pass_zero_finding_is_legal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._workspace(Path(tmp))
            compiled = self._compile(outdir, manuscript)
            self.assertTrue(compiled.ok, compiled.findings)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertTrue(result.ok, result.findings)
        self.assertEqual("PASS", result.metrics["recommendation"])

    def test_zero_finding_requires_all_three_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._workspace(Path(tmp))
            output = outdir / "review_prompts" / "methods_review_output.md"
            output.write_text(pass_review("methods").replace("Review Verdict: PASS", "Review Verdict: FINDINGS"), encoding="utf-8")
            assurance = json.loads((outdir / "review_assurance.json").read_text(encoding="utf-8"))
            assurance["reviewers"][0]["output_sha256"] = digest(output)
            write_json(outdir / "review_assurance.json", assurance)
            result = self._compile(outdir, manuscript)
        self.assertFalse(result.ok)
        self.assertTrue(any("FINDINGS requires" in issue or "zero findings" in issue for issue in result.findings))

    def test_open_scaffold_is_created_but_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
            self.assertEqual("OPEN", resolution["resolutions"][0]["status"])
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertFalse(result.ok)
        self.assertTrue(any("resolution is not closed" in issue for issue in result.findings))

    def test_omitted_major_finding_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
            resolution["resolutions"] = []
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertFalse(result.ok)
        self.assertTrue(any("omitted Finding ID" in issue for issue in result.findings))

    def test_raw_finding_omission_from_registry_fails_reverse_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            registry = json.loads((outdir / "review_findings.json").read_text(encoding="utf-8"))
            registry["findings"] = []
            write_json(outdir / "review_findings.json", registry)
            resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
            resolution["findings_sha256"] = digest(outdir / "review_findings.json")
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertFalse(result.ok)
        self.assertTrue(any("was omitted from review_findings" in issue for issue in result.findings))

    def test_critical_cannot_be_ordinary_waived(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._workspace(
                Path(tmp),
                methods=finding_review("methods", severity="CRITICAL"),
                claim_ids=("CLM-001",),
            )
            self.assertTrue(self._compile(outdir, manuscript).ok)
            resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
            row = resolution["resolutions"][0]
            row.update(
                {
                    "status": "WAIVED",
                    "decision": "WAIVED",
                    "authorization": {
                        "authorized_by": "editor",
                        "authorization_evidence": "explicit decision",
                        "risk_statement": "core validity risk accepted",
                    },
                    "history": [
                        {"from": "OPEN", "to": "WAIVED", "by": "editor", "at": "2026-08-23T00:00:00Z"}
                    ],
                }
            )
            resolution["status"] = "CLOSED"
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertFalse(result.ok)
        self.assertTrue(any("Critical findings cannot be WAIVED" in issue for issue in result.findings))

    def test_severity_downgrade_requires_adjudication(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
            resolution["resolutions"][0]["final_severity"] = "MINOR"
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertTrue(any("severity change requires" in issue for issue in result.findings))

    def test_major_unresolved_identity_mapping_cannot_enter_applied_or_verified(self) -> None:
        for terminal_status in ("APPLIED", "VERIFIED"):
            with self.subTest(status=terminal_status), tempfile.TemporaryDirectory() as tmp:
                outdir, manuscript = self._workspace(
                    Path(tmp), methods=finding_review("methods")
                )
                self.assertTrue(self._compile(outdir, manuscript).ok)
                resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
                row = resolution["resolutions"][0]
                history = [
                    {"from": "OPEN", "to": "PLANNED", "by": "editor", "at": "2026-08-23T00:00:00Z"},
                    {"from": "PLANNED", "to": "APPLIED", "by": "writer", "at": "2026-08-23T01:00:00Z"},
                ]
                if terminal_status == "VERIFIED":
                    history.append(
                        {"from": "APPLIED", "to": "VERIFIED", "by": "checker", "at": "2026-08-23T02:00:00Z"}
                    )
                row.update(
                    {
                        "status": terminal_status,
                        "decision": "ACCEPTED",
                        "history": history,
                    }
                )
                resolution["status"] = "CLOSED" if terminal_status == "VERIFIED" else "ACTIVE"
                write_json(outdir / "review_resolution.json", resolution)
                self._render(outdir)
                result = review_lifecycle.validate_lifecycle(outdir, manuscript)
            self.assertFalse(result.ok)
            self.assertTrue(
                any("Critical/Major identity mapping must be exact or inferred" in issue for issue in result.findings)
            )

    def test_merged_dangling_target_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
            row = resolution["resolutions"][0]
            row.update(
                {
                    "status": "MERGED",
                    "decision": "MERGED",
                    "merge_target_finding_id": "REV-MET-999",
                    "adjudication": {
                        "changed_by": "editor",
                        "context_id": "ctx-editor",
                        "reason": "claimed duplicate",
                    },
                    "history": [
                        {"from": "OPEN", "to": "MERGED", "by": "editor", "at": "2026-08-23T00:00:00Z"}
                    ],
                }
            )
            resolution["status"] = "CLOSED"
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertFalse(result.ok)
        self.assertTrue(any("valid merge target" in issue for issue in result.findings))

    def test_merged_cycle_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._workspace(
                Path(tmp),
                methods=finding_review("methods"),
                contribution=finding_review("contribution"),
                claim_ids=("CLM-001",),
            )
            self.assertTrue(self._compile(outdir, manuscript).ok)
            resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
            rows = {row["finding_id"]: row for row in resolution["resolutions"]}
            for finding_id, target_id in (
                ("REV-MET-001", "REV-CON-001"),
                ("REV-CON-001", "REV-MET-001"),
            ):
                rows[finding_id].update(
                    {
                        "status": "MERGED",
                        "decision": "MERGED",
                        "merge_target_finding_id": target_id,
                        "adjudication": {
                            "changed_by": "editor",
                            "context_id": "ctx-editor",
                            "reason": "duplicate finding projection",
                        },
                        "history": [
                            {"from": "OPEN", "to": "MERGED", "by": "editor", "at": "2026-08-23T00:00:00Z"}
                        ],
                    }
                )
            resolution["status"] = "CLOSED"
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertFalse(result.ok)
        self.assertTrue(any("MERGED cycle is forbidden" in issue for issue in result.findings))

    def test_valid_major_verified_accepts_registered_standard_artifacts_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            resolution = self._verified_resolution(outdir, manuscript)
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertTrue(result.ok, result.findings)

    def test_lifecycle_rejects_noncanonical_manuscript_argument(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            resolution = self._verified_resolution(outdir, manuscript)
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            scratch = outdir / "scratch" / "arbitrary.md"
            scratch.parent.mkdir(parents=True)
            scratch.write_bytes(manuscript.read_bytes())
            result = review_lifecycle.validate_lifecycle(outdir, scratch)
        self.assertFalse(result.ok)
        self.assertTrue(any("must equal the registry canonical manuscript path" in issue for issue in result.findings))

    def test_fake_verified_without_delta_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            resolution = self._verified_resolution(outdir, manuscript)
            current = digest(manuscript)
            row = resolution["resolutions"][0]
            row["change"]["before_manuscript_sha256"] = current
            row["change"]["after_manuscript_sha256"] = current
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertTrue(any("actual manuscript delta" in issue for issue in result.findings))

    def test_minor_text_edit_cannot_fake_verified_without_a_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._workspace(
                Path(tmp),
                methods=finding_review(
                    "methods",
                    severity="MINOR",
                    repair_kind="TEXT_EDIT",
                    owner_stage="build",
                ),
            )
            self.assertTrue(self._compile(outdir, manuscript).ok)
            registry = json.loads((outdir / "review_findings.json").read_text(encoding="utf-8"))
            current = digest(manuscript)
            artifact = outdir / "review_prompts" / "verifications" / "REV-MET-001.md"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text(
                f"Review Run ID: {registry['review_run_id']}\n"
                "Finding ID: REV-MET-001\n"
                f"Before Manuscript SHA-256: {current}\n"
                f"Verified Manuscript SHA-256: {current}\n"
                "Verification Method: recheck\n"
                "Remaining Boundary: none\n"
                "Verification Result: PASS\n"
                "Verified By: checker\n"
                "Verifier Context ID: ctx-checker\n",
                encoding="utf-8",
            )
            resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
            row = resolution["resolutions"][0]
            row.update(
                {
                    "status": "VERIFIED",
                    "decision": "ACCEPTED",
                    "change": {
                        "before_manuscript_sha256": current,
                        "after_manuscript_sha256": current,
                        "changed_locations": ["Methods paragraph 1"],
                        "affected_claim_ids": [],
                        "affected_evidence_ids": [],
                        "affected_design_ids": [],
                        "affected_execution_ids": [],
                        "rerun_artifacts": [],
                        "change_summary": "Claimed a text edit without changing the manuscript.",
                        "applied_by": "writer",
                        "applier_context_id": "ctx-writer",
                        "propagation_checks": [],
                    },
                    "verification": {
                        "method": "recheck",
                        "verified_by": "checker",
                        "verifier_context_id": "ctx-checker",
                        "verified_against_sha256": current,
                        "result": "PASS",
                        "remaining_boundary": "none",
                        "output_path": "review_prompts/verifications/REV-MET-001.md",
                        "output_sha256": digest(artifact),
                    },
                    "history": [
                        {"from": "OPEN", "to": "PLANNED", "by": "editor", "at": "1"},
                        {"from": "PLANNED", "to": "APPLIED", "by": "writer", "at": "2"},
                        {"from": "APPLIED", "to": "VERIFIED", "by": "checker", "at": "3"},
                    ],
                }
            )
            resolution["status"] = "CLOSED"
            resolution["findings_sha256"] = digest(outdir / "review_findings.json")
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertFalse(result.ok)
        self.assertTrue(any("VERIFIED requires an actual manuscript delta" in issue for issue in result.findings))

    def test_evidence_bounded_text_add_routes_as_argument_build_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._workspace(
                Path(tmp),
                methods=finding_review(
                    "methods",
                    severity="MINOR",
                    repair_kind="TEXT_EDIT",
                    owner_stage="build",
                    text_action="ADD",
                    delta=12,
                    recommended_action=(
                        "Add a BRIDGE only if the build expression budget binds it to the existing warrant."
                    ),
                ),
                claim_ids=("CLM-001",),
            )
            result = self._compile(outdir, manuscript)
            self.assertTrue(result.ok, result.findings)
            registry = json.loads(
                (outdir / "review_findings.json").read_text(encoding="utf-8")
            )
            action = registry["findings"][0]["recommended_action"]
            self.assertEqual("argument", action["change_class"])
            self.assertEqual("build", action["owner_stage"])
            self.assertEqual("ADD", action["text_action"])

    def test_same_applier_and_verifier_context_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            resolution = self._verified_resolution(outdir, manuscript)
            row = resolution["resolutions"][0]
            row["verification"]["verifier_context_id"] = row["change"]["applier_context_id"]
            row["verification"]["verified_by"] = row["change"]["applied_by"]
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        joined = "\n".join(result.findings)
        self.assertIn("verifier context must differ", joined)
        self.assertIn("verifier identity must differ", joined)

    def test_verification_sha_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            resolution = self._verified_resolution(outdir, manuscript)
            resolution["resolutions"][0]["verification"]["verified_against_sha256"] = "0" * 64
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertTrue(any("current canonical manuscript SHA" in issue for issue in result.findings))

    def test_random_file_cannot_serve_as_verification_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            resolution = self._verified_resolution(outdir, manuscript)
            output = outdir / resolution["resolutions"][0]["verification"]["output_path"]
            output.write_text("This unrelated file happens to say PASS.\n", encoding="utf-8")
            resolution["resolutions"][0]["verification"]["output_sha256"] = digest(output)
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertFalse(result.ok)
        self.assertTrue(any("verification artifact requires exactly one Finding ID" in issue for issue in result.findings))

    def test_verification_artifact_must_bind_finding_sha_result_and_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            resolution = self._verified_resolution(outdir, manuscript)
            row = resolution["resolutions"][0]
            output = outdir / row["verification"]["output_path"]
            output.write_text(
                "Finding ID: REV-CON-999\n"
                f"Verified Manuscript SHA-256: {'0' * 64}\n"
                "Verification Result: FAIL\n"
                "Verified By: another-agent\n"
                "Verifier Context ID: another-context\n",
                encoding="utf-8",
            )
            row["verification"]["output_sha256"] = digest(output)
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        joined = "\n".join(result.findings)
        self.assertIn("verification artifact Finding ID does not match", joined)
        self.assertIn("verification artifact Verified Manuscript SHA-256 does not match", joined)
        self.assertIn("verification artifact Verification Result does not match", joined)
        self.assertIn("verification artifact Verifier Context ID does not match", joined)

    def test_verification_artifact_must_use_dedicated_review_prompts_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            resolution = self._verified_resolution(outdir, manuscript)
            row = resolution["resolutions"][0]
            original = outdir / row["verification"]["output_path"]
            unrelated = outdir / "unrelated_workflow_file.md"
            unrelated.write_bytes(original.read_bytes())
            row["verification"]["output_path"] = "unrelated_workflow_file.md"
            row["verification"]["output_sha256"] = digest(unrelated)
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertFalse(result.ok)
        self.assertTrue(any("verification output must be the dedicated artifact" in issue for issue in result.findings))

    def test_raw_source_output_cannot_be_reused_as_verification_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            resolution = self._verified_resolution(outdir, manuscript)
            row = resolution["resolutions"][0]
            source = outdir / "review_prompts" / "methods_review_output.md"
            row["verification"]["output_path"] = "review_prompts/methods_review_output.md"
            row["verification"]["output_sha256"] = digest(source)
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertFalse(result.ok)
        self.assertTrue(
            any("review_prompts/verifications/REV-MET-001.md" in issue for issue in result.findings)
        )

    def test_rejected_finding_cannot_bypass_review_after_manuscript_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            manuscript.write_text(
                manuscript.read_text(encoding="utf-8")
                + "\n# Unreviewed Addition\n\nA new unreviewed claim was added.\n",
                encoding="utf-8",
            )
            resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
            row = resolution["resolutions"][0]
            row.update(
                {
                    "status": "REJECTED",
                    "decision": "REJECTED",
                    "adjudication": {
                        "changed_by": "editor",
                        "context_id": "ctx-editor",
                        "reason": "the original finding was rejected",
                    },
                    "history": [
                        {"from": "OPEN", "to": "REJECTED", "by": "editor", "at": "2026-08-23T00:00:00Z"}
                    ],
                }
            )
            resolution["status"] = "CLOSED"
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertFalse(result.ok)
        self.assertTrue(any("requires an append-only review cycle" in issue for issue in result.findings))

    def test_major_verification_requires_every_propagation_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            resolution = self._verified_resolution(outdir, manuscript)
            resolution["resolutions"][0]["change"]["propagation_checks"].pop()
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertFalse(result.ok)
        self.assertTrue(any("lacks propagation checks" in issue for issue in result.findings))

    def test_rerun_analysis_cannot_close_with_prose_only_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            resolution = self._verified_resolution(outdir, manuscript)
            resolution["resolutions"][0]["change"]["rerun_artifacts"] = []
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertFalse(result.ok)
        self.assertTrue(any("requires at least one rerun artifact" in issue for issue in result.findings))

    def test_rerun_analysis_requires_exact_method_execution_artifact_registration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            resolution = self._verified_resolution(outdir, manuscript)
            unregistered = outdir / "analysis" / "unregistered.csv"
            unregistered.parent.mkdir(parents=True, exist_ok=True)
            unregistered.write_text("estimate\n0.9\n", encoding="utf-8")
            resolution["resolutions"][0]["change"]["rerun_artifacts"] = [
                {
                    "artifact_id": "ART-UNREGISTERED-001",
                    "kind": "execution",
                    "path": "analysis/unregistered.csv",
                    "sha256": digest(unregistered),
                }
            ]
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertFalse(result.ok)
        self.assertTrue(
            any("must exactly match method_execution.json runs[].artifacts" in issue for issue in result.findings)
        )

    def test_controller_and_source_review_files_cannot_be_rerun_artifacts(self) -> None:
        for relative in ("workflow_config.json", "review_prompts/methods_review_output.md"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as tmp:
                outdir, manuscript = self._major_workspace(Path(tmp))
                resolution = self._verified_resolution(outdir, manuscript)
                target = outdir / relative
                resolution["resolutions"][0]["change"]["rerun_artifacts"] = [
                    {
                        "artifact_id": "ART-FORGED-001",
                        "kind": "execution",
                        "path": relative,
                        "sha256": digest(target),
                    }
                ]
                write_json(outdir / "review_resolution.json", resolution)
                self._render(outdir)
                result = review_lifecycle.validate_lifecycle(outdir, manuscript)
            self.assertFalse(result.ok)
            self.assertTrue(
                any("cannot reuse a controller, prompt, raw review" in issue for issue in result.findings)
            )

    def test_non_rerun_scientific_repair_also_denies_workflow_config_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._workspace(
                Path(tmp),
                methods=finding_review(
                    "methods",
                    repair_kind="ADD_EVIDENCE",
                    owner_stage="research",
                ),
                claim_ids=("CLM-001",),
            )
            self.assertTrue(self._compile(outdir, manuscript).ok)
            resolution = self._verified_resolution(outdir, manuscript)
            row = resolution["resolutions"][0]
            row["earliest_reopen_stage"] = "research"
            row["change"]["rerun_artifacts"] = [
                {
                    "artifact_id": "SRC-FORGED-001",
                    "kind": "evidence",
                    "path": "workflow_config.json",
                    "sha256": digest(outdir / "workflow_config.json"),
                }
            ]
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertFalse(result.ok)
        self.assertTrue(
            any("cannot reuse a controller, prompt, raw review" in issue for issue in result.findings)
        )

    def test_review_cycle_covers_all_actual_changed_units(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            resolution = self._verified_resolution(outdir, manuscript)
            resolution["review_cycles"][0]["reviewed_unit_ids"] = ["MSU-UNRELATED"]
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        joined = "\n".join(result.findings)
        self.assertFalse(result.ok)
        self.assertIn("reviewed units omit actual changed units", joined)
        self.assertIn("RC-001", joined)

    def test_independent_mode_rejects_duplicate_contexts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._workspace(
                Path(tmp), contexts=("same-context", "same-context", "ctx-clarity")
            )
            result = self._compile(outdir, manuscript)
        self.assertFalse(result.ok)
        self.assertTrue(any("distinct context_id" in issue for issue in result.findings))

    def test_independent_mode_rejects_duplicate_output_sha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._workspace(Path(tmp))
            review_dir = outdir / "review_prompts"
            methods = review_dir / "methods_review_output.md"
            contribution = review_dir / "contribution_review_output.md"
            contribution.write_bytes(methods.read_bytes())
            assurance = json.loads((outdir / "review_assurance.json").read_text(encoding="utf-8"))
            assurance["reviewers"][1]["output_sha256"] = digest(contribution)
            write_json(outdir / "review_assurance.json", assurance)
            result = self._compile(outdir, manuscript)
        self.assertFalse(result.ok)
        self.assertTrue(any("distinct output SHA-256" in issue for issue in result.findings))

    def test_single_agent_mode_records_non_isolation_without_claiming_independence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._workspace(
                Path(tmp),
                mode="single_agent",
                contexts=("ctx-main", "ctx-main", "ctx-main"),
            )
            result = self._compile(outdir, manuscript)
            registry = json.loads((outdir / "review_findings.json").read_text(encoding="utf-8"))
        self.assertTrue(result.ok, result.findings)
        self.assertFalse(registry["provenance"]["provenance_independence"])
        self.assertTrue(
            all(source["isolation_declared"] is False for source in registry["source_reviews"])
        )

    def test_single_agent_mode_cannot_declare_isolation_true(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._workspace(Path(tmp), mode="single_agent")
            assurance = json.loads((outdir / "review_assurance.json").read_text(encoding="utf-8"))
            for reviewer in assurance["reviewers"]:
                reviewer["isolation_declared"] = True
            write_json(outdir / "review_assurance.json", assurance)
            result = self._compile(outdir, manuscript)
        self.assertFalse(result.ok)
        self.assertTrue(any("isolation=false" in issue for issue in result.findings))

    def test_independent_mode_requires_isolation_true(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._workspace(Path(tmp))
            assurance = json.loads((outdir / "review_assurance.json").read_text(encoding="utf-8"))
            assurance["reviewers"][0]["isolation_declared"] = False
            write_json(outdir / "review_assurance.json", assurance)
            result = self._compile(outdir, manuscript)
        self.assertFalse(result.ok)
        self.assertTrue(any("isolation=true" in issue for issue in result.findings))

    def test_duplicate_resolution_row_cannot_hide_coverage_ambiguity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
            resolution["resolutions"].append(dict(resolution["resolutions"][0]))
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertFalse(result.ok)
        self.assertTrue(
            any(
                "repeats Finding ID" in issue or "array items must be unique" in issue
                for issue in result.findings
            )
        )

    def test_v1_assurance_is_read_only_needs_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            write_json(
                outdir / "review_assurance.json",
                {"schema_version": "cnki-review-assurance/v1", "mode": "independent", "reviewers": []},
            )
            summary = review_lifecycle.assurance_summary(outdir)
            controller_ready, controller_issues = cli.review_assurance_status(outdir)
        self.assertTrue(summary["valid"])
        self.assertFalse(summary["lifecycle_ready"])
        self.assertEqual("legacy_read_only_needs_review", summary["status"])
        self.assertFalse(controller_ready)
        self.assertTrue(any("read-only historical evidence" in issue for issue in controller_issues))

    def test_unverified_venue_cannot_be_scored_applicable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            contribution = pass_review("contribution").replace(
                "| CON-VENUE-FIT | BLOCKED | N/A | The verified venue contract declares this dimension blocked for this review run. | N/A |",
                "| CON-VENUE-FIT | APPLICABLE | 5 | General impressions suggest a strong venue match for the manuscript. | Introduction, paragraph 1 |",
            )
            outdir, manuscript = self._workspace(Path(tmp), contribution=contribution)
            result = self._compile(outdir, manuscript)
        self.assertFalse(result.ok)
        self.assertTrue(any("CON-VENUE-FIT applicability" in issue for issue in result.findings))

    def test_markdown_tampering_cannot_change_lifecycle_truth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._workspace(Path(tmp))
            self.assertTrue(self._compile(outdir, manuscript).ok)
            self._render(outdir)
            (outdir / "reviewer_audit.md").write_text("# forged PASS\n", encoding="utf-8")
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertFalse(result.ok)
        self.assertTrue(any("not the current JSON-derived view" in issue for issue in result.findings))

    def test_profile_routes_are_plan_only_and_stage_aware(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, _ = self._major_workspace(Path(tmp))
            registry = json.loads((outdir / "review_findings.json").read_text(encoding="utf-8"))
            resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
            open_plan = review_lifecycle.review_route_plan(registry, resolution, profile="full_paper")
            resolution["resolutions"][0].update(
                {
                    "status": "PLANNED",
                    "decision": "ACCEPTED",
                    "history": [
                        {"from": "OPEN", "to": "PLANNED", "by": "editor", "at": "2026-08-23T00:00:00Z"}
                    ],
                }
            )
            full = review_lifecycle.review_route_plan(registry, resolution, profile="full_paper")
            audit = review_lifecycle.review_route_plan(registry, resolution, profile="manuscript_audit")
            revision = review_lifecycle.review_route_plan(registry, resolution, profile="manuscript_revision")
            authorized_contract = self._authorized_revision_contract(registry, outdir)
            write_json(outdir / "revision_contract.json", authorized_contract)
            contract_before = (outdir / "revision_contract.json").read_bytes()
            linked = review_lifecycle.review_route_plan(
                registry,
                resolution,
                profile="manuscript_revision",
                revision_contract=authorized_contract,
                outdir=outdir,
            )
            contract_unchanged = (outdir / "revision_contract.json").read_bytes() == contract_before
        self.assertIsNone(open_plan["effective_earliest_reopen_stage"])
        self.assertEqual("adjudicate_and_plan_review_findings", open_plan["action"])
        self.assertEqual("execution", full["effective_earliest_reopen_stage"])
        self.assertEqual("reopen_existing_full_paper_stage", full["action"])
        self.assertEqual("request_profile_expansion", audit["action"])
        self.assertEqual("request_revision_contract_amendment", revision["action"])
        self.assertEqual("follow_authorized_revision_contract", linked["action"])
        self.assertTrue(linked["revision_contract_linked"])
        self.assertTrue(contract_unchanged)

    def test_applied_finding_stays_in_audit_for_independent_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, _ = self._major_workspace(Path(tmp))
            registry = json.loads((outdir / "review_findings.json").read_text(encoding="utf-8"))
            resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
            resolution["resolutions"][0].update(
                {
                    "status": "APPLIED",
                    "decision": "ACCEPTED",
                    "history": [
                        {"from": "OPEN", "to": "PLANNED", "by": "editor", "at": "2026-08-23T00:00:00Z"},
                        {"from": "PLANNED", "to": "APPLIED", "by": "writer", "at": "2026-08-23T01:00:00Z"},
                    ],
                }
            )
            route = review_lifecycle.review_route_plan(registry, resolution, profile="full_paper")
        self.assertEqual("AWAITING_VERIFICATION", route["status"])
        self.assertEqual("await_independent_verification", route["action"])
        self.assertIsNone(route["effective_earliest_reopen_stage"])
        self.assertEqual([], route["routable_finding_ids"])

    def test_registry_provenance_mode_tamper_cannot_be_resealed_downstream(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._workspace(
                Path(tmp), mode="single_agent", contexts=("ctx-main",) * 3
            )
            self.assertTrue(self._compile(outdir, manuscript).ok)
            registry = json.loads((outdir / "review_findings.json").read_text(encoding="utf-8"))
            registry["provenance"]["mode"] = "independent"
            registry["provenance"]["provenance_independence"] = True
            write_json(outdir / "review_findings.json", registry)
            resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
            resolution["findings_sha256"] = digest(outdir / "review_findings.json")
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertFalse(result.ok)
        self.assertTrue(any("provenance no longer equals" in issue for issue in result.findings))

    def test_dispatch_authority_inputs_cannot_drift_after_compilation(self) -> None:
        for relative, mutate in (
            (
                "confirmed_contribution.md",
                lambda payload: payload + "\nChanged confirmed contribution.\n",
            ),
            (
                "workflow_config.json",
                lambda payload: payload.replace(
                    '"scene": "journal"',
                    '"scene": "journal",\n  "target_name": "Changed Venue"',
                ),
            ),
        ):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as tmp:
                outdir, manuscript = self._workspace(Path(tmp))
                self.assertTrue(self._compile(outdir, manuscript).ok)
                self._render(outdir)
                target = outdir / relative
                target.write_text(mutate(target.read_text(encoding="utf-8")), encoding="utf-8")
                result = review_lifecycle.validate_lifecycle(outdir, manuscript)
            self.assertFalse(result.ok)
            self.assertTrue(any("root review inputs changed" in issue for issue in result.findings))

    def test_registered_schema_shape_is_enforced_at_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
            resolution["resolutions"][0].pop("verification")
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            missing_result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertTrue(any("missing required property verification" in issue for issue in missing_result.findings))

        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._workspace(Path(tmp))
            self.assertTrue(self._compile(outdir, manuscript).ok)
            assurance = json.loads((outdir / "review_assurance.json").read_text(encoding="utf-8"))
            assurance["invented_completion_truth"] = True
            write_json(outdir / "review_assurance.json", assurance)
            self._render(outdir)
            assurance_result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertIn(
            "unexpected property invented_completion_truth",
            "\n".join(assurance_result.findings),
        )

        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._workspace(Path(tmp))
            self.assertTrue(self._compile(outdir, manuscript).ok)
            registry = json.loads((outdir / "review_findings.json").read_text(encoding="utf-8"))
            registry["unexpected"] = "forged"
            write_json(outdir / "review_findings.json", registry)
            resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
            resolution["findings_sha256"] = digest(outdir / "review_findings.json")
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            extra_result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        joined = "\n".join(extra_result.findings)
        self.assertIn("unexpected property unexpected", joined)

    def test_malformed_contract_shapes_fail_closed_without_exceptions(self) -> None:
        mutations = (
            ("registry", lambda registry, resolution, assurance: registry.update({"manuscript": "bad"})),
            ("resolution", lambda registry, resolution, assurance: resolution.update({"resolutions": "bad"})),
            ("assurance", lambda registry, resolution, assurance: assurance.update({"reviewers": "bad"})),
        )
        for label, mutate in mutations:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                outdir, manuscript = self._workspace(Path(tmp))
                self.assertTrue(self._compile(outdir, manuscript).ok)
                registry = json.loads((outdir / "review_findings.json").read_text(encoding="utf-8"))
                resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
                assurance = json.loads((outdir / "review_assurance.json").read_text(encoding="utf-8"))
                mutate(registry, resolution, assurance)
                write_json(outdir / "review_findings.json", registry)
                resolution["findings_sha256"] = digest(outdir / "review_findings.json")
                write_json(outdir / "review_resolution.json", resolution)
                write_json(outdir / "review_assurance.json", assurance)
                result = review_lifecycle.validate_lifecycle(
                    outdir, manuscript, require_views=False
                )
            self.assertFalse(result.ok)
            self.assertTrue(any("schema:" in issue for issue in result.findings), result.findings)

    def test_identity_mapping_is_a_deterministic_compiler_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._workspace(
                Path(tmp),
                methods=finding_review("methods"),
                claim_rows=(
                    ("CLM-001", "The baseline comparison is omitted."),
                    ("CLM-999", "An unrelated registered statement."),
                ),
            )
            self.assertTrue(self._compile(outdir, manuscript).ok)
            registry = json.loads((outdir / "review_findings.json").read_text(encoding="utf-8"))
            registry["findings"][0]["identity_mapping"]["claim_ids"] = ["CLM-999"]
            write_json(outdir / "review_findings.json", registry)
            resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
            resolution["findings_sha256"] = digest(outdir / "review_findings.json")
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertFalse(result.ok)
        self.assertTrue(any("deterministic compiler projection" in issue for issue in result.findings))

    def test_verified_change_must_cover_every_mapped_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._workspace(
                Path(tmp),
                methods=finding_review("methods"),
                claim_ids=("CLM-001", "CLM-002"),
            )
            self.assertTrue(self._compile(outdir, manuscript).ok)
            resolution = self._verified_resolution(outdir, manuscript)
            self.assertEqual(
                ["CLM-001", "CLM-002"],
                json.loads((outdir / "review_findings.json").read_text(encoding="utf-8"))["findings"][0]["identity_mapping"]["claim_ids"],
            )
            resolution["resolutions"][0]["change"]["affected_claim_ids"] = ["CLM-001"]
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertFalse(result.ok)
        self.assertTrue(any("does not cover every mapped claim_ids: CLM-002" in issue for issue in result.findings))

    def test_adjudicated_final_severity_drives_recommendation_and_critical_waiver_gate(self) -> None:
        registry = {
            "findings": [{"finding_id": "REV-MET-001", "severity": "MAJOR"}]
        }
        row = {
            "finding_id": "REV-MET-001",
            "status": "PLANNED",
            "final_severity": "CRITICAL",
            "adjudication": {"changed_by": "editor", "context_id": "ctx", "reason": "upgraded"},
        }
        self.assertEqual("BLOCK", review_lifecycle.lifecycle_recommendation(registry, {"resolutions": [row]}))
        registry["findings"][0]["severity"] = "CRITICAL"
        row["final_severity"] = "MINOR"
        row["adjudication"]["reason"] = "downgraded with evidence"
        self.assertEqual("MINOR_REVISION", review_lifecycle.lifecycle_recommendation(registry, {"resolutions": [row]}))

        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
            waived = resolution["resolutions"][0]
            waived.update(
                {
                    "status": "WAIVED",
                    "decision": "WAIVED",
                    "final_severity": "CRITICAL",
                    "adjudication": {"changed_by": "editor", "context_id": "ctx", "reason": "upgraded"},
                    "authorization": {
                        "authorized_by": "editor",
                        "authorization_evidence": "explicit",
                        "risk_statement": "accepted",
                    },
                    "history": [{"from": "OPEN", "to": "WAIVED", "by": "editor", "at": "now"}],
                }
            )
            resolution["status"] = "CLOSED"
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertTrue(any("Critical findings cannot be WAIVED" in issue for issue in result.findings))

    def test_mixed_verified_and_rejected_closure_uses_global_delta_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._workspace(
                Path(tmp),
                methods=finding_review("methods"),
                contribution=finding_review("contribution"),
                claim_ids=("CLM-001",),
            )
            self.assertTrue(self._compile(outdir, manuscript).ok)
            scaffold = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
            contribution = next(
                row for row in scaffold["resolutions"] if row["finding_id"] == "REV-CON-001"
            )
            contribution.update(
                {
                    "status": "REJECTED",
                    "decision": "REJECTED",
                    "adjudication": {
                        "changed_by": "editor",
                        "context_id": "ctx-editor",
                        "reason": "the contribution concern duplicates no actual manuscript defect",
                    },
                    "history": [
                        {"from": "OPEN", "to": "REJECTED", "by": "editor", "at": "2026-08-23T00:00:00Z"}
                    ],
                }
            )
            resolution = self._verified_resolution(outdir, manuscript)
            resolution["resolutions"].append(contribution)
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertTrue(result.ok, result.findings)

    def test_profile_authorization_issues_block_lifecycle_receipt(self) -> None:
        for profile in ("manuscript_audit", "manuscript_revision"):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as tmp:
                outdir, manuscript = self._major_workspace(Path(tmp), profile=profile)
                resolution = self._verified_resolution(outdir, manuscript)
                write_json(outdir / "review_resolution.json", resolution)
                self._render(outdir)
                result = review_lifecycle.validate_lifecycle(outdir, manuscript)
            self.assertFalse(result.ok)
            self.assertTrue(any("review profile authorization" in issue for issue in result.findings))

        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp), profile="manuscript_revision")
            registry = json.loads((outdir / "review_findings.json").read_text(encoding="utf-8"))
            resolution = self._verified_resolution(outdir, manuscript)
            write_json(
                outdir / "revision_contract.json",
                self._authorized_revision_contract(registry, outdir),
            )
            write_json(outdir / "review_resolution.json", resolution)
            self._render(outdir)
            result = review_lifecycle.validate_lifecycle(outdir, manuscript)
        self.assertTrue(result.ok, result.findings)

    def test_revision_contract_must_bind_baseline_route_and_mapped_identities(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, _ = self._major_workspace(Path(tmp))
            registry = json.loads((outdir / "review_findings.json").read_text(encoding="utf-8"))
            resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
            resolution["resolutions"][0].update(
                {
                    "status": "PLANNED",
                    "decision": "ACCEPTED",
                    "history": [{"from": "OPEN", "to": "PLANNED", "by": "editor", "at": "now"}],
                }
            )
            contract = self._authorized_revision_contract(registry, outdir)
            contract["baseline"]["path"] = "other.md"
            contract["baseline"]["sha256"] = "0" * 64
            contract["affected_identities"]["claim_ids"] = ["CLM-OTHER"]
            write_json(outdir / "revision_contract.json", contract)
            route = review_lifecycle.review_route_plan(
                registry,
                resolution,
                profile="manuscript_revision",
                revision_contract=contract,
                outdir=outdir,
            )
        joined = "\n".join(route["issues"])
        self.assertIn("baseline path/SHA", joined)
        self.assertIn("does not authorize mapped claim_ids: CLM-001", joined)
        self.assertFalse(route["revision_contract_linked"])

    def test_revision_contract_snapshot_must_exist_and_match(self) -> None:
        for mutation in ("missing", "tampered"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                outdir, _ = self._major_workspace(Path(tmp))
                registry = json.loads((outdir / "review_findings.json").read_text(encoding="utf-8"))
                resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
                resolution["resolutions"][0].update(
                    {
                        "status": "PLANNED",
                        "decision": "ACCEPTED",
                        "history": [{"from": "OPEN", "to": "PLANNED", "by": "editor", "at": "now"}],
                    }
                )
                contract = self._authorized_revision_contract(registry, outdir)
                write_json(outdir / "revision_contract.json", contract)
                snapshot = outdir / contract["baseline"]["snapshot_path"]
                if mutation == "missing":
                    snapshot.unlink()
                else:
                    snapshot.write_text("tampered baseline", encoding="utf-8")
                route = review_lifecycle.review_route_plan(
                    registry,
                    resolution,
                    profile="manuscript_revision",
                    revision_contract=contract,
                    outdir=outdir,
                )
            joined = "\n".join(route["issues"])
            self.assertIn("baseline snapshot", joined)
            self.assertFalse(route["revision_contract_linked"])

    def test_full_paper_planned_route_projects_next_stage_without_applying(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, _ = self._major_workspace(Path(tmp))
            resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
            resolution["resolutions"][0].update(
                {
                    "status": "PLANNED",
                    "decision": "ACCEPTED",
                    "history": [{"from": "OPEN", "to": "PLANNED", "by": "editor", "at": "now"}],
                }
            )
            write_json(outdir / "review_resolution.json", resolution)
            payload = {"next_stage": "audit", "is_complete": False}
            with patch.object(cli, "audit_receipt_status", return_value=(False, "pending")):
                projected, _ = cli._finish_from_receipts(payload, outdir)
        self.assertEqual("execution", projected["next_stage"])
        self.assertEqual("review_stage_reopen_plan", projected["next_checkpoint"])

    def test_reviewer_audit_renders_adjudication_merge_and_waiver_evidence(self) -> None:
        registry = {
            "review_run_id": "REV-0000000000000000",
            "status": "HAS_FINDINGS",
            "source_reviews": [],
            "findings": [
                {
                    "finding_id": "REV-MET-001",
                    "severity": "MAJOR",
                    "source": {"reviewer_role": "methods"},
                    "manuscript_locator": {"location": "Methods"},
                    "recommended_action": {"repair_kind": "TEXT_EDIT", "owner_stage": "build"},
                    "identity_mapping": {"mapping_status": "exact"},
                }
            ],
        }
        resolution = {
            "resolutions": [
                {
                    "finding_id": "REV-MET-001",
                    "status": "WAIVED",
                    "final_severity": "MAJOR",
                    "adjudication": {"changed_by": "editor", "context_id": "ctx-editor", "reason": "reasoned"},
                    "merge_target_finding_id": "REV-CON-001",
                    "authorization": {
                        "authorized_by": "owner",
                        "authorization_evidence": "signed decision",
                        "risk_statement": "known risk",
                    },
                }
            ],
            "post_revision_review": None,
        }
        rendered = review_lifecycle.render_reviewer_audit(registry, resolution)
        self.assertIn("adjudicated by editor [ctx-editor]: reasoned", rendered)
        self.assertIn("merged into REV-CON-001", rendered)
        self.assertIn("waived by owner; evidence=signed decision; risk=known risk", rendered)

    def test_all_json_derived_tables_escape_pipe_backslash_and_newline_cells(self) -> None:
        injected = "Methods | forged\\path\n| FAKE | VERIFIED |"
        registry = {
            "review_run_id": "REV-0000000000000000",
            "status": "HAS_FINDINGS",
            "manuscript": {"path": "final_paper/main.md", "sha256": "0" * 64},
            "provenance": {},
            "source_reviews": [
                {
                    "role": "methods",
                    "verdict": "FINDINGS",
                    "context_id": "ctx\\methods|fake\nrow",
                    "output_path": "review_prompts/methods_review_output.md",
                    "output_sha256": "1" * 64,
                    "rubric": [
                        {
                            "dimension_id": "MET-RIGOR",
                            "applicability": "APPLICABLE",
                            "score": 2,
                            "reason": injected,
                            "manuscript_location": injected,
                        }
                    ],
                }
            ],
            "findings": [
                {
                    "finding_id": "REV-MET-001",
                    "severity": "MAJOR",
                    "confidence": "HIGH",
                    "source": {"reviewer_role": "methods"},
                    "manuscript_locator": {"location": injected},
                    "recommended_action": {
                        "repair_kind": "TEXT_EDIT",
                        "owner_stage": "build",
                    },
                    "identity_mapping": {
                        "mapping_status": "exact",
                        "claim_ids": [injected],
                        "evidence_ids": [],
                        "design_ids": [],
                        "execution_ids": [],
                    },
                }
            ],
        }
        resolution = {
            "resolutions": [
                {
                    "finding_id": "REV-MET-001",
                    "status": "REJECTED",
                    "final_severity": "MAJOR",
                    "earliest_reopen_stage": "build",
                    "adjudication": {
                        "changed_by": "editor",
                        "context_id": "ctx-editor",
                        "reason": injected,
                    },
                }
            ],
            "post_revision_review": None,
        }
        rendered_views = (
            review_lifecycle.render_structured_review(registry, resolution),
            review_lifecycle.render_reviewer_audit(registry, resolution),
            review_lifecycle.render_revision_plan(registry, resolution),
        )
        for rendered in rendered_views:
            self.assertIn("&#124;", rendered)
            self.assertIn("&#92;", rendered)
            self.assertIn("<br>", rendered)
            table_cells = [
                cell.strip()
                for table in review_lifecycle.markdown_tables(rendered)
                for row in table
                for cell in row
            ]
            self.assertNotIn("FAKE", table_cells)
            self.assertNotIn("VERIFIED", table_cells)

    def test_audit_action_graph_orders_compile_and_closure_after_raw_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outdir, manuscript = self._workspace(root)
            config = json.loads((outdir / "workflow_config.json").read_text(encoding="utf-8"))
            skills_dir = Path(__file__).resolve().parents[4]
            names = [action.name for action in _actions(outdir, skills_dir, config, manuscript)]
        self.assertEqual(
            ["structured_review", "review_finding_compile", "review_lifecycle", "reviewer_assurance"],
            names[-4:],
        )
        self.assertGreater(names.index("structured_review"), names.index("contribution"))

    def test_finding_key_survives_issue_rewording_and_paragraph_move(self) -> None:
        base = {
            "category": "missing_baseline",
            "source": {"reviewer_role": "methods"},
            "manuscript_locator": {
                "location": "Methods paragraph 2",
                "quoted_span": "The baseline comparison is omitted.",
                "manuscript_unit_id": review_lifecycle._stable_manuscript_unit_id(
                    "The baseline comparison is omitted."
                ),
            },
            "recommended_action": {"repair_kind": "RERUN_ANALYSIS"},
            "identity_mapping": {
                "claim_ids": ["CLM-001"], "evidence_ids": [],
                "design_ids": [], "execution_ids": ["EXE-001"],
            },
            "problem": "The manuscript omits the baseline comparison.",
        }
        moved = json.loads(json.dumps(base))
        moved["problem"] = "A required comparator is absent from the reported analysis."
        moved["manuscript_locator"]["location"] = "Appendix paragraph 7"
        self.assertEqual(review_lifecycle.finding_key(base), review_lifecycle.finding_key(moved))

    def test_second_reopen_requires_structured_root_cause(self) -> None:
        finding = {
            "finding_id": "REV-MET-001", "finding_key": "RFK-" + "A" * 24,
            "materiality": "BLOCKING",
        }
        registry = {"status": "HAS_FINDINGS", "findings": [finding]}
        resolution = {
            "resolutions": [{
                "finding_id": "REV-MET-001", "finding_key": finding["finding_key"],
                "status": "REOPENED", "reopen_count": 2, "root_cause_analysis": None,
            }],
            "review_cycles": [],
        }
        review_lifecycle._refresh_convergence(registry, resolution)
        self.assertEqual("ROOT_CAUSE_REQUIRED", resolution["convergence"]["status"])
        resolution["resolutions"][0]["root_cause_analysis"] = {
            "instruction_failure": "The repair instruction targeted wording, not the estimator.",
            "owner_stage_check": "execution",
            "rewrite_scope": "Methods and propagated conclusion",
            "claim_or_evidence_change": "Execution artifact and CLM-001 change",
            "reviewer_conflict": "none",
            "next_strategy": "rerun the registered comparison before rewriting",
        }
        review_lifecycle._refresh_convergence(registry, resolution)
        self.assertEqual("ACTIVE", resolution["convergence"]["status"])

    def test_blocked_review_cycle_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            registry = json.loads((outdir / "review_findings.json").read_text(encoding="utf-8"))
            before = registry["manuscript"]["sha256"]
            manuscript.write_text(manuscript.read_text(encoding="utf-8") + "\nA clarification.\n", encoding="utf-8")
            after = digest(manuscript)
            impact = {
                "schema_version": "avereth-revision-impact/v1", "batch_id": "RB-001",
                "before_sha256": before, "after_sha256": after,
                "changed_unit_ids": ["MSU-CHANGED"],
                "changed_unit_context": [{
                    "unit_id": "MSU-CHANGED", "before": None,
                    "after": {"section": "document", "text": "A clarification."},
                }],
                "required_reviewers": ["clarity"], "full_review_required": False,
                "preflight_status": "PASS",
            }
            write_json(outdir / "revision_impact.json", impact)
            structured_review.dispatch_delta_review(
                outdir, manuscript, outdir / "revision_impact.json", cycle_id="RC-001"
            )
            cycle_dir = outdir / "review_prompts" / "cycles" / "RC-001"
            prompt = cycle_dir / "clarity_delta_reviewer.md"
            write_json(
                cycle_dir / "cycle_assurance.json",
                {
                    "schema_version": "avereth-review-cycle-assurance/v1",
                    "cycle_id": "RC-001", "mode": "independent", "result": "BLOCKED",
                    "block_reason": "reviewer context unavailable after dispatch",
                    "reviewers": [{
                        "role": "clarity", "context_id": "ctx-blocked",
                        "prompt_path": "review_prompts/cycles/RC-001/clarity_delta_reviewer.md",
                        "prompt_sha256": digest(prompt),
                        "output_path": "review_prompts/cycles/RC-001/clarity_delta_output.md",
                        "output_sha256": "",
                    }],
                },
            )
            result = review_lifecycle.compile_review_cycle(
                outdir, "RC-001", manuscript, write=True
            )
            resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
        self.assertFalse(result.ok)
        self.assertEqual("BLOCKED", resolution["review_cycles"][-1]["result"])
        self.assertEqual("reviewer context unavailable after dispatch", resolution["review_cycles"][-1]["block_reason"])

    def test_delta_dispatch_reuses_identical_role_projection_after_whole_sha_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            registry = json.loads((outdir / "review_findings.json").read_text(encoding="utf-8"))
            before = registry["manuscript"]["sha256"]
            manuscript.write_text(manuscript.read_text(encoding="utf-8") + "\nA clarification.\n", encoding="utf-8")
            impact = {
                "schema_version": "avereth-revision-impact/v1", "batch_id": "RB-001",
                "before_sha256": before, "after_sha256": digest(manuscript),
                "changed_unit_ids": ["MSU-CHANGED"],
                "changed_unit_context": [{
                    "unit_id": "MSU-CHANGED", "before": None,
                    "after": {"section": "document", "text": "A clarification."},
                }],
                "required_reviewers": ["clarity"], "full_review_required": False,
                "preflight_status": "PASS",
            }
            write_json(outdir / "revision_impact.json", impact)
            first = structured_review.dispatch_delta_review(
                outdir, manuscript, outdir / "revision_impact.json", cycle_id="RC-001"
            )
            delta_prompt = (
                outdir / "review_prompts" / "cycles" / "RC-001" / "clarity_delta_reviewer.md"
            ).read_text(encoding="utf-8")
            self.assertIn("A clarification.", delta_prompt)
            self.assertNotIn("The claimed contrast is decisive.", delta_prompt)
            self.assertNotIn("## Complete Canonical Manuscript", delta_prompt)
            resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
            resolution["review_cycles"].append(
                {
                    "cycle_id": "RC-001",
                    "role_input_digests": first["role_input_digests"],
                    "role_results": {"clarity": "PASS"},
                }
            )
            write_json(outdir / "review_resolution.json", resolution)
            manuscript.write_text(manuscript.read_text(encoding="utf-8") + "\nUnrelated appendix metadata.\n", encoding="utf-8")
            impact["after_sha256"] = digest(manuscript)
            write_json(outdir / "revision_impact.json", impact)
            second = structured_review.dispatch_delta_review(
                outdir, manuscript, outdir / "revision_impact.json", cycle_id="RC-002"
            )
        self.assertEqual(["clarity"], second["reused_reviewers"])
        self.assertEqual({"clarity": "RC-001"}, second["reused_from_cycles"])
        self.assertEqual([], second["dispatched_reviewers"])

    def test_delta_dispatch_authority_change_invalidates_relevant_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            registry = json.loads((outdir / "review_findings.json").read_text(encoding="utf-8"))
            before = registry["manuscript"]["sha256"]
            manuscript.write_text(manuscript.read_text(encoding="utf-8") + "\nA result clarification.\n", encoding="utf-8")
            impact = {
                "schema_version": "avereth-revision-impact/v1", "batch_id": "RB-001",
                "before_sha256": before, "after_sha256": digest(manuscript),
                "changed_unit_ids": ["MSU-CHANGED"],
                "changed_unit_context": [{
                    "unit_id": "MSU-CHANGED", "before": None,
                    "after": {"section": "results", "text": "A result clarification."},
                }],
                "affected_execution_ids": ["EXE-001"],
                "change_classes": ["execution"], "impact_radius": "LOCAL",
                "required_reviewers": ["methods"], "full_review_required": False,
                "preflight_status": "PASS",
            }
            write_json(outdir / "revision_impact.json", impact)
            first = structured_review.dispatch_delta_review(
                outdir, manuscript, outdir / "revision_impact.json", cycle_id="RC-001"
            )
            resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
            resolution["review_cycles"].append({
                "cycle_id": "RC-001", "role_input_digests": first["role_input_digests"],
                "role_results": {"methods": "PASS"},
            })
            write_json(outdir / "review_resolution.json", resolution)
            execution_path = outdir / "method_execution.json"
            execution_text = execution_path.read_text(encoding="utf-8")
            execution_path.write_text(
                execution_text.replace(
                    '"id": "EXE-001",',
                    '"id": "EXE-001", "review_visible_status": "reopened",',
                ),
                encoding="utf-8",
            )
            second = structured_review.dispatch_delta_review(
                outdir, manuscript, outdir / "revision_impact.json", cycle_id="RC-002"
            )
        self.assertNotEqual(first["role_input_digests"]["methods"], second["role_input_digests"]["methods"])
        self.assertEqual(["methods"], second["dispatched_reviewers"])
        self.assertEqual([], second["reused_reviewers"])

    def test_delta_dispatch_unprojected_authority_change_keeps_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            registry = json.loads((outdir / "review_findings.json").read_text(encoding="utf-8"))
            manuscript.write_text(manuscript.read_text(encoding="utf-8") + "\nA result clarification.\n", encoding="utf-8")
            impact = {
                "schema_version": "avereth-revision-impact/v1", "batch_id": "RB-001",
                "before_sha256": registry["manuscript"]["sha256"], "after_sha256": digest(manuscript),
                "changed_unit_ids": ["MSU-CHANGED"],
                "changed_unit_context": [{
                    "unit_id": "MSU-CHANGED", "before": None,
                    "after": {"section": "results", "text": "A result clarification."},
                }],
                "affected_execution_ids": ["EXE-001"],
                "change_classes": ["execution"], "impact_radius": "LOCAL",
                "required_reviewers": ["methods"], "full_review_required": False,
                "preflight_status": "PASS",
            }
            write_json(outdir / "revision_impact.json", impact)
            first = structured_review.dispatch_delta_review(
                outdir, manuscript, outdir / "revision_impact.json", cycle_id="RC-001"
            )
            resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
            resolution["review_cycles"].append({
                "cycle_id": "RC-001", "role_input_digests": first["role_input_digests"],
                "role_results": {"methods": "PASS"},
            })
            write_json(outdir / "review_resolution.json", resolution)
            execution = json.loads((outdir / "method_execution.json").read_text(encoding="utf-8"))
            execution["status"] = "reopened"
            write_json(outdir / "method_execution.json", execution)
            second = structured_review.dispatch_delta_review(
                outdir, manuscript, outdir / "revision_impact.json", cycle_id="RC-002"
            )
        self.assertEqual(first["role_input_digests"]["methods"], second["role_input_digests"]["methods"])
        self.assertEqual(["methods"], second["reused_reviewers"])
        self.assertEqual([], second["dispatched_reviewers"])

    def test_delta_dispatch_preserves_writing_method_without_expanding_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            registry = json.loads((outdir / "review_findings.json").read_text(encoding="utf-8"))
            manuscript.write_text(manuscript.read_text(encoding="utf-8") + "\nA conceptual distinction.\n", encoding="utf-8")
            impact = {
                "schema_version": "avereth-revision-impact/v1", "batch_id": "RB-001",
                "before_sha256": registry["manuscript"]["sha256"], "after_sha256": digest(manuscript),
                "changed_unit_ids": ["MSU-CHANGED"],
                "changed_unit_context": [{"unit_id": "MSU-CHANGED", "before": None,
                                          "after": {"section": "discussion", "text": "A conceptual distinction."}}],
                "change_classes": ["surface"], "impact_radius": "LOCAL",
                "required_reviewers": ["clarity", "contribution"], "full_review_required": False,
                "preflight_status": "PASS",
            }
            write_json(outdir / "revision_impact.json", impact)
            structured_review.dispatch_delta_review(outdir, manuscript, outdir / "revision_impact.json", cycle_id="RC-001")
            directory = outdir / "review_prompts/cycles/RC-001"
            clarity = (directory / "clarity_delta_reviewer.md").read_text(encoding="utf-8")
            contribution = (directory / "contribution_delta_reviewer.md").read_text(encoding="utf-8")
            self.assertIn("not a mandated sentence order", clarity)
            self.assertIn("a clear long sentence", clarity)
            self.assertIn("analogy is not independent corroboration", clarity)
            self.assertIn("adds, revises, rejects, or reorganizes", contribution)
            self.assertIn("Do not assess or infer omitted, unchanged manuscript text", clarity)

    def test_delta_dispatch_role_impact_change_invalidates_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            registry = json.loads((outdir / "review_findings.json").read_text(encoding="utf-8"))
            manuscript.write_text(manuscript.read_text(encoding="utf-8") + "\nA clarification.\n", encoding="utf-8")
            impact = {
                "schema_version": "avereth-revision-impact/v1", "batch_id": "RB-001",
                "before_sha256": registry["manuscript"]["sha256"], "after_sha256": digest(manuscript),
                "changed_unit_ids": ["MSU-CHANGED"],
                "changed_unit_context": [{
                    "unit_id": "MSU-CHANGED", "before": None,
                    "after": {"section": "document", "text": "A clarification."},
                }],
                "change_classes": ["surface"], "impact_radius": "LOCAL",
                "required_reviewers": ["clarity"], "full_review_required": False,
                "preflight_status": "PASS",
            }
            write_json(outdir / "revision_impact.json", impact)
            first = structured_review.dispatch_delta_review(
                outdir, manuscript, outdir / "revision_impact.json", cycle_id="RC-001"
            )
            resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
            resolution["review_cycles"].append({
                "cycle_id": "RC-001", "role_input_digests": first["role_input_digests"],
                "role_results": {"clarity": "PASS"},
            })
            write_json(outdir / "review_resolution.json", resolution)
            impact["impact_radius"] = "DOCUMENT"
            write_json(outdir / "revision_impact.json", impact)
            second = structured_review.dispatch_delta_review(
                outdir, manuscript, outdir / "revision_impact.json", cycle_id="RC-002"
            )
        self.assertNotEqual(first["role_input_digests"]["clarity"], second["role_input_digests"]["clarity"])
        self.assertEqual(["clarity"], second["dispatched_reviewers"])

    def test_full_dispatch_reviews_complete_manuscript_with_all_roles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            registry = json.loads((outdir / "review_findings.json").read_text(encoding="utf-8"))
            manuscript.write_text(manuscript.read_text(encoding="utf-8") + "\nChanged design sentence.\n", encoding="utf-8")
            impact = {
                "schema_version": "avereth-revision-impact/v1", "batch_id": "RB-001",
                "before_sha256": registry["manuscript"]["sha256"], "after_sha256": digest(manuscript),
                "changed_unit_ids": ["MSU-CHANGED"],
                "changed_unit_context": [{
                    "unit_id": "MSU-CHANGED", "before": None,
                    "after": {"section": "methods", "text": "Changed design sentence."},
                }],
                "change_classes": ["design"], "impact_radius": "DOCUMENT",
                "required_reviewers": ["methods", "contribution", "clarity"],
                "full_review_required": True, "preflight_status": "PASS",
            }
            write_json(outdir / "revision_impact.json", impact)
            dispatched = structured_review.dispatch_delta_review(
                outdir, manuscript, outdir / "revision_impact.json", cycle_id="RC-001"
            )
            prompts = [
                (outdir / relative).read_text(encoding="utf-8")
                for relative in dispatched["files"]
            ]
        self.assertEqual("FULL", dispatched["mode"])
        self.assertEqual(["methods", "contribution", "clarity"], dispatched["dispatched_reviewers"])
        self.assertEqual(["MSU-CHANGED"], dispatched["reviewed_unit_ids"])
        self.assertEqual(3, len(prompts))
        for prompt in prompts:
            self.assertIn("Review the complete canonical manuscript", prompt)
            self.assertIn("## Complete Canonical Manuscript", prompt)
            self.assertIn("The baseline comparison is omitted.", prompt)
            self.assertIn("The claimed contrast is decisive.", prompt)
            self.assertIn("## Role Rubric", prompt)

    def test_delta_dispatch_implementation_change_invalidates_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, manuscript = self._major_workspace(Path(tmp))
            registry = json.loads((outdir / "review_findings.json").read_text(encoding="utf-8"))
            manuscript.write_text(manuscript.read_text(encoding="utf-8") + "\nA clarification.\n", encoding="utf-8")
            impact = {
                "schema_version": "avereth-revision-impact/v1", "batch_id": "RB-001",
                "before_sha256": registry["manuscript"]["sha256"], "after_sha256": digest(manuscript),
                "changed_unit_ids": ["MSU-CHANGED"],
                "changed_unit_context": [{
                    "unit_id": "MSU-CHANGED", "before": None,
                    "after": {"section": "document", "text": "A clarification."},
                }],
                "change_classes": ["surface"], "impact_radius": "LOCAL",
                "required_reviewers": ["clarity"], "full_review_required": False,
                "preflight_status": "PASS",
            }
            write_json(outdir / "revision_impact.json", impact)
            first = structured_review.dispatch_delta_review(
                outdir, manuscript, outdir / "revision_impact.json", cycle_id="RC-001"
            )
            resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
            resolution["review_cycles"].append({
                "cycle_id": "RC-001", "role_input_digests": first["role_input_digests"],
                "role_results": {"clarity": "PASS"},
            })
            write_json(outdir / "review_resolution.json", resolution)
            with patch.object(
                structured_review,
                "_delta_reviewer_implementation_digest",
                return_value="f" * 64,
            ):
                second = structured_review.dispatch_delta_review(
                    outdir, manuscript, outdir / "revision_impact.json", cycle_id="RC-002"
                )
        self.assertNotEqual(first["role_input_digests"]["clarity"], second["role_input_digests"]["clarity"])
        self.assertEqual(["clarity"], second["dispatched_reviewers"])
        self.assertEqual([], second["reused_reviewers"])

    def test_legacy_review_pair_requires_explicit_migration_and_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir, _ = self._major_workspace(Path(tmp))
            registry = json.loads((outdir / "review_findings.json").read_text(encoding="utf-8"))
            resolution = json.loads((outdir / "review_resolution.json").read_text(encoding="utf-8"))
            registry["schema_version"] = review_lifecycle.LEGACY_FINDINGS_SCHEMA
            registry.pop("root_review_run_id", None)
            for item in registry["findings"]:
                for field in (
                    "finding_key", "first_seen_run_id", "last_seen_cycle_id", "discovery_class",
                    "materiality", "lineage", "occurrences",
                ):
                    item.pop(field, None)
                item["manuscript_locator"].pop("manuscript_unit_id", None)
            resolution["schema_version"] = review_lifecycle.LEGACY_RESOLUTION_SCHEMA
            resolution["post_revision_review"] = None
            for field in ("revision_batches", "review_cycles", "optional_backlog", "convergence"):
                resolution.pop(field, None)
            for row in resolution["resolutions"]:
                for field in ("finding_key", "reopen_count", "root_cause_analysis"):
                    row.pop(field, None)
            write_json(outdir / "review_findings.json", registry)
            resolution["findings_sha256"] = digest(outdir / "review_findings.json")
            write_json(outdir / "review_resolution.json", resolution)
            before = (outdir / "review_findings.json").read_bytes()
            dry = review_lifecycle.migrate_review_lifecycle(outdir, apply=False)
            self.assertTrue(dry.ok, dry.findings)
            self.assertEqual(before, (outdir / "review_findings.json").read_bytes())
            applied = review_lifecycle.migrate_review_lifecycle(outdir, apply=True)
            self.assertTrue(applied.ok, applied.findings)
            migrated = json.loads((outdir / "review_findings.json").read_text(encoding="utf-8"))
            self.assertEqual(review_lifecycle.FINDINGS_SCHEMA, migrated["schema_version"])
            self.assertTrue((outdir / "migration" / "review_convergence_v66" / "review_findings.v2.json").is_file())


if __name__ == "__main__":
    unittest.main()
