#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from check_journal_overlays import (  # noqa: E402
    CORE_METHOD_AUTHORITY_KEYS,
    validate_journal_overlays,
    validate_venue_overlay_registry,
)

EMPIRICAL_SCRIPTS = ROOT / "skills" / "empirical-research" / "scripts"
sys.path.insert(0, str(EMPIRICAL_SCRIPTS))
from method_contract_loader import RESERVED_SUPPLEMENTAL_KEYS  # noqa: E402


class JournalOverlayCheckTests(unittest.TestCase):
    def _workspace(self, temp_dir: str) -> tuple[Path, Path]:
        root = Path(temp_dir)
        pack = root / "skills" / "journal-fit" / "packs" / "example-journal"
        pack.mkdir(parents=True)
        (pack / "SKILL.md").write_text(
            "# Example journal\n\nReport the estimand stored in the core method contract.\n",
            encoding="utf-8",
        )
        core = (
            root
            / "skills"
            / "empirical-research"
            / "references"
            / "schemas"
            / "methods"
            / "example-v1.schema.json"
        )
        core.parent.mkdir(parents=True)
        core.write_text("{}\n", encoding="utf-8")
        registry = (
            root
            / "skills"
            / "empirical-research"
            / "references"
            / "method-adapter-registry.json"
        )
        registry.write_text(
            json.dumps(
                {
                    "schema_version": "cnki-method-adapter-registry/v2",
                    "method_contracts": {
                        "example/v1": {
                            "asset": "references/schemas/methods/example-v1.schema.json",
                            "revision": "1",
                            "validator": "example",
                        }
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        requirements = (
            root
            / "skills"
            / "empirical-research"
            / "references"
            / "method-adapters.md"
        )
        requirements.write_text(
            "| Requirement ID | Core rule |\n"
            "|---|---|\n"
            "| `CORE.CAUSAL.ESTIMAND_BINDING` | Registered target. |\n"
            "| `CORE.EXPERIMENT.REGISTERED_DESIGN` | Registered experiment. |\n"
            "| `CORE.QUAL.REGISTERED_SELECTION_EVIDENCE` | Registered qualitative evidence. |\n"
            "| `CORE.MEASUREMENT.REGISTERED_VALIDATION` | Registered validation. |\n"
            "| `CORE.INFERENCE.DEPENDENCE_ALIGNMENT` | Registered dependence record. |\n",
            encoding="utf-8",
        )
        return root, pack

    def _valid_overlay(self) -> dict[str, object]:
        return {
            "schema_version": "avereth-journal-method-overlay/v1",
            "journal": "example-journal",
            "core_method_contract_ref": {"id": "example/v1", "revision": "1"},
            "reporting": {"require_core_fields": ["estimand_or_target", "diagnostics"]},
            "transparency": {},
            "presentation": {},
            "submission": {},
            "sources": [],
        }

    def test_checked_in_journal_packs_are_overlay_only(self) -> None:
        self.assertEqual([], validate_journal_overlays(ROOT))

    def test_reserved_method_keys_match_the_core_loader(self) -> None:
        self.assertEqual(RESERVED_SUPPLEMENTAL_KEYS, CORE_METHOD_AUTHORITY_KEYS)

    def test_every_discovered_workflow_inherits_the_workspace_control_plane(self) -> None:
        self.assertEqual([], validate_venue_overlay_registry(ROOT))
        registry = json.loads(
            (ROOT / "skills/journal-fit/references/venue-overlay-registry.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("cnki-paper", registry["workspace_control_plane"])
        registered = registry["workflow_overlays"]
        discovered = sorted(
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "skills/journal-fit/packs").rglob("SKILL.md")
            if path.parent.name.lower().endswith("workflow")
        )
        self.assertTrue(discovered)
        self.assertEqual(discovered, sorted(registered))
        self.assertEqual(len(registered), len(set(registered)))

    def test_valid_structured_overlay_references_core_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, pack = self._workspace(temp_dir)
            (pack / "journal-overlay.json").write_text(
                json.dumps(self._valid_overlay(), indent=2) + "\n",
                encoding="utf-8",
            )
            self.assertEqual([], validate_journal_overlays(root, check_repository_boundaries=False))

    def test_overlay_cannot_redefine_reserved_method_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, pack = self._workspace(temp_dir)
            for reserved_key in sorted(CORE_METHOD_AUTHORITY_KEYS):
                with self.subTest(reserved_key=reserved_key):
                    payload = self._valid_overlay()
                    payload["reporting"] = {reserved_key: "journal-specific override"}
                    (pack / "journal-overlay.json").write_text(
                        json.dumps(payload, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    issues = validate_journal_overlays(
                        root, check_repository_boundaries=False
                    )
                    self.assertTrue(
                        any(
                            "reserved core method key" in item
                            and reserved_key in item
                            for item in issues
                        ),
                        issues,
                    )

    def test_unregistered_workflow_overlay_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, _ = self._workspace(temp_dir)
            workflow = (
                root
                / "skills"
                / "journal-fit"
                / "packs"
                / "example-journal"
                / "skills"
                / "example-workflow"
            )
            workflow.mkdir(parents=True)
            (workflow / "SKILL.md").write_text(
                "# Example workflow\n\nReturn all stage actions to cnki-paper.\n",
                encoding="utf-8",
            )
            registry = (
                root
                / "skills"
                / "journal-fit"
                / "references"
                / "venue-overlay-registry.json"
            )
            registry.parent.mkdir(parents=True)
            registry.write_text(
                json.dumps(
                    {
                        "schema_version": "avereth-venue-overlay-registry/v1",
                        "workspace_control_plane": "cnki-paper",
                        "method_contract_authority": "skills/empirical-research/references/method-adapter-registry.json",
                        "workflow_overlays": [],
                        "forbidden_workflow_fields": [
                            "next_stage",
                            "completed_stage",
                            "status",
                            "gate",
                            "receipt",
                            "method_override",
                            "execution_engine",
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            issues = validate_venue_overlay_registry(root)
            self.assertTrue(
                any("unregistered workflow overlays" in item for item in issues),
                issues,
            )

    def test_overlay_cannot_reference_noncore_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, pack = self._workspace(temp_dir)
            payload = self._valid_overlay()
            payload["core_method_contract_ref"] = {
                "id": "journal-local/v1",
                "revision": "1",
            }
            (pack / "journal-overlay.json").write_text(
                json.dumps(payload, indent=2) + "\n",
                encoding="utf-8",
            )
            issues = validate_journal_overlays(root, check_repository_boundaries=False)
            self.assertTrue(any("unregistered core method contract id" in item for item in issues))

    def test_orphan_empirical_schema_is_not_a_core_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, pack = self._workspace(temp_dir)
            orphan = (
                root
                / "skills"
                / "empirical-research"
                / "references"
                / "schemas"
                / "methods"
                / "orphan-v1.schema.json"
            )
            orphan.write_text("{}\n", encoding="utf-8")
            payload = self._valid_overlay()
            payload["core_method_contract_ref"] = {
                "id": "orphan/v1",
                "revision": "1",
            }
            (pack / "journal-overlay.json").write_text(
                json.dumps(payload, indent=2) + "\n",
                encoding="utf-8",
            )
            issues = validate_journal_overlays(root, check_repository_boundaries=False)
            self.assertTrue(any("unregistered core method contract id" in item for item in issues))

    def test_overlay_core_contract_revision_must_match_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, pack = self._workspace(temp_dir)
            payload = self._valid_overlay()
            payload["core_method_contract_ref"] = {
                "id": "example/v1",
                "revision": "99",
            }
            (pack / "journal-overlay.json").write_text(
                json.dumps(payload, indent=2) + "\n",
                encoding="utf-8",
            )
            issues = validate_journal_overlays(root, check_repository_boundaries=False)
            self.assertTrue(any("revision mismatch" in item for item in issues))

    def test_pack_cannot_add_schema_validator_or_structured_markdown_definition(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, pack = self._workspace(temp_dir)
            (pack / "local.schema.json").write_text("{}\n", encoding="utf-8")
            (pack / "method_validator.py").write_text("def validate(): return True\n", encoding="utf-8")
            (pack / "METHODS.md").write_text("estimand: journal-defined effect\n", encoding="utf-8")
            issues = validate_journal_overlays(root, check_repository_boundaries=False)
            self.assertTrue(any("may not define a method schema" in item for item in issues))
            self.assertTrue(any("may not define a method validator" in item for item in issues))
            self.assertTrue(any("structured definition" in item and "estimand" in item for item in issues))

    def test_nonworkflow_venue_skill_cannot_directly_invoke_method_engine(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, pack = self._workspace(temp_dir)
            (pack / "data-analysis.md").write_text(
                "# Venue advice\n\nExecution bridge (StatsPAI / Stata MCP)\n",
                encoding="utf-8",
            )
            issues = validate_journal_overlays(root, check_repository_boundaries=False)
            self.assertTrue(any("directly invokes a method engine" in item for item in issues))

    def test_non_apsr_pack_cannot_prescribe_core_design_or_model_rules(self) -> None:
        prohibited = {
            "experiment": "Preregister the design and primary analyses; report power and MDE.",
            "qualitative": "Case selection must be justified by design logic; use process tracing with explicit tests.",
            "measurement": "Validate the computational measure against human-labeled samples.",
            "model": "Use a multilevel model rather than OLS.",
            "meta_regression": "Use mixed-effects meta-regression for all moderators.",
            "bias_battery": "Run Egger regression, trim-and-fill, PET-PEESE, and selection models.",
            "dependent_effects": "Dependent effect sizes must use RVE or multilevel meta-analysis.",
            "coder_staffing": "All records must be coded by at least two independent coders.",
            "double_coding": "Use double-coding for every extracted effect.",
            "survey_inference": "Use design-based inference; weights, strata, and clusters belong in the variance estimator.",
            "scale_validation": "Validate scales and latent constructs with CFA.",
            "event_model": "Use a discrete-time hazard with couple-clustered uncertainty.",
            "internal_meta": "Fit a random-effects internal meta-analysis across studies.",
            "venue_did_battery_zh": "交错 DID 必上事件研究图、安慰剂和异质性稳健估计。",
            "venue_exhibit_battery": "This skill requires every forest plot to show a pooled effect and prediction interval.",
            "reviewer_method_request": "When a reviewer asks for another bias test, add a selection model and rerun the diagnostics.",
            "analysis_skill_authority": "The numbers come from the analysis skills, which choose random-effects models.",
        }
        for label, advice in prohibited.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp_dir:
                root, pack = self._workspace(temp_dir)
                (pack / "research-design.md").write_text(advice + "\n", encoding="utf-8")
                issues = validate_journal_overlays(root, check_repository_boundaries=False)
                self.assertTrue(
                    any("restates core method authority" in item for item in issues),
                    issues,
                )

    def test_reporting_registered_core_facts_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, pack = self._workspace(temp_dir)
            (pack / "research-design.md").write_text(
                "Report the core-registered experiment design, case-selection rationale, "
                "coder identities, synthesis/dependence identity, validation and diagnostic "
                "Artifact IDs, and observed inference ceiling under "
                "CORE.EXPERIMENT.REGISTERED_DESIGN and "
                "CORE.QUAL.REGISTERED_SELECTION_EVIDENCE, "
                "CORE.MEASUREMENT.REGISTERED_VALIDATION, and "
                "CORE.INFERENCE.DEPENDENCE_ALIGNMENT. Missing records return to "
                "empirical-research.\n",
                encoding="utf-8",
            )
            self.assertEqual(
                [],
                validate_journal_overlays(root, check_repository_boundaries=False),
            )

    def test_unknown_core_requirement_reference_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, pack = self._workspace(temp_dir)
            (pack / "research-design.md").write_text(
                "Report CORE.INVENTED.VENUE_RULE.\n",
                encoding="utf-8",
            )
            issues = validate_journal_overlays(root, check_repository_boundaries=False)
            self.assertTrue(
                any("unknown empirical core requirement" in item for item in issues),
                issues,
            )

    def test_method_tool_catalog_requires_core_selection_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, pack = self._workspace(temp_dir)
            resources = pack / "resources"
            resources.mkdir()
            catalog = resources / "external_tools.md"
            catalog.write_text("# Tools\n\n- did (Callaway-Sant'Anna)\n", encoding="utf-8")
            issues = validate_journal_overlays(root, check_repository_boundaries=False)
            self.assertTrue(any("method-tool catalog lacks" in item for item in issues), issues)

            catalog.write_text(
                "# Tools\n\n> **Tool catalog only.** The empirical-core contract selects "
                "the method and validator.\n\n- did (Callaway-Sant'Anna)\n",
                encoding="utf-8",
            )
            self.assertEqual(
                [],
                validate_journal_overlays(root, check_repository_boundaries=False),
            )


if __name__ == "__main__":
    unittest.main()
