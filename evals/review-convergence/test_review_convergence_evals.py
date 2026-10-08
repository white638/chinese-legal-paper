from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "cnki-paper" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import revision_contract
from avereth_core.tools import review_lifecycle
from avereth_core.tools import test_review_lifecycle as lifecycle_regressions
from avereth_core.audit import test_run_all as audit_regressions
import test_revision_contract as revision_regressions


class ReviewConvergenceForwardEvals(unittest.TestCase):
    def test_change_class_routes_are_minimal_but_scientific_changes_expand(self) -> None:
        self.assertEqual((["clarity"], False), revision_contract._required_reviewers(["surface"]))
        self.assertEqual(
            (["contribution", "clarity"], False),
            revision_contract._required_reviewers(["argument"]),
        )
        self.assertEqual(
            (["methods", "contribution", "clarity"], False),
            revision_contract._required_reviewers(["evidence"]),
        )
        self.assertEqual(
            (["methods", "contribution", "clarity"], True),
            revision_contract._required_reviewers(["design"]),
        )
        self.assertEqual(
            (["methods", "contribution", "clarity"], True),
            revision_contract._required_reviewers(["execution"]),
        )

    def test_actual_diff_cannot_be_hidden_by_declared_scope(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            outdir = Path(raw)
            canonical = outdir / "main.md"
            candidate = outdir / "candidate.md"
            canonical.write_text("# Result\n\nOriginal bounded claim.\n", encoding="utf-8")
            candidate.write_text("# Result\n\nExpanded unregistered claim.\n", encoding="utf-8")
            finding_key = "RFK-" + "A" * 24
            contract = {
                "baseline": {"path": "main.md"},
                "requested_changes": [
                    {
                        "change_id": "CH-001", "change_class": "surface", "summary": "copy edit",
                        "target_finding_keys": [finding_key],
                    }
                ],
                "affected_identities": {
                    "source_ids": [], "claim_ids": ["CLM-001"],
                    "design_ids": [], "execution_ids": [], "manuscript_units": ["main.md"],
                },
            }
            batch = {
                "batch_id": "RB-001", "candidate_path": "candidate.md",
                "target_change_ids": ["CH-001"], "target_finding_keys": [finding_key],
                "declared_changed_unit_ids": [],
                "authority_digests": {"research_design.json": "", "method_execution.json": ""},
            }
            impact = revision_contract.compute_revision_impact(outdir, contract, batch)
            self.assertEqual("FAIL", impact["preflight_status"])
            self.assertTrue(impact["undeclared_changed_unit_ids"])
            self.assertEqual(["clarity"], impact["required_reviewers"])

    def test_undeclared_design_authority_drift_blocks_surface_batch(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            outdir = Path(raw)
            canonical = outdir / "main.md"
            candidate = outdir / "candidate.md"
            canonical.write_text("# Result\n\nOriginal bounded claim.\n", encoding="utf-8")
            candidate.write_text("# Result\n\nEdited bounded claim.\n", encoding="utf-8")
            finding_key = "RFK-" + "A" * 24
            contract = {
                "baseline": {"path": "main.md"},
                "requested_changes": [
                    {
                        "change_id": "CH-001", "change_class": "surface", "summary": "copy edit",
                        "target_finding_keys": [finding_key],
                    }
                ],
                "affected_identities": {
                    "source_ids": [], "claim_ids": [], "design_ids": [],
                    "execution_ids": [], "manuscript_units": ["main.md"],
                },
            }
            batch = {
                "batch_id": "RB-001", "candidate_path": "candidate.md",
                "target_change_ids": ["CH-001"], "target_finding_keys": [finding_key],
                "declared_changed_unit_ids": [],
                "authority_digests": {"research_design.json": ""},
            }
            (outdir / "research_design.json").write_text(
                '{"schema_version":"cnki-research-design/v4"}\n', encoding="utf-8"
            )
            impact = revision_contract.compute_revision_impact(outdir, contract, batch)
        self.assertEqual("FAIL", impact["preflight_status"])
        self.assertEqual(["research_design.json"], impact["unexpected_changed_authorities"])
        self.assertTrue(impact["full_review_required"])

    def test_same_problem_keeps_key_across_editorial_rephrasing(self) -> None:
        finding = {
            "category": "scope_overreach",
            "source": {"reviewer_role": "contribution"},
            "manuscript_locator": {
                "location": "Conclusion paragraph 1",
                "quoted_span": "The result applies to all cases.",
                "manuscript_unit_id": "MSU-BOUNDARY",
            },
            "recommended_action": {"repair_kind": "NARROW_CLAIM"},
            "identity_mapping": {
                "claim_ids": ["CLM-009"], "evidence_ids": ["SRC-004"],
                "design_ids": [], "execution_ids": [],
            },
            "problem": "The conclusion exceeds the evidence.",
        }
        rewritten = json.loads(json.dumps(finding))
        rewritten["problem"] = "Evidence does not warrant the universal scope."
        rewritten["manuscript_locator"]["location"] = "Discussion paragraph 4"
        self.assertEqual(
            review_lifecycle.finding_key(finding),
            review_lifecycle.finding_key(rewritten),
        )

    def test_nonblocking_polish_does_not_enter_active_blocking_set(self) -> None:
        registry = {
            "status": "HAS_FINDINGS",
            "findings": [
                {
                    "finding_id": "REV-CLR-001", "finding_key": "RFK-" + "B" * 24,
                    "materiality": "NON_BLOCKING",
                }
            ],
        }
        resolution = {
            "resolutions": [
                {
                    "finding_id": "REV-CLR-001", "finding_key": "RFK-" + "B" * 24,
                    "status": "OPEN", "reopen_count": 0, "root_cause_analysis": None,
                }
            ],
            "review_cycles": [],
        }
        review_lifecycle._refresh_convergence(registry, resolution)
        self.assertEqual([], resolution["convergence"]["active_blocking_finding_keys"])
        self.assertEqual(["RFK-" + "B" * 24], resolution["optional_backlog"])


def load_tests(loader: unittest.TestLoader, standard_tests: unittest.TestSuite, pattern: str | None) -> unittest.TestSuite:
    """Keep the forward suite tied to the proposal's release-critical regressions."""
    selected = (
        (lifecycle_regressions.ReviewLifecycleTests, "test_finding_key_survives_issue_rewording_and_paragraph_move"),
        (lifecycle_regressions.ReviewLifecycleTests, "test_blocked_review_cycle_is_preserved"),
        (lifecycle_regressions.ReviewLifecycleTests, "test_second_reopen_requires_structured_root_cause"),
        (lifecycle_regressions.ReviewLifecycleTests, "test_delta_dispatch_reuses_identical_role_projection_after_whole_sha_changes"),
        (lifecycle_regressions.ReviewLifecycleTests, "test_delta_dispatch_authority_change_invalidates_relevant_role"),
        (lifecycle_regressions.ReviewLifecycleTests, "test_delta_dispatch_unprojected_authority_change_keeps_reuse"),
        (lifecycle_regressions.ReviewLifecycleTests, "test_delta_dispatch_role_impact_change_invalidates_reuse"),
        (lifecycle_regressions.ReviewLifecycleTests, "test_delta_dispatch_implementation_change_invalidates_reuse"),
        (lifecycle_regressions.ReviewLifecycleTests, "test_full_dispatch_reviews_complete_manuscript_with_all_roles"),
        (revision_regressions.RevisionContractTests, "test_batch_preflight_and_single_atomic_promotion"),
        (revision_regressions.RevisionContractTests, "test_preflight_blocks_uncovered_batch_finding_key"),
        (revision_regressions.RevisionContractTests, "test_v1_migration_binds_registered_finding_key_and_keeps_backup"),
        (revision_regressions.RevisionContractTests, "test_init_binds_real_finding_keys_and_rejects_count_mismatch"),
        (audit_regressions.AuditCompletionOrderTests, "test_action_cache_binds_inputs_implementation_and_outputs"),
    )
    for case, name in selected:
        standard_tests.addTest(case(name))
    return standard_tests


if __name__ == "__main__":
    unittest.main()
