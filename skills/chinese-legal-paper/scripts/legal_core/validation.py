"""Read-only legal checks consumed by the existing controller gates."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import re

from .common import (FILES, PROFILE, SKILL, LegalError, binding, controller, digest,
                     excerpt, iso_date, read_json, schema_errors, scoped)

NORM_KINDS = {"statute", "regulation", "judicial_interpretation", "policy"}


def support_digest(entry, source, claim):
    return digest({"source": source, "claim": claim, "citation": {
        key: value for key, value in entry.items() if key != "support_review"}})


def receipt_paths(outdir):
    """Only explicit local bindings; changing a referenced file invalidates receipts."""
    result = set()
    def visit(value):
        if isinstance(value, dict):
            if "path" in value and "sha256" in value:
                try:
                    p = scoped(outdir, value["path"])
                    if p.is_file():
                        result.add(p.relative_to(Path(outdir).resolve()).as_posix())
                except LegalError:
                    pass
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    for relative in FILES.values():
        try:
            visit(read_json(scoped(outdir, relative)))
        except LegalError:
            pass
    return sorted(result)


class Check:
    def __init__(self, outdir, config, stage):
        self.root = Path(outdir).resolve()
        self.config = config
        self.stage = stage
        self.issues = []
        self.artifact = "workflow_config.json"

    def issue(self, code, message):
        self.issues.append({"stage": self.stage, "code": code, "message": message,
                            "artifact": self.artifact, "severity": "error"})

    def attempt(self, action):
        try:
            return action()
        except LegalError as exc:
            self.issue(exc.code, str(exc))
            return None

    def load(self, name):
        self.artifact = FILES[name]
        data = self.attempt(lambda: read_json(scoped(self.root, self.artifact)))
        if data is None:
            return None
        errors = schema_errors(data, read_json(SKILL / "schemas" / f"legal-{name}-v1.schema.json"))
        for error in errors:
            self.issue("CONTRACT.INVALID", error)
        return None if errors else data

    def review(self, value):
        if value["status"] != "verified":
            self.issue("REVIEW.PENDING", "A substantive review is still pending")
        if any(re.fullmatch(r"\s*(TODO|TBD|待填|待核|占位|pending)\s*", value[k], re.I)
               for k in ("reviewer", "reason")):
            self.issue("REVIEW.PLACEHOLDER", "Review needs an actual reviewer and reason")
        if iso_date(value["reviewed_at"]) > date.today():
            self.issue("REVIEW.FUTURE", "Review date cannot be in the future")
        if "basis" in value:
            self.attempt(lambda: binding(self.root, value["basis"]))

    def sources(self):
        data = self.load("sources")
        if data is None:
            return {}, {}
        registry = self.attempt(lambda: read_json(scoped(self.root, "reference_materials/literature_registry.json")))
        if not isinstance(registry, dict) or not isinstance(registry.get("sources"), list):
            self.issue("REGISTRY.MISSING", "Canonical literature_registry.json with sources is required")
            return {}, {}
        records = {s.get("source_id"): s for s in registry["sources"] if isinstance(s, dict)}
        rows = {}
        if not data["sources"] and data["scope"] != "literature_only":
            self.issue("SOURCE.EMPTY", "Legal-source scope requires at least one canonical source")
        for s in data["sources"]:
            sid = s["source_id"]
            if sid in rows:
                self.issue("SOURCE.DUPLICATE", f"Duplicate source extension: {sid}")
            rows[sid] = s
            record = records.get(sid)
            if record is None:
                self.issue("SOURCE.UNKNOWN", f"Not in the canonical registry: {sid}")
            elif s["source_digest"] != digest(record):
                self.issue("SOURCE.STALE", f"Canonical source changed: {sid}")
            self.review(s["identity_review"])
            access = s["access"]
            if access["level"] in {"partial", "fulltext"}:
                if access["permission"] == "unknown" or "text" not in access:
                    self.issue("ACCESS.UNPROVEN", f"{sid}: text access requires permission basis and a bound local text")
                else:
                    self.attempt(lambda: binding(self.root, access["text"], text=True))
                    if record:
                        verification = record.get("verification", {})
                        known = {record.get("local_file"), verification.get("ocr_text_file")}
                        if access["text"]["path"] not in known:
                            self.issue("TEXT.NOT_CANONICAL", f"{sid}: text must be the canonical local_file or verification.ocr_text_file")
            if s["kind"] in NORM_KINDS:
                if "authority" not in s or "temporal" not in s:
                    self.issue("LAW.METADATA", f"{sid}: authority and temporal metadata are required")
            if s["kind"] in {"case", "case_summary"} and "case" not in s:
                self.issue("CASE.METADATA", f"{sid}: case number, court and procedure are required")
            if s["kind"] == "case" and s["representation"] != "court_document":
                self.issue("CASE.REPRESENTATION", f"{sid}: an editorial summary must be classified as case_summary")
            if "case" in s:
                for related in s["case"]["related_source_ids"]:
                    if related not in records:
                        self.issue("CASE.RELATED_UNKNOWN", f"{sid}: unknown procedural relation {related}")
            temporal = s.get("temporal")
            if temporal:
                self.attempt(lambda: binding(self.root, temporal["basis"]))
                if iso_date(temporal["checked_at"]) > date.today():
                    self.issue("LAW.FUTURE_CHECK", f"{sid}: impossible future version check")
                start, end = temporal.get("effective_from"), temporal.get("effective_to")
                if start and end and iso_date(start) >= iso_date(end):
                    self.issue("LAW.INTERVAL", f"{sid}: effective interval must be nonempty [from, to)")
                if temporal["status"] in {"repealed", "amended"} and not end:
                    self.issue("LAW.INTERVAL_UNKNOWN", f"{sid}: record the end of this superseded version, not only a status label")
            if data["scope"] == "literature_only" and s["kind"] != "scholarship":
                self.issue("SCOPE.CONFLICT", "literature_only cannot contain legal authorities")
        return rows, records

    def analysis(self, sources):
        data = self.load("analysis")
        if data is None:
            return {}
        if data["design"]["path"] != "research_design.json":
            self.issue("DESIGN.AUTHORITY", "Legal analysis must bind the canonical research_design.json")
        design_path = self.attempt(lambda: binding(self.root, data["design"]))
        design = self.attempt(lambda: read_json(design_path)) if design_path else None
        claims = {c.get("id"): c for c in (design or {}).get("claims", []) if isinstance(c, dict)}
        profiles = read_json(SKILL / "assets" / "method-profiles.json")["profiles"]
        method = profiles.get(data["method"])
        if method is None:
            self.issue("METHOD.UNKNOWN", "Select a supported method profile")
        else:
            for field in method["required_fields"]:
                if not data["method_card"].get(field, "").strip():
                    self.issue("METHOD.INCOMPLETE", f"Method card requires {field}")
        annotated = set()
        for row in data["claims"]:
            cid = row["claim_id"]
            if cid in annotated:
                self.issue("CLAIM.DUPLICATE", f"Duplicate annotation: {cid}")
            annotated.add(cid)
            if cid not in claims:
                self.issue("CLAIM.UNKNOWN", f"Not in the canonical design: {cid}")
            elif row["claim_digest"] != digest(claims[cid]):
                self.issue("CLAIM.STALE", f"Claim changed: {cid}")
            self.review(row["applicability_review"])
            for sid in row["source_ids"]:
                source = sources.get(sid)
                if not source:
                    self.issue("CLAIM.SOURCE_UNKNOWN", f"{cid}: source lacks legal extension: {sid}")
                    continue
                if source["jurisdiction"] != row["jurisdiction"] and not row.get("cross_jurisdiction_reason"):
                    self.issue("CLAIM.JURISDICTION", f"{cid}: explain the use of a different jurisdiction")
                temporal = source.get("temporal", {})
                if row["use"] in {"current_law", "historical_law"} and source["kind"] in NORM_KINDS:
                    if row["use"] == "historical_law" and "fact_date" not in row:
                        self.issue("LAW.FACT_DATE", f"{cid}: historical application requires fact_date")
                    target = row.get("fact_date") if row["use"] == "historical_law" else row["as_of"]
                    start, end = temporal.get("effective_from"), temporal.get("effective_to")
                    if not start or not target or target < start or (end and target >= end):
                        self.issue("LAW.NOT_EFFECTIVE", f"{cid}: cited version is not effective at the declared date")
                    if row["use"] == "current_law" and (temporal.get("status") == "unknown" or temporal.get("checked_at", "") < row["as_of"]):
                        self.issue("LAW.VERSION_UNCHECKED", f"{cid}: version needs verification through as_of")
        if set(claims) - annotated:
            self.issue("CLAIM.COVERAGE", "All canonical claims need legal method/scope annotations")
        return claims

    def citations(self, sources, records, claims):
        data = self.load("citations")
        if data is None:
            return None
        canonical = self.config.get("canonical_manuscript") or self.config.get("citation_audit_manuscript")
        if canonical and data["manuscript"]["path"] != canonical:
            self.issue("MANUSCRIPT.AUTHORITY", "Citation ledger must bind the configured canonical manuscript")
        manuscript = self.attempt(lambda: binding(self.root, data["manuscript"], text=True))
        if data["style"] == "journal-supplied":
            if "style_basis" not in data:
                self.issue("STYLE.BASIS_MISSING", "Journal rules require a bound supplied rule document")
            else:
                self.attempt(lambda: binding(self.root, data["style_basis"]))
        seen = set()
        for entry in data["entries"]:
            cid = entry["citation_id"]
            if cid in seen:
                self.issue("CITATION.DUPLICATE", f"Duplicate citation: {cid}")
            seen.add(cid)
            source = sources.get(entry["source_id"])
            if source is None:
                self.issue("CITATION.SOURCE_UNKNOWN", f"{cid}: source lacks a verified legal extension")
                continue
            if entry["version_id"] != source["version_id"]:
                self.issue("CITATION.VERSION", f"{cid}: version binding changed")
            if entry["manuscript_span"]["path"] != data["manuscript"]["path"] or entry["manuscript_span"]["sha256"] != data["manuscript"]["sha256"]:
                self.issue("CITATION.MANUSCRIPT", f"{cid}: span is not in the current manuscript")
            prose = self.attempt(lambda: excerpt(self.root, entry["manuscript_span"]))
            evidence = self.attempt(lambda: excerpt(self.root, entry["evidence"]))
            if entry["mode"] == "quotation" and evidence and prose and evidence not in prose:
                self.issue("QUOTATION.MISMATCH", f"{cid}: direct quotation differs from the anchored source")
            access = source["access"]
            if access["level"] not in {"partial", "fulltext"} or access.get("text") != {k: entry["evidence"][k] for k in ("path", "sha256")}:
                self.issue("CITATION.TEXT_ACCESS", f"{cid}: abstract/metadata or unbound text cannot support a full-text claim")
            if source["representation"] == "secondary_quote" and entry["mode"] != "secondary":
                self.issue("CITATION.SECONDARY", f"{cid}: label the secondhand quotation")
            if entry["mode"] == "secondary" and (entry.get("original_source_id") not in records or entry.get("original_source_id") == entry["source_id"]):
                self.issue("CITATION.SECONDARY_SOURCE", f"{cid}: source_id is the consulted intermediary; identify a distinct original_source_id")
            locator = entry["locator"]
            self.review(locator["verification"])
            if locator["kind"] == "printed_page" and not locator.get("printed_page"):
                self.issue("LOCATOR.PAGE", f"{cid}: printed page needs observed printed_page, never inferred from PDF index")
            if locator["kind"] == "pdf_page" and not locator.get("pdf_page"):
                self.issue("LOCATOR.PDF_PAGE", f"{cid}: PDF locator needs its explicit one-based page index")
            claim = claims.get(entry["claim_id"])
            if self.config.get("task_profile") != "manuscript_audit" and claim is None:
                self.issue("CITATION.CLAIM_UNKNOWN", f"{cid}: bind a canonical claim")
            if self.config.get("task_profile") == "manuscript_audit" and entry["claim_id"] is not None and claim is None:
                self.issue("CITATION.CLAIM_UNKNOWN", f"{cid}: audit-only without a design must use null and an exact manuscript span")
            self.review(entry["support_review"])
            expected = support_digest(entry, records.get(entry["source_id"]), claim)
            if entry["support_review"]["binding_digest"] != expected:
                self.issue("SUPPORT.STALE", f"{cid}: claim/source/text/locator binding changed; review support again")
        if manuscript:
            markers = set(re.findall(r"\[\^(CIT-[A-Za-z0-9_-]+)\](?!:)", manuscript))
            if markers != seen:
                self.issue("CITATION.COVERAGE", "CIT footnote markers and ledger IDs must match exactly")
        return data

    def review_document(self, citations):
        data = self.load("review")
        if data is None:
            return
        self.attempt(lambda: binding(self.root, data["manuscript"]))
        if citations and data["manuscript"] != citations["manuscript"]:
            self.issue("REVIEW.MANUSCRIPT", "Legal review is not bound to the cited manuscript")
        for review in data["checks"].values():
            self.review(review)
        for finding in data["findings"]:
            if finding["severity"] == "blocking" and finding["status"] != "resolved":
                self.issue("REVIEW.OPEN", f"Unresolved blocking finding: {finding['id']}")
            if finding["status"] == "resolved":
                if "resolution_basis" not in finding:
                    self.issue("REVIEW.RESOLUTION_MISSING", f"Resolution needs evidence: {finding['id']}")
                else:
                    self.attempt(lambda: binding(self.root, finding["resolution_basis"]))


def check_workspace(outdir, *, stage="audit", config=None):
    config_module, registry = controller()
    stages = registry.STAGE_ORDER
    if stage not in stages:
        raise LegalError("STAGE.UNKNOWN", "Use one of cnki-paper's canonical stages")
    config = config if config is not None else config_module.read_config(Path(outdir)).payload
    check = Check(outdir, config, "intake")
    declared = config.get("legal_profile")
    artifacts = any((Path(outdir) / p).exists() for p in FILES.values())
    if declared != PROFILE:
        if declared is not None or artifacts:
            check.issue("PROFILE.REQUIRED", "Legal artifacts require legal_profile=chinese-law-v1")
        return {"status": "FAIL" if check.issues else "NOT_APPLICABLE", "issues": check.issues,
                "through_stage": stage, "is_completion_receipt": False}
    sources, records, claims, citations = {}, {}, {}, None
    audit_only = config.get("task_profile") == "manuscript_audit"
    try:
        for current in stages[:stages.index(stage) + 1]:
            check.stage = current
            if current == "acquisition":
                sources, records = check.sources()
            elif current == "design" and not audit_only:
                claims = check.analysis(sources)
            elif current == "build":
                citations = check.citations(sources, records, claims)
            elif current == "audit":
                check.review_document(citations)
    except (KeyError, TypeError, ValueError, OSError, RecursionError) as exc:
        check.issue("CONTRACT.MALFORMED", f"Cannot validate malformed contract ({type(exc).__name__})")
    return {"status": "FAIL" if check.issues else "PASS", "issues": check.issues,
            "through_stage": stage, "is_completion_receipt": False,
            "scope": "structural and binding checks; substantive reviews remain human/agent judgments"}
