#!/usr/bin/env python3
"""Packet regressions use only the original synthetic full-text fixtures."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import commonplace_bank as cb
import commonplace_retrieve as cr
from test_commonplace_bank import synthetic_request, update_metadata


def synthetic_prose() -> dict:
    # Minimal binding fixture; full semantic ProsePacket validation is upstream.
    return {"schema_version": "avereth-prose-packet/v2", "section_role": "literature_review", "rhetorical_task": {"argument_action": "PRESS"}, "claim": {"text": "A synthetic association remains bounded."}}


class CommonplaceRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.request = synthetic_request(self.root)
        self.bank = cb.compile_bank(self.request)
        self.prose = synthetic_prose()
        self.target = {"section_role": "literature_review", "argument_action": "PRESS", "discourse_function": "reframe"}

    def packet(self, **kwargs):
        return cr.retrieve_packet(self.bank, self.prose, "MOVE-SYNTHETIC-1", self.target, **kwargs)

    def test_deterministic_packet_and_full_validation(self):
        packet = self.packet()
        self.assertEqual("READY", packet["status"])
        self.assertEqual(3, len(packet["exemplars"]))
        self.assertEqual(packet, self.packet())
        self.assertEqual([], cr.validate_packet(packet, bank=self.bank, prose_packet=self.prose, move_ref="MOVE-SYNTHETIC-1"))
        self.assertIn("Under these conditions", packet["exemplars"][0]["allowed_bundles"])

    def test_packet_carries_no_private_source_payload(self):
        packet = self.packet()
        serialized = json.dumps(packet)
        for source in self.bank["sources"]:
            self.assertNotIn(source["path"], serialized)
            self.assertNotIn(source["metadata_path"], serialized)
        self.assertNotIn('"fulltext"', serialized)
        self.assertNotIn('"metadata"', serialized)
        self.assertEqual(cr.PACKET_KEYS, set(packet))

    def test_move_action_and_section_bound_to_prose(self):
        for key, value in (("section_role", "methods"), ("argument_action", "DEFINE")):
            with self.subTest(key=key):
                target = {**self.target, key: value}
                with self.assertRaisesRegex(cb.CommonplaceError, "does not match"):
                    cr.retrieve_packet(self.bank, self.prose, "MOVE-SYNTHETIC-1", target)

    def test_no_matching_action_returns_explicit_miss(self):
        for entry in self.request["entries"]:
            entry["argument_action"] = "DEFINE"
        self.bank = cb.compile_bank(self.request)
        packet = self.packet()
        self.assertEqual("COMMONPLACE_MISS", packet["status"])
        self.assertEqual([], packet["exemplars"])
        self.assertEqual([], packet["cross_source_conventions"])
        self.assertEqual([], cr.validate_packet(packet, bank=self.bank, prose_packet=self.prose))

    def test_topic_cannot_substitute_for_move_match(self):
        self.request["entries"][0]["argument_action"] = "DEFINE"
        self.target["topic_terms"] = ["fictional-topic-1"]
        self.bank = cb.compile_bank(self.request)
        self.assertNotIn("CP-SYNTHETIC-1", {entry["cp_id"] for entry in self.packet()["exemplars"]})

    def test_action_and_function_outrank_topic(self):
        self.request["entries"][0]["discourse_function"] = "different-function"
        self.target["topic_terms"] = ["fictional-topic-1"]
        self.bank = cb.compile_bank(self.request)
        self.assertEqual("CP-SYNTHETIC-2", self.packet(limit=1)["exemplars"][0]["cp_id"])

    def test_single_available_source_does_not_force_three(self):
        self.bank = cb.compile_bank({"sources": self.request["sources"][:1], "entries": self.request["entries"][:1]})
        packet = self.packet()
        self.assertEqual(1, len(packet["exemplars"]))
        self.assertEqual([], packet["exemplars"][0]["allowed_bundles"])
        self.assertIn("Under these conditions", packet["exemplars"][0]["blocked_spans"])

    def test_convention_permission_is_bound_to_its_supported_function(self):
        self.request["entries"][0]["discourse_function"] = "different-function"
        self.bank = cb.compile_bank(self.request)
        packet = self.packet()
        by_id = {item["cp_id"]: item for item in packet["exemplars"]}
        self.assertIn("Under these conditions", by_id["CP-SYNTHETIC-2"]["allowed_bundles"])
        self.assertIn("Under these conditions", by_id["CP-SYNTHETIC-1"]["blocked_spans"])
        self.assertEqual([], cr.validate_packet(packet, bank=self.bank, prose_packet=self.prose))

    def test_article_aliases_cannot_fill_packet(self):
        for index in range(3):
            update_metadata(self.request, index, article_id="same-synthetic-article")
        self.bank = cb.compile_bank(self.request)
        self.assertEqual(1, len(self.packet()["exemplars"]))

    def test_independent_author_preferred_among_matching_moves(self):
        update_metadata(self.request, 1, authors=["Synthetic Author 1"])
        self.bank = cb.compile_bank(self.request)
        self.assertEqual(["CP-SYNTHETIC-1", "CP-SYNTHETIC-3"], [item["cp_id"] for item in self.packet(limit=2)["exemplars"]])

    def test_configurable_total_excerpt_budget(self):
        self.target["max_total_excerpt_chars"] = 400
        packet = self.packet()
        self.assertEqual(1, len(packet["exemplars"]))
        self.assertEqual([], cr.validate_packet(packet, bank=self.bank, prose_packet=self.prose))
        self.target["max_total_excerpt_chars"] = 1
        self.assertEqual("COMMONPLACE_MISS", self.packet()["status"])

    def test_resealed_packet_cannot_inject_language(self):
        packet = self.packet()
        packet["exemplars"][0]["syntactic_skeleton"] = "an unauthorized new frame"
        self.assertIn("deterministic", " ".join(cr.validate_packet(packet, bank=self.bank, prose_packet=self.prose)))

    def test_forbidden_fields_rejected_at_every_boundary(self):
        original = self.packet()
        for location in ((), ("target",), ("exemplars", 0), ("exemplars", 0, "neighborhood"), ("cross_source_conventions", 0)):
            with self.subTest(location=location):
                packet = copy.deepcopy(original)
                target = packet
                for key in location:
                    target = target[key]
                target["private_path"] = "secret"
                self.assertIn("forbidden", " ".join(cr.validate_packet(packet)))

    def test_current_prose_hash_and_move_are_required(self):
        packet = self.packet()
        self.prose["claim"]["text"] = "A changed synthetic claim."
        self.assertIn("hash is stale", " ".join(cr.validate_packet(packet, prose_packet=self.prose)))
        self.assertIn("different Move", " ".join(cr.validate_packet(packet, move_ref="MOVE-OTHER")))
        self.assertIn("current ProsePacket", " ".join(cr.validate_packet(packet, bank=self.bank)))

    def test_source_drift_invalidates_existing_packet(self):
        packet = self.packet()
        Path(self.bank["sources"][0]["path"]).write_text("changed", encoding="utf-8")
        self.assertIn("SHA changed", " ".join(cr.validate_packet(packet, bank=self.bank, prose_packet=self.prose)))

    def test_cli_round_trip_from_harvest_to_packet(self):
        script_dir = Path(cb.__file__).parent
        request_path = self.root / "request.json"
        bank_path = self.root / ".avereth-commonplace" / "bank.json"
        prose_path = self.root / "prose.json"
        target_path = self.root / "target.json"
        packet_path = self.root / ".avereth-prose" / "packet.json"
        for path, payload in ((request_path, self.request), (prose_path, self.prose), (target_path, self.target)):
            path.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run([sys.executable, str(script_dir / "commonplace_bank.py"), "compile", "--request", str(request_path), "--output", str(bank_path)], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        result = subprocess.run([sys.executable, str(script_dir / "commonplace_retrieve.py"), "--bank", str(bank_path), "--prose-packet", str(prose_path), "--move-ref", "MOVE-SYNTHETIC-1", "--target", str(target_path), "--output", str(packet_path)], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        self.assertEqual([], cr.validate_packet(packet, bank=self.bank, prose_packet=self.prose))

    def test_packet_schema_preserves_exact_public_whitelists(self):
        path = Path(cr.__file__).parent.parent / "references" / "schemas" / "avereth-commonplace-packet-v1.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        for node, expected in ((schema, cr.PACKET_KEYS), (schema["properties"]["target"], cr.TARGET_KEYS), (schema["properties"]["exemplars"]["items"], cr.EXEMPLAR_KEYS), (schema["properties"]["cross_source_conventions"]["items"], cr.CONVENTION_KEYS)):
            self.assertEqual(expected, set(node["properties"]))
            self.assertEqual(expected, set(node["required"]))
            self.assertFalse(node["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
