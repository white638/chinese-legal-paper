"""Tests for the OpenAlex snowball disruption-index helper (network stubbed)."""

from __future__ import annotations

import unittest
from unittest import mock

import openalex_snowball as snowball


class DisruptionIndexTests(unittest.TestCase):
    def test_counts_citers_that_bypass_or_keep_the_predecessors(self) -> None:
        seed = {
            "publication_year": 2019,
            "referenced_works": ["https://openalex.org/W1", "https://openalex.org/W2"],
        }
        pages = [
            {
                "meta": {"count": 4, "next_cursor": "c2"},
                "results": [
                    {"id": "https://openalex.org/W10", "referenced_works": ["https://openalex.org/W1"]},
                    {"id": "https://openalex.org/W11", "referenced_works": ["https://openalex.org/W9"]},
                ],
            },
            {
                "meta": {"count": 4, "next_cursor": None},
                "results": [
                    {"id": "https://openalex.org/W12", "referenced_works": []},
                    {
                        "id": "https://openalex.org/W13",
                        "referenced_works": ["https://openalex.org/W2", "https://openalex.org/W7"],
                    },
                ],
            },
        ]
        calls: list[str] = []

        def fake_fetch(url: str) -> dict:
            calls.append(url)
            return pages[len(calls) - 1]

        with mock.patch.object(snowball, "fetch", fake_fetch), mock.patch.object(
            snowball.time, "sleep", lambda _s: None
        ):
            result = snowball.disruption_index(seed, "W5", {}, window=5, sample=200)
        self.assertEqual(2, result["n_i"])
        self.assertEqual(2, result["n_j"])
        self.assertEqual(0.0, result["cd"])
        self.assertEqual(4, result["scanned_citers"])
        self.assertEqual(4, result["citers_in_window"])
        self.assertEqual(2, result["seed_reference_count"])
        self.assertIn("cites%3AW5", calls[0])
        self.assertIn("from_publication_date%3A2019-01-01", calls[0])
        self.assertIn("to_publication_date%3A2024-12-31", calls[0])
        self.assertIn("select=id%2Creferenced_works", calls[0])

    def test_sample_cap_and_empty_result_stop_pagination(self) -> None:
        seed = {"publication_year": None, "referenced_works": []}
        pages = [
            {"meta": {"count": 10, "next_cursor": "c2"}, "results": [{"id": "W1", "referenced_works": []}] * 3},
            {"meta": {"count": 10, "next_cursor": "c3"}, "results": []},
        ]
        calls: list[str] = []

        def fake_fetch(url: str) -> dict:
            calls.append(url)
            return pages[len(calls) - 1]

        with mock.patch.object(snowball, "fetch", fake_fetch), mock.patch.object(
            snowball.time, "sleep", lambda _s: None
        ):
            result = snowball.disruption_index(seed, "W5", {}, window=5, sample=3)
        self.assertEqual(1, len(calls))
        self.assertNotIn("from_publication_date", calls[0])
        self.assertEqual(3, result["n_i"])
        self.assertEqual(1.0, result["cd"])
        calls.clear()
        with mock.patch.object(snowball, "fetch", fake_fetch), mock.patch.object(
            snowball.time, "sleep", lambda _s: None
        ):
            result = snowball.disruption_index(seed, "W5", {}, window=0, sample=0)
        self.assertEqual([], calls)
        self.assertIsNone(result["cd"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
