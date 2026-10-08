from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cnki_acquisition as acq


def minimal_pdf_bytes(label: str = "fixture", body_text: str | None = None) -> bytes:
    safe_label = re.sub(r"[^A-Za-z0-9._-]", "-", label).encode("ascii")
    if body_text is None:
        body_text = (
            "Introduction. This regression article develops a theory and conceptual framework. "
            "Methods and data identify the research design. Analysis and results compare evidence "
            "with competing explanations. Discussion and conclusion state limitations. "
            "References. Author One 2024. Author Two 2025. " * 5
        )
    escaped_body = (
        body_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    ).encode("ascii", errors="ignore")
    content = b"BT /F1 10 Tf 36 740 Td (" + escaped_body + b") Tj ET"
    header = b"%PDF-1.4\n% " + safe_label + b"\n"
    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R 4 0 R 5 0 R] /Count 3 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 9 0 R >> >> /Contents 6 0 R >>\nendobj\n",
        b"4 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 9 0 R >> >> /Contents 7 0 R >>\nendobj\n",
        b"5 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 9 0 R >> >> /Contents 8 0 R >>\nendobj\n",
        b"6 0 obj\n<< /Length "
        + str(len(content)).encode("ascii")
        + b" >>\nstream\n"
        + content
        + b"\nendstream\nendobj\n",
        b"7 0 obj\n<< /Length "
        + str(len(content)).encode("ascii")
        + b" >>\nstream\n"
        + content
        + b"\nendstream\nendobj\n",
        b"8 0 obj\n<< /Length "
        + str(len(content)).encode("ascii")
        + b" >>\nstream\n"
        + content
        + b"\nendstream\nendobj\n",
        b"9 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    body = bytearray(header)
    offsets = [0]
    for obj in objects:
        offsets.append(len(body))
        body.extend(obj)
    xref_offset = len(body)
    body.extend(b"xref\n0 10\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        body.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    body.extend(
        b"trailer\n<< /Size 10 /Root 1 0 R >>\nstartxref\n"
        + str(xref_offset).encode("ascii")
        + b"\n%%EOF\n"
    )
    return bytes(body)


