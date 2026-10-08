from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from avereth_core.config import LEGACY_CONFIG_REL, WORKFLOW_CONFIG_REL
from avereth_core.legacy import workspace_migration
from avereth_core.version import VERSION, WORKFLOW_CONFIG_SCHEMA


def legacy_config() -> dict[str, object]:
    return {
        "framework_version": "5.1.0",
        "workflow": "rewrite_existing",
        "task_profile": "manuscript_audit",
        "publication_track": "cnki-cn",
        "scene": "report_review",
        "tier": "flash",
        "output_language": "zh",
        "word_output": "none",
        "pdf_output": "none",
        "citation_mode": "author_year",
        "word_font_policy": "default",
        "prose_mode": "clear",
        "translation_package": "none",
        "submission_package": "none",
        "response_package": "none",
    }


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class WorkspaceMigrationV60Tests(unittest.TestCase):
    def test_v701_topic_selection_migration_refuses_to_invent_direction_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = legacy_config()
            payload.update(
                {
                    "framework_version": "7.0.1",
                    "schema_version": WORKFLOW_CONFIG_SCHEMA,
                    "task_profile": "topic_selection",
                }
            )
            write_json(root / WORKFLOW_CONFIG_REL, payload)
            blocked = workspace_migration.plan(root)
            self.assertEqual("blocked", blocked["status"])
            self.assertTrue(
                any(
                    "requires an explicit topic_selection policy" in issue
                    or "requires direction_contract" in issue
                    for issue in blocked["issues"]
                )
            )

            payload["topic_selection"] = {
                "origin_mode": "direction_first",
                "brainstorm_depth": "broad",
                "workspace_policy": "quarantine_until_divergence",
            }
            payload["direction_contract"] = {
                "current_user_goal": "Generate a direction-led topic portfolio",
                "field": "public administration",
                "core_problem": "Explain divergent institutional responses",
                "preferred_contribution": ["mechanism explanation"],
                "object_scope": "Comparable public organizations",
                "must_preserve": [],
                "must_avoid": ["dataset-led topic selection"],
                "acceptable_adjacency": "medium",
                "publication_track": "cnki-cn",
                "method_role": "open",
                "workspace_role": "optional-after-divergence",
                "authority": "current-user-request",
            }
            write_json(root / WORKFLOW_CONFIG_REL, payload)
            self.assertEqual("planned", workspace_migration.plan(root)["status"])

    def test_plan_apply_already_current_and_rollback_are_reversible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / LEGACY_CONFIG_REL, legacy_config())
            self.assertEqual("planned", workspace_migration.plan(root)["status"])

            applied, exit_code = workspace_migration.apply(root)
            self.assertEqual(0, exit_code)
            self.assertEqual("applied", applied["status"])
            current = json.loads((root / WORKFLOW_CONFIG_REL).read_text(encoding="utf-8"))
            self.assertEqual(VERSION, current["framework_version"])
            self.assertEqual(WORKFLOW_CONFIG_SCHEMA, current["schema_version"])
            material_skeleton = json.loads(
                (root / "reference_materials" / "research_material_registry.json").read_text(encoding="utf-8")
            )
            feasibility_skeleton = json.loads(
                (root / "research_feasibility.json").read_text(encoding="utf-8")
            )
            self.assertEqual("NEEDS_REVIEW", material_skeleton["applicability"]["status"])
            self.assertEqual("NEEDS_REVIEW", feasibility_skeleton["status"])
            self.assertNotEqual("PASS", feasibility_skeleton["status"])
            self.assertEqual("already-current", workspace_migration.plan(root)["status"])

            manifest = root / str(applied["backup_manifest"])
            rolled_back, exit_code = workspace_migration.rollback(root, manifest)
            self.assertEqual(0, exit_code)
            self.assertEqual("rolled_back", rolled_back["status"])
            self.assertFalse((root / WORKFLOW_CONFIG_REL).exists())
            self.assertTrue((root / LEGACY_CONFIG_REL).is_file())
            self.assertFalse((root / "reference_materials" / "research_material_registry.json").exists())
            self.assertFalse((root / "research_feasibility.json").exists())

    def test_rollback_accepts_equivalent_lexical_workspace_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            canonical_root = Path(tmp)
            (canonical_root / "path-alias-anchor").mkdir()
            aliased_root = canonical_root / "path-alias-anchor" / ".."
            self.assertEqual(canonical_root.resolve(), aliased_root.resolve())
            self.assertNotEqual(canonical_root, aliased_root)
            write_json(aliased_root / LEGACY_CONFIG_REL, legacy_config())

            applied, exit_code = workspace_migration.apply(aliased_root)
            self.assertEqual(0, exit_code)
            manifest = aliased_root / str(applied["backup_manifest"])

            rolled_back, exit_code = workspace_migration.rollback(aliased_root, manifest)
            self.assertEqual(0, exit_code)
            self.assertEqual("rolled_back", rolled_back["status"])
            self.assertEqual(applied["backup_manifest"], rolled_back["backup_manifest"])
            self.assertFalse((aliased_root / WORKFLOW_CONFIG_REL).exists())
            self.assertTrue((aliased_root / LEGACY_CONFIG_REL).is_file())

    def test_future_version_or_unknown_schema_blocks_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = legacy_config()
            payload.update({
                "framework_version": "6.9.0",
                "schema_version": "avereth-workflow-config/vX",
            })
            write_json(root / WORKFLOW_CONFIG_REL, payload)
            before = (root / WORKFLOW_CONFIG_REL).read_bytes()
            planned = workspace_migration.plan(root)
            self.assertEqual("blocked", planned["status"])
            self.assertTrue(any("future framework" in issue or "schema" in issue for issue in planned["issues"]))
            result, exit_code = workspace_migration.apply(root)
            self.assertEqual(2, exit_code)
            self.assertEqual("blocked", result["status"])
            self.assertEqual(before, (root / WORKFLOW_CONFIG_REL).read_bytes())

    def test_secret_scan_covers_camel_case_and_url_userinfo_without_value_leak(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = legacy_config()
            payload["clientSecret"] = "do-not-print-this-value"
            payload["endpoint"] = "https://user:password@example.invalid/api"
            write_json(root / LEGACY_CONFIG_REL, payload)
            planned = workspace_migration.plan(root)
            serialized = json.dumps(planned, ensure_ascii=False)
            self.assertEqual("blocked", planned["status"])
            self.assertIn("clientSecret", serialized)
            self.assertIn("url_userinfo", serialized)
            self.assertNotIn("do-not-print-this-value", serialized)
            self.assertNotIn("user:password", serialized)

    def test_unknown_legacy_keys_and_unseparated_credentials_block_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = legacy_config()
            payload["apikey"] = "DO-NOT-MIGRATE"
            payload["credentials"] = {"sessionid": "COOKIE-SECRET"}
            write_json(root / LEGACY_CONFIG_REL, payload)

            planned = workspace_migration.plan(root)
            serialized = json.dumps(planned, ensure_ascii=False)
            self.assertEqual("blocked", planned["status"])
            self.assertIn("apikey", serialized)
            self.assertIn("credentials", serialized)
            self.assertIn("sessionid", serialized)
            self.assertNotIn("DO-NOT-MIGRATE", serialized)
            self.assertNotIn("COOKIE-SECRET", serialized)

            result, exit_code = workspace_migration.apply(root)
            self.assertEqual(2, exit_code)
            self.assertEqual("blocked", result["status"])
            self.assertFalse((root / WORKFLOW_CONFIG_REL).exists())
            self.assertFalse((root / workspace_migration.MIGRATION_DIR).exists())

    def test_real_v5_fields_are_retired_or_handed_to_acquisition_without_loss(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = legacy_config()
            payload.update({
                "detection_platform": "auto",
                "humanize_thresholds": {"max_long_sentence_ratio": 0.35},
                "humanize_tier": "standard",
                "official_urls": ["https://example.invalid/journal"],
                "reference_mode": "hybrid",
                "reference_paths": ["reference_materials/source.pdf"],
                "ui_language": "zh",
                "v5_migration": {"status": "complete"},
            })
            write_json(root / LEGACY_CONFIG_REL, payload)

            planned = workspace_migration.plan(root)
            self.assertEqual("planned", planned["status"])
            self.assertEqual("acquisition", planned["earliest_reopen_stage"])
            self.assertEqual(
                [
                    "detection_platform",
                    "humanize_thresholds",
                    "humanize_tier",
                    "reference_mode",
                    "ui_language",
                    "v5_migration",
                ],
                planned["retired_config_keys"],
            )
            self.assertEqual(["official_urls", "reference_paths"], planned["acquisition_handoff_keys"])

            applied, exit_code = workspace_migration.apply(root)
            self.assertEqual(0, exit_code)
            self.assertEqual("applied", applied["status"])
            current = json.loads((root / WORKFLOW_CONFIG_REL).read_text(encoding="utf-8"))
            for key in (*workspace_migration.KNOWN_RETIRED_CONFIG_FIELDS, *workspace_migration.ACQUISITION_HANDOFF_FIELDS):
                self.assertNotIn(key, current)
            handoff = json.loads((root / workspace_migration.ACQUISITION_HANDOFF_REL).read_text(encoding="utf-8"))
            original_handoff = (root / workspace_migration.ACQUISITION_HANDOFF_REL).read_bytes()
            self.assertEqual("needs_review", handoff["status"])
            self.assertTrue(current["migration"]["acquisition_handoff_required"])
            self.assertEqual(handoff["input_digest"], current["migration"]["acquisition_handoff_input_digest"])
            self.assertEqual(payload["official_urls"], handoff["input_fields"]["official_urls"])
            self.assertEqual(payload["reference_paths"], handoff["input_fields"]["reference_paths"])
            self.assertIn(
                "ACQUISITION.MIGRATION_HANDOFF_PENDING",
                " ".join(workspace_migration.acquisition_handoff_issues(root)),
            )

            (root / workspace_migration.ACQUISITION_HANDOFF_REL).unlink()
            self.assertIn(
                "ACQUISITION.MIGRATION_HANDOFF_MISSING",
                " ".join(workspace_migration.acquisition_handoff_issues(root)),
            )
            (root / workspace_migration.ACQUISITION_HANDOFF_REL).write_bytes(original_handoff)

            handoff["status"] = "resolved"
            handoff["resolved_by"] = "author-test"
            handoff["dispositions"] = [
                {
                    "input_id": item["input_id"],
                    "status": "discarded",
                    "reason": "legacy candidate reviewed and intentionally not retained",
                }
                for item in handoff["items"]
            ]
            write_json(root / workspace_migration.ACQUISITION_HANDOFF_REL, handoff)
            self.assertEqual([], workspace_migration.acquisition_handoff_issues(root))
            tampered = dict(handoff)
            tampered["input_fields"] = {}
            tampered["items"] = []
            tampered["dispositions"] = []
            write_json(root / workspace_migration.ACQUISITION_HANDOFF_REL, tampered)
            self.assertIn(
                "ACQUISITION.MIGRATION_HANDOFF_DIGEST",
                " ".join(workspace_migration.acquisition_handoff_issues(root)),
            )
            (root / workspace_migration.ACQUISITION_HANDOFF_REL).write_bytes(original_handoff)

            manifest = root / str(applied["backup_manifest"])
            rolled_back, exit_code = workspace_migration.rollback(root, manifest)
            self.assertEqual(0, exit_code)
            self.assertEqual("rolled_back", rolled_back["status"])
            self.assertFalse((root / workspace_migration.ACQUISITION_HANDOFF_REL).exists())

    def test_reference_directory_handoff_seals_each_file_and_requires_exact_registry_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            materials = root / "reference_materials" / "legacy"
            materials.mkdir(parents=True)
            first = materials / "one.pdf"
            second = materials / "notes.md"
            first.write_bytes(b"PDF-one")
            second.write_text("source notes", encoding="utf-8")
            payload = legacy_config()
            payload["reference_paths"] = ["reference_materials/legacy"]
            write_json(root / LEGACY_CONFIG_REL, payload)

            applied, exit_code = workspace_migration.apply(root)
            self.assertEqual(0, exit_code)
            handoff_path = root / workspace_migration.ACQUISITION_HANDOFF_REL
            handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
            item = handoff["items"][0]
            self.assertEqual("directory", item["path_kind"])
            self.assertEqual(
                ["reference_materials/legacy/notes.md", "reference_materials/legacy/one.pdf"],
                [entry["path"] for entry in item["inventory"]],
            )

            registry = root / "reference_materials" / "literature_registry.json"
            write_json(registry, {
                "schema_version": "cnki-acquisition/v2",
                "queries": [],
                "sources": [
                    {
                        "source_id": f"LOCAL-{index}",
                        "local_file": entry["path"],
                        "sha256": entry["sha256"],
                    }
                    for index, entry in enumerate(item["inventory"], start=1)
                ],
            })
            handoff["status"] = "resolved"
            handoff["resolved_by"] = "author-test"
            handoff["dispositions"] = [{
                "input_id": item["input_id"],
                "status": "expanded",
                "file_dispositions": [
                    {
                        "path": entry["path"],
                        "status": "registered",
                        "source_ids": [f"LOCAL-{index}"],
                    }
                    for index, entry in enumerate(item["inventory"], start=1)
                ],
            }]
            write_json(handoff_path, handoff)
            self.assertEqual([], workspace_migration.acquisition_handoff_issues(root))

            registry_payload = json.loads(registry.read_text(encoding="utf-8"))
            registry_payload["sources"][0]["sha256"] = "0" * 64
            write_json(registry, registry_payload)
            self.assertIn(
                "ACQUISITION.MIGRATION_HANDOFF_BINDING",
                " ".join(workspace_migration.acquisition_handoff_issues(root)),
            )

    def test_revision_authorization_container_is_not_a_credential_but_children_still_scan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / LEGACY_CONFIG_REL, legacy_config())
            write_json(root / "revision_contract.json", {
                "schema_version": "cnki-manuscript-revision/v1",
                "authorization": {
                    "status": "confirmed",
                    "evidence": "user requested this revision",
                },
            })
            self.assertEqual("planned", workspace_migration.plan(root)["status"])

            contract = json.loads((root / "revision_contract.json").read_text(encoding="utf-8"))
            contract["authorization"]["bearer"] = "DO-NOT-PRINT"
            write_json(root / "revision_contract.json", contract)
            planned = workspace_migration.plan(root)
            serialized = json.dumps(planned, ensure_ascii=False)
            self.assertEqual("blocked", planned["status"])
            self.assertIn("revision_contract.json.authorization.bearer", serialized)
            self.assertNotIn("DO-NOT-PRINT", serialized)


if __name__ == "__main__":
    unittest.main()
