"""Synthetic text probes for per-source borrowing judgments."""
import unittest

from commonplace_overlap_check import check_overlap


def packet(text="The archive is a clock with missing hands.", *, blocked=None, allowed=None, sid="SRC-STYLE"):
    return {"exemplars": [{"source_id": sid, "neighborhood": {"before": "", "focus": text, "after": ""},
                           "blocked_spans": blocked or [], "allowed_bundles": allowed or []}]}


class OverlapTests(unittest.TestCase):
    def test_distinctive_phrase_is_hard_failure(self):
        report = check_overlap("A clock with missing hands.", packet(blocked=["clock with missing hands"]), {})
        self.assertEqual("FAIL", report["verdict"])

    def test_registered_bundle_is_permitted(self):
        text = "in the context of this analysis"
        report = check_overlap(text, packet(text, allowed=[text]), {})
        self.assertEqual("PASS", report["verdict"])
        self.assertTrue(report["allowed_bundle_matches"])

    def test_unregistered_contiguous_language_requires_review(self):
        report = check_overlap("The archive is a clock with missing hands.", packet(), {})
        self.assertEqual("REVIEW", report["verdict"])
        self.assertEqual(1, report["single_source_concentration"]["SRC-STYLE"]["fraction"])

    def test_chinese_punctuation_does_not_hide_distinctive_reuse(self):
        report = check_overlap("制度，沿着档案的裂缝生长。", packet("制度沿着档案的裂缝生长", blocked=["档案的裂缝"]), {})
        self.assertEqual("FAIL", report["verdict"])

    def test_evidence_authorized_same_source_quote_exempts_only_quoted_occurrence(self):
        phrase = "clock with missing hands"
        prose = {"evidence_items": [{"citation_key": "[3]", "context_anchor": {
            "type": "quotation", "authority_ref": "SRC-STYLE", "exact_span": phrase}}]}
        cp = packet(blocked=[phrase])
        self.assertEqual("PASS", check_overlap(f'“{phrase}” [3]', cp, prose)["verdict"])
        self.assertEqual("FAIL", check_overlap(f'“{phrase}” [3]. {phrase}.', cp, prose)["verdict"])

    def test_quote_from_different_source_does_not_exempt(self):
        phrase = "clock with missing hands"
        prose = {"evidence_items": [{"citation_key": "[3]", "context_anchor": {
            "type": "quotation", "authority_ref": "SRC-OTHER", "exact_span": phrase}}]}
        self.assertEqual("FAIL", check_overlap(f'“{phrase}” [3]', packet(blocked=[phrase]), prose)["verdict"])

    def test_allowed_bundle_cannot_override_distinctive_registration(self):
        phrase = "clock with missing hands"
        self.assertEqual("FAIL", check_overlap(phrase, packet(blocked=[phrase], allowed=[phrase]), {})["verdict"])

    def test_new_text_passes_without_claiming_semantic_originality(self):
        self.assertEqual("PASS", check_overlap("Records differ across offices.", packet(), {})["verdict"])

    def test_empty_draft_fails(self):
        self.assertEqual("FAIL", check_overlap("", packet(), {})["verdict"])

    def test_sources_are_reported_separately(self):
        cp = packet()
        cp["exemplars"] += packet("Routine comparison provides a different starting point.", sid="SRC-TWO")["exemplars"]
        report = check_overlap("The archive is a clock with missing hands.", cp, {})
        self.assertEqual({"SRC-STYLE", "SRC-TWO"}, set(report["single_source_concentration"]))

    def test_split_short_fragments_still_trigger_source_review(self):
        source = "amber stone quiet copper silver river narrow garden violet window distant meadow"
        draft = "amber stone quiet copper then silver river narrow garden then violet window distant meadow"
        self.assertEqual("REVIEW", check_overlap(draft, packet(source), {})["verdict"])

    def test_citation_key_prefix_cannot_exempt_a_quote(self):
        prose = {"evidence_items": [{"citation_key": "Smith2020", "context_anchor": {
            "type": "quotation", "authority_ref": "SRC-STYLE", "exact_span": "quiet copper"}}]}
        cp = packet("quiet copper", blocked=["quiet copper"])
        self.assertEqual("FAIL", check_overlap('"quiet copper" (Smith20201)', cp, prose)["verdict"])


if __name__ == "__main__":
    unittest.main()
