from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from avereth_core.build import manuscript_compiler as compiler


PROFILE_DIR = Path(compiler.__file__).resolve().parents[3] / "references" / "manuscript-profiles"
PROSE_PACKET_ROLES = {"abstract", "introduction", "theory", "methods", "findings", "discussion", "conclusion"}


class ManuscriptProfileCatalogueTests(unittest.TestCase):
    """Every installed profile must be closed under the compiler's structural rules."""

    def test_catalogue_lists_exactly_the_installed_profile_files(self) -> None:
        installed = sorted(path.name for path in PROFILE_DIR.glob("*.json"))
        self.assertEqual(sorted(compiler.PROFILE_FILES.values()), installed)
        self.assertIn(compiler.SUPPORTED_PROFILE, compiler.PROFILE_FILES)
        self.assertIn(compiler.HUMANITIES_PROFILE, compiler.PROFILE_FILES)
        self.assertEqual(set(compiler.PROFILE_FILES), set(compiler.SUPPORTED_PROFILES))
        for profile_id in compiler.SUPPORTED_PROFILES:
            self.assertIn(compiler.profile_path(profile_id), compiler.implementation_paths())

    def test_every_installed_profile_is_structurally_closed(self) -> None:
        for profile_id, file_name in compiler.PROFILE_FILES.items():
            with self.subTest(profile=profile_id):
                profile = json.loads((PROFILE_DIR / file_name).read_text(encoding="utf-8"))
                self.assertEqual(compiler.PROFILE_SCHEMA_VERSION, profile["schema_version"])
                self.assertEqual(profile_id, profile["profile_id"])
                sections = profile["sections"]
                roles = [section["semantic_role"] for section in sections]
                self.assertEqual(len(roles), len(set(roles)))
                self.assertEqual(sorted(roles), sorted(profile["render_order"]))
                self.assertEqual(
                    ["research_question", "claim", "design", "execution", "result"],
                    profile["scientific_commitment_order"],
                )
                moves = {}
                for section in sections:
                    self.assertIn(section["prose_packet_role"], PROSE_PACKET_ROLES)
                    self.assertTrue(section["required_moves"], section["section_id"])
                    for move in section["required_moves"]:
                        self.assertNotIn(move["move_id"], moves, "move ids must be unique across sections")
                        self.assertTrue(move["authority_groups"], move["move_id"])
                        self.assertTrue(set(move["authority_groups"]) <= set(compiler.IDENTITY_GROUPS), move["move_id"])
                        moves[move["move_id"]] = (section, move)

                self.assertEqual(profile["initial_reader_state"], sections[0]["reader_state_before"])
                for previous, current in zip(sections, sections[1:]):
                    self.assertEqual(previous["reader_state_after_id"], current["reader_state_before_id"])
                    self.assertEqual(previous["reader_state_after"], current["reader_state_before"])
                self.assertEqual(profile["final_reader_update"], sections[-1]["reader_state_after"])

                self.assertEqual(set(compiler.LIFECYCLE_STAGES), set(profile["claim_lifecycle"]))
                for stage, refs in profile["claim_lifecycle"].items():
                    self.assertTrue(refs, stage)
                    for ref in refs:
                        self.assertIn(ref, moves, f"{stage} -> {ref}")
                        self.assertIn("claims", moves[ref][1]["authority_groups"], f"{stage} move {ref} must carry Claim identity")

                for promise in profile["promise_templates"]:
                    self.assertIn(promise["source_move_ref"], moves, promise["promise_id"])
                    promised = set(promise["authority_groups"])
                    self.assertTrue(promised <= set(compiler.IDENTITY_GROUPS))
                    self.assertTrue(promise["delivery_move_refs"], promise["promise_id"])
                    for delivery in promise["delivery_move_refs"]:
                        self.assertIn(delivery, moves, f"{promise['promise_id']} -> {delivery}")
                        self.assertTrue(
                            promised & set(moves[delivery][1]["authority_groups"]),
                            f"{promise['promise_id']} delivery {delivery} shares no promised authority",
                        )

                edge_ids = [edge["edge_id"] for edge in profile["edge_templates"]]
                self.assertEqual(len(edge_ids), len(set(edge_ids)))
                for edge in profile["edge_templates"]:
                    self.assertIn(edge["source_ref"], moves, edge["edge_id"])
                    self.assertIn(edge["target_ref"], moves, edge["edge_id"])
                    self.assertNotEqual(edge["source_ref"], edge["target_ref"], edge["edge_id"])
                    self.assertIn(edge["relation"], compiler.RELATIONS, edge["edge_id"])

                groups_by_role = {
                    section["semantic_role"]: {group for move in section["required_moves"] for group in move["authority_groups"]}
                    for section in sections
                }
                for group, required_roles in profile["sync_requirements"].items():
                    self.assertIn(group, compiler.IDENTITY_GROUPS)
                    for role in required_roles:
                        self.assertIn(role, groups_by_role, f"sync {group} names unknown role {role}")
                        self.assertIn(group, groups_by_role[role], f"role {role} carries no {group} authority")


