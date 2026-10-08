"""Incomplete templates deliberately cannot satisfy evidence gates."""
from .common import SKILL, read_json


def template(name, method="doctrinal"):
    bound = {"path": "", "sha256": ""}
    review = {"status": "pending", "reviewer": "", "reviewed_at": "", "reason": "", "basis": dict(bound)}
    if name == "sources":
        return {"schema_version": "legal-sources/v1", "scope": "legal_sources", "scope_reason": "", "sources": []}
    if name == "source":
        return {"source_id": "", "source_digest": "", "version_id": "", "kind": "statute",
                "jurisdiction": "", "representation": "official_text",
                "authority": {"issuer": "", "level": "", "document_number": ""},
                "identity_review": review, "access": {"level": "metadata", "permission": "unknown", "basis": ""},
                "temporal": {"status": "unknown", "checked_at": "", "basis": dict(bound)}}
    if name == "analysis":
        profiles = read_json(SKILL / "assets/method-profiles.json")["profiles"]
        if method not in profiles:
            from .common import LegalError
            raise LegalError("METHOD.UNKNOWN", "Unknown method profile")
        return {"schema_version": "legal-analysis/v1", "design": {**bound, "path": "research_design.json"},
                "method": method, "method_card": {k: "" for k in profiles[method]["required_fields"]}, "claims": []}
    if name == "claim":
        return {"claim_id": "", "claim_digest": "", "source_ids": [], "jurisdiction": "",
                "as_of": "", "use": "interpretation", "applicability_review": review}
    if name == "citations":
        return {"schema_version": "legal-citations/v1", "manuscript": bound, "style": "working-footnote-v1", "entries": []}
    if name == "citation":
        anchor = {**bound, "start": 0, "end": 0, "quote": ""}
        return {"citation_id": "CIT-001", "source_id": "", "version_id": "", "claim_id": None,
                "manuscript_span": dict(anchor), "evidence": dict(anchor), "mode": "paraphrase",
                "locator": {"kind": "article", "label": "", "verification": review},
                "support_review": {"status": "pending", "reviewer": "", "reviewed_at": "", "reason": "", "binding_digest": ""}}
    if name == "review":
        return {"schema_version": "legal-review/v1", "manuscript": bound,
                "checks": {k: dict(review) for k in ("sources", "applicability", "claim_support", "method", "opposition", "semantic_fidelity", "citation_rules")},
                "findings": []}
    raise ValueError(name)
