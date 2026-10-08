"""Tests for the branch taste-card registry and its resolution rules."""

from __future__ import annotations

import copy
import unittest

import taste_cards


class RegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = taste_cards.load_registry()

    def test_shipped_registry_is_valid_and_projected_in_anatomy(self) -> None:
        self.assertEqual([], taste_cards.registry_issues(self.registry))
        anatomy = taste_cards.DEFAULT_ANATOMY.read_text(encoding="utf-8-sig")
        self.assertEqual([], taste_cards.anatomy_issues(self.registry, anatomy))

    def test_shipped_cards_cover_the_political_science_branches(self) -> None:
        slugs = {card["slug"] for card in taste_cards.cards(self.registry)}
        for expected in (
            "political-theory",
            "comparative-politics",
            "international-politics",
            "chinese-politics",
            "public-administration-policy",
            "marxism",
            "historical-political-science",
        ):
            self.assertIn(expected, slugs)
        for card in taste_cards.cards(self.registry):
            self.assertEqual("exemplars-registered", taste_cards.card_status(card))
            for role in ("positive", "negative"):
                for entry in card["exemplars"][role]:
                    self.assertEqual("cohort-signal+isolated-reading", entry["selected_by"])
                    self.assertTrue(entry["identifier"])
                    self.assertIn("cohort_percentile", entry["signals"])

    def test_alias_collision_and_missing_flavor_are_reported(self) -> None:
        broken = copy.deepcopy(self.registry)
        broken["cards"][1]["aliases"].append(broken["cards"][0]["aliases"][0])
        del broken["cards"][2]["flavors"]["thick"]
        broken["cards"][3]["adjacent_branches"] = [broken["cards"][3]["slug"]]
        issues = taste_cards.registry_issues(broken)
        self.assertTrue(any("collides with card" in item for item in issues))
        self.assertTrue(any("flavors.thick" in item for item in issues))
        self.assertTrue(any("cannot include itself" in item for item in issues))

    def test_exemplars_need_identity_and_reason(self) -> None:
        broken = copy.deepcopy(self.registry)
        broken["cards"][0]["exemplars"]["positive"].append({"title": "某篇论文"})
        issues = taste_cards.registry_issues(broken)
        self.assertTrue(any("why must say" in item for item in issues))
        self.assertTrue(any("needs an identifier or venue plus year" in item for item in issues))
        good = copy.deepcopy(self.registry)
        card = good["cards"][0]
        card["exemplars"]["positive"] = [
            {"title": f"正例论文{i}", "venue": "政治学研究", "year": 2020 + i, "why": "概念区分改变了既有规范判断"}
            for i in range(3)
        ]
        card["exemplars"]["negative"] = [
            {"title": f"负例论文{i}", "identifier": f"10.0000/neg{i}", "why": "三段式当代价值，引语堆砌"}
            for i in range(2)
        ]
        self.assertEqual([], taste_cards.registry_issues(good))
        self.assertEqual("exemplars-registered", taste_cards.card_status(card))


class ResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = taste_cards.load_registry()

    def test_longest_alias_wins(self) -> None:
        resolution = taste_cards.resolve_card(self.registry, "比较政治学中的国家能力问题")
        self.assertTrue(resolution.resolved)
        self.assertEqual("comparative-politics", resolution.slug)
        self.assertEqual("比较政治学", resolution.matched_alias)

    def test_broad_or_unknown_field_keeps_taste_off(self) -> None:
        self.assertEqual("no_card", taste_cards.resolve_card(self.registry, "政治学").status)
        self.assertEqual("no_card", taste_cards.resolve_card(self.registry, "").status)

    def test_equal_length_matches_are_ambiguous_until_pinned(self) -> None:
        ambiguous = taste_cards.resolve_card(self.registry, "公共管理与国际关系的交叉")
        self.assertEqual("ambiguous", ambiguous.status)
        self.assertEqual(("international-politics", "public-administration-policy"), ambiguous.matches)
        pinned = taste_cards.resolve_card(self.registry, "公共管理与国际关系的交叉", explicit="international-politics")
        self.assertEqual("explicit", pinned.status)
        self.assertEqual("international-politics", pinned.slug)
        self.assertEqual("unknown_explicit", taste_cards.resolve_card(self.registry, "x", explicit="nope").status)

    def test_config_resolution_prefers_explicit_taste_card(self) -> None:
        payload = {
            "direction_contract": {"field": "比较政治"},
            "topic_selection": {"taste_card": "historical-political-science"},
        }
        self.assertEqual("historical-political-science", taste_cards.resolve_from_config(self.registry, payload).slug)
        del payload["topic_selection"]["taste_card"]
        self.assertEqual("comparative-politics", taste_cards.resolve_from_config(self.registry, payload).slug)

    def test_hot_terms_merge_branch_and_generic_longest_first(self) -> None:
        card = taste_cards.card_by_slug(self.registry, "international-politics")
        assert card is not None
        terms = taste_cards.hot_terms_for(self.registry, card)
        self.assertIn("一带一路", terms)
        self.assertIn("中国式现代化", terms)
        self.assertEqual(terms, sorted(terms, key=lambda item: (-len(item), item)))


class CliTests(unittest.TestCase):
    def test_validate_and_resolve_exit_codes(self) -> None:
        self.assertEqual(0, taste_cards.main(["validate"]))
        self.assertEqual(0, taste_cards.main(["resolve", "--field", "马克思主义政治经济学"]))
        self.assertEqual(2, taste_cards.main(["resolve", "--field", "政治学"]))
        self.assertEqual(2, taste_cards.main(["show", "unknown-card"]))
        self.assertEqual(0, taste_cards.main(["show", "marxism"]))


class FreshnessTests(unittest.TestCase):
    def test_age_and_stale_warning(self) -> None:
        from datetime import datetime, timezone

        registry = taste_cards.load_registry()
        card = taste_cards.card_by_slug(registry, "comparative-politics")
        now = datetime(2027, 12, 1, tzinfo=timezone.utc)
        age = taste_cards.exemplar_age_days(card, now=now)
        self.assertIsNotNone(age)
        self.assertGreater(age, taste_cards.EXEMPLAR_MAX_AGE_DAYS)
        warnings = taste_cards.stale_exemplar_warnings(registry, now=now)
        self.assertTrue(any(item.startswith("comparative-politics:") for item in warnings))
        fresh_now = datetime(2026, 9, 10, tzinfo=timezone.utc)
        self.assertEqual([], taste_cards.stale_exemplar_warnings(registry, now=fresh_now))
        bare = {"slug": "x", "exemplars": {"positive": [], "negative": []}}
        self.assertIsNone(taste_cards.exemplar_age_days(bare, now=now))


if __name__ == "__main__":
    unittest.main()
