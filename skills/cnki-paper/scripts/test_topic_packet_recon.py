"""Tests for reconnaissance grounding and version-bound generation prompts."""

from __future__ import annotations

import hashlib
import unittest

import topic_packet


def synthetic_recon() -> list[dict]:
    """Return protocol-test data, never a record of retrieved literature."""

    return [{
        "query": "synthetic accountability fixture",
        "source": "other",
        "title": "Synthetic reconnaissance fixture",
        "year": 2024,
        "claim": "Synthetic abstract content for a protocol test; not research evidence.",
        "identifier": "https://example.invalid/recon-fixture",
        "retrieved_at": "2026-08-15T07:00:00+00:00",
    }]


def _entry(identifier: str, **overrides) -> dict:
    entry = {
        "query": "密折 信息 国家能力",
        "source": "openalex",
        "title": f"Work {identifier}",
        "year": 2024,
        "claim": "A one-sentence conclusion copied from the abstract.",
        "identifier": identifier,
    }
    entry.update(overrides)
    return entry


class ReconRelationTests(unittest.TestCase):
    def test_relations_between_identified_entries_are_accepted(self) -> None:
        entries = [
            _entry("10.1/a"),
            _entry("10.1/b", relations=[{"target": "10.1/a", "relation": "cites", "evidence": "openalex"}]),
        ]
        self.assertEqual([], topic_packet._recon_issues(entries))

    def test_relation_targets_must_name_another_entry(self) -> None:
        entries = [
            _entry("10.1/a", relations=[{"target": "10.1/zzz", "relation": "cites", "evidence": "openalex"}]),
            _entry("10.1/b", relations=[{"target": "10.1/b", "relation": "cites", "evidence": "openalex"}]),
        ]
        issues = topic_packet._recon_issues(entries)
        joined = " ".join(issues)
        self.assertIn("must equal another entry's identifier", joined)
        self.assertIn("cannot be the entry itself", joined)

    def test_relation_enums_fields_and_duplicates_are_checked(self) -> None:
        entries = [
            _entry("10.1/a"),
            _entry(
                "10.1/b",
                relations=[
                    {"target": "10.1/a", "relation": "extends", "evidence": "gossip", "note": "x"},
                    {"target": "10.1/a", "relation": "cites", "evidence": "cnki"},
                    {"target": "10.1/a", "relation": "cites", "evidence": "openalex"},
                ],
            ),
        ]
        issues = topic_packet._recon_issues(entries)
        joined = " ".join(issues)
        self.assertIn("relation must be one of", joined)
        self.assertIn("evidence must be one of", joined)
        self.assertIn("unauthorized fields: note", joined)
        self.assertIn("repeats cites toward 10.1/a", joined)
        self.assertFalse(any("exceeds" in item for item in issues))

    def test_relations_must_be_an_array_and_stay_bounded(self) -> None:
        entries = [_entry("10.1/a"), _entry("10.1/b", relations={"target": "10.1/a"})]
        self.assertTrue(any("must be an array" in item for item in topic_packet._recon_issues(entries)))
        many = [{"target": "10.1/a", "relation": "cites", "evidence": "openalex"}] + [
            {"target": "10.1/a", "relation": "co-cited-with", "evidence": "other"} for _ in range(topic_packet.RECON_MAX_RELATIONS)
        ]
        entries = [_entry("10.1/a"), _entry("10.1/b", relations=many)]
        self.assertTrue(any("cannot exceed" in item for item in topic_packet._recon_issues(entries)))

    def test_generation_prompt_explains_relation_semantics(self) -> None:
        packet = {
            "origin_mode": "direction_first",
            topic_packet.RECON_INPUT_KEY: [
                _entry("10.1/a"),
                _entry("10.1/b", relations=[{"target": "10.1/a", "relation": "cites", "evidence": "openalex"}]),
            ],
        }
        prompt = topic_packet.canonical_generation_prompt(packet, "core_problem")
        self.assertIn("treat a missing relation as unverified rather than", prompt)
        self.assertIn('"target":"10.1/a"', prompt)
        self.assertIn('"relation":"cites"', prompt)


