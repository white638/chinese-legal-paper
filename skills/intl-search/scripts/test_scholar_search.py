from __future__ import annotations

import unittest

import scholar_search as scholar


class FakeScholarly:
    def __init__(self, publications: list[dict]) -> None:
        self.publications = publications
        self.calls: list[tuple[str, dict]] = []

    def search_pubs(self, query: str, **kwargs):
        self.calls.append((query, kwargs))
        return iter(self.publications)


class ScholarSearchTests(unittest.TestCase):
    PUBLICATION = {
        "bib": {
            "title": "Weaponized Interdependence",
            "author": ["Henry Farrell", "Abraham Newman"],
            "pub_year": "2019",
            "venue": "International Security",
            "abstract": "This is only a Google Scholar result-page snippet.",
        },
        "pub_url": "https://doi.org/10.1162/isec_a_00351",
        "num_citations": "1,800",
    }

    def test_query_url_is_reproducible_and_first_page_scoped(self) -> None:
        url = scholar.scholar_query_url(
            '"weaponized interdependence"',
            year_low=2019,
            year_high=2026,
            sort_by="date",
        )
        self.assertTrue(url.startswith("https://scholar.google.com/scholar?"))
        self.assertIn("q=%22weaponized+interdependence%22", url)
        self.assertIn("as_ylo=2019", url)
        self.assertIn("as_yhi=2026", url)
        self.assertIn("scisbd=1", url)

    def test_scholarly_output_is_registry_shaped_candidate_only(self) -> None:
        api = FakeScholarly([self.PUBLICATION])
        payload = scholar.search_publications(
            '"weaponized interdependence"',
            query_id="Q-GS-001",
            purpose="collision",
            api=api,
            collected_at="2026-08-04",
        )
        query = payload["query"]
        source = payload["sources"][0]
        self.assertEqual("Google Scholar", query["channel"])
        self.assertEqual("first-page-extracted", query["result_count_basis"])
        self.assertTrue(query["result_count_is_approximate"])
        self.assertEqual("Google Scholar", source["channel"])
        self.assertEqual("discovered", source["state"])
        self.assertEqual("candidate-only", source["citation_scope"])
        self.assertEqual({}, source["verification"])
        self.assertEqual(1800, source["metadata"]["scholar_cited_by"])
        self.assertEqual("10.1162/isec_a_00351", source["doi"])
        self.assertNotIn("bibtex", source)

    def test_session_waits_five_seconds_and_caps_at_five_searches(self) -> None:
        now = [0.0]
        sleeps: list[float] = []

        def clock() -> float:
            return now[0]

        def sleeper(seconds: float) -> None:
            sleeps.append(seconds)
            now[0] += seconds

        session = scholar.ScholarSearchSession(clock=clock, sleeper=sleeper)
        session.run(lambda: [])
        now[0] = 1.0
        session.run(lambda: [])
        self.assertEqual([4.0], sleeps)
        for _ in range(3):
            now[0] += 5.0
            session.run(lambda: [])
        with self.assertRaises(scholar.ScholarBlocked):
            session.run(lambda: [])

    def test_captcha_exception_is_not_retried_or_proxied(self) -> None:
        class BlockedAPI:
            def search_pubs(self, query: str, **kwargs):
                raise RuntimeError("CAPTCHA at google.com/sorry")

        with self.assertRaisesRegex(scholar.ScholarBlocked, "do not retry"):
            scholar.search_publications(
                "test",
                query_id="Q-GS-001",
                purpose="citation",
                api=BlockedAPI(),
            )

    def test_limit_cannot_trigger_pagination(self) -> None:
        with self.assertRaisesRegex(ValueError, "first page only"):
            scholar.search_publications(
                "test",
                query_id="Q-GS-001",
                purpose="citation",
                limit=11,
                api=FakeScholarly([]),
            )


if __name__ == "__main__":
    unittest.main()
