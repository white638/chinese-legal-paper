from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from avereth_core.gates.integration_gate import validate_integration_artifacts
from avereth_core.infrastructure.integration_contracts import (
    validate_exa_manifest,
    validate_exa_run,
    validate_zotero_snapshot,
)


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "integrations"


def payload(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class IntegrationContractTests(unittest.TestCase):
    def test_positive_offline_fixtures_pass(self) -> None:
        self.assertEqual([], validate_exa_run(payload("exa_run.json")))
        self.assertEqual([], validate_zotero_snapshot(payload("zotero_snapshot.json")))

    def test_exa_highlight_cannot_be_promoted(self) -> None:
        run = payload("exa_run.json")
        run["results"][0]["citation_scope"] = "final-source"  # type: ignore[index]
        issues = validate_exa_run(run)
        self.assertTrue(any("candidate-only" in issue for issue in issues), issues)

    def test_contracts_reject_fields_outside_the_checked_in_schemas(self) -> None:
        run = payload("exa_run.json")
        run["results"][0]["support_claim"] = "must not cross the discovery boundary"  # type: ignore[index]
        self.assertTrue(
            any(
                "unsupported field 'support_claim'" in issue
                for issue in validate_exa_run(run)
            )
        )

    def test_malformed_nested_collections_fail_without_crashing(self) -> None:
        run = payload("exa_run.json")
        run["executed_at"] = "2026-08-21T03:00:00"
        run["results"][0]["author"] = 7  # type: ignore[index]
        run_issues = validate_exa_run(run)
        self.assertTrue(any("ISO date-time" in issue for issue in run_issues))
        self.assertTrue(any("author must be a string" in issue for issue in run_issues))
        snapshot = payload("zotero_snapshot.json")
        snapshot["items"][0]["attachment_keys"] = 7  # type: ignore[index]
        snapshot["items"][0]["doi"] = 7  # type: ignore[index]
        snapshot_issues = validate_zotero_snapshot(snapshot)
        self.assertTrue(any("attachment_keys must be a list" in issue for issue in snapshot_issues))
        self.assertTrue(any("doi must be a string" in issue for issue in snapshot_issues))
        manifest = payload("exa_manifest.json")
        manifest["runs"] = {"not": "a list"}
        self.assertTrue(validate_exa_manifest(manifest))
        snapshot = payload("zotero_snapshot.json")
        snapshot["items"][0]["citation_scope"] = "final-source"  # type: ignore[index]
        self.assertTrue(
            any(
                "unsupported field 'citation_scope'" in issue
                for issue in validate_zotero_snapshot(snapshot)
            )
        )

    def test_manifest_verifies_controlled_path_hash_and_run_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_path = (
                root
                / "reference_materials"
                / "integrations"
                / "exa_runs"
                / "Q-EXA-COLLISION-001.json"
            )
            run_path.parent.mkdir(parents=True)
            run_path.write_bytes((FIXTURES / "exa_run.json").read_bytes())
            manifest = payload("exa_manifest.json")
            self.assertEqual([], validate_exa_manifest(manifest, workspace=root))

            run_path.write_text("{}\n", encoding="utf-8")
            issues = validate_exa_manifest(manifest, workspace=root)
            self.assertTrue(any("sha256" in issue for issue in issues), issues)

    def test_manifest_rejects_path_escape_and_duplicate_query(self) -> None:
        manifest = payload("exa_manifest.json")
        duplicate = copy.deepcopy(manifest["runs"][0])  # type: ignore[index]
        duplicate["path"] = "../outside.json"
        manifest["runs"].append(duplicate)  # type: ignore[union-attr]
        issues = validate_exa_manifest(manifest)
        self.assertTrue(any("outside" in issue for issue in issues), issues)
        self.assertTrue(any("duplicated" in issue for issue in issues), issues)

    def test_zotero_snapshot_rejects_duplicate_source_and_item(self) -> None:
        snapshot = payload("zotero_snapshot.json")
        snapshot["items"].append(copy.deepcopy(snapshot["items"][0]))  # type: ignore[union-attr,index]
        issues = validate_zotero_snapshot(snapshot)
        self.assertTrue(any("source_id is duplicated" in issue for issue in issues), issues)
        self.assertTrue(any("item_key is duplicated" in issue for issue in issues), issues)

    def test_zotero_identity_digest_is_recomputed(self) -> None:
        snapshot = payload("zotero_snapshot.json")
        snapshot["items"][0]["item_version"] = 18  # type: ignore[index]
        issues = validate_zotero_snapshot(snapshot)
        self.assertTrue(any("does not match" in issue for issue in issues), issues)

    def test_optional_gate_is_read_only_and_validates_present_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual("PASS", validate_integration_artifacts(root)["status"])
            run_dir = root / "reference_materials" / "integrations" / "exa_runs"
            run_dir.mkdir(parents=True)
            (run_dir / "Q-EXA-COLLISION-001.json").write_bytes(
                (FIXTURES / "exa_run.json").read_bytes()
            )
            (run_dir / "manifest.json").write_bytes(
                (FIXTURES / "exa_manifest.json").read_bytes()
            )
            snapshot_path = root / "reference_materials" / "integrations" / "zotero_snapshot.json"
            snapshot_path.write_bytes((FIXTURES / "zotero_snapshot.json").read_bytes())
            registry_path = root / "reference_materials" / "literature_registry.json"
            registry_path.write_text(
                json.dumps(
                    {
                        "schema_version": "cnki-acquisition/v3",
                        "queries": [
                            {
                                "query_id": "Q-EXA-COLLISION-001",
                                "channel": "Exa",
                                "run_artifact": "reference_materials/integrations/exa_runs/Q-EXA-COLLISION-001.json",
                                "run_sha256": "f1ad13dd63229f5c5687165229f563fd9fab7a27ce99c667e61ae33be84fd03d",
                            }
                        ],
                        "sources": [
                            {
                                "source_id": "INTL-S014",
                                "discovery_events": [
                                    {
                                        "provider": "exa",
                                        "query_id": "Q-EXA-COLLISION-001",
                                        "rank": 1,
                                        "discovered_url": "https://example.org/candidate",
                                        "run_sha256": "f1ad13dd63229f5c5687165229f563fd9fab7a27ce99c667e61ae33be84fd03d",
                                    }
                                ],
                                "zotero_link": {
                                    "server_id": "local-profile-fixture",
                                    "library_id": 1,
                                    "item_key": "PXW99EKT",
                                    "item_version": 17,
                                    "citation_key": "farrellNewInterdependence2019",
                                    "attachment_keys": ["2JAZS9U8"],
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual("PASS", validate_integration_artifacts(root)["status"])

            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            registry["queries"][0]["run_sha256"] = "0" * 64
            registry_path.write_text(json.dumps(registry), encoding="utf-8")
            report = validate_integration_artifacts(root)
            self.assertEqual("FAIL", report["status"])
            self.assertTrue(any("run_sha256" in issue for issue in report["issues"]))

            registry["queries"][0]["run_sha256"] = (
                "f1ad13dd63229f5c5687165229f563fd9fab7a27ce99c667e61ae33be84fd03d"
            )
            registry["sources"][0]["discovery_events"][0]["run_sha256"] = "0" * 64
            registry_path.write_text(json.dumps(registry), encoding="utf-8")
            report = validate_integration_artifacts(root)
            self.assertEqual("FAIL", report["status"])
            self.assertTrue(
                any("discovery event" in issue and "run_sha256" in issue for issue in report["issues"])
            )

            registry["sources"][0]["discovery_events"][0]["run_sha256"] = (
                "f1ad13dd63229f5c5687165229f563fd9fab7a27ce99c667e61ae33be84fd03d"
            )
            del registry["sources"][0]["zotero_link"]
            registry_path.write_text(json.dumps(registry), encoding="utf-8")
            report = validate_integration_artifacts(root)
            self.assertEqual("FAIL", report["status"])
            self.assertTrue(
                any("no canonical zotero_link" in issue for issue in report["issues"])
            )

            registry_path.write_text(
                json.dumps(
                    {
                        "schema_version": "cnki-acquisition/v3",
                        "queries": [
                            {
                                "query_id": "Q-EXA-COLLISION-001",
                                "channel": "Exa",
                                "run_artifact": "reference_materials/integrations/exa_runs/Q-EXA-COLLISION-001.json",
                                "run_sha256": "f1ad13dd63229f5c5687165229f563fd9fab7a27ce99c667e61ae33be84fd03d",
                            }
                        ],
                        "sources": [{"source_id": "OTHER-SOURCE"}],
                    }
                ),
                encoding="utf-8",
            )
            report = validate_integration_artifacts(root)
            self.assertEqual("FAIL", report["status"])
            self.assertEqual(
                "invalid",
                report["artifacts"][
                    "reference_materials/integrations/zotero_snapshot.json"
                ],
            )
            self.assertTrue(any("unknown Source ID" in issue for issue in report["issues"]))

    def test_registry_integration_fields_require_their_supporting_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "reference_materials" / "literature_registry.json"
            registry.parent.mkdir(parents=True)
            registry.write_text(
                json.dumps(
                    {
                        "schema_version": "cnki-acquisition/v3",
                        "queries": [
                            {
                                "query_id": "Q-EXA-001",
                                "channel": "Exa",
                            }
                        ],
                        "sources": [
                            {
                                "source_id": "INTL-S001",
                                "zotero_link": {"item_key": "PXW99EKT"},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            report = validate_integration_artifacts(root)
            self.assertEqual("FAIL", report["status"])
            self.assertEqual(
                "required-but-missing",
                report["artifacts"][
                    "reference_materials/integrations/exa_runs/manifest.json"
                ],
            )
            self.assertEqual(
                "required-but-missing",
                report["artifacts"][
                    "reference_materials/integrations/zotero_snapshot.json"
                ],
            )


if __name__ == "__main__":
    unittest.main()