class GenerationFocusTests(unittest.TestCase):
    def test_focus_uses_existing_fields_and_preserves_legitimate_question_routes(self) -> None:
        for origin in sorted(topic_packet.ORIGIN_MODES):
            with self.subTest(origin=origin):
                packet = {
                    "origin_mode": origin,
                    topic_packet.RECON_INPUT_KEY: synthetic_recon(),
                }
                materials = [] if origin == "direction_first" else [
                    {"path": "source.txt", "sha256": "a" * 64, "text": "Bounded observation."}
                ]
                prompt = topic_packet.canonical_generation_prompt(packet, "core_problem", materials)
                for instruction in (
                    "In problem, ask the question without prescribing a preferred answer",
                    "In anomaly_or_unknown, name a packet-supported existing explanation",
                    "alternatively identify an important unknown",
                    "In why_it_matters, state which substantive judgment an answer would change",
                    "In potential_disconfirmation, specify feasible evidence or reasoning",
                    "support, revise, or withdraw",
                    "compatible explanations may coexist",
                    "Descriptive, historical, normative, and synthesis questions are legitimate",
                    "a thin search or different scopes do not establish a dominant assumption",
                ):
                    self.assertIn(instruction, prompt)
                protocol = topic_packet.generation_protocol(packet)
                self.assertEqual("avereth-topic-generation-protocol/v2", protocol["schema_version"])
                self.assertEqual(topic_packet.SEED_KEYS, set(protocol["output_fields"]))
                self.assertEqual(
                    topic_packet.SEED_KEYS,
                    set(topic_packet.seed_output_schema()["items"]["properties"]),
                )

    def test_legacy_generation_prompt_and_protocol_hashes_remain_exact(self) -> None:
        cases = (
            ("direction_first", False,
             "d86cda18055c957fcdd0aaaab40500a21b924d065704163982f85dd43cde464e",
             "4b45585cee74a1f40076bce8fc4d5a5759c1b553eda2da768db4a5c3002115dd"),
            ("direction_first", True,
             "75c997f98b583f3d9bfc11ee2c2d76ab8135d6d3901dadf9bd989db9edc0846a",
             "31f9d563c981b5c61bc213402da05a6763fbb4ae42115921b0ca10e9ddaaba9a"),
            ("material_opportunity", False,
             "e03386a6dd4bf712a5dd699b9f0d09f4e7523d731b90eda76f7a357701406c01",
             "45138a5b83dfbc9e2a03c670fd89ae719299be27ecbefd6f1bda1c0f44aa0d74"),
            ("phenomenon_first", True,
             "876f707e3e3a6b7a2a45ac3710b974290fcb574febc2173940cdd5d6c249edb4",
             "5ead8d69ff1860b62adc483043f8b305d02cde13193ed5d8ad7ed222d8f46b1d"),
        )
        for origin, with_recon, prompt_sha, protocol_sha in cases:
            with self.subTest(origin=origin, recon=with_recon):
                packet = {"origin_mode": origin}
                if with_recon:
                    packet[topic_packet.RECON_INPUT_KEY] = synthetic_recon()
                materials = [] if origin == "direction_first" else [{
                    "path": "source.txt",
                    "sha256": "a" * 64,
                    "text": "A bounded observation with unknown recording conditions.",
                }]
                version = topic_packet.LEGACY_GENERATION_PROTOCOL_SCHEMA_VERSION
                prompt = topic_packet.canonical_generation_prompt(
                    packet, "core_problem", materials, protocol_version=version
                )
                self.assertEqual(prompt_sha, hashlib.sha256(prompt.encode("utf-8")).hexdigest())
                self.assertEqual(
                    protocol_sha,
                    topic_packet.canonical_digest(
                        topic_packet.generation_protocol(packet, protocol_version=version)
                    ),
                )
                self.assertNotEqual(
                    prompt, topic_packet.canonical_generation_prompt(packet, "core_problem", materials)
                )

    def test_unknown_generation_protocol_cannot_select_a_prompt(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported topic generation protocol"):
            topic_packet.canonical_generation_prompt(
                {"origin_mode": "direction_first"},
                "core_problem",
                protocol_version="avereth-topic-generation-protocol/v99",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
