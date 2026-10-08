"""Tests for verified citation edges shared by acquisition, sufficiency, and analysis."""

from __future__ import annotations

import unittest

import citation_edges as edges_module


def _edge(edge_id: str = "EDGE-001", **overrides) -> dict:
    edge = {
        "edge_id": edge_id,
        "from_source_id": "S2",
        "to_source_id": "S1",
        "relation": "cites",
        "evidence": "openalex",
        "verified_at": "2026-09-04",
    }
    edge.update(overrides)
    return edge


class CitationEdgeValidationTests(unittest.TestCase):
    def test_minimal_cites_edge_is_valid(self) -> None:
        registry = {"edges": [_edge()]}
        self.assertEqual([], edges_module.edge_issues(registry, valid_source_ids={"S1", "S2"}))

    def test_missing_edges_key_is_not_an_error(self) -> None:
        self.assertEqual([], edges_module.edge_issues({}))
        self.assertFalse(edges_module.has_edges({}))

    def test_endpoints_must_be_registered_and_distinct(self) -> None:
        registry = {"edges": [_edge(to_source_id="S9"), _edge("EDGE-002", from_source_id="S1", to_source_id="S1")]}
        issues = edges_module.edge_issues(registry, valid_source_ids={"S1", "S2"})
        self.assertTrue(any("S9 is not a registered Source ID" in item for item in issues))
        self.assertTrue(any("cannot relate a source to itself" in item for item in issues))

    def test_stance_requires_citing_text_and_a_quote(self) -> None:
        registry = {"edges": [_edge(stance="critical")]}
        issues = edges_module.edge_issues(registry, valid_source_ids={"S1", "S2"})
        self.assertTrue(any("requires evidence from the citing text" in item for item in issues))
        self.assertTrue(any("requires a context_quote" in item for item in issues))
        good = {
            "edges": [
                _edge(
                    stance="critical",
                    evidence="full-text-read",
                    context_quote="该文将奏折数量当作信息流量，忽略了内容层的失真问题。",
                    context_locator="p. 45",
                )
            ]
        }
        self.assertEqual([], edges_module.edge_issues(good, valid_source_ids={"S1", "S2"}))

    def test_stance_is_only_meaningful_on_cites_edges(self) -> None:
        registry = {
            "edges": [
                _edge(
                    relation="co-cited-with",
                    stance="supportive",
                    evidence="full-text-read",
                    context_quote="a sufficiently long quote for the test",
                )
            ]
        }
        issues = edges_module.edge_issues(registry, valid_source_ids={"S1", "S2"})
        self.assertTrue(any("only meaningful on a cites edge" in item for item in issues))

    def test_co_mention_requires_paragraph_evidence(self) -> None:
        registry = {"edges": [_edge(relation="co-mentioned-with", evidence="cnki-detail")]}
        issues = edges_module.edge_issues(registry, valid_source_ids={"S1", "S2"})
        self.assertTrue(any("paragraph-level text evidence" in item for item in issues))
        self.assertTrue(any("co-mentioning context_quote" in item for item in issues))

    def test_duplicate_ids_and_symmetric_pairs_are_rejected(self) -> None:
        registry = {
            "edges": [
                _edge("EDGE-001", relation="co-cited-with"),
                _edge("EDGE-001", relation="co-cited-with", from_source_id="S1", to_source_id="S2"),
            ]
        }
        issues = edges_module.edge_issues(registry, valid_source_ids={"S1", "S2"})
        self.assertTrue(any("duplicates edge_id" in item for item in issues))
        self.assertTrue(any("repeats an existing co-cited-with edge" in item for item in issues))

    def test_enums_dates_and_query_ids_are_checked(self) -> None:
        registry = {"edges": [_edge(relation="extends", evidence="rumour", verified_at="yesterday", query_id="Q-X")]}
        issues = edges_module.edge_issues(registry, valid_source_ids={"S1", "S2"}, valid_query_ids={"Q-1"})
        joined = " ".join(issues)
        self.assertIn("relation must be one of", joined)
        self.assertIn("evidence must be one of", joined)
        self.assertIn("ISO-8601", joined)
        self.assertIn("Q-X is not a registered Query ID", joined)


class CitationGraphTests(unittest.TestCase):
    def test_connectivity_uses_only_cites_edges_and_allows_intermediates(self) -> None:
        edges = [
            _edge("EDGE-001", from_source_id="S3", to_source_id="S1"),
            _edge("EDGE-002", from_source_id="S3", to_source_id="S2"),
            _edge("EDGE-003", from_source_id="S4", to_source_id="S2", relation="co-cited-with"),
        ]
        graph = edges_module.cites_adjacency(edges)
        connected, unreachable = edges_module.connected_through(graph, ["S1", "S2"])
        self.assertTrue(connected)
        self.assertEqual([], unreachable)
        connected, unreachable = edges_module.connected_through(graph, ["S1", "S4"])
        self.assertFalse(connected)
        self.assertEqual(["S4"], unreachable)
        self.assertTrue(edges_module.connected_through(graph, ["S1"])[0])

    def test_touching_and_critical_filters(self) -> None:
        edges = [
            _edge("EDGE-001", stance="critical", evidence="full-text-read", context_quote="a long enough critical quote"),
            _edge("EDGE-002", from_source_id="S3", to_source_id="S4"),
        ]
        touching = edges_module.edges_touching(edges, ["S1"])
        self.assertEqual(["EDGE-001"], [item["edge_id"] for item in touching])
        self.assertEqual(["EDGE-001"], [item["edge_id"] for item in edges_module.critical_edges(edges)])

    def test_markdown_view_lists_every_edge(self) -> None:
        text = edges_module.render_edges_markdown({"edges": [_edge(), _edge("EDGE-002", relation="co-cited-with")]})
        self.assertIn("## Citation Edges", text)
        self.assertIn("| EDGE-001 | S2 | cites | S1 | openalex | unknown | 2026-09-04 | - |", text)
        self.assertIn("co-cited-with", text)
        self.assertEqual("", edges_module.render_edges_markdown({}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