class AcquisitionRegistryTests(unittest.TestCase):
    def test_public_web_channel_still_requires_review_after_local_capture(self) -> None:
        self.assertTrue(
            acq.is_public_web_source(
                {
                    "channel": "web",
                    "url": "",
                    "local_file": "reference_materials/pdfs/captured-page.pdf",
                }
            )
        )
        self.assertFalse(
            acq.is_public_web_source(
                {
                    "channel": "official-web",
                    "url": "",
                    "local_file": "reference_materials/pdfs/official-record.pdf",
                }
            )
        )

    PDF_BYTES = minimal_pdf_bytes()

    def test_article_body_signals_accepts_chinese_footnote_reference_apparatus(self) -> None:
        text = """
        摘要：本文讨论国际制度选择。
        一、制度经验
        正文材料与分析。①张三：《国际制度研究》，《国际关系研究》2024年第1期。
        二、制度约束
        继续展开论证。②李四：《全球治理研究》，《世界经济与政治》2023年第2期。
        三、竞争解释
        比较不同解释。③王五：《非正式制度研究》，《国际政治科学》2022年第3期。
        五、结语
        本文总结证据边界。
        """
        self.assertTrue(acq.article_body_signals(text))

    def make_project(self, root: Path) -> tuple[Path, dict]:
        base = root / "paper_rewriting_output"
        pdf_dir = base / "materials" / "cnki_pdfs"
        pdf_dir.mkdir(parents=True)
        (base / "workflow_config.json").write_text(
            json.dumps(
                {
                    "workflow": "build_from_materials",
                    "scene": "journal",
                    "tier": "flash",
                    "output_language": "zh",
                    "target_name": "测试期刊",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        queries = [
            {
                "query_id": "Q-VENUE",
                "channel": "CNKI",
                "purpose": "venue",
                "query": "测试期刊",
                "result_count": 1,
                "url": "https://navi.cnki.net/knavi/detail?id=venue",
                "collected_at": "2026-07-28",
                "status": "complete",
            },
            {
                "query_id": "Q-EXEMPLAR",
                "channel": "CNKI",
                "purpose": "target-exemplar",
                "query": "测试期刊 2026",
                "result_count": 12,
                "url": "https://navi.cnki.net/knavi/detail?id=examples",
                "collected_at": "2026-07-28",
                "status": "complete",
            },
            {
                "query_id": "Q-SOTA",
                "channel": "CNKI",
                "purpose": "sota",
                "query": "主题=治理机制",
                "result_count": 80,
                "url": "https://kns.cnki.net/kns8s/search?kw=sota",
                "collected_at": "2026-07-28",
                "status": "complete",
            },
        ]
        sources = []
        for index in range(1, 4):
            relative = f"materials/cnki_pdfs/T{index}.pdf"
            pdf = base / relative
            pdf.write_bytes(self.PDF_BYTES + f"% exemplar {index}\n".encode("ascii"))
            sources.append(
                {
                    "source_id": f"CNKI-T{index:03d}",
                    "channel": "CNKI",
                    "roles": ["target-example"],
                    "title": f"目标范文{index}",
                    "url": f"https://kns.cnki.net/kcms2/article/abstract?id=T{index}",
                    "query_ids": ["Q-EXEMPLAR"],
                    "state": "pdf-downloaded",
                    "verification": {
                        "method": "pdf",
                        "verified_at": "2026-07-28",
                        "title_match": "yes",
                        "support_claim": "这是一条从完整范文中核验出的结构与论证用途说明。",
                    },
                    "local_file": relative,
                    "sha256": acq.sha256_file(pdf),
                    "citation_scope": "not-for-citation",
                    "reason": "目标刊任务同构范文",
                    "used_for": ["style"],
                    "collected_at": "2026-07-28",
                }
            )
        for index in range(1, 4):
            sources.append(
                {
                    "source_id": f"CNKI-S{index:03d}",
                    "channel": "CNKI",
                    "roles": ["field-sota", "citation-candidate"],
                    "title": f"前沿文献{index}",
                    "publication_year": 2026,
                    "url": f"https://kns.cnki.net/kcms2/article/abstract?id=S{index}",
                    "query_ids": ["Q-SOTA"],
                    "state": "content-verified",
                    "verification": {
                        "method": "abstract",
                        "verified_at": "2026-07-28",
                        "support_claim": "这是一条从摘要或详情页核验出的、能够支持具体文献判断的陈述。",
                    },
                    "local_file": "",
                    "citation_scope": "final-source",
                    "reason": "领域前沿与候选主张直接相关",
                    "used_for": ["sota", "citation"],
                    "collected_at": "2026-07-28",
                }
            )
        registry = {
            "schema_version": acq.SCHEMA_VERSION,
            "target_name": "测试期刊",
            "tier": "flash",
            "access": {
                "status": "verified",
                "method": "institutional-ip",
                "checked_at": "2026-07-28",
                "download_probe": {
                    "status": "passed",
                    "url": "https://kns.cnki.net/kcms2/article/abstract?id=probe",
                },
            },
            "queries": queries,
            "sources": sources,
        }
        acq.atomic_write_json(acq.registry_path(base), registry)
        (base / acq.INDEX_REL).write_text(acq.build_source_index(registry), encoding="utf-8")
        return base, registry

    def add_public_web_source(
        self,
        registry: dict,
        source_id: str,
        *,
        corroborating_source_ids: list[str],
        contradicting_source_ids: list[str] | None = None,
        status: str = "passed",
    ) -> dict:
        if not any(query.get("query_id") == "Q-WEB" for query in registry["queries"]):
            registry["queries"].append(
                {
                    "query_id": "Q-WEB",
                    "channel": "web",
                    "purpose": "other",
                    "query": "public commentary",
                    "result_count": 10,
                    "url": "https://example.org/search",
                    "collected_at": "2026-07-28",
                    "status": "complete",
                }
            )
        source = {
            "source_id": source_id,
            "channel": "web",
            "roles": ["other"],
            "title": f"Public commentary {source_id}",
            "publication_year": 2026,
            "url": f"https://example.org/{source_id.lower()}",
            "query_ids": ["Q-WEB"],
            "state": "content-verified",
            "verification": {
                "method": "full-text",
                "verified_at": "2026-07-28",
                "support_claim": (
                    f"The verified page {source_id} supplies a concrete factual statement "
                    "for lateral comparison."
                ),
            },
            "citation_scope": "final-source",
            "reason": "Provides a public claim material to the empirical chronology",
            "used_for": ["background"],
            "collected_at": "2026-07-28",
            "credibility": {
                "source_class": "news-media",
                "authorship_publisher": "Example newsroom; named staff writer",
                "sponsorship_interest": "Ownership and disclosed sponsorship reviewed",
                "corroborating_source_ids": corroborating_source_ids,
                "contradicting_source_ids": contradicting_source_ids or [],
                "checked_at": "2026-07-28",
                "status": status,
                "note": "Authorship, interests, and registered lateral evidence were reviewed.",
            },
        }
        registry["sources"].append(source)
        return source

    def add_scholar_query(
        self,
        registry: dict,
        *,
        query_id: str = "Q-GS",
        purpose: str = "citation",
        url: str = "https://scholar.google.com/scholar?q=%22weaponized+interdependence%22&hl=en",
    ) -> dict:
        query = {
            "query_id": query_id,
            "channel": "Google Scholar",
            "purpose": purpose,
            "query": '"weaponized interdependence"',
            "filters": {
                "years": "2019-2026",
                "sort": "relevance",
                "first_page_only": True,
            },
            "result_count": 1250,
            "result_count_is_approximate": True,
            "result_count_basis": "page-displayed-about-total",
            "result_count_note": "Scholar page displayed an About/约数 total.",
            "url": url,
            "collected_at": "2026-08-04",
            "status": "complete",
        }
        registry["queries"].append(query)
        return query

    def add_scholar_candidate(
        self,
        registry: dict,
        *,
        source_id: str = "GS-001",
        query_id: str = "Q-GS",
        state: str = "discovered",
    ) -> dict:
        source = {
            "source_id": source_id,
            "channel": "Google Scholar",
            "roles": ["citation-candidate"],
            "title": "Weaponized Interdependence",
            "authors": ["Henry Farrell", "Abraham Newman"],
            "venue": "International Security",
            "publication_year": 2019,
            "url": f"https://direct.mit.edu/isec/article/{source_id.lower()}",
            "query_ids": [query_id],
            "state": state,
            "verification": {},
            "citation_scope": "candidate-only",
            "reason": "Foreign discovery candidate for collision and DOI recovery",
            "used_for": ["screening", "collision"],
            "collected_at": "2026-08-04",
            "metadata": {
                "scholar_snippet": "A search-result excerpt that is not content verification.",
                "scholar_cited_by": 1800,
            },
        }
        registry["sources"].append(source)
        return source

    def validate_updated_registry(self, base: Path, registry: dict) -> acq.ValidationResult:
        acq.atomic_write_json(acq.registry_path(base), registry)
        (base / acq.INDEX_REL).write_text(
            acq.build_source_index(registry), encoding="utf-8"
        )
        return acq.validate_registry(base)

    def authorize_external_target_examples(self, base: Path, registry: dict) -> None:
        target = "Journal of Chinese Governance"
        registry["target_name"] = target
        config_path = base / "workflow_config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["target_name"] = target
        contract = {
            "exception_id": "USER-EX-JCG",
            "authorized_by": "user",
            "authorized_at": "2026-08-12",
            "scope": "target-exemplar-channel",
            "target_venue": target,
            "activation_condition": "completed-cnki-zero-result",
            "cnki_probe_query_ids": ["Q-VENUE", "Q-EXEMPLAR"],
            "allowed_channels": [
                "publisher-official",
                "lawful-institutional-repository",
            ],
            "allowed_origin_hosts": ["publisher.example"],
            "required_count": 3,
            "require_not_for_citation": True,
        }
        config["target_exemplar_acquisition_override"] = contract
        config_path.write_text(json.dumps(config), encoding="utf-8")
        registry["queries"][0]["result_count"] = 0
        registry["queries"][0]["query"] = f"source={target}"
        registry["queries"][1]["result_count"] = 0
        registry["queries"][1]["query"] = (
            f"title=External target exemplar 1 AND source={target}"
        )
        registry["authorized_exceptions"] = [contract]
        for index, source in enumerate(registry["sources"][:3], start=1):
            channel = (
                "publisher-official"
                if index % 2
                else "lawful-institutional-repository"
            )
            query_id = f"Q-EXT-{index}"
            doi = f"10.1080/23812346.2026.{index}"
            registry["queries"].append(
                {
                    "query_id": query_id,
                    "channel": channel,
                    "purpose": "target-exemplar",
                    "query": f"DOI={doi}",
                    "result_count": 1,
                    "url": f"https://publisher.example/search/{index}",
                    "collected_at": "2026-08-12",
                    "status": "complete",
                }
            )
            source.update(
                {
                    "channel": channel,
                    "venue": target,
                    "doi": doi,
                    "url": f"https://publisher.example/article/{index}",
                    "query_ids": [query_id],
                    "citation_scope": "not-for-citation",
                }
            )
            source["verification"]["acquisition_exception_id"] = "USER-EX-JCG"
            source["verification"]["content_url"] = (
                f"https://publisher.example/pdf/{index}"
            )

    def make_international_project(self, root: Path) -> tuple[Path, dict]:
        base = root / "paper_rewriting_output"
        pdf_dir = base / "materials" / "target_exemplars"
        pdf_dir.mkdir(parents=True)
        target = "International Security"
        config = {
            "workflow": "build_from_materials",
            "scene": "journal",
            "tier": "pro",
            "output_language": "en",
            "target_name": target,
            "publication_track": "international-ssci",
        }
        (base / "workflow_config.json").write_text(
            json.dumps(config), encoding="utf-8"
        )
        target_pdf = pdf_dir / "INTL-T001.pdf"
        target_pdf.write_bytes(minimal_pdf_bytes("international-exemplar"))
        sota_pdf = base / "materials" / "sota" / "INTL-S001.pdf"
        sota_pdf.parent.mkdir(parents=True)
        sota_pdf.write_bytes(minimal_pdf_bytes("international-sota"))
        registry = {
            "schema_version": acq.SCHEMA_VERSION,
            "target_name": target,
            "tier": "pro",
            "publication_track": "international-ssci",
            "access": {
                "status": "verified",
                "method": "publisher-subscription",
                "checked_at": "2026-08-14",
                "download_probe": {
                    "status": "passed",
                    "url": "https://direct.mit.edu/isec/article-pdf/probe",
                },
            },
            "queries": [
                {
                    "query_id": "Q-I-VENUE",
                    "channel": "publisher-official",
                    "purpose": "venue",
                    "query": f"journal={target}",
                    "result_count": 1,
                    "url": "https://direct.mit.edu/isec",
                    "collected_at": "2026-08-14",
                    "status": "complete",
                },
                {
                    "query_id": "Q-I-EXEMPLAR",
                    "channel": "publisher-official",
                    "purpose": "target-exemplar",
                    "query": "DOI=10.1162/isec_a_00499",
                    "result_count": 1,
                    "url": "https://direct.mit.edu/isec/search-results",
                    "collected_at": "2026-08-14",
                    "status": "complete",
                },
                {
                    "query_id": "Q-I-SOTA",
                    "channel": "OpenAlex",
                    "purpose": "sota",
                    "query": "security interdependence institutional mechanism",
                    "result_count": 42,
                    "url": "https://api.openalex.org/works?search=security+interdependence",
                    "collected_at": "2026-08-14",
                    "status": "complete",
                },
            ],
            "sources": [
                {
                    "source_id": "INTL-T001",
                    "channel": "publisher-official",
                    "roles": ["target-example"],
                    "title": "A Role-Valid International Target Exemplar",
                    "venue": target,
                    "doi": "10.1162/isec_a_00499",
                    "url": "https://direct.mit.edu/isec/article/49/1/1/000001",
                    "query_ids": ["Q-I-EXEMPLAR"],
                    "state": "pdf-downloaded",
                    "verification": {
                        "method": "pdf",
                        "verified_at": "2026-08-14",
                        "title_match": "yes",
                        "support_claim": "The full article verifies the target journal's argument structure and evidence-to-claim sequence.",
                        "content_url": "https://direct.mit.edu/isec/article-pdf/49/1/1/000001",
                        "retraction_status": "not-retracted",
                        "retraction_checked_at": "2026-08-14",
                    },
                    "local_file": "materials/target_exemplars/INTL-T001.pdf",
                    "sha256": acq.sha256_file(target_pdf),
                    "citation_scope": "not-for-citation",
                    "reason": "Same-journal exemplar for structure and genre calibration",
                    "used_for": ["style"],
                    "collected_at": "2026-08-14",
                },
                {
                    "source_id": "INTL-S001",
                    "channel": "publisher-official",
                    "roles": ["field-sota", "citation-candidate"],
                    "title": "International Evidence on Interdependence Mechanisms",
                    "authors": ["Alex Researcher"],
                    "venue": "International Organization",
                    "publication_year": 2026,
                    "doi": "10.1017/S0020818326000010",
                    "url": "https://www.cambridge.org/core/journals/international-organization/article/000001",
                    "query_ids": ["Q-I-SOTA"],
                    "state": "content-verified",
                    "verification": {
                        "method": "full-text",
                        "verified_at": "2026-08-14",
                        "support_claim": "The verified article states a competing mechanism and the observable conditions under which it should operate.",
                        "content_url": "https://www.cambridge.org/core/services/aop-file-manager/file/000001.pdf",
                        "retraction_status": "not-retracted",
                        "retraction_checked_at": "2026-08-14",
                    },
                    "local_file": "materials/sota/INTL-S001.pdf",
                    "sha256": acq.sha256_file(sota_pdf),
                    "citation_scope": "final-source",
                    "reason": "Directly bears on the field-SOTA dispute and competing explanation",
                    "used_for": ["sota", "citation"],
                    "collected_at": "2026-08-14",
                },
            ],
        }
        acq.atomic_write_json(acq.registry_path(base), registry)
        (base / acq.INDEX_REL).write_text(
            acq.build_source_index(registry), encoding="utf-8"
        )
        return base, registry

    def test_valid_flash_registry_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, _ = self.make_project(Path(tmp))
            result = acq.validate_registry(base)
            self.assertTrue(result.ok, result.issues)
            self.assertEqual(3, result.stats["target_examples"])
            self.assertEqual(3, result.stats["field_sota"])

    def test_international_track_accepts_role_valid_foreign_exemplar_and_sota_without_cnki(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, _ = self.make_international_project(Path(tmp))
            result = acq.validate_registry(base)
            self.assertTrue(result.ok, result.issues)
            self.assertEqual("international-ssci", result.stats["publication_track"])
            self.assertEqual(0, result.stats["cnki_sources"])
            self.assertEqual(1, result.stats["target_examples_international"])
            self.assertEqual(1, result.stats["field_sota_international"])

    def test_same_foreign_only_registry_still_fails_when_switched_to_cnki_cn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_international_project(Path(tmp))
            config_path = base / "workflow_config.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["publication_track"] = "cnki-cn"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            registry["publication_track"] = "cnki-cn"
            result = self.validate_updated_registry(base, registry)
            self.assertFalse(result.ok)
            self.assertTrue(
                any("no CNKI source records" in issue for issue in result.issues),
                result.issues,
            )

    def test_international_track_must_be_persisted_in_both_config_and_registry(self) -> None:
        for missing_side in ("config", "registry"):
            with self.subTest(missing_side=missing_side), tempfile.TemporaryDirectory() as tmp:
                base, registry = self.make_international_project(Path(tmp))
                if missing_side == "config":
                    config_path = base / "workflow_config.json"
                    config = json.loads(config_path.read_text(encoding="utf-8"))
                    config.pop("publication_track")
                    config_path.write_text(json.dumps(config), encoding="utf-8")
                    result = acq.validate_registry(base)
                else:
                    registry.pop("publication_track")
                    result = self.validate_updated_registry(base, registry)
                self.assertFalse(result.ok)
                self.assertTrue(
                    any("persist publication_track in both" in issue for issue in result.issues),
                    result.issues,
                )

    def test_international_role_rejects_discovery_metadata_as_full_text_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_international_project(Path(tmp))
            target_source = registry["sources"][0]
            target_source["channel"] = "Google Scholar"
            target_source["verification"]["content_url"] = (
                "https://scholar.google.com/scholar?q=target"
            )
            result = self.validate_updated_registry(base, registry)
            self.assertFalse(result.ok)
            self.assertTrue(
                any("international role contract" in issue for issue in result.issues),
                result.issues,
            )

    def test_international_role_rejects_self_declared_metadata_as_field_sota(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_international_project(Path(tmp))
            source = registry["sources"][1]
            source.pop("doi")
            source["url"] = "https://metadata.example.org/record/INTL-S001"
            source["verification"]["content_url"] = source["url"]
            result = self.validate_updated_registry(base, registry)
            self.assertFalse(result.ok)
            self.assertTrue(
                any(
                    "discovery/metadata page" in issue
                    or "positive-result international sota query" in issue
                    for issue in result.issues
                ),
                result.issues,
            )

    def test_padded_metadata_pdf_cannot_satisfy_international_field_sota(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_international_project(Path(tmp))
            source = registry["sources"][1]
            metadata_text = (
                "OpenAlex metadata record. Title: International Evidence on Interdependence Mechanisms. "
                "Authors: Alex Researcher. Venue: International Organization. Year: 2026. "
                "Abstract snippet and keywords only; no article body, no full text, no article references. "
                * 8
            )
            pdf = base / source["local_file"]
            pdf.write_bytes(minimal_pdf_bytes("metadata-only-sota", metadata_text))
            source["sha256"] = acq.sha256_file(pdf)
            source["verification"]["support_claim"] = (
                "Metadata-only abstract snippet repeats a possible mechanism without an article body."
            )
            result = self.validate_updated_registry(base, registry)
            self.assertFalse(result.ok)
            self.assertTrue(
                any("no verifiable article-body text" in issue for issue in result.issues),
                result.issues,
            )

    def test_international_roles_require_retraction_check_for_every_discovery_channel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_international_project(Path(tmp))
            for source in registry["sources"]:
                source["verification"].pop("retraction_status")
                source["verification"].pop("retraction_checked_at")
            result = self.validate_updated_registry(base, registry)
            self.assertFalse(result.ok)
            self.assertTrue(
                any("retraction_status=not-retracted" in issue for issue in result.issues),
                result.issues,
            )

    def test_user_authorized_external_target_exemplars_pass_only_the_channel_exception(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            self.authorize_external_target_examples(base, registry)
            result = self.validate_updated_registry(base, registry)
            self.assertTrue(result.ok, result.issues)
            self.assertEqual(3, result.stats["target_examples"])

    def test_external_target_exception_rejects_missing_authorization_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            self.authorize_external_target_examples(base, registry)
            registry["sources"][0]["verification"].pop("acquisition_exception_id")
            issues = self.validate_updated_registry(base, registry).issues
            self.assertTrue(
                any("acquisition_exception_id is missing" in issue for issue in issues),
                issues,
            )

    def test_external_target_exception_rejects_non_user_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            self.authorize_external_target_examples(base, registry)
            registry["authorized_exceptions"][0]["authorized_by"] = "agent"
            config_path = base / "workflow_config.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["target_exemplar_acquisition_override"]["authorized_by"] = "agent"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            issues = self.validate_updated_registry(base, registry).issues
            self.assertTrue(any("authorized_by=user" in issue for issue in issues), issues)

    def test_external_target_exception_rejects_target_venue_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            self.authorize_external_target_examples(base, registry)
            registry["sources"][0]["venue"] = "Different Journal"
            issues = self.validate_updated_registry(base, registry).issues
            self.assertTrue(any("authorized target_venue" in issue for issue in issues), issues)

    def test_external_target_exception_rejects_each_registry_contract_mismatch(self) -> None:
        mutations = {
            "authorized_by": "agent",
            "authorized_at": "2026-08-11",
            "scope": "other",
            "target_venue": "Different Journal",
            "activation_condition": "always",
            "cnki_probe_query_ids": ["Q-VENUE"],
            "allowed_channels": ["publisher-official"],
            "allowed_origin_hosts": ["evil.example"],
            "required_count": 4,
            "require_not_for_citation": False,
        }
        for field, value in mutations.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                base, registry = self.make_project(Path(tmp))
                self.authorize_external_target_examples(base, registry)
                registry["authorized_exceptions"][0][field] = value
                issues = self.validate_updated_registry(base, registry).issues
                self.assertTrue(
                    any(
                        f"field {field} differs from the config authorization contract"
                        in issue
                        for issue in issues
                    ),
                    issues,
                )

    def test_external_target_exception_requires_target_bound_cnki_probes(self) -> None:
        mutations = [
            (
                0,
                "source=Unrelated Journal",
                "requires at least one purpose=venue CNKI probe naming target_venue",
            ),
            (
                1,
                "title=Unrelated article AND source=Unrelated Journal",
                "is not bound to the target venue or an authorized exemplar",
            ),
        ]
        for query_index, query_text, expected in mutations:
            with self.subTest(query_index=query_index), tempfile.TemporaryDirectory() as tmp:
                base, registry = self.make_project(Path(tmp))
                self.authorize_external_target_examples(base, registry)
                registry["queries"][query_index]["query"] = query_text
                issues = self.validate_updated_registry(base, registry).issues
                self.assertTrue(any(expected in issue for issue in issues), issues)

    def test_external_target_exception_rejects_unapproved_origin_hosts(self) -> None:
        mutations = [
            (
                lambda registry: registry["sources"][0].__setitem__(
                    "url", "https://evil.example/article/1"
                ),
                "source URL host is not authorized",
            ),
            (
                lambda registry: registry["sources"][0]["verification"].__setitem__(
                    "content_url", "https://evil.example/file.pdf"
                ),
                "verification.content_url host is not authorized",
            ),
            (
                lambda registry: next(
                    query
                    for query in registry["queries"]
                    if query["query_id"] == "Q-EXT-1"
                ).__setitem__("url", "https://evil.example/search"),
                "positive target-exemplar query Q-EXT-1 URL host is not authorized",
            ),
        ]
        for mutate, expected in mutations:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as tmp:
                base, registry = self.make_project(Path(tmp))
                self.authorize_external_target_examples(base, registry)
                mutate(registry)
                issues = self.validate_updated_registry(base, registry).issues
                self.assertTrue(any(expected in issue for issue in issues), issues)

    def test_external_target_exception_rejects_short_doi_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            self.authorize_external_target_examples(base, registry)
            registry["sources"][0]["doi"] = "10.1234/x"
            external_query = next(
                query for query in registry["queries"] if query["query_id"] == "Q-EXT-1"
            )
            external_query["query"] = "DOI=10.1234/x"
            issues = self.validate_updated_registry(base, registry).issues
            self.assertTrue(any("not a valid strict DOI" in issue for issue in issues), issues)

    def test_external_target_exception_required_count_matches_linked_sources_not_tier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            self.authorize_external_target_examples(base, registry)
            registry["authorized_exceptions"][0]["required_count"] = 2
            config_path = base / "workflow_config.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["target_exemplar_acquisition_override"]["required_count"] = 2
            config_path.write_text(json.dumps(config), encoding="utf-8")
            issues = self.validate_updated_registry(base, registry).issues
            self.assertFalse(any("required by tier" in issue for issue in issues), issues)
            self.assertTrue(
                any("number of source records linked to it" in issue for issue in issues),
                issues,
            )

    def test_external_target_exception_requires_all_named_cnki_probes_to_be_complete_zero(self) -> None:
        mutations = [
            ("status", "incomplete", "is not complete"),
            ("result_count", 1, "exact result_count=0"),
            ("result_count_is_approximate", True, "cannot mark its zero count approximate"),
            ("channel", "web", "must have channel=CNKI"),
        ]
        for field, value, expected in mutations:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                base, registry = self.make_project(Path(tmp))
                self.authorize_external_target_examples(base, registry)
                registry["queries"][1][field] = value
                issues = self.validate_updated_registry(base, registry).issues
                self.assertTrue(any(expected in issue for issue in issues), issues)

    def test_external_target_exception_rejects_non_whitelisted_channel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            self.authorize_external_target_examples(base, registry)
            registry["sources"][0]["channel"] = "open-web"
            issues = self.validate_updated_registry(base, registry).issues
            self.assertTrue(any("outside the" in issue and "whitelist" in issue for issue in issues), issues)

    def test_external_target_exception_requires_positive_identity_linked_target_query(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            self.authorize_external_target_examples(base, registry)
            external_query = next(
                query for query in registry["queries"] if query["query_id"] == "Q-EXT-1"
            )
            external_query["query"] = "unrelated target article"
            issues = self.validate_updated_registry(base, registry).issues
            self.assertTrue(any("positive-result target-exemplar query" in issue for issue in issues), issues)

    def test_external_target_exception_does_not_waive_pdf_hash_or_title_checks(self) -> None:
        mutations = [
            (lambda source: source.__setitem__("sha256", "0" * 64), "SHA-256 does not match"),
            (lambda source: source["verification"].__setitem__("title_match", "no"), "title_match=yes"),
            (lambda source: source.__setitem__("local_file", "missing.pdf"), "valid workspace-local PDF"),
        ]
        for mutate, expected in mutations:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as tmp:
                base, registry = self.make_project(Path(tmp))
                self.authorize_external_target_examples(base, registry)
                mutate(registry["sources"][0])
                issues = self.validate_updated_registry(base, registry).issues
                self.assertTrue(any(expected in issue for issue in issues), issues)

    def test_final_source_requires_a_concrete_research_fit_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            registry["sources"][3]["reason"] = ""
            acq.atomic_write_json(acq.registry_path(base), registry)
            (base / acq.INDEX_REL).write_text(acq.build_source_index(registry), encoding="utf-8")
            issues = acq.validate_registry(base).issues
            self.assertTrue(any("lacks a concrete reason" in issue for issue in issues), issues)

    def test_missing_pdf_seal_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            registry["sources"][0]["sha256"] = ""
            acq.atomic_write_json(acq.registry_path(base), registry)
            (base / acq.INDEX_REL).write_text(acq.build_source_index(registry), encoding="utf-8")
            issues = acq.validate_registry(base).issues
            self.assertTrue(any("SHA-256" in issue for issue in issues))

    def test_truncated_pdf_without_eof_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            pdf = base / registry["sources"][0]["local_file"]
            pdf.write_bytes(b"%PDF-1.4\ntruncated content without trailer")
            registry["sources"][0]["sha256"] = acq.sha256_file(pdf)
            acq.atomic_write_json(acq.registry_path(base), registry)
            (base / acq.INDEX_REL).write_text(acq.build_source_index(registry), encoding="utf-8")
            issues = acq.validate_registry(base).issues
            self.assertTrue(any("valid workspace-local PDF" in issue for issue in issues))

    def test_duplicate_exemplar_pdf_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            registry["sources"][1]["local_file"] = registry["sources"][0]["local_file"]
            registry["sources"][1]["sha256"] = registry["sources"][0]["sha256"]
            acq.atomic_write_json(acq.registry_path(base), registry)
            (base / acq.INDEX_REL).write_text(acq.build_source_index(registry), encoding="utf-8")
            issues = acq.validate_registry(base).issues
            self.assertTrue(any("reuses another exemplar PDF path" in issue for issue in issues))

    def test_target_exemplar_requires_title_match_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            registry["sources"][0]["verification"].pop("title_match")
            acq.atomic_write_json(acq.registry_path(base), registry)
            (base / acq.INDEX_REL).write_text(acq.build_source_index(registry), encoding="utf-8")
            issues = acq.validate_registry(base).issues
            self.assertTrue(any("title_match=yes" in issue for issue in issues))

    def test_generated_index_drift_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, _ = self.make_project(Path(tmp))
            with (base / acq.INDEX_REL).open("a", encoding="utf-8") as handle:
                handle.write("\nmanual edit\n")
            issues = acq.validate_registry(base).issues
            self.assertTrue(any("out of sync" in issue for issue in issues))

    def test_citation_row_must_reuse_registry_source_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, _ = self.make_project(Path(tmp))
            (base / "citation_support_bank.md").write_text(
                "| Candidate ID | Reference/BibTeX | Year | Recency | Supports Section | "
                "Support Claim Sentence | Why This Paper Fits | Source | Source Channel | Verified | "
                "Citation Scope | Verification Note |\n"
                "|---|---|---|---|---|---|---|---|---|---|---|---|\n"
                "| UNKNOWN | ref | 2026 | recent | intro | 具体支撑判断不少于二十个字符并来自摘要核验 | "
                "直接相关 | https://kns.cnki.net/kcms2/article/abstract?id=S1 | CNKI | yes | "
                "final-source | abstract 2026-07-28 |\n",
                encoding="utf-8",
            )
            issues = acq.validate_registry(base, require_citations=True).issues
            self.assertTrue(any("absent from literature_registry" in issue for issue in issues))

    def test_citation_row_cross_link_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, _ = self.make_project(Path(tmp))
            self.assertEqual(0, acq.sync_index(base))
            result = acq.validate_registry(base, require_citations=True)
            self.assertTrue(result.ok, result.issues)
            bank = (base / acq.CITATION_REL).read_text(encoding="utf-8")
            self.assertIn(acq.CITATION_GENERATED_MARKER, bank)
            self.assertIn("CNKI-S001", bank)

    def test_sync_force_backs_up_legacy_citation_view_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, _ = self.make_project(Path(tmp))
            legacy = base / acq.CITATION_REL
            legacy.write_text("# hand-maintained legacy citation bank\n", encoding="utf-8")
            self.assertEqual(2, acq.sync_index(base))
            self.assertEqual(0, acq.sync_index(base, force=True))
            backup = base / acq.CITATION_BACKUP_REL
            self.assertEqual(
                "# hand-maintained legacy citation bank\n",
                backup.read_text(encoding="utf-8"),
            )
            self.assertIn(
                acq.CITATION_GENERATED_MARKER,
                legacy.read_text(encoding="utf-8"),
            )

    def test_supplementary_non_cnki_query_and_source_are_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            registry["queries"].append(
                {
                    "query_id": "Q-LOCAL",
                    "channel": "local",
                    "purpose": "other",
                    "query": "用户提供的本地研究材料",
                    "result_count": 1,
                    "url": "materials/user-materials/",
                    "collected_at": "2026-07-28",
                    "status": "complete",
                }
            )
            registry["sources"].append(
                {
                    "source_id": "LOCAL-001",
                    "channel": "local",
                    "roles": ["local-material"],
                    "title": "用户提供的研究材料",
                    "url": "materials/user-materials/note.md",
                    "query_ids": ["Q-LOCAL"],
                    "state": "discovered",
                    "verification": {},
                    "local_file": "materials/user-materials/note.md",
                    "citation_scope": "not-for-citation",
                    "reason": "作为研究边界与案例背景材料",
                    "used_for": ["background"],
                    "collected_at": "2026-07-28",
                }
            )
            acq.atomic_write_json(acq.registry_path(base), registry)
            (base / acq.INDEX_REL).write_text(acq.build_source_index(registry), encoding="utf-8")
            result = acq.validate_registry(base)
            self.assertTrue(result.ok, result.issues)

    def test_google_scholar_query_and_candidate_enter_the_unified_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            self.add_scholar_query(registry)
            self.add_scholar_candidate(registry)
            result = self.validate_updated_registry(base, registry)
            self.assertTrue(result.ok, result.issues)

    def test_scholar_bibtex_is_metadata_only_and_remains_unverified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            self.add_scholar_query(registry)
            source = self.add_scholar_candidate(
                registry,
                state="metadata-exported",
            )
            source["verification"] = {"method": "scholar-bibtex"}
            source["bibtex"] = "@article{candidate, title={Weaponized Interdependence}}"
            result = self.validate_updated_registry(base, registry)
            self.assertTrue(result.ok, result.issues)
            bank = acq.build_citation_support_bank(registry)
            row = next(line for line in bank.splitlines() if "GS-001" in line)
            self.assertIn("| no | candidate-only |", row)

    def test_scholar_queries_cannot_satisfy_cnki_only_contracts(self) -> None:
        query_index = {"venue": 0, "target-exemplar": 1, "sota": 2}
        for purpose, index in query_index.items():
            with self.subTest(purpose=purpose), tempfile.TemporaryDirectory() as tmp:
                base, registry = self.make_project(Path(tmp))
                query = registry["queries"][index]
                query.update(
                    {
                        "channel": "Google Scholar",
                        "query": f'"{purpose} discovery"',
                        "filters": {"first_page_only": True},
                        "result_count": 100,
                        "result_count_is_approximate": True,
                        "result_count_basis": "page-displayed-about-total",
                        "result_count_note": "Scholar displayed an approximate total.",
                        "url": f"https://scholar.google.com/scholar?q=%22{purpose}%22&hl=en",
                    }
                )
                result = self.validate_updated_registry(base, registry)
                self.assertTrue(
                    any(
                        f"cannot satisfy the CNKI-only {purpose} acquisition contract"
                        in issue
                        for issue in result.issues
                    ),
                    result.issues,
                )

    def test_invalid_google_scholar_query_url_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            self.add_scholar_query(
                registry,
                url="https://www.google.com/search?q=weaponized+interdependence",
            )
            result = self.validate_updated_registry(base, registry)
            self.assertTrue(
                any("must retain a scholar.google.com/scholar URL with q=" in issue for issue in result.issues),
                result.issues,
            )

    def test_scholar_discovery_artifacts_cannot_verify_content(self) -> None:
        for method in ("scholar-snippet", "scholar-cited-by", "scholar-bibtex"):
            with self.subTest(method=method), tempfile.TemporaryDirectory() as tmp:
                base, registry = self.make_project(Path(tmp))
                self.add_scholar_query(registry)
                source = self.add_scholar_candidate(registry)
                source.update(
                    {
                        "channel": "Publisher",
                        "state": "content-verified",
                        "citation_scope": "final-source",
                    }
                )
                source["verification"] = {
                    "method": method,
                    "verified_at": "2026-08-04",
                    "support_claim": "A Scholar display artifact is being misused as a load-bearing claim.",
                    "content_url": "https://direct.mit.edu/isec/article/44/1/42/12230/",
                    "retraction_status": "not-retracted",
                    "retraction_checked_at": "2026-08-04",
                }
                result = self.validate_updated_registry(base, registry)
                self.assertTrue(
                    any("cannot use a Scholar result, snippet, cited-by count" in issue for issue in result.issues),
                    result.issues,
                )

    def test_scholar_query_url_cannot_be_promoted_as_original_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            query = self.add_scholar_query(registry)
            source = self.add_scholar_candidate(registry)
            source.update(
                {
                    "channel": "Publisher",
                    "url": query["url"],
                    "state": "content-verified",
                    "citation_scope": "final-source",
                }
            )
            source["verification"] = {
                "method": "abstract",
                "verified_at": "2026-08-04",
                "support_claim": "This sentence claims content review but points only to the Scholar query page.",
                "content_url": query["url"],
                "retraction_status": "not-retracted",
                "retraction_checked_at": "2026-08-04",
            }
            result = self.validate_updated_registry(base, registry)
            self.assertTrue(
                any("publisher or lawful-OA verification.content_url" in issue for issue in result.issues),
                result.issues,
            )
            self.assertTrue(
                any("cannot retain a Scholar query/result URL" in issue for issue in result.issues),
                result.issues,
            )

    def test_scholar_exact_duplicates_require_source_id_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            self.add_scholar_query(registry)
            first = self.add_scholar_candidate(registry, source_id="GS-001")
            first["doi"] = "10.1162/isec_a_00351"
            second = json.loads(json.dumps(first))
            second["source_id"] = "GS-002"
            second["url"] = "https://doi.org/10.1162/isec_a_00351"
            registry["sources"].append(second)
            result = self.validate_updated_registry(base, registry)
            self.assertTrue(
                any("duplicate DOI" in issue and "reuse the existing Source ID" in issue for issue in result.issues),
                result.issues,
            )
            self.assertTrue(
                any("duplicate title/first-author/year identity" in issue for issue in result.issues),
                result.issues,
            )

    def test_scholar_discovered_source_can_promote_after_original_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            self.add_scholar_query(registry)
            source = self.add_scholar_candidate(registry)
            source.update(
                {
                    "channel": "Publisher",
                    "doi": "10.1162/isec_a_00351",
                    "state": "content-verified",
                    "citation_scope": "final-source",
                }
            )
            source["verification"] = {
                "method": "abstract",
                "verified_at": "2026-08-04",
                "support_claim": (
                    "The publisher abstract was read and supports a bounded claim "
                    "about asymmetric network dependence."
                ),
                "content_url": "https://direct.mit.edu/isec/article/44/1/42/12230/",
                "retraction_status": "not-retracted",
                "retraction_checked_at": "2026-08-04",
            }
            source["credibility"] = {
                "source_class": "scholarly-publisher",
                "authorship_publisher": "Named authors and MIT Press journal page checked",
                "sponsorship_interest": "Funding and disclosure information reviewed",
                "corroborating_source_ids": ["CNKI-S001"],
                "contradicting_source_ids": [],
                "checked_at": "2026-08-04",
                "status": "passed",
                "note": "Publisher metadata and an independently verified registered source were compared.",
            }
            result = self.validate_updated_registry(base, registry)
            self.assertTrue(result.ok, result.issues)

    def test_v1_registry_remains_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            registry["schema_version"] = acq.SCHEMA_VERSION_V1
            acq.atomic_write_json(acq.registry_path(base), registry)
            (base / acq.INDEX_REL).write_text(acq.build_source_index(registry), encoding="utf-8")
            result = acq.validate_registry(base)
            self.assertTrue(result.ok, result.issues)
            self.assertEqual(acq.SCHEMA_VERSION_V1, result.stats["acquisition_schema"])

    def test_open_web_final_source_requires_passed_lateral_credibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            registry["queries"].append(
                {
                    "query_id": "Q-WEB",
                    "channel": "web",
                    "purpose": "other",
                    "query": "public commentary",
                    "result_count": 1,
                    "url": "https://example.org/search",
                    "collected_at": "2026-07-28",
                    "status": "complete",
                }
            )
            registry["sources"].append(
                {
                    "source_id": "WEB-001",
                    "channel": "web",
                    "roles": ["other"],
                    "title": "Public commentary",
                    "publication_year": 2026,
                    "url": "https://example.org/commentary",
                    "query_ids": ["Q-WEB"],
                    "state": "content-verified",
                    "verification": {
                        "method": "full-text",
                        "verified_at": "2026-07-28",
                        "support_claim": "This verified public page supplies a concrete factual statement for the paper.",
                    },
                    "citation_scope": "final-source",
                    "reason": "Provides a public claim that is material to the empirical chronology",
                    "used_for": ["background"],
                    "collected_at": "2026-07-28",
                    "credibility": {
                        "source_class": "news-media",
                        "authorship_publisher": "Example newsroom; named staff writer",
                        "sponsorship_interest": "Ownership and disclosed sponsorship reviewed",
                        "corroborating_source_ids": ["CNKI-S001"],
                        "contradicting_source_ids": [],
                        "checked_at": "2026-07-28",
                        "status": "needs-review",
                        "note": "Authorship is known, but the lateral comparison has not been adjudicated.",
                    },
                }
            )
            acq.atomic_write_json(acq.registry_path(base), registry)
            (base / acq.INDEX_REL).write_text(acq.build_source_index(registry), encoding="utf-8")
            issues = acq.validate_registry(base).issues
            self.assertTrue(any("credibility remains needs-review" in issue for issue in issues), issues)

            registry["sources"][-1]["credibility"]["status"] = "passed"
            registry["sources"][-1]["credibility"]["note"] = (
                "Named authorship, funding disclosure, and the registered lateral source were checked."
            )
            acq.atomic_write_json(acq.registry_path(base), registry)
            (base / acq.INDEX_REL).write_text(acq.build_source_index(registry), encoding="utf-8")
            result = acq.validate_registry(base)
            self.assertTrue(result.ok, result.issues)
            self.assertEqual(1, result.stats["credibility_passed"])

    def test_open_web_credibility_rejects_self_corroboration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            self.add_public_web_source(
                registry,
                "WEB-001",
                corroborating_source_ids=["WEB-001"],
            )
            result = self.validate_updated_registry(base, registry)
            self.assertFalse(result.ok)
            self.assertTrue(
                any(
                    "cannot use itself for lateral credibility verification" in issue
                    for issue in result.issues
                ),
                result.issues,
            )
            self.assertEqual(0, result.stats["credibility_passed"])

    def test_open_web_credibility_rejects_two_node_pure_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            self.add_public_web_source(
                registry,
                "WEB-001",
                corroborating_source_ids=["WEB-002"],
            )
            self.add_public_web_source(
                registry,
                "WEB-002",
                corroborating_source_ids=["WEB-001"],
            )
            result = self.validate_updated_registry(base, registry)
            self.assertFalse(result.ok)
            self.assertTrue(
                any("same corroboration cycle" in issue for issue in result.issues),
                result.issues,
            )
            self.assertEqual(0, result.stats["credibility_passed"])

    def test_open_web_credibility_rejects_multi_node_pure_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            self.add_public_web_source(
                registry,
                "WEB-001",
                corroborating_source_ids=["WEB-002"],
            )
            self.add_public_web_source(
                registry,
                "WEB-002",
                corroborating_source_ids=["WEB-003"],
            )
            self.add_public_web_source(
                registry,
                "WEB-003",
                corroborating_source_ids=["WEB-001"],
            )
            result = self.validate_updated_registry(base, registry)
            self.assertFalse(result.ok)
            cycle_issues = [
                issue for issue in result.issues if "same corroboration cycle" in issue
            ]
            self.assertEqual(3, len(cycle_issues), result.issues)
            self.assertEqual(0, result.stats["credibility_passed"])

    def test_open_web_credibility_rejects_unverified_corroborator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            registry["sources"].append(
                {
                    "source_id": "CNKI-C001",
                    "channel": "CNKI",
                    "roles": ["citation-candidate"],
                    "title": "Unverified candidate",
                    "publication_year": 2026,
                    "url": "https://kns.cnki.net/kcms2/article/abstract?id=C001",
                    "query_ids": ["Q-SOTA"],
                    "state": "discovered",
                    "citation_scope": "candidate-only",
                    "reason": "Candidate retained pending content review",
                    "used_for": ["screening"],
                    "collected_at": "2026-07-28",
                }
            )
            self.add_public_web_source(
                registry,
                "WEB-001",
                corroborating_source_ids=["CNKI-C001"],
            )
            result = self.validate_updated_registry(base, registry)
            self.assertFalse(result.ok)
            self.assertTrue(
                any(
                    "has not completed content verification" in issue
                    for issue in result.issues
                ),
                result.issues,
            )
            self.assertEqual(0, result.stats["credibility_passed"])

    def test_open_web_credibility_rejects_ineligible_corroborator_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            self.add_public_web_source(
                registry,
                "WEB-001",
                corroborating_source_ids=["CNKI-T001"],
            )
            result = self.validate_updated_registry(base, registry)
            self.assertFalse(result.ok)
            self.assertTrue(
                any(
                    "has no evidence-eligible source role" in issue
                    for issue in result.issues
                ),
                result.issues,
            )
            self.assertEqual(0, result.stats["credibility_passed"])

    def test_contradicting_source_does_not_satisfy_corroboration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            self.add_public_web_source(
                registry,
                "WEB-001",
                corroborating_source_ids=[],
                contradicting_source_ids=["CNKI-S001"],
            )
            result = self.validate_updated_registry(base, registry)
            self.assertFalse(result.ok)
            self.assertTrue(
                any(
                    "contradicting sources do not count as corroboration" in issue
                    for issue in result.issues
                ),
                result.issues,
            )
            self.assertEqual(0, result.stats["credibility_passed"])

    def test_open_web_credibility_accepts_independently_anchored_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            self.add_public_web_source(
                registry,
                "WEB-001",
                corroborating_source_ids=["WEB-002"],
            )
            self.add_public_web_source(
                registry,
                "WEB-002",
                corroborating_source_ids=["CNKI-S001"],
            )
            result = self.validate_updated_registry(base, registry)
            self.assertTrue(result.ok, result.issues)
            self.assertEqual(2, result.stats["credibility_passed"])

    def test_official_primary_web_source_has_no_uniform_lateral_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            registry["queries"].append(
                {
                    "query_id": "Q-OFFICIAL",
                    "channel": "official-web",
                    "purpose": "other",
                    "query": "official statistical release",
                    "result_count": 1,
                    "url": "https://gov.example/statistics",
                    "collected_at": "2026-07-28",
                    "status": "complete",
                }
            )
            registry["sources"].append(
                {
                    "source_id": "OFF-001",
                    "channel": "official-web",
                    "roles": ["web-experience"],
                    "title": "Official statistical release",
                    "publication_year": 2026,
                    "url": "https://gov.example/statistics/release",
                    "query_ids": ["Q-OFFICIAL"],
                    "state": "content-verified",
                    "verification": {
                        "method": "full-text",
                        "verified_at": "2026-07-28",
                        "support_claim": "The official record states the publication date and reported aggregate.",
                    },
                    "citation_scope": "final-source",
                    "reason": "Primary official record for its own published statistic",
                    "used_for": ["background"],
                    "collected_at": "2026-07-28",
                }
            )
            acq.atomic_write_json(acq.registry_path(base), registry)
            (base / acq.INDEX_REL).write_text(acq.build_source_index(registry), encoding="utf-8")
            result = acq.validate_registry(base)
            self.assertTrue(result.ok, result.issues)

    def test_v1_to_v2_migration_is_zero_write_then_conservative(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            registry["schema_version"] = acq.SCHEMA_VERSION_V1
            registry["queries"].append(
                {
                    "query_id": "Q-WEB",
                    "channel": "web",
                    "purpose": "other",
                    "query": "public claim",
                    "result_count": 1,
                    "url": "https://example.org/search",
                    "collected_at": "2026-07-28",
                    "status": "complete",
                }
            )
            registry["sources"].append(
                {
                    "source_id": "WEB-001",
                    "channel": "web",
                    "roles": ["other"],
                    "title": "Public claim",
                    "publication_year": 2026,
                    "url": "https://example.org/claim",
                    "query_ids": ["Q-WEB"],
                    "state": "content-verified",
                    "verification": {
                        "method": "full-text",
                        "verified_at": "2026-07-28",
                        "support_claim": "The public page contains a concrete claim checked against its displayed text.",
                    },
                    "citation_scope": "final-source",
                    "reason": "Potential factual source requiring lateral verification",
                    "used_for": ["background"],
                    "collected_at": "2026-07-28",
                }
            )
            path = acq.registry_path(base)
            acq.atomic_write_json(path, registry)
            before = path.read_bytes()
            self.assertEqual(0, acq.migrate_registry(base, apply=False, to="v2"))
            self.assertEqual(before, path.read_bytes())
            self.assertFalse((base / acq.MIGRATION_V2_REL).exists())

            self.assertEqual(0, acq.migrate_registry(base, apply=True, to="v2"))
            migrated = acq.load_json(path)
            self.assertEqual(acq.SCHEMA_VERSION_V2, migrated["schema_version"])
            credibility = migrated["sources"][-1]["credibility"]
            self.assertEqual("needs-review", credibility["status"])
            self.assertEqual([], credibility["corroborating_source_ids"])
            backups = list((base / acq.MIGRATION_V2_REL).glob("literature_registry.*.v1.json"))
            self.assertEqual(1, len(backups))
            files_before = sorted((base / acq.MIGRATION_V2_REL).glob("*.json"))
            self.assertEqual(0, acq.migrate_registry(base, apply=True, to="v2"))
            self.assertEqual(files_before, sorted((base / acq.MIGRATION_V2_REL).glob("*.json")))

    def test_v2_to_v3_migration_dry_run_apply_and_guarded_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            registry["schema_version"] = acq.SCHEMA_VERSION_V2
            path = acq.registry_path(base)
            acq.atomic_write_json(path, registry)
            before = path.read_bytes()

            self.assertEqual(0, acq.migrate_registry(base, apply=False, to="v3"))
            self.assertEqual(before, path.read_bytes())
            self.assertFalse((base / acq.MIGRATION_V3_REL).exists())

            self.assertEqual(0, acq.migrate_registry(base, apply=True, to="v3"))
            migrated = acq.load_json(path)
            self.assertEqual(acq.SCHEMA_VERSION_V3, migrated["schema_version"])
            expected = dict(registry)
            expected["schema_version"] = acq.SCHEMA_VERSION_V3
            self.assertEqual(expected, migrated)
            manifests = list((base / acq.MIGRATION_V3_REL).glob("migration.*.json"))
            self.assertEqual(1, len(manifests))

            self.assertEqual(
                0,
                acq.migrate_registry(
                    base,
                    apply=False,
                    rollback_manifest=manifests[0],
                ),
            )
            self.assertEqual(before, path.read_bytes())

            self.assertEqual(0, acq.migrate_registry(base, apply=True, to="v3"))
            current = path.read_bytes()
            migration_files = sorted((base / acq.MIGRATION_V3_REL).glob("*.json"))
            self.assertEqual(0, acq.migrate_registry(base, apply=True, to="v3"))
            self.assertEqual(current, path.read_bytes())
            self.assertEqual(
                migration_files,
                sorted((base / acq.MIGRATION_V3_REL).glob("*.json")),
            )
            migrated["target_name"] = "changed after migration"
            acq.atomic_write_json(path, migrated)
            tampered = path.read_bytes()
            self.assertEqual(
                2,
                acq.migrate_registry(
                    base,
                    apply=False,
                    rollback_manifest=manifests[0],
                ),
            )
            self.assertEqual(tampered, path.read_bytes())

    def test_future_acquisition_schema_is_blocked_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            registry["schema_version"] = "cnki-acquisition/v99"
            path = acq.registry_path(base)
            acq.atomic_write_json(path, registry)
            before = path.read_bytes()

            self.assertEqual(2, acq.migrate_registry(base, apply=False, to="v3"))
            self.assertEqual(before, path.read_bytes())
            self.assertFalse((base / acq.MIGRATION_V3_REL).exists())

    def test_v3_apply_failure_restores_registry_and_removes_transaction_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            registry["schema_version"] = acq.SCHEMA_VERSION_V2
            path = acq.registry_path(base)
            acq.atomic_write_json(path, registry)
            before = path.read_bytes()
            original_write_json = acq.atomic_write_json

            def fail_registry_write(target: Path, payload: dict) -> None:
                if target == path:
                    raise OSError("injected registry replace failure")
                original_write_json(target, payload)

            with mock.patch.object(
                acq,
                "atomic_write_json",
                side_effect=fail_registry_write,
            ):
                self.assertEqual(2, acq.migrate_registry(base, apply=True, to="v3"))
            self.assertEqual(before, path.read_bytes())
            self.assertFalse((base / acq.MIGRATION_V3_REL).exists())

    def test_v3_rollback_receipt_failure_restores_pre_rollback_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            registry["schema_version"] = acq.SCHEMA_VERSION_V2
            path = acq.registry_path(base)
            acq.atomic_write_json(path, registry)
            self.assertEqual(0, acq.migrate_registry(base, apply=True, to="v3"))
            migrated = path.read_bytes()
            manifest = next((base / acq.MIGRATION_V3_REL).glob("migration.*.json"))
            # macOS exposes temporary directories through both /var and
            # /private/var; normalize the injected target before comparison.
            receipt = (manifest.parent / "rollback_receipt.json").resolve()
            original_write_json = acq.atomic_write_json

            def fail_receipt_write(target: Path, payload: dict) -> None:
                if target == receipt:
                    raise OSError("injected rollback receipt failure")
                original_write_json(target, payload)

            with mock.patch.object(
                acq,
                "atomic_write_json",
                side_effect=fail_receipt_write,
            ):
                self.assertEqual(
                    2,
                    acq.migrate_registry(
                        base,
                        apply=False,
                        rollback_manifest=manifest,
                    ),
                )
            self.assertEqual(migrated, path.read_bytes())
            self.assertFalse(receipt.exists())

    def test_v3_rollback_rejects_noncanonical_manifest_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            registry["schema_version"] = acq.SCHEMA_VERSION_V2
            path = acq.registry_path(base)
            acq.atomic_write_json(path, registry)
            self.assertEqual(0, acq.migrate_registry(base, apply=True, to="v3"))
            migrated = path.read_bytes()
            manifest = next((base / acq.MIGRATION_V3_REL).glob("migration.*.json"))
            manifest_payload = acq.load_json(manifest)
            manifest_payload["registry"] = "reference_materials/other.json"
            acq.atomic_write_json(manifest, manifest_payload)

            self.assertEqual(
                2,
                acq.migrate_registry(
                    base,
                    apply=False,
                    rollback_manifest=manifest,
                ),
            )
            self.assertEqual(migrated, path.read_bytes())

    def test_exa_is_discovery_only_and_cannot_satisfy_academic_roles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            registry["schema_version"] = acq.SCHEMA_VERSION_V3
            registry["queries"].append(
                {
                    "query_id": "Q-EXA-001",
                    "channel": "Exa",
                    "purpose": "collision",
                    "query": "semantic near-duplicate scan",
                    "result_count": 1,
                    "run_artifact": "reference_materials/integrations/exa_runs/Q-EXA-001.json",
                    "run_sha256": "1" * 64,
                    "collected_at": "2026-08-21",
                    "status": "complete",
                }
            )
            registry["sources"].append(
                {
                    "source_id": "EXA-001",
                    "channel": "Exa",
                    "roles": ["citation-candidate"],
                    "title": "Semantic discovery candidate",
                    "publication_year": 2026,
                    "url": "https://example.org/candidate",
                    "query_ids": ["Q-EXA-001"],
                    "state": "discovered",
                    "verification": {},
                    "citation_scope": "candidate-only",
                    "reason": "Collision screening only",
                    "used_for": ["collision"],
                    "collected_at": "2026-08-21",
                }
            )
            acq.atomic_write_json(acq.registry_path(base), registry)
            (base / acq.INDEX_REL).write_text(acq.build_source_index(registry), encoding="utf-8")
            result = acq.validate_registry(base)
            self.assertTrue(result.ok, result.issues)

            source = registry["sources"][-1]
            source["roles"] = ["field-sota"]
            source["state"] = "content-verified"
            source["citation_scope"] = "final-source"
            source["verification"] = {
                "method": "full-text",
                "verified_at": "2026-08-21",
                "support_claim": "An Exa highlight is incorrectly being treated as content evidence.",
            }
            acq.atomic_write_json(acq.registry_path(base), registry)
            (base / acq.INDEX_REL).write_text(acq.build_source_index(registry), encoding="utf-8")
            issues = acq.validate_registry(base).issues
            self.assertTrue(any("must remain citation_scope=candidate-only" in issue for issue in issues), issues)
            self.assertTrue(any("cannot satisfy field-sota" in issue for issue in issues), issues)
            self.assertTrue(any("discovery metadata" in issue for issue in issues), issues)

    def test_zotero_link_does_not_promote_an_unverified_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            registry["schema_version"] = acq.SCHEMA_VERSION_V3
            source = registry["sources"][0]
            source["zotero_link"] = {
                "server_id": "local-profile",
                "library_id": 1,
                "item_key": "PXW99EKT",
                "item_version": 17,
                "citation_key": "fixtureCitation2026",
                "citation_key_locked": True,
                "attachment_keys": ["2JAZS9U8"],
                "last_reconciled_at": "2026-08-21T03:05:00Z",
            }
            source["state"] = "discovered"
            source["citation_scope"] = "final-source"
            source["verification"] = {}
            acq.atomic_write_json(acq.registry_path(base), registry)
            (base / acq.INDEX_REL).write_text(acq.build_source_index(registry), encoding="utf-8")
            issues = acq.validate_registry(base).issues
            self.assertTrue(any("is not content-verified" in issue for issue in issues), issues)
            self.assertTrue(any("no accepted content verification" in issue for issue in issues), issues)

    def test_non_cnki_query_cannot_satisfy_required_cnki_purpose(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            registry["queries"][2]["channel"] = "web"
            registry["queries"][2]["url"] = "https://example.org/search?q=sota"
            acq.atomic_write_json(acq.registry_path(base), registry)
            (base / acq.INDEX_REL).write_text(acq.build_source_index(registry), encoding="utf-8")
            issues = acq.validate_registry(base).issues
            self.assertTrue(any("lacks completed query purposes: sota" in issue for issue in issues))

    def test_cnki_lookalike_domain_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            registry["access"]["download_probe"]["url"] = "https://notcnki.net/fake"
            acq.atomic_write_json(acq.registry_path(base), registry)
            (base / acq.INDEX_REL).write_text(acq.build_source_index(registry), encoding="utf-8")
            issues = acq.validate_registry(base).issues
            self.assertTrue(any("download_probe" in issue for issue in issues))

    def test_duplicate_supplementary_url_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            registry["queries"].append(
                {
                    "query_id": "Q-WEB",
                    "channel": "web",
                    "purpose": "other",
                    "query": "supplementary evidence",
                    "result_count": 2,
                    "url": "https://example.org/search",
                    "collected_at": "2026-07-28",
                    "status": "complete",
                }
            )
            for index in range(2):
                registry["sources"].append(
                    {
                        "source_id": f"WEB-00{index + 1}",
                        "channel": "web",
                        "roles": ["other"],
                        "title": f"Supplementary source {index + 1}",
                        "url": "https://example.org/same-record",
                        "query_ids": ["Q-WEB"],
                        "state": "discovered",
                        "verification": {},
                        "citation_scope": "not-for-citation",
                        "reason": "Supplementary context",
                        "used_for": ["background"],
                        "collected_at": "2026-07-28",
                    }
                )
            acq.atomic_write_json(acq.registry_path(base), registry)
            (base / acq.INDEX_REL).write_text(acq.build_source_index(registry), encoding="utf-8")
            issues = acq.validate_registry(base).issues
            self.assertTrue(any("duplicate source URL" in issue for issue in issues))

    def test_init_creates_blocking_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "paper_rewriting_output"
            base.mkdir()
            (base / "workflow_config.json").write_text(
                '{"target_name":"测试期刊","tier":"flash"}',
                encoding="utf-8",
            )
            self.assertEqual(0, acq.init_registry(base))
            result = acq.validate_registry(base, check_index=False)
            self.assertFalse(result.ok)
            self.assertTrue(any("access status" in issue for issue in result.issues))

    def _edge(self, registry: dict, **overrides) -> dict:
        sources = [item["source_id"] for item in registry["sources"]]
        edge = {
            "edge_id": "EDGE-001",
            "from_source_id": sources[1],
            "to_source_id": sources[0],
            "relation": "cites",
            "evidence": "cnki-detail",
            "verified_at": "2026-09-04",
        }
        edge.update(overrides)
        return edge

    def test_valid_edges_pass_and_enter_the_generated_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            registry["edges"] = [self._edge(registry)]
            result = self.validate_updated_registry(base, registry)
            self.assertTrue(result.ok, result.issues)
            self.assertEqual(1, result.stats["citation_edges"])
            index = acq.build_source_index(registry)
            self.assertIn("## Citation Edges", index)
            self.assertIn("| EDGE-001 |", index)

    def test_invalid_edges_block_the_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, registry = self.make_project(Path(tmp))
            registry["edges"] = [
                self._edge(registry, to_source_id="GHOST-999"),
                self._edge(registry, edge_id="EDGE-002", stance="critical"),
                self._edge(registry, edge_id="EDGE-003", query_id="Q-NOPE"),
            ]
            result = self.validate_updated_registry(base, registry)
            joined = " ".join(result.issues)
            self.assertIn("GHOST-999 is not a registered Source ID", joined)
            self.assertIn("requires evidence from the citing text", joined)
            self.assertIn("Q-NOPE is not a registered Query ID", joined)


if __name__ == "__main__":
    unittest.main()


class StructurallyParseablePdfCnkiStyleTests(unittest.TestCase):
    def test_accepts_xref_keyword_followed_by_space(self) -> None:
        """CNKI-produced PDFs emit ``xref 0 N`` on one line; the structural check must not reject them."""
        body = bytearray(b"%PDF-1.6\r%\xe5\xbf\x8f\r\n")
        body.extend(b"1 0 obj\r<</Type /Catalog /Pages 2 0 R>>\rendobj\r")
        body.extend(b"2 0 obj\r<</Type /Pages /Kids [3 0 R] /Count 1>>\rendobj\r")
        body.extend(b"3 0 obj\r<</Type /Page /Parent 2 0 R /MediaBox [0 0 595 842]>>\rendobj\r")
        xref_offset = len(body)
        body.extend(
            b"xref 0 4\r\n0000000000 65535 f\r\n0000000018 00000 n\r\n"
            b"0000000060 00000 n\r\n0000000110 00000 n\r\n"
        )
        body.extend(
            b"trailer\r<</Size 4 /Root 1 0 R>>\rstartxref\r\n"
            + str(xref_offset).encode("ascii")
            + b"\r\n%%EOF"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cnki_style.pdf"
            path.write_bytes(bytes(body))
            self.assertTrue(acq.structurally_parseable_pdf(path))
