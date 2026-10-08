"""Tests for automated top-journal exemplar harvesting, shortlisting, and selection."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
import urllib.parse
from pathlib import Path

import taste_cards
import taste_exemplars

MODEL = "test-exemplar-model"


def _work(index: int, year: int, cited: int, *, refs: int = 30, abstract: str | None = None, title: str | None = None) -> dict:
    words = (abstract or f"This article studies institutions and mechanisms in case {index} with careful comparative evidence and a clear scope condition.").split()
    inverted: dict[str, list[int]] = {}
    for position, word in enumerate(words):
        inverted.setdefault(word, []).append(position)
    return {
        "id": f"https://openalex.org/W{index}",
        "doi": f"https://doi.org/10.1000/wp.{year}.{index}",
        "title": title or f"Paper {index} on comparative institutions",
        "publication_year": year,
        "cited_by_count": cited,
        "cited_by_percentile_year": {"min": 50, "max": 60},
        "fwci": cited / 10,
        "language": "en",
        "is_retracted": False,
        "referenced_works_count": refs,
        "abstract_inverted_index": inverted,
    }


def fake_fetch_factory(works_by_source: dict[str, list[dict]]):
    def fake_fetch(url: str) -> dict:
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        if parsed.path.endswith("/sources"):
            name = query["search"][0]
            return {
                "results": [
                    {"id": "https://openalex.org/S1", "display_name": "World Politics", "issn_l": "0043-8871", "works_count": 10, "type": "journal"}
                ]
                if "World Politics" in name
                else []
            }
        filters = query["filter"][0]
        source_id = filters.split("primary_location.source.id:")[1].split(",")[0]
        cursor = query.get("cursor", ["*"])[0]
        works = works_by_source.get(source_id, [])
        if cursor == "*":
            return {"results": works[:2], "meta": {"next_cursor": "page2" if len(works) > 2 else None}}
        return {"results": works[2:], "meta": {"next_cursor": None}}

    return fake_fetch


def build_harvest(slug: str = "comparative-politics") -> dict:
    records = []
    for year in (2020, 2021):
        for index in range(20):
            records.append(
                {
                    "record_id": f"OPENALEX-{year}{index:02d}",
                    "source": "openalex",
                    "identifier": f"10.1000/wp.{year}.{index}",
                    "title": f"Paper {year}-{index}" + (" on the Global South" if index == 19 else ""),
                    "venue": "World Politics",
                    "year": year,
                    "cited_by": index * 5,
                    "abstract": "A" * 250,
                    "language": "en",
                    "referenced_works_count": 40,
                    "fwci": index / 2,
                    "hot_term_hits": ["Global South"] if index == 19 else [],
                }
            )
    for index in range(20):
        records.append(
            {
                "record_id": f"CNKI-{index:02d}",
                "source": "cnki",
                "identifier": f"https://kns.cnki.net/kcms2/article/abstract?v={index}",
                "title": f"比较政治论文{index}",
                "venue": "比较政治学研究",
                "year": 2021,
                "cited_by": index,
                "abstract": "摘要" * 40 if index != 0 else "",
                "language": "zh",
                "reprints": [],
                "hot_term_hits": [],
            }
        )
    records.append(
        {
            "record_id": "OPENALEX-RECENT",
            "source": "openalex",
            "identifier": "10.1000/wp.2025.1",
            "title": "Too recent",
            "venue": "World Politics",
            "year": 2025,
            "cited_by": 500,
            "abstract": "A" * 250,
            "language": "en",
            "referenced_works_count": 40,
            "fwci": 9.0,
            "hot_term_hits": [],
        }
    )
    return {
        "schema_version": taste_exemplars.HARVEST_SCHEMA,
        "card_slug": slug,
        "years": [2019, 2025],
        "harvested_at": "2026-09-04T00:00:00Z",
        "journals": [],
        "records": records,
    }


class HarvestTests(unittest.TestCase):
    def test_openalex_harvest_paginates_and_normalises(self) -> None:
        works = [_work(1, 2020, 120), _work(2, 2020, 3), _work(3, 2021, 40, refs=2), _work(4, 2021, 0)]
        fetch = fake_fetch_factory({"S1": works})
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "harvest.json"
            code = taste_exemplars.main(
                ["harvest-openalex", "comparative-politics", "--out", str(out), "--journal", "World Politics", "--years", "2019-2025"],
                fetch=fetch,
            )
            self.assertEqual(0, code)
            harvest = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(4, len(harvest["records"]))
            first = harvest["records"][0]
            self.assertEqual("openalex", first["source"])
            self.assertEqual("10.1000/wp.2020.1", first["identifier"])
            self.assertTrue(first["abstract"].startswith("This article studies"))
            self.assertEqual("World Politics", first["venue"])
            self.assertEqual(1, len(harvest["journals"]))
            # re-running merges instead of duplicating
            code = taste_exemplars.main(
                ["harvest-openalex", "comparative-politics", "--out", str(out), "--journal", "World Politics"], fetch=fetch
            )
            self.assertEqual(0, code)
            self.assertEqual(4, len(json.loads(out.read_text(encoding="utf-8"))["records"]))

    def test_cnki_ingest_normalises_browser_exports(self) -> None:
        registry = taste_cards.load_registry()
        card = taste_cards.card_by_slug(registry, "chinese-politics")
        terms = taste_cards.hot_terms_for(registry, card)
        record = taste_exemplars.cnki_record(
            {
                "title": "基层治理中的责任配置",
                "url": "https://kns.cnki.net/kcms2/article/abstract?v=abc",
                "journal": "政治学研究",
                "date": "2021-03-15",
                "citations": "37",
                "downloads": "1,204",
                "abstract": "本文讨论基层治理中的责任配置。",
            },
            terms,
        )
        self.assertEqual("cnki", record["source"])
        self.assertEqual(2021, record["year"])
        self.assertEqual(37, record["cited_by"])
        self.assertEqual(1204, record["downloads"])
        self.assertIn("基层治理", record["hot_term_hits"])
        self.assertIsNone(taste_exemplars.cnki_record({"title": "短", "url": ""}, terms))


class ShortlistTests(unittest.TestCase):
    def test_cohort_percentiles_are_within_venue_year(self) -> None:
        records = [
            {"record_id": "a", "venue": "X", "year": 2020, "cited_by": 0},
            {"record_id": "b", "venue": "X", "year": 2020, "cited_by": 10},
            {"record_id": "c", "venue": "X", "year": 2020, "cited_by": 10},
            {"record_id": "d", "venue": "X", "year": 2020, "cited_by": 50},
            {"record_id": "e", "venue": "Y", "year": 2020, "cited_by": 1},
        ]
        percentiles = taste_exemplars.cohort_percentiles(records)
        self.assertEqual(percentiles["b"], percentiles["c"])
        self.assertLess(percentiles["a"], percentiles["b"])
        self.assertGreater(percentiles["d"], percentiles["b"])
        self.assertEqual(100.0, percentiles["e"])

    def test_shortlist_applies_window_caps_and_cold_topic_guarantee(self) -> None:
        shortlist = taste_exemplars.build_shortlist(build_harvest(), top=6, bottom=4, per_journal=3, min_cohort=15, now_year=2026)
        positive_ids = [item["record_id"] for item in shortlist["positive"]]
        self.assertNotIn("OPENALEX-RECENT", positive_ids)
        self.assertEqual(1, shortlist["excluded"].get("citation-window-too-short"))
        venues = [item["venue"] for item in shortlist["positive"]]
        self.assertLessEqual(venues.count("World Politics"), 3)
        self.assertTrue(all(item["cohort_percentile"] >= 90 for item in shortlist["positive"]))
        self.assertTrue(any(not item["hot_term_hits"] for item in shortlist["positive"]))
        self.assertTrue(all(item["cohort_percentile"] <= 25 for item in shortlist["negative"]))
        self.assertTrue(any(item["source"] == "cnki" for item in shortlist["positive"]))
        missing = [item for item in shortlist["negative"] if item["abstract_missing"]]
        self.assertTrue(all(item["record_id"] == "CNKI-00" for item in missing))

    def test_small_cohorts_are_excluded(self) -> None:
        harvest = build_harvest()
        harvest["records"] = [item for item in harvest["records"] if item["source"] == "cnki"][:10]
        with self.assertRaises(ValueError):
            taste_exemplars.build_shortlist({"records": []})
        shortlist = taste_exemplars.build_shortlist(harvest, now_year=2026)
        self.assertEqual([], shortlist["positive"])
        self.assertEqual(10, shortlist["excluded"].get("cohort-too-small"))


def anonymous_response(response, shortlist):
    pool = taste_exemplars.anonymous_pool(shortlist)
    aliases = {item["record_id"]: key for key, item in pool.items()}
    seen = set()
    for role in ("positive", "negative", "rejected"):
        for item in response[role]:
            item["record_id"] = aliases[item["record_id"]]
            seen.add(item["record_id"])
    response["uncertain"] = [{"record_id": key, "why": "The abstract alone does not establish the quality of the full argument."} for key in pool if key not in seen]
    return response


class SelectionRoundTripTests(unittest.TestCase):
    def _shortlist_file(self, base: Path) -> Path:
        shortlist = taste_exemplars.build_shortlist(build_harvest(), top=6, bottom=4, per_journal=3, now_year=2026)
        shortlist["negative"] = [item for item in shortlist["negative"] if not item["abstract_missing"]]
        path = base / "shortlist.json"
        path.write_text(json.dumps(shortlist, ensure_ascii=False), encoding="utf-8")
        return path

    def test_emit_and_collect_write_exemplars_with_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            registry_path = base / "cards.json"
            registry_path.write_text(json.dumps(taste_cards.load_registry(), ensure_ascii=False), encoding="utf-8")
            shortlist_path = self._shortlist_file(base)
            capture = base / "capture"
            argv = [
                "--registry",
                str(registry_path),
                "emit-select",
                "comparative-politics",
                "--shortlist",
                str(shortlist_path),
                "--out",
                str(capture),
                "--model-revision",
                MODEL,
                "--pick-positive",
                "3",
                "--pick-negative",
                "2",
            ]
            self.assertEqual(0, taste_exemplars.main(argv))
            prompt = (capture / "taste-exemplars-comparative-politics.prompt.md").read_text(encoding="utf-8")
            self.assertIn("## 匿名混合池", prompt)
            self.assertNotIn("cited_by", prompt)
            self.assertNotIn("World Politics", prompt.split("## 匿名混合池")[1])
            shortlist = json.loads(shortlist_path.read_text(encoding="utf-8"))
            response = {
                "positive": [
                    {"record_id": item["record_id"], "why": "标题即提出机制失效的反常案例，摘要给出范围条件与反面观察，厚味与趣味俱在。"}
                    for item in shortlist["positive"][:3]
                ],
                "negative": [
                    {"record_id": item["record_id"], "why": "摘要只做多案例并列描述，结尾以启示收束，缺厚味。"}
                    for item in shortlist["negative"][:2]
                ],
                "rejected": [{"record_id": shortlist["positive"][3]["record_id"], "reason": "题材热门但摘要没有可证伪预期"}],
            }
            response = anonymous_response(response, shortlist)
            (capture / "taste-exemplars-comparative-politics.response.json").write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")
            (capture / "taste-exemplars-comparative-politics.context.txt").write_text("ctx-exemplars-001", encoding="utf-8")
            collect = [
                "--registry",
                str(registry_path),
                "collect-select",
                "comparative-politics",
                "--shortlist",
                str(shortlist_path),
                "--responses",
                str(capture),
                "--model-revision",
                MODEL,
                "--pick-positive",
                "3",
                "--pick-negative",
                "2",
                "--write",
            ]
            self.assertEqual(0, taste_exemplars.main(collect))
            registry = taste_cards.load_registry(registry_path)
            self.assertEqual([], taste_cards.registry_issues(registry))
            card = taste_cards.card_by_slug(registry, "comparative-politics")
            self.assertEqual("exemplars-registered", taste_cards.card_status(card))
            entry = card["exemplars"]["positive"][0]
            self.assertEqual(taste_exemplars.SELECTED_BY, entry["selected_by"])
            self.assertEqual("ctx-exemplars-001", entry["selection_context_id"])
            self.assertIn("cohort_percentile", entry["signals"])
            self.assertTrue(entry["identifier"])
            # other cards untouched
            before = taste_cards.card_by_slug(taste_cards.load_registry(), "marxism")
            other = taste_cards.card_by_slug(registry, "marxism")
            self.assertEqual(before["exemplars"], other["exemplars"])

    def test_bad_picks_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            shortlist = json.loads(self._shortlist_file(base).read_text(encoding="utf-8"))
            bad = {
                "positive": [{"record_id": next(iter(taste_exemplars.anonymous_pool(shortlist))), "why": "x" * 25}] * 3,
                "negative": [{"record_id": "nope", "why": "y" * 25}] * 2,
                "rejected": [],
            }
            issues = taste_exemplars.selection_issues(bad, shortlist, pick_positive=3, pick_negative=2)
            self.assertTrue(any("every anonymous item" in item for item in issues))
            self.assertTrue(any("picked twice" in item for item in issues))
            self.assertTrue(any("not in the anonymous shortlist" in item for item in issues))

    def test_missing_abstract_blocks_emit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            shortlist = taste_exemplars.build_shortlist(build_harvest(), top=6, bottom=4, per_journal=3, now_year=2026)
            shortlist["negative"][0]["abstract"] = ""
            shortlist["negative"][0]["abstract_missing"] = True
            path = base / "shortlist.json"
            path.write_text(json.dumps(shortlist, ensure_ascii=False), encoding="utf-8")
            code = taste_exemplars.main(
                ["emit-select", "comparative-politics", "--shortlist", str(path), "--out", str(base / "cap"), "--model-revision", MODEL, "--pick-positive", "3", "--pick-negative", "2"]
            )
            self.assertEqual(1, code)


class PlanTests(unittest.TestCase):
    def test_plan_lists_both_journal_routes(self) -> None:
        registry = taste_cards.load_registry()
        card = taste_cards.card_by_slug(registry, "marxism")
        plan = taste_exemplars.render_plan(registry, card, (2019, 2025))
        self.assertIn("OpenAlex", plan)
        self.assertIn("马克思主义研究", plan)
        self.assertIn("$Python -X utf8", plan)
        self.assertEqual(0, taste_exemplars.main(["plan", "marxism"]))


class RefreshTests(unittest.TestCase):
    def test_status_reports_age_and_action(self) -> None:
        from datetime import datetime, timezone

        registry = taste_cards.load_registry()
        cards = taste_cards.cards(registry)
        fresh = taste_exemplars.render_status(cards, now=datetime(2026, 9, 10, tzinfo=timezone.utc))
        self.assertIn("| fresh |", fresh)
        stale = taste_exemplars.render_status(cards, now=datetime(2028, 1, 1, tzinfo=timezone.utc))
        self.assertIn("STALE", stale)
        self.assertIn("refresh:", stale)
        self.assertEqual(0, taste_exemplars.main(["status", "marxism"]))
        self.assertEqual(1, taste_exemplars.main(["status", "nope"]))

    def test_locked_exemplars_survive_collect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            registry = taste_cards.load_registry()
            card = taste_cards.card_by_slug(registry, "comparative-politics")
            card["exemplars"]["positive"][0]["locked"] = True
            keep_id = card["exemplars"]["positive"][0]["identifier"]
            registry_path = base / "cards.json"
            registry_path.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")
            shortlist = taste_exemplars.build_shortlist(build_harvest(), top=6, bottom=4, per_journal=3, now_year=2026)
            shortlist["negative"] = [item for item in shortlist["negative"] if not item["abstract_missing"]]
            shortlist_path = base / "shortlist.json"
            shortlist_path.write_text(json.dumps(shortlist, ensure_ascii=False), encoding="utf-8")
            capture = base / "capture"
            common = ["--registry", str(registry_path)]
            self.assertEqual(0, taste_exemplars.main(common + ["emit-select", "comparative-politics", "--shortlist", str(shortlist_path), "--out", str(capture), "--model-revision", MODEL, "--pick-positive", "3", "--pick-negative", "2"]))
            response = {
                "positive": [{"record_id": item["record_id"], "why": "标题即提出机制失效的反常案例，摘要给出范围条件与反面观察。"} for item in shortlist["positive"][:3]],
                "negative": [{"record_id": item["record_id"], "why": "摘要只做多案例并列描述，结尾以启示收束，缺厚味。"} for item in shortlist["negative"][:2]],
                "rejected": [],
            }
            response = anonymous_response(response, shortlist)
            (capture / "taste-exemplars-comparative-politics.response.json").write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")
            (capture / "taste-exemplars-comparative-politics.context.txt").write_text("ctx-locked-001", encoding="utf-8")
            self.assertEqual(0, taste_exemplars.main(common + ["collect-select", "comparative-politics", "--shortlist", str(shortlist_path), "--responses", str(capture), "--model-revision", MODEL, "--pick-positive", "3", "--pick-negative", "2", "--write"]))
            updated = taste_cards.card_by_slug(taste_cards.load_registry(registry_path), "comparative-politics")
            positives = updated["exemplars"]["positive"]
            self.assertEqual(4, len(positives))
            self.assertEqual(keep_id, positives[0]["identifier"])
            self.assertTrue(positives[0]["locked"])
            self.assertEqual(2, len(updated["exemplars"]["negative"]))


if __name__ == "__main__":
    unittest.main()
