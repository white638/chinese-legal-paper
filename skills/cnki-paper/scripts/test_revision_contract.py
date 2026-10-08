#!/usr/bin/env python3
"""Regression tests for controlled manuscript revision routing."""

from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path

import revision_contract as revision


class RevisionContractTests(unittest.TestCase):
    def test_portable_schema_asset_matches_runtime_contract(self) -> None:
        schema_path = (
            Path(__file__).resolve().parent.parent
            / "references"
            / "schemas"
            / "cnki-manuscript-revision-v2.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(
            revision.SCHEMA_VERSION,
            schema["properties"]["schema_version"]["const"],
        )
        self.assertNotIn("*** Add File", schema_path.read_text(encoding="utf-8"))

    def test_workspace_and_standalone_entry_points_preserve_baseline_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            inside = workspace / "draft.md"
            inside.write_text("Substantive manuscript draft.", encoding="utf-8")
            outside = root / "old.docx"
            outside.write_bytes(b"PK-test-docx")
            self.assertEqual(
                "workspace",
                revision.baseline_from_path(inside, workspace_root=workspace)["kind"],
            )
            self.assertEqual(
                "standalone",
                revision.baseline_from_path(outside, workspace_root=workspace)["kind"],
            )

    def test_init_creates_revision_profile_without_inventing_full_assurance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manuscript = root / "paper.docx"
            manuscript.write_bytes(b"PK-test-docx")
            outdir = root / "revision"
            args = argparse.Namespace(
                outdir=str(outdir),
                manuscript=str(manuscript),
                change=["surface:correct punctuation and formatting"],
                assurance_level="legacy_limited",
                authorization_evidence="user request in current task",
                scene="journal",
                publication_track="cnki-cn",
                output_language="zh",
                word_output="docx",
                pdf_output="none",
                citation_mode="author_year",
                word_font_policy="default",
                prose_mode="clear",
                force=False,
            )
            self.assertEqual(0, revision.command_init(args))
            contract = json.loads((outdir / revision.CONTRACT_REL).read_text(encoding="utf-8"))
            config = json.loads((outdir / "workflow_config.json").read_text(encoding="utf-8"))
            self.assertRegex(contract["requested_changes"][0]["target_finding_keys"][0], r"^RFK-[A-F0-9]{24}$")
            self.assertEqual("build", contract["earliest_reopen_stage"])
            self.assertEqual("legacy_limited", contract["assurance_level"])
            self.assertEqual("manuscript_revision", config["task_profile"])
            snapshot = outdir / contract["baseline"]["snapshot_path"]
            working = outdir / config["canonical_manuscript"]
            self.assertTrue(snapshot.is_file())
            self.assertTrue(working.is_file())
            self.assertEqual(manuscript.read_bytes(), snapshot.read_bytes())
            self.assertEqual(manuscript.read_bytes(), working.read_bytes())
            _, current_issues = revision.load_and_validate(outdir, stage="build")
            self.assertFalse(current_issues, current_issues)
            self.assertTrue(
                any(item["code"] == "REV.ASSURANCE.OUTPUT" for item in revision.validate_revision_contract(contract, stage="output"))
            )
            snapshot.write_bytes(b"tampered")
            _, tampered_issues = revision.load_and_validate(outdir, stage="build")
            self.assertTrue(
                any(item["code"] == "REV.BASELINE.SNAPSHOT" for item in tampered_issues)
            )

    def test_title_scope_and_new_evidence_are_research_changes(self) -> None:
        self.assertEqual("research", revision.route_for_change_classes(["evidence"]))
        self.assertEqual("design", revision.route_for_change_classes(["design"]))
        self.assertEqual("execution", revision.route_for_change_classes(["execution"]))
        self.assertEqual("build", revision.route_for_change_classes(["argument"]))

    def test_init_binds_real_finding_keys_and_rejects_count_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manuscript = root / "paper.md"
            manuscript.write_text("# Paper\n\nOriginal paragraph.\n", encoding="utf-8")
            real_key = "RFK-" + "D" * 24

            def init_args(outdir: Path, keys: list[str]) -> argparse.Namespace:
                return argparse.Namespace(
                    outdir=str(outdir), manuscript=str(manuscript),
                    change=["surface:repair located wording"], finding_key=keys,
                    assurance_level="legacy_limited", authorization_evidence="authorized review repair",
                    scene="journal", publication_track="cnki-cn", output_language="zh",
                    word_output="docx", pdf_output="none", citation_mode="author_year",
                    word_font_policy="default", prose_mode="clear", force=False,
                )

            self.assertEqual(2, revision.command_init(init_args(root / "bad", [real_key, "RFK-" + "E" * 24])))
            outdir = root / "valid"
            self.assertEqual(0, revision.command_init(init_args(outdir, [real_key])))
            contract = json.loads((outdir / revision.CONTRACT_REL).read_text(encoding="utf-8"))
            self.assertEqual([real_key], contract["requested_changes"][0]["target_finding_keys"])

    def test_batch_preflight_and_single_atomic_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp) / "revision"
            manuscript = Path(tmp) / "source.md"
            manuscript.write_text("# Title\n\nOriginal paragraph.\n", encoding="utf-8")
            init = argparse.Namespace(
                outdir=str(outdir), manuscript=str(manuscript),
                change=["surface:clarify one paragraph"], assurance_level="full",
                authorization_evidence="user-authorized test", scene="journal",
                publication_track="cnki-cn", output_language="zh", word_output="docx",
                pdf_output="none", citation_mode="author_year", word_font_policy="default",
                prose_mode="clear", force=False,
            )
            self.assertEqual(0, revision.command_init(init))
            contract = json.loads((outdir / revision.CONTRACT_REL).read_text(encoding="utf-8"))
            finding_key = contract["requested_changes"][0]["target_finding_keys"][0]
            start = argparse.Namespace(
                outdir=str(outdir), batch_id="RB-001",
                change_id=["CH-001"], finding_key=[finding_key],
            )
            self.assertEqual(0, revision.command_batch_start(start))
            contract = json.loads((outdir / revision.CONTRACT_REL).read_text(encoding="utf-8"))
            batch = contract["revision_batches"][0]
            self.assertEqual([finding_key], batch["target_finding_keys"])
            candidate = outdir / batch["candidate_path"]
            canonical = outdir / contract["baseline"]["path"]
            before = canonical.read_text(encoding="utf-8")
            candidate.write_text("# Title\n\nClear revised paragraph.\n", encoding="utf-8")
            self.assertEqual(
                1,
                revision.command_impact(
                    argparse.Namespace(outdir=str(outdir), batch_id="RB-001", accept_actual_diff=False)
                ),
            )
            self.assertEqual(before, canonical.read_text(encoding="utf-8"))
            self.assertEqual(
                0,
                revision.command_impact(
                    argparse.Namespace(outdir=str(outdir), batch_id="RB-001", accept_actual_diff=True)
                ),
            )
            impact = json.loads((outdir / revision.IMPACT_REL).read_text(encoding="utf-8"))
            self.assertEqual(["clarity"], impact["required_reviewers"])
            self.assertEqual("PASS", impact["preflight_status"])
            self.assertEqual(0, revision.command_promote(argparse.Namespace(outdir=str(outdir), batch_id="RB-001")))
            self.assertEqual(candidate.read_text(encoding="utf-8"), canonical.read_text(encoding="utf-8"))
            self.assertEqual(1, revision.command_promote(argparse.Namespace(outdir=str(outdir), batch_id="RB-001")))

    def test_preflight_blocks_uncovered_batch_finding_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            canonical = outdir / "main.md"
            candidate = outdir / "candidate.md"
            canonical.write_text("# Result\n\nOriginal claim.\n", encoding="utf-8")
            candidate.write_text("# Result\n\nRevised claim.\n", encoding="utf-8")
            covered = "RFK-" + "A" * 24
            uncovered = "RFK-" + "B" * 24
            contract = {
                "baseline": {"path": "main.md"},
                "requested_changes": [{
                    "change_id": "CH-001", "change_class": "surface", "summary": "copy edit",
                    "target_finding_keys": [covered],
                }],
                "affected_identities": {
                    "source_ids": [], "claim_ids": [], "design_ids": [],
                    "execution_ids": [], "manuscript_units": ["main.md"],
                },
            }
            batch = {
                "batch_id": "RB-001", "candidate_path": "candidate.md",
                "target_change_ids": ["CH-001"],
                "target_finding_keys": [covered, uncovered],
                "declared_changed_unit_ids": [], "authority_digests": {},
            }
            impact = revision.compute_revision_impact(outdir, contract, batch)
        self.assertEqual("FAIL", impact["preflight_status"])
        self.assertEqual([uncovered], impact["uncovered_target_finding_keys"])

    def test_v1_migration_binds_registered_finding_key_and_keeps_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            registered = "RFK-" + "C" * 24
            legacy = {
                "schema_version": revision.LEGACY_SCHEMA_VERSION,
                "baseline": {
                    "kind": "workspace", "path": "final_paper/main.md",
                    "snapshot_path": "revision_baseline/main.md", "sha256": "a" * 64,
                },
                "requested_changes": [{
                    "change_id": "REV-MET-001", "summary": "repair baseline",
                    "change_class": "execution",
                }],
                "affected_identities": {
                    "source_ids": [], "claim_ids": ["CLM-001"], "design_ids": [],
                    "execution_ids": [], "manuscript_units": ["final_paper/main.md"],
                },
                "earliest_reopen_stage": "execution", "assurance_level": "full",
                "authorization": {"status": "confirmed", "evidence": "user authorization"},
            }
            (outdir / revision.CONTRACT_REL).write_text(json.dumps(legacy), encoding="utf-8")
            (outdir / "review_findings.json").write_text(
                json.dumps({"findings": [{"finding_id": "REV-MET-001", "finding_key": registered}]}),
                encoding="utf-8",
            )
            self.assertEqual(0, revision.command_migrate(argparse.Namespace(outdir=str(outdir), apply=True)))
            migrated = json.loads((outdir / revision.CONTRACT_REL).read_text(encoding="utf-8"))
            self.assertEqual(revision.SCHEMA_VERSION, migrated["schema_version"])
            self.assertEqual("CH-001", migrated["requested_changes"][0]["change_id"])
            self.assertEqual([registered], migrated["requested_changes"][0]["target_finding_keys"])
            self.assertTrue((outdir / "migration" / "revision_contract_v2" / "revision_contract.v1.json").is_file())


if __name__ == "__main__":
    unittest.main()
