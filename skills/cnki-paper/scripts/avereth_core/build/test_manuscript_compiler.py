from __future__ import annotations

import copy
import json
import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from codex_cnki_gate import check_build_artifacts
from avereth_core import cli as controller_cli
from avereth_core.build import manuscript_compiler as compiler
from avereth_core.build.run import build_run_status
from avereth_core.cli import artifact_manifest
from avereth_core.workflow_registry import REBUILDABLE_VIEW_PATHS
import prose_packet


class ManuscriptCompilerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.outdir = Path(self.temporary.name)
        self.config = {
            "task_profile": "full_paper",
            "canonical_manuscript": "final_paper/main.md",
            "scene": "generic-empirical-social-science",
            "output_language": "zh-CN",
        }
        self.semantic_run_counter = 0
        self._write_text("confirmed_motivation.md", "Why does the focal relationship occur?\n")
        self._write_json(
            "literature_analysis.json",
            {"schema_version": "cnki-literature-analysis/v1", "status": "confirmed"},
        )
        self._write_json(
            "research_design.json",
            {
                "schema_version": "cnki-research-design/v4",
                "status": "confirmed",
                "claims": [
                    {
                        "claim_id": "CLM-001",
                        "type": "association",
                        "statement": "The registered predictor is associated with the outcome.",
                        "protected_atoms": {
                            "subject": "registered predictor",
                            "relation": "associated with the outcome",
                            "direction": "positive association",
                            "polarity": "affirmative",
                            "inferential_strength": "association",
                            "scope": "the registered sample",
                            "protected_literals": ["registered predictor", "outcome"],
                            "protected_numbers": [],
                            "citation_anchors": [],
                        },
                    }
                ],
                "evidence": [
                    {
                        "evidence_id": "EVD-001",
                        "text": "Registered evidence supports the bounded association.",
                    }
                ],
            },
        )
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
                                "estimate": "registered-result-v1",
                            }
                        ]
                    }
                ],
            },
        )
        self._write_text("confirmed_contribution.md", "Registered contribution identity.\n")
        self._write_json(
            "reference_materials/literature_registry.json",
            {"sources": [{"source_id": "SRC-001", "title": "Registered source"}]},
        )
        self._write_json(
            "reference_materials/research_material_registry.json",
            {"materials": [{"material_id": "MAT-001", "material_type": "document"}]},
        )
        self._write_text("final_paper/main.md", "# Manuscript\n\nInitial registered prose.\n")
        contract = compiler.init_contract(self.outdir, self.config)
        compiler.write_initialized_contract(self.outdir, contract)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _path(self, relative: str | Path) -> Path:
        return self.outdir / relative

    def _write_text(self, relative: str | Path, text: str) -> None:
        path = self._path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _write_json(self, relative: str | Path, payload: object) -> None:
        self._write_text(relative, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    def _write_docx(
        self,
        relative: str | Path,
        paragraphs: list[str],
        *,
        table_cells: list[str] | None = None,
    ) -> None:
        """Write the smallest OOXML package needed by the canonical-text gate."""

        path = self._path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        namespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        ElementTree.register_namespace("w", namespace)
        document = ElementTree.Element(f"{{{namespace}}}document")
        body = ElementTree.SubElement(document, f"{{{namespace}}}body")

        def add_paragraph(parent: ElementTree.Element, text: str) -> None:
            paragraph = ElementTree.SubElement(parent, f"{{{namespace}}}p")
            run = ElementTree.SubElement(paragraph, f"{{{namespace}}}r")
            node = ElementTree.SubElement(run, f"{{{namespace}}}t")
            node.text = text

        for paragraph_text in paragraphs:
            add_paragraph(body, paragraph_text)
        if table_cells:
            table = ElementTree.SubElement(body, f"{{{namespace}}}tbl")
            for cell_text in table_cells:
                row = ElementTree.SubElement(table, f"{{{namespace}}}tr")
                cell = ElementTree.SubElement(row, f"{{{namespace}}}tc")
                add_paragraph(cell, cell_text)
        document_xml = ElementTree.tostring(
            document,
            encoding="utf-8",
            xml_declaration=True,
        )
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "[Content_Types].xml",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""",
            )
            archive.writestr(
                "_rels/.rels",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""",
            )
            archive.writestr("word/document.xml", document_xml)

    def _make_directory_alias(self, target: Path, link: Path) -> str:
        try:
            os.symlink(target, link, target_is_directory=True)
            return "symlink"
        except OSError as symlink_error:
            if os.name != "nt":
                self.skipTest(f"directory symlink unavailable: {symlink_error}")
            created = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
                check=False,
                capture_output=True,
                text=True,
            )
            if created.returncode != 0:
                detail = (created.stderr or created.stdout).strip()
                self.skipTest(
                    f"directory symlink and junction unavailable: {symlink_error}; {detail}"
                )
            return "junction"

    @staticmethod
    def _remove_directory_alias(link: Path, alias_kind: str) -> None:
        if not os.path.lexists(link):
            return
        if alias_kind == "junction":
            os.rmdir(link)
        else:
            link.unlink()

    def _contract(self) -> dict:
        return json.loads(self._path(compiler.CONTRACT_REL).read_text(encoding="utf-8"))

    def _replace_contract(self, payload: dict) -> None:
        self._write_json(compiler.CONTRACT_REL, payload)

    def _issue_codes(self) -> set[str]:
        return {issue.code for issue in compiler.compile_workspace(self.outdir, self.config).issues}

    def _baseline(self) -> None:
        compiler.render_workspace(self.outdir, self.config, baseline=True)
        self.assertEqual([], compiler.validate_workspace(self.outdir, self.config))

    def _with_argument_focus(self, contract: dict | None = None) -> dict:
        contract = contract or self._contract()
        contract["narrative_contract"]["central_throughline"] = "Determine which bounded explanation of the registered relationship the evidence supports."
        moves = {item["move_id"]: item for item in contract["moves"]}
        delivery_id = "MOVE-RESULTS-CORE" if "MOVE-RESULTS-CORE" in moves else "MOVE-ANALYSIS-CORE"
        source = moves["MOVE-INTRO-QUESTION"]
        source["authority_refs"].append("CLM-001")
        source["claim_refs"].append("CLM-001")
        source["promise_refs"].append("PROMISE-CORE-PROOF")
        moves[delivery_id]["delivery_refs"].append("PROMISE-CORE-PROOF")
        contract["promises"].append({
            "promise_id": "PROMISE-CORE-PROOF",
            "promise_type": "proof_obligation",
            "source_move_ref": source["move_id"],
            "delivery_move_refs": [delivery_id],
            "authority_refs": ["RQ-MAIN", "CLM-001", "RES-001"],
            "required_authority_refs": ["CLM-001", "RES-001"],
            "warrant": "The registered result assesses the bounded relationship under the design assumptions.",
            "failure_consequence": "An indeterminate result leaves the explanation unresolved and narrows the answer.",
        })
        section = next(item for item in contract["sections"] if delivery_id in item["move_refs"])
        section.update({
            "argument_role": "core_argument",
            "serves_promise_refs": ["PROMISE-CORE-PROOF"],
            "if_removed": "The reader would lose the actual evidential assessment of the central relationship.",
        })
        self._replace_contract(contract)
        return contract

    def test_proof_obligation_renders_coverage_without_claiming_truth(self) -> None:
        self._with_argument_focus()
        self.assertEqual(set(), self._issue_codes())
        self._baseline()
        view = self._path("promise_delivery_matrix.md").read_text(encoding="utf-8")
        self.assertIn("coverage does not establish the truth", view)
        self.assertIn("COVERED; inferential adequacy requires evidence review", view)
        self.assertIn("Consequence of Removal", self._path("writing_rationale_matrix.md").read_text(encoding="utf-8"))

    def test_proof_obligation_shared_claim_does_not_cover_missing_evidence(self) -> None:
        contract = self._with_argument_focus()
        contract["promises"][-1]["required_authority_refs"].append("EVD-001")
        contract["promises"][-1]["authority_refs"].append("EVD-001")
        self._replace_contract(contract)
        self.assertIn("MS-PROOF-COVERAGE", self._issue_codes())

    def test_proof_obligation_allows_evidence_distributed_across_deliveries(self) -> None:
        contract = self._with_argument_focus()
        obligation = contract["promises"][-1]
        obligation["required_authority_refs"].append("EVD-001")
        obligation["authority_refs"].append("EVD-001")
        obligation["delivery_move_refs"].append("MOVE-RESULTS-EVIDENCE")
        delivery = next(item for item in contract["moves"] if item["move_id"] == "MOVE-RESULTS-EVIDENCE")
        delivery["authority_refs"].append("EVD-001")
        delivery["delivery_refs"].append(obligation["promise_id"])
        self._replace_contract(contract)
        self.assertEqual(set(), self._issue_codes())

    def test_proof_obligation_source_must_carry_question_and_claim(self) -> None:
        contract = self._with_argument_focus()
        source = next(item for item in contract["moves"] if item["move_id"] == "MOVE-INTRO-QUESTION")
        source["authority_refs"].remove("RQ-MAIN")
        self._replace_contract(contract)
        self.assertIn("MS-PROOF-SOURCE", self._issue_codes())

    def test_proof_obligation_requires_source_and_delivery_backlinks(self) -> None:
        original = self._with_argument_focus()
        for move_id, field, code in (
            ("MOVE-INTRO-QUESTION", "promise_refs", "MS-PROOF-SOURCE"),
            ("MOVE-RESULTS-CORE", "delivery_refs", "MS-PROOF-DELIVERY"),
        ):
            with self.subTest(field=field):
                contract = copy.deepcopy(original)
                move = next(item for item in contract["moves"] if item["move_id"] == move_id)
                move[field].remove("PROMISE-CORE-PROOF")
                self._replace_contract(contract)
                self.assertIn(code, self._issue_codes())

    def test_proof_obligation_requires_evidential_or_reasoning_basis(self) -> None:
        contract = self._with_argument_focus()
        contract["promises"][-1]["required_authority_refs"] = ["CLM-001"]
        self._replace_contract(contract)
        self.assertIn("MS-PROOF-BASIS", self._issue_codes())

    def test_proof_fields_cannot_be_hidden_under_an_ordinary_promise(self) -> None:
        contract = self._with_argument_focus()
        contract["promises"][-1]["promise_type"] = "research_answer"
        self._replace_contract(contract)
        self.assertIn("MS-PROOF-SHAPE", self._issue_codes())

    def test_focused_contract_cannot_keep_the_generic_throughline(self) -> None:
        template = self._contract()["narrative_contract"]["central_throughline"]
        contract = self._with_argument_focus()
        contract["narrative_contract"]["central_throughline"] = template
        self._replace_contract(contract)
        self.assertIn("MS-FOCUS-TEMPLATE", self._issue_codes())

    def test_core_section_must_deliver_its_declared_obligation(self) -> None:
        contract = self._with_argument_focus()
        intro = next(item for item in contract["sections"] if item["semantic_role"] == "introduction")
        intro.update({"argument_role": "core_argument", "serves_promise_refs": ["PROMISE-CORE-PROOF"], "if_removed": "The evidence would allegedly be absent without this introduction."})
        self._replace_contract(contract)
        self.assertIn("MS-FOCUS-ORPHAN", self._issue_codes())

    def test_enabling_context_can_be_necessary_without_delivering_a_proof(self) -> None:
        contract = self._with_argument_focus()
        intro = next(item for item in contract["sections"] if item["semantic_role"] == "introduction")
        intro.update({"argument_role": "enabling", "serves_promise_refs": [], "if_removed": "The reader would lack the institutional context needed to interpret the evidence."})
        self._replace_contract(contract)
        self.assertEqual(set(), self._issue_codes())

    def test_section_focus_fields_require_a_complete_group_and_real_refs(self) -> None:
        contract = self._with_argument_focus()
        section = next(item for item in contract["sections"] if "argument_role" in item)
        section["serves_promise_refs"] = ["PROMISE-UNKNOWN"]
        del section["if_removed"]
        self._replace_contract(contract)
        self.assertTrue({"MS-FOCUS-SHAPE", "MS-FOCUS-IDENTITY"}.issubset(self._issue_codes()))

    def test_proof_warrant_change_invalidates_source_delivery_and_dependents(self) -> None:
        contract = self._with_argument_focus()
        self._baseline()
        contract["promises"][-1]["warrant"] = "The comparison addresses a narrower explanation under the same registered evidence."
        self._replace_contract(contract)
        result = compiler.compile_workspace(self.outdir, self.config)
        self.assertFalse(result.issues)
        self.assertEqual("STALE", result.stale["status"])
        self.assertTrue({"MOVE-INTRO-QUESTION", "MOVE-RESULTS-CORE", "MOVE-CONCLUSION-ANSWER"}.issubset(result.stale["stale_move_refs"]))

    def test_section_removal_reason_change_invalidates_its_prose(self) -> None:
        contract = self._with_argument_focus()
        self._baseline()
        section = next(item for item in contract["sections"] if "argument_role" in item)
        section["if_removed"] = "The reader would lose the distinction between the bounded finding and a rival explanation."
        self._replace_contract(contract)
        result = compiler.compile_workspace(self.outdir, self.config)
        self.assertTrue(set(section["move_refs"]).issubset(result.stale["stale_move_refs"]))

    def test_humanities_proof_can_use_registered_reasoning_without_a_rival(self) -> None:
        contract = compiler.init_contract(self.outdir, self.config, profile_id="humanities-argument")
        contract = self._with_argument_focus(contract)
        obligation = contract["promises"][-1]
        obligation["authority_refs"] = ["RQ-MAIN", "CLM-001", "DESIGN-MAIN"]
        obligation["required_authority_refs"] = ["CLM-001", "DESIGN-MAIN"]
        obligation["warrant"] = "The registered interpretive procedure relates the premises to the bounded conclusion."
        self._replace_contract(contract)
        self.assertEqual(set(), self._issue_codes())

    def test_inconclusive_result_does_not_fail_argument_coverage(self) -> None:
        execution = json.loads(self._path("method_execution.json").read_text(encoding="utf-8"))
        execution["runs"][0]["results"][0]["estimate"] = "inconclusive; the explanations cannot be distinguished"
        self._write_json("method_execution.json", execution)
        self._with_argument_focus()
        self.assertEqual(set(), self._issue_codes())

    def test_malformed_focus_identity_reports_schema_errors_without_crashing(self) -> None:
        original = self._with_argument_focus()
        for field in ("global_identity", "narrative_contract"):
            for malformed in (["unexpected"], "unexpected"):
                with self.subTest(field=field, malformed=malformed):
                    contract = copy.deepcopy(original)
                    contract[field] = malformed
                    self._replace_contract(contract)
                    self.assertIn("MS-CONTRACT-SCHEMA", self._issue_codes())

    def _drift_execution(self) -> compiler.Compilation:
        execution = json.loads(self._path("method_execution.json").read_text(encoding="utf-8"))
        execution["runs"][0]["results"][0]["estimate"] = "registered-result-v2"
        self._write_json("method_execution.json", execution)
        compilation = compiler.compile_workspace(self.outdir, self.config)
        self.assertEqual("STALE", compilation.stale["status"])
        return compilation

    def _complete_rebuild(
        self,
        compilation: compiler.Compilation,
        *,
        docx: bool = False,
    ) -> list[tuple[str, str, str]]:
        entries: list[tuple[str, str, str]] = []
        outputs: list[str] = []
        for move_ref in compilation.stale["stale_move_refs"]:
            pair = self._rebuild_pair(compilation, move_ref)
            entries.extend(pair)
            outputs.append(self._path(pair[1][2]).read_text(encoding="utf-8"))
        manuscript = str(self.config["canonical_manuscript"])
        if docx:
            midpoint = max(1, len(outputs) // 2)
            self._write_docx(
                manuscript,
                ["Manuscript", *outputs[:midpoint]],
                table_cells=outputs[midpoint:],
            )
        else:
            self._write_text(manuscript, "# Manuscript\n\n" + "\n\n".join(outputs))
        compiler.record_rebuild_proofs(self.outdir, self.config, entries)
        compiler.render_workspace(self.outdir, self.config)
        self.assertEqual([], compiler.validate_workspace(self.outdir, self.config))
        return entries

    def _rebuild_pair(
        self,
        compilation: compiler.Compilation,
        move_ref: str,
        *,
        output_relative: str | None = None,
        claim_id: str = "CLM-001",
        claim_override: dict | None = None,
        reader_question: str | None = None,
        reader_update: str | None = None,
    ) -> list[tuple[str, str, str]]:
        self.semantic_run_counter += 1
        node = next(
            item
            for item in compilation.ir["moves"]
            if item["contract"]["move_id"] == move_ref
        )
        design = json.loads(self._path("research_design.json").read_text(encoding="utf-8"))
        claim_record = next(
            item
            for item in design.get("claims", [])
            if str(item.get("id") or item.get("claim_id")) == claim_id
        )
        claim_payload = claim_override or {
            "id": claim_id,
            "canonical_proposition": str(
                claim_record.get("canonical_proposition")
                or claim_record.get("statement")
                or claim_record.get("text")
            ),
            "strength": str(claim_record.get("strength") or claim_record.get("type")),
            "realization_mode": "semantic",
            "protected_atoms": copy.deepcopy(claim_record["protected_atoms"]),
        }
        packet = prose_packet.compile_prose_packet(
            {
                "section_role": node["contract"]["prose_packet_role"],
                "object": f"Registered rebuild unit for {move_ref}",
                "claim": claim_payload,
                "evidence_items": [
                    {
                        "id": "EVD-001",
                        "text": "Registered evidence supports the bounded association.",
                        "evidence_function": "supports the registered Claim",
                    }
                ],
                "warrant": "The registered evidence warrants the bounded associational statement.",
                "reader_question": reader_question
                if reader_question is not None
                else node["contract"]["reader_question"],
                "plain_core": claim_payload["canonical_proposition"],
                "explanation_path": [
                    {
                        "order": 1,
                        "function": "claim",
                        "content": claim_payload["canonical_proposition"],
                        "anchor_id": claim_id,
                    },
                    {
                        "order": 2,
                        "function": "evidence_role",
                        "content": "Registered evidence supports the bounded Claim.",
                        "anchor_id": "EVD-001",
                    },
                    {
                        "order": 3,
                        "function": "warrant",
                        "content": "The registered evidence warrants only the declared inference strength.",
                    },
                ],
                "reader_update": reader_update
                if reader_update is not None
                else node["contract"]["required_update"],
            },
            registered_ids=prose_packet.discover_registered_ids(self.outdir),
        )
        suffix = f"{self.semantic_run_counter:04d}"
        packet_relative = f".avereth-prose/rebuild-evidence/{move_ref}/packet-{suffix}.json"
        self._write_json(packet_relative, packet)
        output_relative = output_relative or f".avereth-prose/rebuild-evidence/{move_ref}/clarity-{suffix}.md"
        draft = (
            packet["claim"]["canonical_proposition"]
            + "\n\n"
            + packet["evidence_items"][0]["text"]
            + "\n\n"
            + node["contract"]["planned_function"]
            + "\n"
        )
        if not self._path(output_relative).exists():
            self._write_text(output_relative, draft)
        clarity_draft = self._path(output_relative).read_text(encoding="utf-8")
        writer_relative = f".avereth-prose/rebuild-evidence/{move_ref}/writer-{suffix}.md"
        self._write_text(writer_relative, clarity_draft)
        ledger_relative = f".avereth-prose/rebuild-evidence/{move_ref}/clarity-ledger-{suffix}.json"
        self._write_json(
            ledger_relative,
            {
                "schema_version": "avereth-clarity-edit-ledger/v1",
                "scope": "section",
                "actions": [],
            },
        )
        run_id = f"SEM-{self.semantic_run_counter:016X}"
        dispatch = prose_packet.dispatch_semantic_fidelity_review(
            self.outdir,
            self._path(packet_relative),
            self._path(output_relative),
            registered_ids=prose_packet.discover_registered_ids(self.outdir),
            writer_context_id=f"writer-context-{suffix}",
            clarity_context_id=f"clarity-context-{suffix}",
            review_run_id=run_id,
        )
        packet_sha, draft_sha = prose_packet.semantic_fidelity_digests(packet, clarity_draft)
        self._write_json(
            dispatch["review_output"],
            {
                "schema_version": prose_packet.SEMANTIC_FIDELITY_REVIEW_SCHEMA_VERSION,
                "review_run_id": run_id,
                "packet_sha256": packet_sha,
                "draft_sha256": draft_sha,
                "dimensions": {
                    dimension: {
                        "status": "PASS",
                        "reason": f"Independent comparison preserves {dimension} for this exact Move output.",
                    }
                    for dimension in prose_packet.SEMANTIC_FIDELITY_DIMENSIONS
                },
                "overall_status": "PASS",
            },
        )
        assurance = prose_packet.create_semantic_fidelity_assurance(
            self.outdir,
            self._path(dispatch["manifest"]),
            reviewer_context_id=f"semantic-reviewer-context-{suffix}",
        )
        return [
            (move_ref, "prose_packet", packet_relative),
            (move_ref, "clarity_draft", output_relative),
            (move_ref, "writer_draft", writer_relative),
            (move_ref, "clarity_ledger", ledger_relative),
            (move_ref, "semantic_dispatch", dispatch["manifest"]),
            (move_ref, "semantic_assurance", assurance["assurance"]),
        ]

    def test_explicit_baseline_renders_current_ir_and_all_views(self) -> None:
        compilation = compiler.compile_workspace(self.outdir, self.config)
        self.assertEqual("BASELINE_REQUIRED", compilation.stale["status"])
        with self.assertRaises(compiler.ManuscriptCompilerError) as caught:
            compiler.render_workspace(self.outdir, self.config)
        self.assertEqual("MS-BASELINE-REQUIRED", caught.exception.issues[0].code)

        rendered = compiler.render_workspace(self.outdir, self.config, baseline=True)

        self.assertEqual(
            {
                compiler.IR_REL,
                compiler.STALE_REL,
                compiler.TRACE_REL,
                *compiler.VIEW_RELS,
            },
            set(rendered),
        )
        self.assertEqual([], compiler.validate_workspace(self.outdir, self.config))
        rationale = self._path("writing_rationale_matrix.md").read_text(encoding="utf-8")
        self.assertIn("Whole-manuscript framework", rationale)
        self.assertIn("User Evidence or Citation Anchor", rationale)
        self.assertEqual(
            [],
            [issue for issue in check_build_artifacts(self.outdir) if "writing_rationale" in issue],
        )

    def test_missing_contract_fails_with_explicit_migration_instruction(self) -> None:
        self._path(compiler.CONTRACT_REL).unlink()
        result = compiler.compile_workspace(self.outdir, self.config)
        self.assertEqual(["MS-CONTRACT-MISSING"], [issue.code for issue in result.issues])
        self.assertIn("manuscript init", result.issues[0].message)
        self.assertIn("--baseline", result.issues[0].message)

        build = build_run_status(self.outdir, self.config)
        self.assertEqual("BUILD.MANUSCRIPT.CONTRACT.MISSING", build.findings[0].code)

    def test_legacy_manuscript_audit_does_not_require_amc_migration(self) -> None:
        self._path(compiler.CONTRACT_REL).unlink()
        audit_config = {**self.config, "task_profile": "manuscript_audit"}
        result = build_run_status(self.outdir, audit_config)
        self.assertEqual("BUILD.RUN_MISSING", result.findings[0].code)

    def test_promise_without_delivery_fails_closed(self) -> None:
        contract = self._contract()
        contract["promises"][0]["delivery_move_refs"] = []
        self._replace_contract(contract)
        self.assertIn("MS-PROMISE-DELIVERY", self._issue_codes())

    def test_legacy_contract_without_rhetorical_fields_remains_compatible(self) -> None:
        contract = self._contract()
        contract["profile_version"] = "1.0.0"
        self._replace_contract(contract)
        self.assertEqual(set(), self._issue_codes())
        compilation = compiler.compile_workspace(self.outdir, self.config)
        views = compiler.render_markdown_views(compilation.ir)
        self.assertNotIn("Argument Action", views[Path("section_blueprints.md")])
        self.assertNotIn("Delay Span", views[Path("promise_delivery_matrix.md")])
        self.assertNotIn("AP-HOOK-CLOSURE", views[Path("cross_section_sync_report.md")])

    def test_distinguished_current_contract_requires_thought_move_state(self) -> None:
        self.config["prose_mode"] = "distinguished"
        self.assertIn("AP.MOTION.STATE_INCOMPLETE", self._issue_codes())

    def test_thought_move_must_advance_the_registered_problem_state(self) -> None:
        contract = self._contract()
        move = next(item for item in contract["moves"] if item["move_id"] == "MOVE-INTRO-GAP")
        move.update(
            {
                "argument_action": "PRESS",
                "problem_state_before": "Existing accounts leave the boundary unexplained.",
                "problem_state_after": "Existing accounts leave the boundary unexplained.",
            }
        )
        self._replace_contract(contract)
        self.assertIn("AP.MOTION.NO_ADVANCE", self._issue_codes())

    def test_thought_move_action_uses_the_registered_vocabulary(self) -> None:
        contract = self._contract()
        move = next(item for item in contract["moves"] if item["move_id"] == "MOVE-INTRO-GAP")
        move.update(
            {
                "argument_action": "PIVOT",
                "problem_state_before": "Existing accounts leave the boundary unexplained.",
                "problem_state_after": "The boundary becomes the live explanatory problem.",
            }
        )
        self._replace_contract(contract)
        self.assertIn("AP.MOTION.ACTION_INVALID", self._issue_codes())

    def test_title_resonance_requires_a_distinct_body_explanation_move(self) -> None:
        contract = self._contract()
        title = next(item for item in contract["moves"] if item["move_id"] == "MOVE-TITLE-IDENTITY")
        title["resonance_device"] = "metaphor"
        self._replace_contract(contract)
        self.assertIn("AP.TITLE.BODY_ANCHOR_MISSING", self._issue_codes())

        title["body_explanation_move_ref"] = "MOVE-DISCUSSION-THEORY"
        self._replace_contract(contract)
        self.assertNotIn("AP.TITLE.BODY_ANCHOR_MISSING", self._issue_codes())

    def test_epistemic_hook_requires_payment_in_the_declared_order_and_delay(self) -> None:
        contract = self._contract()
        contract["promises"].append(
            {
                "promise_id": "PROMISE-HOOK",
                "promise_type": "epistemic_hook",
                "source_move_ref": "MOVE-INTRO-ANSWER",
                "authority_refs": ["CLM-001"],
                "delivery_move_refs": [],
                "delay_span": "same_section",
                "resolution_type": "RESOLVE",
            }
        )
        self._replace_contract(contract)
        self.assertIn("AP.HOOK.UNPAID", self._issue_codes())

        hook = contract["promises"][-1]
        hook["source_move_ref"] = "MOVE-RESULTS-CORE"
        hook["delivery_move_refs"] = ["MOVE-INTRO-ANSWER"]
        self._replace_contract(contract)
        self.assertIn("AP.HOOK.ORDER_INVALID", self._issue_codes())

        hook["source_move_ref"] = "MOVE-INTRO-ANSWER"
        hook["delivery_move_refs"] = ["MOVE-RESULTS-CORE"]
        self._replace_contract(contract)
        self.assertIn("AP.HOOK.OVERDELAY", self._issue_codes())

        hook["delay_span"] = "next_answer_section"
        self._replace_contract(contract)
        codes = self._issue_codes()
        self.assertNotIn("AP.HOOK.UNPAID", codes)
        self.assertNotIn("AP.HOOK.ORDER_INVALID", codes)
        self.assertNotIn("AP.HOOK.OVERDELAY", codes)

        hook["delivery_move_refs"] = ["MOVE-INTRO-DESIGN"]
        self._replace_contract(contract)
        self.assertIn("AP.HOOK.OVERDELAY", self._issue_codes())

    def test_scene_return_binds_one_verified_context_anchor_without_cycle(self) -> None:
        contract = self._contract()
        intro = next(item for item in contract["moves"] if item["move_id"] == "MOVE-INTRO-QUESTION")
        conclusion = next(item for item in contract["moves"] if item["move_id"] == "MOVE-CONCLUSION-ANSWER")
        intro["authority_refs"].append("EVD-001")
        conclusion["authority_refs"].append("EVD-001")
        intro["verified_scene"] = {"anchor_id": "ANCHOR-OPENING", "authority_ref": "EVD-001"}
        conclusion["verified_scene"] = {"anchor_id": "ANCHOR-OPENING", "authority_ref": "EVD-001"}
        self._write_text(
            "evidence_bank.md",
            "| Anchor ID | Authority Ref | Type | Locator | Exact Span/Known Details | Original Problem | Logical Context | Protected Qualifiers | Manuscript Function | Status |\n"
            "|---|---|---|---|---|---|---|---|---|---|\n"
            "| ANCHOR-OPENING | EVD-001 | scene | p. 1 | one registered opening detail | why the case differs | the detail bounds the explanation | none | opening and return | content-verified |\n",
        )
        contract["cross_section_edges"].append(
            {
                "edge_id": "EDGE-SCENE-RETURN",
                "source_ref": "MOVE-CONCLUSION-ANSWER",
                "target_ref": "MOVE-INTRO-QUESTION",
                "relation": "returns_to",
                "anchor_id": "ANCHOR-OPENING",
            }
        )
        self._replace_contract(contract)
        codes = self._issue_codes()
        self.assertNotIn("AP.SCENE.UNBOUND", codes)
        self.assertNotIn("AP.CLOSURE.ANCHOR_MISMATCH", codes)
        self.assertNotIn("MS-DEPENDENCY-CYCLE", codes)

        self._write_text(
            "evidence_bank.md",
            "| Anchor ID | Authority Ref | Type | Locator | Status |\n"
            "|---|---|---|---|---|\n"
            "| ANCHOR-OPENING | EVD-001 | scene | p. 1 | content-verified |\n",
        )
        self.assertIn("AP.SCENE.UNBOUND", self._issue_codes())
        self._write_text(
            "evidence_bank.md",
            "| Anchor ID | Authority Ref | Type | Locator | Exact Span/Known Details | Original Problem | Logical Context | Protected Qualifiers | Manuscript Function | Status |\n"
            "|---|---|---|---|---|---|---|---|---|---|\n"
            "| ANCHOR-OPENING | EVD-001 | scene | p. 1 | one registered opening detail | why the case differs | the detail bounds the explanation | none | opening and return | content-verified |\n",
        )

        contract["cross_section_edges"][-1]["anchor_id"] = "ANCHOR-OTHER"
        self._replace_contract(contract)
        self.assertIn("AP.CLOSURE.ANCHOR_MISMATCH", self._issue_codes())

        contract["cross_section_edges"][-1].update(
            {
                "source_ref": "MOVE-INTRO-QUESTION",
                "target_ref": "MOVE-CONCLUSION-ANSWER",
                "anchor_id": "ANCHOR-OPENING",
            }
        )
        self._replace_contract(contract)
        self.assertIn("AP.CLOSURE.ORDER_INVALID", self._issue_codes())

    def test_missing_claim_lifecycle_stage_fails_closed(self) -> None:
        contract = self._contract()
        contract["claim_lifecycle"][0]["evaluated"] = []
        self._replace_contract(contract)
        self.assertIn("MS-CLAIM-LIFECYCLE", self._issue_codes())

    def test_reader_state_discontinuity_fails_closed(self) -> None:
        contract = self._contract()
        contract["sections"][1]["reader_state_before"] = ["mutated state"]
        self._replace_contract(contract)
        self.assertIn("MS-READER-STATE", self._issue_codes())

    def test_claim_inference_strengthening_fails_closed(self) -> None:
        contract = self._contract()
        discussion = next(
            move for move in contract["moves"] if move["move_id"] == "MOVE-DISCUSSION-THEORY"
        )
        discussion["inference_strength"] = "causal_effect"
        self._replace_contract(contract)
        self.assertIn("MS-CLAIM-STRENGTHENING", self._issue_codes())

    def test_ghost_claim_on_move_fails_closed(self) -> None:
        contract = self._contract()
        move = next(item for item in contract["moves"] if item["claim_refs"])
        move["claim_refs"].append("CLM-GHOST")
        self._replace_contract(contract)
        self.assertIn("MS-NO-GHOST-CLAIM", self._issue_codes())

    def test_unmapped_formal_proposition_requires_disposition(self) -> None:
        design = json.loads(self._path("research_design.json").read_text(encoding="utf-8"))
        design["propositions"] = [
            {"proposition_id": "PROP-001", "text": "A registered formal proposition."}
        ]
        self._write_json("research_design.json", design)
        self.assertIn("MS-HYPOTHESIS-DISPOSITION", self._issue_codes())

    def test_cross_section_identity_codes_use_singular_claim_and_result(self) -> None:
        contract = self._contract()
        title = next(item for item in contract["moves"] if item["move_id"] == "MOVE-TITLE-IDENTITY")
        title["authority_refs"].remove("CLM-001")
        title["claim_refs"].remove("CLM-001")
        for move in contract["moves"]:
            if move["section_ref"] == "SEC-ABSTRACT" and "RES-001" in move["authority_refs"]:
                move["authority_refs"].remove("RES-001")
        self._replace_contract(contract)
        codes = self._issue_codes()
        self.assertIn("MS-CLAIM-IDENTITY", codes)
        self.assertIn("MS-RESULT-IDENTITY", codes)
        self.assertNotIn("MS-CLAIMS-IDENTITY", codes)
        self.assertNotIn("MS-RESULTS-IDENTITY", codes)

    def test_global_identity_authority_kind_mismatch_fails_closed(self) -> None:
        contract = self._contract()
        contract["global_identity"]["main_claim_refs"] = ["RES-001"]
        self._replace_contract(contract)
        self.assertIn("MS-CLAIM-IDENTITY", self._issue_codes())

    def test_scientific_and_render_orders_are_strict_contract_inputs(self) -> None:
        contract = self._contract()
        contract["scientific_commitment_order"].reverse()
        contract["render_order"] = contract["render_order"][:-1]
        self._replace_contract(contract)
        codes = self._issue_codes()
        self.assertIn("MS-SCIENTIFIC-ORDER", codes)
        self.assertIn("MS-RENDER-ORDER", codes)

    def test_contract_schema_rejects_missing_required_and_extra_fields(self) -> None:
        contract = self._contract()
        contract.pop("contract_id")
        contract["undeclared_control_plane"] = "forbidden"
        self._replace_contract(contract)
        compilation = compiler.compile_workspace(self.outdir, self.config)
        schema_messages = [
            issue.message for issue in compilation.issues if issue.code == "MS-CONTRACT-SCHEMA"
        ]
        self.assertTrue(any("missing required property contract_id" in item for item in schema_messages))
        self.assertTrue(any("unexpected property undeclared_control_plane" in item for item in schema_messages))

    def test_contract_cannot_use_compiler_or_build_output_as_authority(self) -> None:
        contract = self._contract()
        research_question = next(
            item for item in contract["authority_bindings"] if item["ref_id"] == "RQ-MAIN"
        )
        # Windows paths are case-insensitive; changing case must not bypass the
        # derived/build-output authority boundary.
        research_question["source_path"] = compiler.CONTRACT_REL.as_posix().upper()
        self._replace_contract(contract)
        self.assertIn("MS-AUTHORITY-DERIVED", self._issue_codes())

    def test_unregistered_workspace_files_cannot_be_scientific_authority(self) -> None:
        base = self._contract()
        cases = (
            ("scratch_authority.md", "Unregistered research question truth.\n"),
            ("custom/research_truth.json", '{"status": "claimed-authority"}\n'),
        )
        for relative, content in cases:
            with self.subTest(relative=relative):
                self._write_text(relative, content)
                contract = copy.deepcopy(base)
                binding = next(
                    item
                    for item in contract["authority_bindings"]
                    if item["ref_id"] == "RQ-MAIN"
                )
                binding["source_path"] = relative
                binding["selector"] = {"type": "whole_file"}
                self._replace_contract(contract)
                self.assertIn("MS-AUTHORITY-SOURCE", self._issue_codes())

    def test_registered_authority_path_kind_and_selector_must_match(self) -> None:
        base = self._contract()
        cases = (
            ("RQ-MAIN", "method_execution.json", {"type": "whole_file"}),
            ("CLM-001", "confirmed_motivation.md", {"type": "whole_file"}),
            (
                "RES-001",
                "research_design.json",
                {"type": "json_object_id", "id": "RES-001", "id_keys": ["result_id"]},
            ),
        )
        for ref_id, source_path, selector in cases:
            with self.subTest(ref_id=ref_id, source_path=source_path):
                contract = copy.deepcopy(base)
                binding = next(
                    item
                    for item in contract["authority_bindings"]
                    if item["ref_id"] == ref_id
                )
                binding["source_path"] = source_path
                binding["selector"] = selector
                self._replace_contract(contract)
                self.assertIn("MS-AUTHORITY-SOURCE", self._issue_codes())

    def test_json_authority_selector_id_must_equal_binding_ref_id(self) -> None:
        design = json.loads(self._path("research_design.json").read_text(encoding="utf-8"))
        second_claim = copy.deepcopy(design["claims"][0])
        second_claim["claim_id"] = "CLM-002"
        second_claim["statement"] = "A second registered predictor is associated with the outcome."
        second_claim["protected_atoms"]["subject"] = "second registered predictor"
        second_claim["protected_atoms"]["protected_literals"] = [
            "second registered predictor",
            "outcome",
        ]
        design["claims"].append(second_claim)
        self._write_json("research_design.json", design)

        contract = self._contract()
        binding = next(
            item for item in contract["authority_bindings"] if item["ref_id"] == "CLM-001"
        )
        binding["selector"]["id"] = "CLM-002"
        self._replace_contract(contract)

        self.assertIn("MS-AUTHORITY-IDENTITY", self._issue_codes())

    def test_json_authority_rejects_conflicting_registered_identity_fields(self) -> None:
        design = json.loads(self._path("research_design.json").read_text(encoding="utf-8"))
        design["claims"][0]["id"] = "CLM-001"
        design["claims"][0]["claim_id"] = "CLM-002"
        self._write_json("research_design.json", design)

        self.assertIn("MS-AUTHORITY-IDENTITY", self._issue_codes())

    def test_json_authority_correct_identity_binding_still_passes(self) -> None:
        compilation = compiler.compile_workspace(self.outdir, self.config)

        self.assertEqual((), compilation.issues)
        claim_authority = next(
            item for item in compilation.ir["authority_snapshot"] if item["ref_id"] == "CLM-001"
        )
        self.assertEqual("CLM-001", claim_authority["selector"]["id"])
        authority_kinds = {
            item["ref_id"]: item["authority_kind"] for item in compilation.ir["authority_snapshot"]
        }
        self.assertEqual("evidence", authority_kinds["EVD-001"])
        self.assertEqual("source", authority_kinds["SRC-001"])
        self.assertEqual("material", authority_kinds["MAT-001"])

    def test_edge_relation_change_marks_contract_closure_stale(self) -> None:
        self._baseline()
        contract = self._contract()
        edge = next(item for item in contract["cross_section_edges"] if item["relation"] == "supports")
        edge["relation"] = "contradicts"
        self._replace_contract(contract)

        compilation = compiler.compile_workspace(self.outdir, self.config)

        self.assertEqual("STALE", compilation.stale["status"])
        self.assertTrue(compilation.stale["contract_changed"])
        self.assertTrue(compilation.stale["stale_move_refs"])
        self.assertIn(edge["source_ref"], compilation.stale["stale_move_refs"])
        self.assertIn(edge["target_ref"], compilation.stale["stale_move_refs"])

    def test_execution_context_change_outside_selected_result_marks_moves_stale(self) -> None:
        self._baseline()
        execution = json.loads(self._path("method_execution.json").read_text(encoding="utf-8"))
        execution["cluster_unit"] = "new registered execution-wide clustering unit"
        self._write_json("method_execution.json", execution)

        compilation = compiler.compile_workspace(self.outdir, self.config)

        self.assertEqual("STALE", compilation.stale["status"])
        self.assertIn("RES-001", compilation.stale["changed_authority_refs"])
        self.assertIn("MOVE-RESULTS-CORE", compilation.stale["stale_move_refs"])

    def test_manuscript_only_semantic_drift_never_auto_resolves(self) -> None:
        self._baseline()
        mutations = (
            "# Manuscript\n\nResults report 12 units; the abstract reports 21 units.\n",
            "# Manuscript\n\nThe registered association causes the outcome.\n",
            "# Manuscript\n\nConclusion: regulators should immediately mandate the intervention.\n",
        )
        for manuscript in mutations:
            with self.subTest(manuscript=manuscript):
                self._write_text("final_paper/main.md", manuscript)
                compilation = compiler.compile_workspace(self.outdir, self.config)
                self.assertEqual("STALE", compilation.stale["status"])
                self.assertTrue(compilation.stale["manuscript_only_drift"])
                self.assertEqual(
                    len(compilation.ir["moves"]),
                    len(compilation.stale["stale_move_refs"]),
                )
                with self.assertRaises(compiler.ManuscriptCompilerError) as caught:
                    compiler.render_workspace(self.outdir, self.config)
                self.assertIn("MS-STALE-UNREBUILT", {issue.code for issue in caught.exception.issues})

    def test_authority_mutation_propagates_stale_closure_and_blocks_fake_rebuild(self) -> None:
        self._baseline()
        execution = json.loads(self._path("method_execution.json").read_text(encoding="utf-8"))
        execution["runs"][0]["results"][0]["estimate"] = "registered-result-v2"
        self._write_json("method_execution.json", execution)

        compilation = compiler.compile_workspace(self.outdir, self.config)
        self.assertEqual("STALE", compilation.stale["status"])
        self.assertIn("RES-001", compilation.stale["changed_authority_refs"])
        stale_moves = set(compilation.stale["stale_move_refs"])
        self.assertIn("MOVE-RESULTS-CORE", stale_moves)
        self.assertIn("MOVE-DISCUSSION-THEORY", stale_moves)
        self.assertIn("MOVE-CONCLUSION-ANSWER", stale_moves)
        self.assertIn("MOVE-ABSTRACT-RESULT", stale_moves)

        with self.assertRaises(compiler.ManuscriptCompilerError) as caught:
            compiler.render_workspace(self.outdir, self.config)
        self.assertEqual("MS-STALE-UNREBUILT", caught.exception.issues[0].code)

        self._write_text(
            "final_paper/main.md",
            "# Manuscript with unrelated title punctuation!\n\nInitial registered prose.\n",
        )
        with self.assertRaises(compiler.ManuscriptCompilerError) as caught:
            compiler.render_workspace(self.outdir, self.config)
        self.assertEqual("MS-STALE-UNREBUILT", caught.exception.issues[0].code)

        self._write_text("final_paper/main.md", "# Manuscript\n\nRebuild in progress.\n")
        current = compiler.compile_workspace(self.outdir, self.config)
        proof_entries: list[tuple[str, str, str]] = []
        rebuilt_outputs: list[str] = []
        for move_ref in current.stale["stale_move_refs"]:
            pair = self._rebuild_pair(current, move_ref)
            proof_entries.extend(pair)
            rebuilt_outputs.append(self._path(pair[1][2]).read_text(encoding="utf-8"))
        self._write_text(
            "final_paper/main.md",
            "# Manuscript\n\n" + "\n\n".join(rebuilt_outputs),
        )
        compiler.record_rebuild_proofs(self.outdir, self.config, proof_entries)
        compiler.render_workspace(self.outdir, self.config)
        self.assertEqual([], compiler.validate_workspace(self.outdir, self.config))

    def test_output_without_a_validated_packet_cannot_clear_stale(self) -> None:
        self._baseline()
        execution = json.loads(self._path("method_execution.json").read_text(encoding="utf-8"))
        execution["runs"][0]["results"][0]["estimate"] = "registered-result-v2"
        self._write_json("method_execution.json", execution)
        self._write_text("final_paper/main.md", "# Manuscript\n\nRebuilt registered prose.\n")
        current = compiler.compile_workspace(self.outdir, self.config)
        move_ref = current.stale["stale_move_refs"][0]
        output = f".avereth-prose/rebuild-evidence/{move_ref}/output.md"
        self._write_text(output, "The registered predictor is associated with the outcome.\n")

        with self.assertRaises(compiler.ManuscriptCompilerError) as caught:
            compiler.record_rebuild_proofs(
                self.outdir,
                self.config,
                [(move_ref, "section_output", output)],
            )
        self.assertIn("MS-STALE-UNREBUILT", {issue.code for issue in caught.exception.issues})

    def test_legal_packets_and_unique_filler_outputs_cannot_bypass_move_semantics(self) -> None:
        self._baseline()
        current = self._drift_execution()
        entries: list[tuple[str, str, str]] = []
        outputs: list[str] = []
        for move_ref in current.stale["stale_move_refs"]:
            pair = self._rebuild_pair(
                current,
                move_ref,
                reader_question=f"Generic filler question for {move_ref}?",
                reader_update=f"Generic filler update for {move_ref}.",
            )
            entries.extend(pair)
            outputs.append(self._path(pair[1][2]).read_text(encoding="utf-8"))
        self._write_text("final_paper/main.md", "# Manuscript\n\n" + "\n\n".join(outputs))

        with self.assertRaises(compiler.ManuscriptCompilerError) as caught:
            compiler.record_rebuild_proofs(self.outdir, self.config, entries)
        messages = [issue.message for issue in caught.exception.issues]
        self.assertTrue(any("reader_question" in message for message in messages), messages)
        self.assertTrue(any("reader_update" in message for message in messages), messages)

    def test_registered_claim_id_cannot_carry_forged_semantics(self) -> None:
        self._baseline()
        current = self._drift_execution()
        move_ref = next(
            item["contract"]["move_id"]
            for item in current.ir["moves"]
            if item["contract"]["move_id"] in current.stale["stale_move_refs"]
            and "CLM-001" in item["contract"]["claim_refs"]
        )
        forged_claim = {
            "id": "CLM-001",
            "canonical_proposition": "Moon gravity causes immediate policy uptake.",
            "strength": "causal_effect",
            "realization_mode": "semantic",
            "protected_atoms": {
                "subject": "Moon gravity",
                "relation": "causes immediate policy uptake",
                "direction": "positive causal effect",
                "polarity": "affirmative",
                "inferential_strength": "causal_effect",
                "scope": "all policy systems",
                "protected_literals": ["Moon gravity", "policy uptake"],
                "protected_numbers": [],
                "citation_anchors": [],
            },
        }
        entries = self._rebuild_pair(current, move_ref, claim_override=forged_claim)
        output = self._path(entries[1][2]).read_text(encoding="utf-8")
        self._write_text("final_paper/main.md", "# Manuscript\n\n" + output)

        with self.assertRaises(compiler.ManuscriptCompilerError) as caught:
            compiler.record_rebuild_proofs(self.outdir, self.config, entries)
        self.assertIn("MS-CLAIM-SEMANTICS", {issue.code for issue in caught.exception.issues})

    def test_registered_packet_claim_must_intersect_the_move_contract(self) -> None:
        self._baseline()
        design = json.loads(self._path("research_design.json").read_text(encoding="utf-8"))
        design["claims"].append(
            {
                "claim_id": "CLM-002",
                "type": "association",
                "statement": "A second registered Claim is not assigned to the compiled Move.",
                "protected_atoms": {
                    "subject": "second registered Claim",
                    "relation": "not assigned to the compiled Move",
                    "direction": "negative assignment",
                    "polarity": "negative",
                    "inferential_strength": "association",
                    "scope": "the compiled Move contract",
                    "protected_literals": ["second registered Claim", "compiled Move"],
                    "protected_numbers": [],
                    "citation_anchors": [],
                },
            }
        )
        self._write_json("research_design.json", design)
        self._write_text("final_paper/main.md", "# Manuscript\n\nRebuild in progress.\n")
        current = compiler.compile_workspace(self.outdir, self.config)
        move_ref = next(
            item["contract"]["move_id"]
            for item in current.ir["moves"]
            if item["contract"]["move_id"] in current.stale["stale_move_refs"]
            and item["contract"]["claim_refs"]
        )
        entries = self._rebuild_pair(current, move_ref, claim_id="CLM-002")
        output = self._path(entries[1][2]).read_text(encoding="utf-8")
        self._write_text("final_paper/main.md", "# Manuscript\n\n" + output)

        with self.assertRaises(compiler.ManuscriptCompilerError) as caught:
            compiler.record_rebuild_proofs(self.outdir, self.config, entries)
        self.assertTrue(
            any("does not intersect" in issue.message for issue in caught.exception.issues),
            caught.exception.issues,
        )

    def test_resolved_rebuild_evidence_remains_required_for_current_validation(self) -> None:
        self._baseline()
        execution = json.loads(self._path("method_execution.json").read_text(encoding="utf-8"))
        execution["runs"][0]["results"][0]["estimate"] = "registered-result-v2"
        self._write_json("method_execution.json", execution)
        self._write_text("final_paper/main.md", "# Manuscript\n\nRebuild in progress.\n")
        current = compiler.compile_workspace(self.outdir, self.config)
        entries: list[tuple[str, str, str]] = []
        outputs: list[str] = []
        for move_ref in current.stale["stale_move_refs"]:
            pair = self._rebuild_pair(current, move_ref)
            entries.extend(pair)
            outputs.append(self._path(pair[1][2]).read_text(encoding="utf-8"))
        self._write_text("final_paper/main.md", "# Manuscript\n\n" + "\n\n".join(outputs))
        compiler.record_rebuild_proofs(self.outdir, self.config, entries)
        compiler.render_workspace(self.outdir, self.config)
        self.assertEqual([], compiler.validate_workspace(self.outdir, self.config))

        self._path(entries[0][2]).unlink()

        issues = compiler.validate_workspace(self.outdir, self.config)
        self.assertTrue(
            {"MS-REBUILD-PROOF", "MS-REBUILD-PROOF-STALE", "MS-IR-DRIFT"}
            & {issue.code for issue in issues},
            issues,
        )
        build = build_run_status(self.outdir, self.config)
        self.assertTrue(
            any(
                finding.code.startswith("BUILD.MANUSCRIPT.REBUILD.PROOF")
                or finding.code == "BUILD.MANUSCRIPT.IR.DRIFT"
                for finding in build.findings
            ),
            build.findings,
        )

    def test_same_unrelated_output_cannot_cover_multiple_stale_moves(self) -> None:
        self._baseline()
        execution = json.loads(self._path("method_execution.json").read_text(encoding="utf-8"))
        execution["runs"][0]["results"][0]["estimate"] = "registered-result-v2"
        self._write_json("method_execution.json", execution)
        self._write_text("final_paper/main.md", "# Manuscript\n\nRebuilt registered prose.\n")
        current = compiler.compile_workspace(self.outdir, self.config)
        shared = ".avereth-prose/rebuild-evidence/shared-output.md"
        self._write_text(
            shared,
            "The registered predictor is associated with the outcome.\n\n"
            "Registered evidence supports the bounded association.\n",
        )
        entries: list[tuple[str, str, str]] = []
        for move_ref in current.stale["stale_move_refs"]:
            entries.extend(self._rebuild_pair(current, move_ref, output_relative=shared))

        with self.assertRaises(compiler.ManuscriptCompilerError) as caught:
            compiler.record_rebuild_proofs(self.outdir, self.config, entries)
        messages = [issue.message for issue in caught.exception.issues]
        self.assertTrue(any("reused" in message for message in messages), messages)

    def test_rebuild_manifest_uses_the_strict_registered_schema(self) -> None:
        self._baseline()
        entries = self._complete_rebuild(self._drift_execution())
        proof_path = self._path(compiler.REBUILD_REL)
        original_bytes = proof_path.read_bytes()
        original = json.loads(original_bytes.decode("utf-8"))
        recorded_ir = json.loads(self._path(compiler.IR_REL).read_text(encoding="utf-8"))
        stale = json.loads(self._path(compiler.STALE_REL).read_text(encoding="utf-8"))
        resolved_change = stale["resolved_change"]

        mutations: list[tuple[str, dict]] = []
        missing_top = copy.deepcopy(original)
        missing_top.pop("control_plane")
        missing_top.pop("recorded_at")
        mutations.append(("missing required top-level fields", missing_top))
        receipt_claim = copy.deepcopy(original)
        receipt_claim["stage_receipt"] = "PASS"
        mutations.append(("forbidden stage receipt", receipt_claim))
        invalid_time = copy.deepcopy(original)
        invalid_time["recorded_at"] = "not-a-date-time"
        mutations.append(("invalid recorded time", invalid_time))
        item_extra = copy.deepcopy(original)
        item_extra["items"][0]["undeclared_item_field"] = True
        mutations.append(("item extra property", item_extra))
        evidence_extra = copy.deepcopy(original)
        evidence_extra["items"][0]["evidence_items"][0]["undeclared_evidence_field"] = True
        mutations.append(("evidence extra property", evidence_extra))

        for label, mutation in mutations:
            with self.subTest(label=label):
                self._write_json(compiler.REBUILD_REL, mutation)
                proof_issues, _ = compiler._rebuild_proof_issues(
                    self.outdir,
                    recorded_ir,
                    resolved_change,
                )
                self.assertIn(
                    "MS-REBUILD-PROOF-SCHEMA",
                    {issue.code for issue in proof_issues},
                    proof_issues,
                )
                self.assertTrue(compiler.validate_workspace(self.outdir, self.config))
        proof_path.write_bytes(original_bytes)
        self.assertEqual([], compiler.validate_workspace(self.outdir, self.config))
        self.assertTrue(entries)

    def test_docx_canonical_manuscript_can_complete_a_semantic_rebuild(self) -> None:
        self.config["canonical_manuscript"] = "final_paper/main.docx"
        self._write_docx(
            "final_paper/main.docx",
            ["Manuscript", "Initial registered prose."],
            table_cells=["Initial table text."],
        )
        self._baseline()
        entries = self._complete_rebuild(self._drift_execution(), docx=True)
        self.assertTrue(entries)
        self.assertEqual([], compiler.validate_workspace(self.outdir, self.config))

    def test_corrupt_docx_rebuild_realization_fails_closed(self) -> None:
        self.config["canonical_manuscript"] = "final_paper/main.docx"
        self._write_docx("final_paper/main.docx", ["Initial registered prose."])
        self._baseline()
        current = self._drift_execution()
        move_ref = current.stale["stale_move_refs"][0]
        entries = self._rebuild_pair(current, move_ref)
        self._path("final_paper/main.docx").write_bytes(b"not-an-ooxml-package")

        with self.assertRaises(compiler.ManuscriptCompilerError) as caught:
            compiler.record_rebuild_proofs(self.outdir, self.config, entries)
        self.assertIn("MS-MANUSCRIPT-READ", {issue.code for issue in caught.exception.issues})

    def test_baseline_archives_pre_existing_legacy_view_with_sha_manifest(self) -> None:
        legacy = "# Human Section Plan\n\nDo not lose this planning work.\n"
        legacy_trace = {"schema_version": "legacy-manuscript-trace/v9", "status": "reviewed"}
        self._write_text("section_blueprints.md", legacy)
        self._write_json(compiler.TRACE_REL, legacy_trace)

        rendered = compiler.render_workspace(self.outdir, self.config, baseline=True)

        archive_manifest = next(path for path in rendered if path.name == "archive_manifest.json")
        manifest = json.loads(self._path(archive_manifest).read_text(encoding="utf-8"))
        entry = next(item for item in manifest["entries"] if item["original_path"] == "section_blueprints.md")
        trace_entry = next(
            item for item in manifest["entries"] if item["original_path"] == compiler.TRACE_REL.as_posix()
        )
        self.assertEqual(legacy, self._path(entry["archived_path"]).read_text(encoding="utf-8"))
        self.assertEqual(
            legacy_trace,
            json.loads(self._path(trace_entry["archived_path"]).read_text(encoding="utf-8")),
        )
        generated = self._path("section_blueprints.md").read_text(encoding="utf-8")
        self.assertTrue(generated.startswith("<!-- GENERATED BY AVERETH MANUSCRIPT COMPILER"))
        self.assertEqual([], compiler.validate_workspace(self.outdir, self.config))

        preview = compiler.restore_legacy_archive(self.outdir, archive_manifest)
        self.assertEqual("READY", preview["status"])
        restored = compiler.restore_legacy_archive(self.outdir, archive_manifest, apply=True)
        self.assertEqual("APPLIED", restored["status"])
        self.assertEqual(legacy, self._path("section_blueprints.md").read_text(encoding="utf-8"))
        self.assertEqual(
            legacy_trace,
            json.loads(self._path(compiler.TRACE_REL).read_text(encoding="utf-8")),
        )
        self.assertTrue(self._path(restored["restore_manifest"]).is_file())

    def test_legacy_restore_refuses_a_target_that_drifted_after_baseline(self) -> None:
        self._write_text("section_blueprints.md", "# Human plan\n")
        rendered = compiler.render_workspace(self.outdir, self.config, baseline=True)
        archive_manifest = next(path for path in rendered if path.name == "archive_manifest.json")
        self._write_text("section_blueprints.md", "# Later human edit\n")

        with self.assertRaises(compiler.ManuscriptCompilerError) as caught:
            compiler.restore_legacy_archive(self.outdir, archive_manifest, apply=True)
        self.assertIn("MS-LEGACY-RESTORE-DRIFT", {issue.code for issue in caught.exception.issues})

    def test_orphan_generated_marker_blocks_baseline_reset_and_is_preserved(self) -> None:
        orphan = (
            "<!-- GENERATED BY AVERETH MANUSCRIPT COMPILER; DO NOT EDIT -->\n"
            "# Orphan view without a valid MIR\n"
        )
        self._write_text("reader_state_report.md", orphan)
        with self.assertRaises(compiler.ManuscriptCompilerError) as caught:
            compiler.render_workspace(self.outdir, self.config, baseline=True)
        self.assertIn("MS-IR-ORPHANED", {issue.code for issue in caught.exception.issues})
        self.assertEqual(orphan, self._path("reader_state_report.md").read_text(encoding="utf-8"))

    def test_trace_is_a_receipt_bound_closure_root_not_a_rebuildable_view(self) -> None:
        self._baseline()
        self.assertNotIn(compiler.TRACE_REL.as_posix(), REBUILDABLE_VIEW_PATHS)
        self.assertIn(
            compiler.TRACE_REL.as_posix(),
            artifact_manifest(self.outdir, excludes=set(), include_rendered=False),
        )

    def test_receipt_fingerprints_and_currentness_bind_rebuild_leaf_evidence(self) -> None:
        self._baseline()
        entries = self._complete_rebuild(self._drift_execution())
        packet_relative = entries[0][2]
        dispatch_relative = next(path for _, kind, path in entries if kind == "semantic_dispatch")
        dispatch = json.loads(self._path(dispatch_relative).read_text(encoding="utf-8"))
        raw_review_relative = dispatch["review_output_path"]

        audit_manifest = artifact_manifest(
            self.outdir,
            excludes=controller_cli.AUDIT_FINGERPRINT_EXCLUDES,
            include_rendered=False,
            bound_prefixes=controller_cli.AUDIT_BOUND_PREFIXES,
        )
        output_manifest = artifact_manifest(
            self.outdir,
            excludes=controller_cli.FINGERPRINT_EXCLUDES,
        )
        self.assertIn(packet_relative, audit_manifest)
        self.assertIn(raw_review_relative, audit_manifest)
        self.assertIn(packet_relative, output_manifest)
        self.assertIn(raw_review_relative, output_manifest)
        audit_before = controller_cli.audit_fingerprint(self.outdir)
        output_before = controller_cli.output_fingerprint(self.outdir)

        # Minimal PASS-shaped receipts are sufficient here because AMC
        # currentness runs before receipt metadata comparisons.
        self._write_json("workflow_config.json", self.config)
        self._write_json(
            controller_cli.AUDIT_RECEIPT_REL,
            {
                "schema_version": controller_cli.AUDIT_RECEIPT_SCHEMA,
                "framework_version": controller_cli.FRAMEWORK_VERSION,
                "status": "PASS",
            },
        )
        self._write_json(
            controller_cli.OUTPUT_RECEIPT_REL,
            {
                "schema_version": controller_cli.OUTPUT_RECEIPT_SCHEMA,
                "framework_version": controller_cli.FRAMEWORK_VERSION,
                "status": "PASS",
            },
        )

        self._path(packet_relative).unlink()

        self.assertNotEqual(audit_before, controller_cli.audit_fingerprint(self.outdir))
        self.assertNotEqual(output_before, controller_cli.output_fingerprint(self.outdir))
        audit_ok, audit_issue = controller_cli.audit_receipt_status(self.outdir)
        output_ok, output_issue = controller_cli.output_receipt_status(self.outdir)
        self.assertFalse(audit_ok)
        self.assertFalse(output_ok)
        self.assertIn("manuscript compiler currentness failed", audit_issue)
        self.assertIn("manuscript compiler currentness failed", output_issue)

    def test_current_compilation_cannot_replace_the_recorded_prior_mir(self) -> None:
        self._baseline()
        current = self._drift_execution()
        self.assertIsNotNone(current.ir)
        self._write_json(compiler.IR_REL, current.ir)

        drifted = compiler.compile_workspace(self.outdir, self.config)
        self.assertIn("MS-IR-DRIFT", {issue.code for issue in drifted.issues})
        with self.assertRaises(compiler.ManuscriptCompilerError) as caught:
            compiler.render_workspace(self.outdir, self.config)
        self.assertIn("MS-IR-DRIFT", {issue.code for issue in caught.exception.issues})

    def test_missing_ir_with_existing_lineage_cannot_be_rebaselined(self) -> None:
        self._baseline()
        self._drift_execution()
        self._path(compiler.IR_REL).unlink()

        with self.assertRaises(compiler.ManuscriptCompilerError) as caught:
            compiler.render_workspace(self.outdir, self.config, baseline=True)
        self.assertIn("MS-IR-ORPHANED", {issue.code for issue in caught.exception.issues})
        self.assertTrue(self._path(compiler.TRACE_REL).is_file())
        self.assertTrue(self._path(compiler.STALE_REL).is_file())

    def test_missing_stale_manifest_cannot_erase_resolved_proof_lineage(self) -> None:
        self._baseline()
        entries = self._complete_rebuild(self._drift_execution())
        proof_before = self._path(compiler.REBUILD_REL).read_bytes()
        self._path(compiler.STALE_REL).unlink()

        with self.assertRaises(compiler.ManuscriptCompilerError) as caught:
            compiler.render_workspace(self.outdir, self.config)
        self.assertIn("MS-IR-ORPHANED", {issue.code for issue in caught.exception.issues})
        self.assertEqual(proof_before, self._path(compiler.REBUILD_REL).read_bytes())
        self._path(entries[0][2]).unlink()
        self.assertTrue(compiler.validate_workspace(self.outdir, self.config))

    def test_workspace_resolver_rejects_reparse_escape(self) -> None:
        with tempfile.TemporaryDirectory() as external_raw:
            link = self.outdir / "outside-link"
            alias_kind = self._make_directory_alias(Path(external_raw), link)
            try:
                for resolver in (
                    compiler._safe_workspace_path,
                    compiler._canonical_workspace_relative,
                ):
                    with self.subTest(resolver=resolver.__name__), self.assertRaises(ValueError):
                        resolver(self.outdir, "outside-link/escaped.json")
            finally:
                self._remove_directory_alias(link, alias_kind)

    def test_workspace_relative_canonicalizes_lexical_root_alias(self) -> None:
        alias_hop = self._path("alias-hop")
        alias_hop.mkdir()
        artifact = Path(".avereth-prose/alias-check.json")
        self._write_json(artifact, {"status": "inside-workspace"})
        lexical_root_alias = alias_hop / ".."

        relative = compiler._canonical_workspace_relative(
            lexical_root_alias,
            self._path(artifact).resolve(),
        )

        self.assertEqual(artifact, relative)

    def test_rebuild_validation_accepts_workspace_symlink_alias(self) -> None:
        self._baseline()
        compilation = self._drift_execution()
        move_ref = compilation.stale["stale_move_refs"][0]
        entries = self._rebuild_pair(compilation, move_ref)
        clarity_relative = next(
            relative for _, kind, relative in entries if kind == "clarity_draft"
        )
        clarity_text = self._path(clarity_relative).read_text(encoding="utf-8")
        self._write_text(
            str(self.config["canonical_manuscript"]),
            "# Manuscript\n\n" + clarity_text,
        )
        compiler.record_rebuild_proofs(self.outdir, self.config, entries)
        current = compiler.compile_workspace(self.outdir, self.config)
        proof = json.loads(self._path(compiler.REBUILD_REL).read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory() as alias_parent_raw:
            alias = Path(alias_parent_raw) / "workspace-alias"
            alias_kind = self._make_directory_alias(self.outdir, alias)
            try:
                proof_issues = compiler._rebuild_items_issues(
                    alias,
                    current.ir,
                    current.stale,
                    proof["items"],
                    require_full_coverage=False,
                )
                self.assertEqual([], proof_issues)

                node = next(
                    item
                    for item in current.ir["moves"]
                    if item["contract"]["move_id"] == move_ref
                )
                authority_snapshots = {
                    str(item["ref_id"]).upper(): item
                    for item in current.ir["authority_snapshot"]
                }
                packet_relative = next(
                    relative for _, kind, relative in entries if kind == "prose_packet"
                )
                packet_result = compiler._packet_for_move_issues(
                    alias,
                    alias / packet_relative,
                    move_ref,
                    node,
                    authority_snapshots,
                )
                self.assertEqual([], packet_result[-1])
            finally:
                self._remove_directory_alias(alias, alias_kind)

    def test_hand_edited_generated_view_is_rejected(self) -> None:
        self._baseline()
        path = self._path("reader_state_report.md")
        path.write_text(path.read_text(encoding="utf-8") + "hand edit\n", encoding="utf-8")
        issues = compiler.validate_workspace(self.outdir, self.config)
        self.assertIn("MS-VIEW-DRIFT", {issue.code for issue in issues})

    def test_baseline_cannot_overwrite_existing_mir(self) -> None:
        self._baseline()
        with self.assertRaises(compiler.ManuscriptCompilerError) as caught:
            compiler.render_workspace(self.outdir, self.config, baseline=True)
        self.assertEqual("MS-BASELINE-EXISTS", caught.exception.issues[0].code)

    def test_initialization_never_overwrites_reviewed_contract(self) -> None:
        replacement = copy.deepcopy(self._contract())
        with self.assertRaises(compiler.ManuscriptCompilerError) as caught:
            compiler.write_initialized_contract(self.outdir, replacement)
        self.assertEqual("MS-CONTRACT-EXISTS", caught.exception.issues[0].code)


if __name__ == "__main__":
    unittest.main()
