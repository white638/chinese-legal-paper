#!/usr/bin/env python3
"""Regression fixtures are original synthetic texts, not published excerpts."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

import commonplace_bank as cb


def synthetic_request(root: Path, count: int = 3) -> dict:
    """Write tiny original full texts and explicitly synthetic verified records."""
    sources, entries = [], []
    for index in range(count):
        source_id = f"SRC-SYNTHETIC-{index + 1}"
        before = f"Synthetic paper {index + 1}. The account begins with an expected sequence. "
        focus = f"Under these conditions, local routines changed in case {index + 1}. The quiet copper hinge {index + 1} marks an invented phrase."
        after = f" This observation redirects the next comparison in fictional study {index + 1}."
        path = root / f"synthetic-{index + 1}.txt"
        path.write_bytes((before + focus + after).encode("utf-8"))
        digest = cb.file_sha256(path)
        metadata = {"source_id": source_id, "article_id": f"synthetic-article-{index + 1}", "title": f"Synthetic paper {index + 1}", "authors": [f"Synthetic Author {index + 1}"], "discipline": "synthetic social science", "venue": "Synthetic Test Journal", "fulltext_sha256": digest, "fulltext_verified": True, "permission_status": "permitted", "synthetic": True}
        metadata_path = root / f"synthetic-{index + 1}.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        sources.append({"source_id": source_id, "path": str(path), "sha256": digest, "metadata_path": str(metadata_path), "metadata_sha256": cb.file_sha256(metadata_path)})
        entries.append({"cp_id": f"CP-SYNTHETIC-{index + 1}", "source_id": source_id, "locator": {"section": "discussion", "paragraph": 1}, "selection": {"before_start": 0, "start": len(before), "end": len(before + focus), "after_end": len(before + focus + after)}, "section_role": "literature_review", "argument_action": "PRESS", "discourse_function": "reframe", "rhetorical_skeleton": ["state interpretation", "redirect comparison"], "citation_pattern": ["position_then_interpretation"], "syntactic_skeleton": "Under [condition], [bounded observation].", "lexical_bundles": [{"text": "Under these conditions", "category": "conventional_bundle"}], "distinctive_spans": [f"quiet copper hinge {index + 1}"], "topic_terms": [f"fictional-topic-{index + 1}"], "reuse_class": "structural_exemplar"})
    return {"sources": sources, "entries": entries}


def update_metadata(request: dict, index: int, **changes) -> None:
    source = request["sources"][index]
    path = Path(source["metadata_path"])
    metadata = json.loads(path.read_text(encoding="utf-8"))
    metadata.update(changes)
    path.write_text(json.dumps(metadata), encoding="utf-8")
    source["metadata_sha256"] = cb.file_sha256(path)


class CommonplaceBankTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.request = synthetic_request(self.root)

    def test_exact_local_span_and_deterministic_bank(self):
        bank = cb.compile_bank(self.request)
        self.assertEqual([], cb.validate_bank(bank))
        self.assertEqual(bank, cb.compile_bank(self.request))
        entry = bank["entries"][0]
        source = bank["sources"][0]
        self.assertEqual(source["fulltext"][entry["selection"]["start"]:entry["selection"]["end"]], entry["neighborhood"]["focus"])
        self.assertTrue(all(source["metadata"]["synthetic"] for source in bank["sources"]))

    def test_source_file_drift_fails_closed(self):
        bank = cb.compile_bank(self.request)
        Path(bank["sources"][0]["path"]).write_text("changed synthetic source", encoding="utf-8")
        self.assertIn("SHA changed", " ".join(cb.validate_bank(bank)))
        with self.assertRaises(cb.CommonplaceError):
            cb.derive_phraseology(bank)

    def test_metadata_file_drift_fails_closed(self):
        bank = cb.compile_bank(self.request)
        update_metadata(self.request, 0, authors=["Different Synthetic Author"])
        self.assertIn("SHA changed", " ".join(cb.validate_bank(bank)))

    def test_requested_source_hash_must_be_current(self):
        self.request["sources"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(cb.CommonplaceError, "SHA changed"):
            cb.compile_bank(self.request)

    def test_requires_verified_permitted_fulltext(self):
        update_metadata(self.request, 0, permission_status="unknown")
        with self.assertRaisesRegex(cb.CommonplaceError, "permitted use"):
            cb.compile_bank(self.request)

    def test_cannot_supply_fabricated_neighborhood(self):
        self.request["entries"][0]["neighborhood"] = {"focus": "invented"}
        with self.assertRaisesRegex(cb.CommonplaceError, "forbidden"):
            cb.compile_bank(self.request)

    def test_requires_neighbor_context_and_bounded_offsets(self):
        selection = self.request["entries"][0]["selection"]
        selection["before_start"] = selection["start"]
        with self.assertRaisesRegex(cb.CommonplaceError, "before and after"):
            cb.compile_bank(self.request)

    def test_registered_expression_must_exist(self):
        self.request["entries"][0]["lexical_bundles"][0]["text"] = "a phrase absent from the source"
        with self.assertRaisesRegex(cb.CommonplaceError, "absent"):
            cb.compile_bank(self.request)

    def test_character_budget_is_cumulative_per_source(self):
        duplicate = copy.deepcopy(self.request["entries"][0])
        duplicate["cp_id"] = "CP-SYNTHETIC-DUPLICATE"
        self.request["entries"].append(duplicate)
        self.request["limits"] = {"max_excerpt_chars_per_entry": 400, "max_excerpt_chars_per_source": 400}
        with self.assertRaisesRegex(cb.CommonplaceError, "cumulative"):
            cb.compile_bank(self.request)

    def test_bank_tampering_cannot_reseal_wrong_context(self):
        bank = cb.compile_bank(self.request)
        bank["entries"][0]["neighborhood"]["focus"] = "made up"
        bank["source_digest"] = cb._digest(bank)
        self.assertIn("does not match", " ".join(cb.validate_bank(bank)))

    def test_common_phrase_needs_independent_authors_and_articles(self):
        phraseology = cb.derive_phraseology(cb.compile_bank(self.request))
        expression = phraseology["expressions"][0]
        self.assertTrue(expression["reuse_allowed"])
        self.assertEqual(3, len(expression["source_ids"]))
        single = {"sources": self.request["sources"][:1], "entries": self.request["entries"][:1]}
        self.assertFalse(cb.derive_phraseology(cb.compile_bank(single))["expressions"][0]["reuse_allowed"])

    def test_coauthors_do_not_count_as_independent_support(self):
        for index in range(3):
            update_metadata(self.request, index, authors=["Shared Synthetic Author", f"Second {index}"])
        expression = cb.derive_phraseology(cb.compile_bank(self.request))["expressions"][0]
        self.assertFalse(expression["independent_support"])
        self.assertEqual("conventional_bundle", expression["category"])
        self.assertFalse(expression["reuse_allowed"])

    def test_article_aliases_do_not_count_as_independent_support(self):
        for index in range(3):
            update_metadata(self.request, index, article_id="same-synthetic-article")
        self.assertFalse(cb.derive_phraseology(cb.compile_bank(self.request))["expressions"][0]["reuse_allowed"])

    def test_explicit_distinctive_span_overrides_frequency(self):
        self.request["entries"][0]["distinctive_spans"].append("Under these conditions")
        self.assertFalse(cb.derive_phraseology(cb.compile_bank(self.request))["expressions"][0]["reuse_allowed"])

    def test_same_function_required_for_convention_support(self):
        for index, entry in enumerate(self.request["entries"]):
            entry["discourse_function"] = f"synthetic-function-{index}"
        self.assertFalse(any(item["reuse_allowed"] for item in cb.derive_phraseology(cb.compile_bank(self.request))["expressions"]))

    def test_schema_assets_preserve_private_bank_contract(self):
        root = Path(cb.__file__).parent.parent / "references" / "schemas"
        schema = json.loads((root / "avereth-commonplace-bank-v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(cb.BANK_KEYS, set(schema["properties"]))
        self.assertFalse(schema["additionalProperties"])
        source = schema["properties"]["sources"]["items"]
        self.assertEqual(cb.SOURCE_KEYS, set(source["properties"]))
        self.assertEqual(cb.METADATA_KEYS, set(source["properties"]["metadata"]["properties"]))
        entry = schema["properties"]["entries"]["items"]
        self.assertEqual(cb.ENTRY_KEYS, set(entry["properties"]))
        phraseology = json.loads((root / "avereth-disciplinary-phraseology-v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(cb.PHRASEOLOGY_SCHEMA_VERSION, phraseology["properties"]["schema_version"]["const"])
        expression = phraseology["properties"]["expressions"]["items"]
        self.assertEqual(cb.CATEGORIES, set(expression["properties"]["category"]["enum"]))


if __name__ == "__main__":
    unittest.main()
