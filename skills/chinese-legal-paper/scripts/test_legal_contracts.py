"""Synthetic contracts only. None of these fixtures is a citable legal source."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

import legal_paper
from legal_core.common import (FILES, SKILL, LegalError, atomic_json, controller, digest,
                               file_hash, read_json, schema_errors, scoped)
from legal_core.validation import check_workspace, receipt_paths, support_digest
from legal_core.citations import audit_docx, render_notes
from legal_core.templates import template


def write(root, path, data):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        target.write_text(data, encoding="utf-8")
    else:
        atomic_json(target, data)
    return target


def bound(root, path):
    return {"path": path, "sha256": file_hash(root / path)}


def anchor(root, path, quote):
    text = (root / path).read_text(encoding="utf-8")
    start = text.index(quote)
    return {**bound(root, path), "start": start, "end": start + len(quote), "quote": quote}


def fixture(root, *, profile="full_paper"):
    config_module, _ = controller()
    from avereth_core.version import VERSION, WORKFLOW_CONFIG_SCHEMA
    cfg = {"schema_version": WORKFLOW_CONFIG_SCHEMA, "framework_version": VERSION,
           "workflow": "rewrite_existing", "task_profile": profile, "publication_track": "cnki-cn",
           "scene": "report_review", "tier": "flash", "output_language": "zh", "word_output": "docx",
           "pdf_output": "none", "citation_mode": "author_year", "word_font_policy": "default",
           "prose_mode": "clear", "translation_package": "none", "submission_package": "none", "response_package": "none",
           "legal_profile": "chinese-law-v1", "canonical_manuscript": "manuscript.md"}
    write(root, "workflow_config.json", cfg)
    write(root, "reference_materials/source.txt", "测试规范第一条：本条只用于软件测试。\n")
    write(root, "review_basis.md", "Synthetic reviewer inspected the synthetic fixture. Not a real legal verification.\n")
    write(root, "manuscript.md", "本条只用于软件测试。[^CIT-001]\n")
    record = {"source_id": "SYNTH-001", "title": "虚构测试规范", "authors": ["测试作者"], "year": "2020", "journal": "测试刊物",
              "local_file": "reference_materials/source.txt", "verification": {"ocr_text_file": "reference_materials/source.txt"}}
    write(root, "reference_materials/literature_registry.json", {"sources": [record]})
    review = {"status": "verified", "reviewer": "synthetic test reviewer", "reviewed_at": date.today().isoformat(),
              "reason": "Synthetic fixture exercise, not a real legal judgment", "basis": bound(root, "review_basis.md")}
    source = {"source_id": record["source_id"], "source_digest": digest(record), "version_id": "synthetic-2020",
              "kind": "statute", "jurisdiction": "synthetic-jurisdiction", "representation": "official_text",
              "authority": {"issuer": "虚构机关", "level": "synthetic", "document_number": "TEST-2020"},
              "identity_review": review, "access": {"level": "fulltext", "permission": "user_provided", "basis": "Synthetic fixture",
                                                      "text": bound(root, "reference_materials/source.txt")},
              "temporal": {"status": "current", "promulgated": "2020-01-01", "effective_from": "2020-01-01",
                           "effective_to": None, "checked_at": date.today().isoformat(), "basis": bound(root, "review_basis.md")}}
    write(root, FILES["sources"], {"schema_version": "legal-sources/v1", "scope": "legal_sources", "scope_reason": "Synthetic test", "sources": [source]})
    claim = {"id": "CLAIM-001", "text": "本条只用于软件测试。", "type": "interpretive"}
    write(root, "research_design.json", {"claims": [claim]})
    method = read_json(SKILL / "assets/method-profiles.json")["profiles"]["doctrinal"]
    analysis = {"schema_version": "legal-analysis/v1", "design": bound(root, "research_design.json"), "method": "doctrinal",
                "method_card": {f: "Synthetic method rationale for " + f for f in method["required_fields"]},
                "claims": [{"claim_id": claim["id"], "claim_digest": digest(claim), "source_ids": [record["source_id"]],
                            "jurisdiction": source["jurisdiction"], "as_of": date.today().isoformat(), "use": "current_law", "applicability_review": review}]}
    write(root, FILES["analysis"], analysis)
    citation = {"citation_id": "CIT-001", "source_id": record["source_id"], "version_id": source["version_id"],
                "claim_id": None if profile == "manuscript_audit" else claim["id"],
                "manuscript_span": anchor(root, "manuscript.md", claim["text"]),
                "evidence": anchor(root, "reference_materials/source.txt", claim["text"]),
                "locator": {"kind": "article", "label": "第一条", "verification": review}, "mode": "quotation"}
    citation["support_review"] = {k: v for k, v in review.items() if k != "basis"}
    citation["support_review"]["binding_digest"] = support_digest(citation, record, None if profile == "manuscript_audit" else claim)
    write(root, FILES["citations"], {"schema_version": "legal-citations/v1", "manuscript": bound(root, "manuscript.md"), "style": "working-footnote-v1", "entries": [citation]})
    write(root, FILES["review"], {"schema_version": "legal-review/v1", "manuscript": bound(root, "manuscript.md"),
                                "checks": {k: review for k in template("review")["checks"]}, "findings": []})
    return cfg


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = fixture(self.root)

    def change(self, name, action):
        data = read_json(self.root / FILES.get(name, name))
        action(data)
        write(self.root, FILES.get(name, name), data)

    def codes(self, stage="audit"):
        return {i["code"] for i in check_workspace(self.root, stage=stage)["issues"]}

    def test_valid_complete_contract_is_read_only(self):
        before = {p.relative_to(self.root): (p.stat().st_mtime_ns, file_hash(p)) for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(check_workspace(self.root)["status"], "PASS")
        after = {p.relative_to(self.root): (p.stat().st_mtime_ns, file_hash(p)) for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_deleted_profile_cannot_bypass_existing_artifacts(self):
        self.change("workflow_config.json", lambda c: c.pop("legal_profile"))
        self.assertIn("PROFILE.REQUIRED", self.codes())

    def test_unknown_fields_rejected(self):
        self.change("sources", lambda d: d.update(trust_everything=True))
        self.assertIn("CONTRACT.INVALID", self.codes())

    def test_source_change_invalidates_binding(self):
        self.change("reference_materials/literature_registry.json", lambda d: d["sources"][0].update(title="changed"))
        self.assertIn("SOURCE.STALE", self.codes())
        self.assertIn("SUPPORT.STALE", self.codes())

    def test_claim_change_invalidates_design_and_support(self):
        self.change("research_design.json", lambda d: d["claims"][0].update(text="different conclusion"))
        self.assertIn("BINDING.STALE", self.codes())
        self.assertIn("SUPPORT.STALE", self.codes())

    def test_wrong_quotation_and_stale_hash(self):
        self.change("citations", lambda d: d["entries"][0]["evidence"].update(quote="invented quotation"))
        self.assertIn("ANCHOR.MISMATCH", self.codes())

    def test_changed_source_file_requires_reacquisition_review(self):
        write(self.root, "reference_materials/source.txt", "replaced content")
        self.assertIn("BINDING.STALE", self.codes("acquisition"))

    def test_abstract_is_not_fulltext_support(self):
        self.change("sources", lambda d: d["sources"][0]["access"].update(level="abstract"))
        self.assertIn("CITATION.TEXT_ACCESS", self.codes())

    def test_unknown_permission_does_not_enable_fulltext(self):
        self.change("sources", lambda d: d["sources"][0]["access"].update(permission="unknown"))
        self.assertIn("ACCESS.UNPROVEN", self.codes())

    def test_source_text_cannot_come_from_an_unregistered_file(self):
        write(self.root, "different.txt", "extra text")
        self.change("sources", lambda d: d["sources"][0]["access"].update(text=bound(self.root, "different.txt")))
        self.assertIn("TEXT.NOT_CANONICAL", self.codes())

    def test_repealed_version_is_not_current(self):
        self.change("sources", lambda d: d["sources"][0]["temporal"].update(status="repealed", effective_to="2021-01-01"))
        self.assertIn("LAW.NOT_EFFECTIVE", self.codes())

    def test_end_date_is_exclusive(self):
        self.change("sources", lambda d: d["sources"][0]["temporal"].update(effective_to=date.today().isoformat()))
        self.assertIn("LAW.NOT_EFFECTIVE", self.codes())

    def test_cross_jurisdiction_needs_reason(self):
        self.change("analysis", lambda d: d["claims"][0].update(jurisdiction="different"))
        self.assertIn("CLAIM.JURISDICTION", self.codes())

    def test_historical_application_needs_fact_date(self):
        self.change("analysis", lambda d: d["claims"][0].update(use="historical_law"))
        self.assertIn("LAW.FACT_DATE", self.codes())

    def test_printed_and_pdf_pages_are_not_interchangeable(self):
        self.change("citations", lambda d: d["entries"][0]["locator"].update(kind="printed_page", pdf_page=10))
        self.assertIn("LOCATOR.PAGE", self.codes())

    def test_missing_marker_detected(self):
        data = read_json(self.root / FILES["citations"])
        data["entries"][0]["citation_id"] = "CIT-002"
        write(self.root, FILES["citations"], data)
        self.assertIn("CITATION.COVERAGE", self.codes())

    def test_unknown_canonical_claim_detected(self):
        self.change("analysis", lambda d: d["claims"][0].update(claim_id="invented"))
        self.assertIn("CLAIM.UNKNOWN", self.codes())
        self.assertIn("CLAIM.COVERAGE", self.codes())

    def test_method_required_fields_checked(self):
        self.change("analysis", lambda d: d["method_card"].pop("strongest_objection"))
        self.assertIn("METHOD.INCOMPLETE", self.codes())

    def test_case_summary_cannot_pretend_to_be_court_text(self):
        self.change("sources", lambda d: d["sources"][0].update(kind="case", representation="editorial_summary"))
        self.assertIn("CASE.REPRESENTATION", self.codes())

    def test_unresolved_finding_blocks_audit(self):
        self.change("review", lambda d: d["findings"].append({"id":"F1","severity":"blocking","status":"open","reason":"Synthetic unresolved issue"}))
        self.assertIn("REVIEW.OPEN", self.codes())

    def test_false_resolution_without_basis_blocked(self):
        self.change("review", lambda d: d["findings"].append({"id":"F1","severity":"blocking","status":"resolved","reason":"Synthetic resolved issue"}))
        self.assertIn("REVIEW.RESOLUTION_MISSING", self.codes())

    def test_empty_templates_are_not_accepted(self):
        write(self.root, FILES["analysis"], template("analysis"))
        self.assertIn("CONTRACT.INVALID", self.codes())

    def test_audit_only_uses_bound_manuscript_without_design(self):
        fixture(self.root, profile="manuscript_audit")
        (self.root / "research_design.json").unlink()
        (self.root / FILES["analysis"]).unlink()
        self.assertEqual("PASS", check_workspace(self.root)["status"])

    def test_partial_task_does_not_require_downstream_artifacts(self):
        (self.root / FILES["analysis"]).unlink()
        self.assertEqual("PASS", check_workspace(self.root, stage="research")["status"])

    def test_receipt_closure_includes_review_evidence(self):
        self.assertIn("review_basis.md", receipt_paths(self.root))
        from avereth_core.cli import artifact_manifest, artifact_fingerprint
        self.assertIn("legal_citations.json", artifact_manifest(self.root, excludes=set()))
        before = artifact_fingerprint(self.root, excludes=set())
        write(self.root, "review_basis.md", "changed review evidence")
        self.assertNotEqual(before, artifact_fingerprint(self.root, excludes=set()))

    def test_core_reopens_earliest_failing_stage(self):
        from avereth_core.cli import attach_canonical_stages
        (self.root / FILES["sources"]).unlink()
        status = attach_canonical_stages({"next_stage":"complete","is_complete":True,"task_profile":"full_paper"}, self.root)
        self.assertEqual(status["next_stage"], "acquisition")
        self.assertFalse(status["is_complete"])
        self.assertEqual(len(status["stages"]), 8)

    def test_core_reports_missing_plugin_instead_of_bypassing_it(self):
        from avereth_core.infrastructure import legal_domain
        with mock.patch.object(legal_domain, "_module", side_effect=ImportError()):
            self.assertEqual("LEGAL.RUNTIME_UNAVAILABLE", legal_domain.checks(self.root, "audit")["issues"][0]["code"])

    def test_nonlegal_workspace_stays_unchanged(self):
        from avereth_core.infrastructure.legal_domain import apply_status
        for relative in FILES.values():
            (self.root / relative).unlink()
        self.change("workflow_config.json", lambda d: d.pop("legal_profile"))
        payload = {"next_stage":"complete", "is_complete":True}
        apply_status(payload, self.root)
        self.assertEqual(payload, {"next_stage":"complete", "is_complete":True})

    def test_withdrawn_research_does_not_reopen_later_stages(self):
        from avereth_core.infrastructure.legal_domain import apply_status
        for name in ("analysis", "citations", "review"):
            (self.root / FILES[name]).unlink()
        payload = {"next_stage":"complete", "is_complete":True, "terminal_stage":"research", "terminal_outcome":"withdrawn"}
        apply_status(payload, self.root)
        self.assertTrue(payload["is_complete"])

    def test_plan_writes_are_domain_conditional(self):
        from avereth_core.application.plan_service import _allowed_writes, _adapters
        self.assertIn(FILES["sources"], _allowed_writes("acquisition", self.config, "full_paper"))
        plain = {k:v for k,v in self.config.items() if k != "legal_profile"}
        self.assertNotIn(FILES["sources"], _allowed_writes("acquisition", plain, "full_paper"))
        self.assertIn("chinese-legal-paper", _adapters("build", "cnki-cn", self.config))

    def test_enable_preview_and_backup_preserve_original(self):
        self.change("workflow_config.json", lambda d: d.pop("legal_profile"))
        (self.root / FILES["sources"]).unlink()
        before = (self.root / "workflow_config.json").read_bytes()
        self.assertFalse(legal_paper.enable(self.root)["changes_applied"])
        self.assertEqual(before, (self.root / "workflow_config.json").read_bytes())
        result = legal_paper.enable(self.root, True)
        self.assertEqual(before, (self.root / result["backup"]).read_bytes())
        self.assertEqual("UNCHANGED", legal_paper.enable(self.root, True)["status"])
        self.assertFalse(result["completion_receipt_created"])

    def test_formatting_uses_actual_structured_fields(self):
        note = render_notes(self.root)
        self.assertIn("[^CIT-001]:", note)
        self.assertIn("TEST-2020", note)
        self.assertIn("第一条", note)
        self.assertNotIn("第10页", note)

    def test_unknown_schema_assertion_fails_closed(self):
        self.assertTrue(schema_errors({"q":"x"}, {"type":"object", "dependentRequired":{"q":["other"]}}))
        self.assertFalse(schema_errors({"q":"x"}, {"type":"object", "required":["q"], "properties":{"q":{"type":"string"}},"additionalProperties":False}))
        self.assertTrue(schema_errors(4, {"oneOf":[{"type":"integer"},{"type":"integer","multipleOf":2}]}))

    def test_duplicate_json_members_are_not_silently_overwritten(self):
        write(self.root, "duplicate.json", '{"status":"pending","status":"verified"}')
        with self.assertRaises(LegalError):
            read_json(self.root / "duplicate.json")

    def test_scientific_receipt_binds_legal_rules_when_enabled(self):
        from avereth_core.cli import scientific_runtime_groups_for_config
        from avereth_core.scientific_runtime import scientific_runtime_manifest
        groups = scientific_runtime_groups_for_config(self.config)
        self.assertIn("legal", groups)
        manifest = scientific_runtime_manifest(SKILL.parent, groups=groups)
        self.assertIn("chinese-legal-paper/scripts/legal_core/validation.py", manifest)
        self.assertIn("chinese-legal-paper/assets/method-profiles.json", manifest)
        self.assertNotIn("missing", manifest.values())

    def test_check_scope_never_claims_a_completion_receipt(self):
        result = check_workspace(self.root, stage="acquisition")
        self.assertEqual("acquisition", result["through_stage"])
        self.assertFalse(result["is_completion_receipt"])

    def test_core_gate_rechecks_stale_complete_snapshot(self):
        from avereth_core import cli
        from types import SimpleNamespace
        from io import StringIO
        from contextlib import redirect_stdout
        (self.root / FILES["review"]).unlink()
        with mock.patch.object(cli,"run_doctor",return_value=SimpleNamespace(ok=True)), mock.patch.object(cli,"status_payload",return_value=({"next_stage":"complete"},0)), redirect_stdout(StringIO()):
            code = cli.gate_stage(self.root, "output", SKILL.parent)
        self.assertEqual(1, code)

    def test_paths_cannot_escape(self):
        for path in ("../secret.txt", "C:/secret.txt", "/etc/passwd", "a\\b.txt"):
            with self.subTest(path=path), self.assertRaises(LegalError):
                scoped(self.root, path)

    def test_docx_native_footnotes_and_orphans(self):
        w = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        path = self.root / "test.docx"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("word/document.xml", f'<w:document xmlns:w="{w}"><w:body><w:p><w:r><w:footnoteReference w:id="1"/></w:r></w:p></w:body></w:document>')
            z.writestr("word/footnotes.xml", f'<w:footnotes xmlns:w="{w}"><w:footnote w:id="1"><w:p><w:r><w:t>test</w:t></w:r></w:p></w:footnote></w:footnotes>')
        self.assertEqual("PASS", audit_docx(path)["status"])
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("word/document.xml", f'<w:document xmlns:w="{w}"><w:footnoteReference w:id="2"/></w:document>')
        self.assertEqual("FAIL", audit_docx(path)["status"])


if __name__ == "__main__":
    unittest.main()
