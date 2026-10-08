#!/usr/bin/env python3
"""Safety tests for typed method-contract migration and rollback."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

import migrate_method_contracts as migration
import test_method_execution as fixtures


LAYER_FIELDS = {
    "method_contract_schema",
    "method_contract_revision",
    "method_profile",
    "method_contract",
    "artifact_refs",
}


def legacy_workspace() -> tuple[tempfile.TemporaryDirectory, Path, bytes, bytes]:
    temporary = tempfile.TemporaryDirectory()
    base = Path(temporary.name)
    design = fixtures.confirmed_design("text_as_data")
    for field in LAYER_FIELDS:
        design["method_routes"][0].pop(field, None)
    execution = copy.deepcopy(fixtures.method_execution.scaffold_payload(fixtures.confirmed_design("survey")))
    execution["design_schema_version"] = "cnki-research-design/v3"
    run = execution["runs"][0]
    for field in LAYER_FIELDS | {"design_method_contract_sha256", "inference_disposition"}:
        run.pop(field, None)
    execution["runs"][0]["design_id"] = design["method_routes"][0]["id"]
    execution["runs"][0]["route_family"] = "text_as_data"
    design_bytes = (json.dumps(design, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    execution_bytes = (json.dumps(execution, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (base / "research_design.json").write_bytes(design_bytes)
    (base / "method_execution.json").write_bytes(execution_bytes)
    return temporary, base, design_bytes, execution_bytes


class MethodContractMigrationTests(unittest.TestCase):
    def test_dry_run_is_zero_write(self) -> None:
        temporary, base, design_before, execution_before = legacy_workspace()
        with temporary:
            report = migration.migrate_workspace(base, apply=False)
            self.assertEqual("dry-run", report["mode"])
            self.assertEqual("needs-review", report["status"])
            self.assertEqual(design_before, (base / "research_design.json").read_bytes())
            self.assertEqual(execution_before, (base / "method_execution.json").read_bytes())
            self.assertFalse((base / "migration").exists())

    def test_apply_is_backed_up_idempotent_and_never_invents_artifacts(self) -> None:
        temporary, base, design_before, execution_before = legacy_workspace()
        with temporary:
            report = migration.migrate_workspace(base, apply=True)
            snapshot = report["snapshot_id"]
            self.assertTrue(snapshot)
            migrated_design = json.loads((base / "research_design.json").read_text(encoding="utf-8"))
            migrated_execution = json.loads((base / "method_execution.json").read_text(encoding="utf-8"))
            route = migrated_design["method_routes"][0]
            run = migrated_execution["runs"][0]
            self.assertEqual("needs-review", migrated_design["status"])
            self.assertEqual("needs-review", migrated_execution["status"])
            self.assertEqual("text-as-data/measurement-v2", route["method_contract_schema"])
            self.assertEqual([], route["artifact_refs"])
            self.assertEqual([], run["artifact_refs"])
            self.assertIn("needs-review", json.dumps(route["method_contract"]))
            backup = base / migration.MIGRATION_REL / "backups" / snapshot
            self.assertEqual(design_before, (backup / "research_design.json").read_bytes())
            self.assertEqual(execution_before, (backup / "method_execution.json").read_bytes())
            second = migration.migrate_workspace(base, apply=True)
            self.assertEqual("already-current", second["status"])
            self.assertIsNone(second["snapshot_id"])

    def test_explicit_rollback_restores_exact_bytes(self) -> None:
        temporary, base, design_before, execution_before = legacy_workspace()
        with temporary:
            snapshot = migration.migrate_workspace(base, apply=True)["snapshot_id"]
            report = migration.rollback_workspace(base, snapshot)
            self.assertEqual("restored", report["status"])
            self.assertEqual(design_before, (base / "research_design.json").read_bytes())
            self.assertEqual(execution_before, (base / "method_execution.json").read_bytes())

    def test_future_contract_schema_fails_closed(self) -> None:
        temporary, base, _, _ = legacy_workspace()
        with temporary:
            design = json.loads((base / "research_design.json").read_text(encoding="utf-8"))
            design["schema_version"] = "cnki-research-design/v99"
            (base / "research_design.json").write_text(json.dumps(design), encoding="utf-8")
            with self.assertRaises(migration.MigrationError):
                migration.migrate_workspace(base, apply=False)

    def test_retired_measurement_v1_maps_to_v2_with_review_and_backup(self) -> None:
        temporary, base, design_before, _ = legacy_workspace()
        with temporary:
            design = json.loads((base / "research_design.json").read_text(encoding="utf-8"))
            route = design["method_routes"][0]
            route.update(
                {
                    "method_contract_schema": "text-as-data/measurement-v1",
                    "method_contract_revision": "1",
                    "method_profile": "text-as-data/measurement-v1",
                    "method_contract": {
                        "gold_standard": {"identity_type": "human_reference"}
                    },
                    "artifact_refs": [],
                }
            )
            (base / "research_design.json").write_text(
                json.dumps(design, ensure_ascii=False), encoding="utf-8"
            )
            report = migration.migrate_workspace(base, apply=True)
            self.assertEqual("needs-review", report["status"])
            migrated = json.loads(
                (base / "research_design.json").read_text(encoding="utf-8")
            )
            migrated_route = migrated["method_routes"][0]
            self.assertEqual(
                "text-as-data/measurement-v2",
                migrated_route["method_contract_schema"],
            )
            self.assertEqual(
                "text-as-data/measurement-v2", migrated_route["method_profile"]
            )
            self.assertIn("needs-review", json.dumps(migrated_route["method_contract"]))
            backup = (
                base
                / migration.MIGRATION_REL
                / "backups"
                / report["snapshot_id"]
                / "research_design.json"
            )
            self.assertIn("human_reference", backup.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