class HumanitiesProfileWorkspaceTests(unittest.TestCase):
    """A non-empirical design must compile through the humanities-argument profile end to end."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.outdir = Path(self.temporary.name)
        self.config = {
            "task_profile": "full_paper",
            "canonical_manuscript": "final_paper/main.md",
            "output_language": "zh-CN",
        }
        self._write_text("confirmed_motivation.md", "密折制度为何在雍正朝定型为常规信息渠道？\n")
        self._write_json("literature_analysis.json", {"schema_version": "cnki-literature-analysis/v1", "status": "confirmed"})
        self._write_json("research_design.json", self._design(family="interpretive", empirical=False, claim_type="interpretive"))
        self._write_json(
            "method_execution.json",
            {
                "schema_version": "cnki-method-execution/v2",
                "runs": [
                    {
                        "results": [
                            {
                                "result_id": "RES-001",
                                "claim_ids": ["CLM-001"],
                                "estimate": "registered-argument-outcome-v1",
                            }
                        ]
                    }
                ],
            },
        )
        self._write_text("confirmed_contribution.md", "Registered contribution identity.\n")
        self._write_text("final_paper/main.md", "# Manuscript\n\nInitial registered prose.\n")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _design(*, family: str, empirical: bool, claim_type: str, with_routes: bool = True) -> dict:
        payload = {
            "schema_version": "cnki-research-design/v4",
            "status": "confirmed",
            "claims": [
                {
                    "claim_id": "CLM-001",
                    "type": claim_type,
                    "statement": "The registered reading of the sources holds within the stated period.",
                    "protected_atoms": {
                        "subject": "registered reading",
                        "relation": "holds within the stated period",
                        "direction": "affirmative reading",
                        "polarity": "affirmative",
                        "inferential_strength": claim_type,
                        "scope": "the registered sources and period",
                        "protected_literals": ["registered reading", "stated period"],
                        "protected_numbers": [],
                        "citation_anchors": [],
                    },
                }
            ],
            "evidence": [{"evidence_id": "EVD-001", "text": "Registered source passages support the bounded reading."}],
        }
        if with_routes:
            payload["method_routes"] = [
                {
                    "id": "DSN-001",
                    "family": family,
                    "function": "analysis",
                    "role": "primary",
                    "empirical": empirical,
                    "claim_ids": ["CLM-001"],
                }
            ]
        return payload

    def _write_text(self, relative: str, text: str) -> None:
        path = self.outdir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _write_json(self, relative: str, payload: object) -> None:
        self._write_text(relative, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    def test_non_empirical_design_auto_selects_humanities_profile_and_compiles(self) -> None:
        contract = compiler.init_contract(self.outdir, self.config)
        self.assertEqual(compiler.HUMANITIES_PROFILE, contract["genre_profile"])
        self.assertEqual("AMC-HUMANITIES-001", contract["contract_id"])
        self.assertEqual("generic-humanities-argument", contract["venue_profile"])
        roles = [section["semantic_role"] for section in contract["sections"]]
        self.assertIn("sources_approach", roles)
        self.assertIn("analysis", roles)
        self.assertNotIn("data_methods", roles)
        self.assertNotIn("results", roles)
        compiler.write_initialized_contract(self.outdir, contract)

        compilation = compiler.compile_workspace(self.outdir, self.config)
        self.assertEqual([], [issue.as_dict() for issue in compilation.issues])
        self.assertEqual("BASELINE_REQUIRED", compilation.stale["status"])
        self.assertTrue(compilation.ir["profile"]["path"].endswith("humanities-argument-v1.json"))

        compiler.render_workspace(self.outdir, self.config, baseline=True)
        self.assertEqual([], compiler.validate_workspace(self.outdir, self.config))
        rationale = (self.outdir / "writing_rationale_matrix.md").read_text(encoding="utf-8")
        self.assertIn("humanities-argument", rationale)
        self.assertNotIn("empirical-social-science", rationale)

    def test_explicit_config_profile_overrides_auto_detection(self) -> None:
        config = {**self.config, "manuscript_profile": compiler.SUPPORTED_PROFILE}
        contract = compiler.init_contract(self.outdir, config)
        self.assertEqual(compiler.SUPPORTED_PROFILE, contract["genre_profile"])
        self.assertIn("data_methods", [section["semantic_role"] for section in contract["sections"]])

    def test_explicit_argument_overrides_config_and_detection(self) -> None:
        self._write_json("research_design.json", self._design(family="quantitative_causal", empirical=True, claim_type="association"))
        contract = compiler.init_contract(self.outdir, self.config, profile_id=compiler.HUMANITIES_PROFILE)
        self.assertEqual(compiler.HUMANITIES_PROFILE, contract["genre_profile"])

    def test_empirical_route_and_routeless_designs_keep_the_empirical_profile(self) -> None:
        self._write_json("research_design.json", self._design(family="case_process", empirical=True, claim_type="causal_mechanism"))
        self.assertEqual(compiler.SUPPORTED_PROFILE, compiler.init_contract(self.outdir, self.config)["genre_profile"])
        self._write_json("research_design.json", self._design(family="interpretive", empirical=False, claim_type="interpretive", with_routes=False))
        self.assertEqual(compiler.SUPPORTED_PROFILE, compiler.init_contract(self.outdir, self.config)["genre_profile"])

    def test_mixed_routes_with_any_empirical_primary_keep_the_empirical_profile(self) -> None:
        payload = self._design(family="normative", empirical=False, claim_type="normative")
        payload["method_routes"].append(
            {"id": "DSN-002", "family": "text_content", "function": "analysis", "role": "primary", "empirical": True, "claim_ids": ["CLM-001"]}
        )
        self._write_json("research_design.json", payload)
        self.assertEqual(compiler.SUPPORTED_PROFILE, compiler.init_contract(self.outdir, self.config)["genre_profile"])

    def test_unknown_profile_fails_closed_at_init_and_at_compile(self) -> None:
        with self.assertRaises(compiler.ManuscriptCompilerError):
            compiler.init_contract(self.outdir, {**self.config, "manuscript_profile": "poetry"})
        with self.assertRaises(compiler.ManuscriptCompilerError):
            compiler.init_contract(self.outdir, self.config, profile_id="poetry")
        contract = compiler.init_contract(self.outdir, self.config)
        contract["genre_profile"] = "poetry"
        compiler.write_initialized_contract(self.outdir, contract)
        codes = [issue.code for issue in compiler.compile_workspace(self.outdir, self.config).issues]
        self.assertIn("MS-PROFILE", codes)

    def test_contract_sections_must_match_the_declared_profile(self) -> None:
        contract = compiler.init_contract(self.outdir, self.config, profile_id=compiler.SUPPORTED_PROFILE)
        humanities = json.loads(compiler.profile_path(compiler.HUMANITIES_PROFILE).read_text(encoding="utf-8"))
        contract["genre_profile"] = compiler.HUMANITIES_PROFILE
        contract["profile_version"] = humanities["profile_version"]
        compiler.write_initialized_contract(self.outdir, contract)
        codes = {issue.code for issue in compiler.compile_workspace(self.outdir, self.config).issues}
        self.assertIn("MS-SECTION-COVERAGE", codes)
        self.assertNotIn("MS-PROFILE", codes)


if __name__ == "__main__":
    unittest.main()
