"""Offline tests for the GB/T 7714-2015 renderer in skills/intl-export/scripts/doi_export.py.

Run from the repository root:
    python -B -X utf8 -m unittest tools.test_doi_export_gbt -v
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "intl-export" / "scripts" / "doi_export.py"
ACCESSED = "2026-09-02"


def load_doi_export():
    spec = importlib.util.spec_from_file_location("doi_export_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def person(family: str, given: str) -> dict:
    return {"family": family, "given": given}


def message(**fields) -> dict:
    """Minimal Crossref-style payload: {"message": {...}}."""
    return {"message": fields}


class GbtRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load_doi_export()

    def render(self, payload: dict) -> str:
        return self.mod.gbt7714(payload, accessed=ACCESSED)

    def test_type_mark_table(self) -> None:
        marks = self.mod.TYPE_MARK
        self.assertEqual("J", marks["journal-article"])
        for key in ("book", "monograph", "edited-book", "reference-book",
                    "book-chapter", "book-section", "book-part"):
            self.assertEqual("M", marks[key], key)
        self.assertEqual("C", marks["proceedings-article"])
        self.assertEqual("D", marks["dissertation"])
        self.assertEqual("R", marks["report"])
        self.assertEqual("EB/OL", marks["posted-content"])
        self.assertEqual("DS/OL", marks["dataset"])

    def test_journal_article(self) -> None:
        payload = message(
            type="journal-article",
            author=[person("Xie", "Fusheng"), person("Jiang", "Nan"), person("Kuang", "Xiaolu")],
            title=["Towards an accurate understanding of 'new quality productive forces'"],
            **{"container-title": ["Economic and Political Studies"],
               "published-print": {"date-parts": [[2025, 1]]},
               "published-online": {"date-parts": [[2024, 8, 12]]}},
            volume="13", issue="1", page="1-15", DOI="10.1080/20954816.2024.2386503",
        )
        self.assertEqual(
            "XIE F, JIANG N, KUANG X. Towards an accurate understanding of 'new quality "
            "productive forces'[J]. Economic and Political Studies, 2025, 13(1): 1-15. "
            "DOI: 10.1080/20954816.2024.2386503.",
            self.render(payload),
        )

    def test_journal_article_without_volume_uses_year_issue(self) -> None:
        payload = message(
            type="journal-article",
            author=[person("Wang", "Shaoguang")],
            title=["State capacity revisited"],
            **{"container-title": ["Public Administration Review"],
               "issued": {"date-parts": [[2020]]}},
            issue="3", page="1-10", DOI="10.1000/j1",
        )
        self.assertEqual(
            "WANG S. State capacity revisited[J]. Public Administration Review, 2020(3): 1-10. "
            "DOI: 10.1000/j1.",
            self.render(payload),
        )

    def test_book_with_edition_and_place(self) -> None:
        payload = message(
            type="book",
            author=[person("Gill", "Richard")],
            title=["Mastering English literature"],
            **{"edition-number": "2", "publisher-location": "London",
               "published-print": {"date-parts": [[1985]]}},
            publisher="Macmillan", DOI="10.1000/book1",
        )
        self.assertEqual(
            "GILL R. Mastering English literature[M]. 2nd ed. London: Macmillan, 1985. "
            "DOI: 10.1000/book1.",
            self.render(payload),
        )

    def test_book_without_place_or_first_edition(self) -> None:
        payload = message(
            type="monograph",
            author=[person("Gill", "Richard")],
            title=["Mastering English literature"],
            **{"edition-number": "1", "issued": {"date-parts": [[1985]]}},
            publisher="Macmillan", DOI="10.1000/book2",
        )
        self.assertEqual(
            "GILL R. Mastering English literature[M]. Macmillan, 1985. DOI: 10.1000/book2.",
            self.render(payload),
        )

    def test_book_missing_imprint_leaves_no_dangling_punctuation(self) -> None:
        payload = message(type="book", author=[person("Doe", "Jane")], title=["Untraced book"],
                          DOI="10.1000/book3")
        self.assertEqual("DOE J. Untraced book[M]. DOI: 10.1000/book3.", self.render(payload))

    def test_book_chapter_with_editors(self) -> None:
        payload = message(
            type="book-chapter",
            author=[person("Weinstein", "Louis"), person("Swertz", "Mark N.")],
            title=["Pathogenic properties of invading microorganisms"],
            editor=[person("Sodeman", "William A."), person("Sodeman", "William A.")],
            **{"container-title": ["Pathologic physiology: mechanisms of disease"],
               "publisher-location": "Philadelphia",
               "published-print": {"date-parts": [[1974]]}},
            publisher="Saunders", page="745-772", DOI="10.1000/chap1",
        )
        self.assertEqual(
            "WEINSTEIN L, SWERTZ M N. Pathogenic properties of invading microorganisms[M]//"
            "SODEMAN W A, SODEMAN W A, eds. Pathologic physiology: mechanisms of disease. "
            "Philadelphia: Saunders, 1974: 745-772. DOI: 10.1000/chap1.",
            self.render(payload),
        )

    def test_book_chapter_single_editor_uses_ed(self) -> None:
        payload = message(
            type="book-section",
            author=[person("Martin", "George")],
            title=["Control of electronic resources in Australia"],
            editor=[person("Pattie", "Ling-yuh W.")],
            **{"container-title": ["Electronic resources"],
               "publisher-location": "New York", "issued": {"date-parts": [[1996]]}},
            publisher="The Haworth Press", page="85-96",
        )
        self.assertEqual(
            "MARTIN G. Control of electronic resources in Australia[M]//PATTIE L W, ed. "
            "Electronic resources. New York: The Haworth Press, 1996: 85-96.",
            self.render(payload),
        )

    def test_proceedings_article(self) -> None:
        payload = message(
            type="proceedings-article",
            author=[person("Kelly", "Mary")],
            title=["Beyond the nuclear tenure system"],
            **{"container-title": ["Proceedings of the 12th International Conference on Public Policy"],
               "publisher-location": "New York",
               "published-print": {"date-parts": [[2019]]}},
            publisher="ACM", page="101-108", DOI="10.1000/proc1",
        )
        self.assertEqual(
            "KELLY M. Beyond the nuclear tenure system[C]//Proceedings of the 12th International "
            "Conference on Public Policy. New York: ACM, 2019: 101-108. DOI: 10.1000/proc1.",
            self.render(payload),
        )

    def test_proceedings_article_falls_back_to_event_name(self) -> None:
        payload = message(
            type="proceedings-article",
            author=[person("Kelly", "Mary")],
            title=["Beyond the nuclear tenure system"],
            event={"name": "Annual Meeting of the Policy Studies Organization", "location": "Toronto"},
            issued={"date-parts": [[2018]]}, page="1-9",
        )
        self.assertEqual(
            "KELLY M. Beyond the nuclear tenure system[C]//Annual Meeting of the Policy Studies "
            "Organization. Toronto, 2018: 1-9.",
            self.render(payload),
        )

    def test_dissertation(self) -> None:
        payload = message(
            type="dissertation",
            author=[person("Calms", "Robert B.")],
            title=["Infrared spectroscopic studies on solid oxygen"],
            institution=[{"name": "University of California", "place": ["Berkeley"]}],
            issued={"date-parts": [[1965]]}, DOI="10.1000/diss1",
        )
        self.assertEqual(
            "CALMS R B. Infrared spectroscopic studies on solid oxygen[D]. Berkeley: "
            "University of California, 1965. DOI: 10.1000/diss1.",
            self.render(payload),
        )

    def test_posted_content_uses_posted_date_and_citation_date(self) -> None:
        payload = message(
            type="posted-content", subtype="preprint",
            author=[person("Doe", "John"), person("Roe", "Rachel")],
            title=["A preprint on bureaucratic discretion"],
            posted={"date-parts": [[2023, 5, 2]]},
            DOI="10.31235/osf.io/abcde",
        )
        self.assertEqual(
            "DOE J, ROE R. A preprint on bureaucratic discretion[EB/OL]. (2023-05-02)[2026-09-02]. "
            "https://doi.org/10.31235/osf.io/abcde.",
            self.render(payload),
        )

    def test_posted_content_without_date_only_has_citation_date(self) -> None:
        payload = message(type="posted-content", author=[person("Doe", "John")],
                          title=["Undated working paper"], DOI="10.2139/ssrn.1")
        self.assertEqual(
            "DOE J. Undated working paper[EB/OL]. [2026-09-02]. https://doi.org/10.2139/ssrn.1.",
            self.render(payload),
        )

    def test_dataset(self) -> None:
        payload = message(
            type="dataset",
            author=[person("Smith", "Anna")],
            title=["Local government survey 2021"],
            publisher="Zenodo", issued={"date-parts": [[2021, 6, 30]]},
            DOI="10.5281/zenodo.123456",
        )
        self.assertEqual(
            "SMITH A. Local government survey 2021[DS/OL]. Zenodo, 2021[2026-09-02]. "
            "https://doi.org/10.5281/zenodo.123456.",
            self.render(payload),
        )

    def test_institutional_author_is_kept_verbatim(self) -> None:
        payload = message(
            type="report",
            author=[{"name": "World Bank"}],
            title=["World development report 2024"],
            **{"publisher-location": "Washington, DC", "issued": {"date-parts": [[2024]]}},
            publisher="World Bank", DOI="10.1596/978-1-4648-2000-5",
        )
        self.assertEqual(
            "World Bank. World development report 2024[R]. Washington, DC: World Bank, 2024. "
            "DOI: 10.1596/978-1-4648-2000-5.",
            self.render(payload),
        )

    def test_report_without_author_uses_institution(self) -> None:
        payload = message(
            type="report",
            title=["Global trends 2040"],
            institution=[{"name": "National Intelligence Council", "place": ["Washington, DC"]}],
            issued={"date-parts": [[2021]]},
        )
        self.assertEqual(
            "National Intelligence Council. Global trends 2040[R]. Washington, DC, 2021.",
            self.render(payload),
        )

    def test_subtitle_is_joined_with_colon(self) -> None:
        payload = message(
            type="book",
            author=[person("Scott", "James C.")],
            title=["Seeing like a state"],
            subtitle=["How certain schemes to improve the human condition have failed"],
            **{"publisher-location": "New Haven", "issued": {"date-parts": [[1998]]}},
            publisher="Yale University Press",
        )
        self.assertEqual(
            "SCOTT J C. Seeing like a state: How certain schemes to improve the human condition "
            "have failed[M]. New Haven: Yale University Press, 1998.",
            self.render(payload),
        )

    def test_subtitle_already_in_title_is_not_duplicated(self) -> None:
        payload = message(
            type="book",
            author=[person("Scott", "James C.")],
            title=["Seeing like a state: how certain schemes to improve the human condition have failed"],
            subtitle=["How certain schemes to improve the human condition have failed"],
            publisher="Yale University Press", issued={"date-parts": [[1998]]},
        )
        self.assertEqual(
            "SCOTT J C. Seeing like a state: how certain schemes to improve the human condition "
            "have failed[M]. Yale University Press, 1998.",
            self.render(payload),
        )

    def test_more_than_three_authors_get_et_al(self) -> None:
        payload = message(
            type="journal-article",
            author=[person("Rood", "S. R."), person("Wolfe", "R. E."),
                    person("Sherman", "F. S."), person("Baker", "T. L.")],
            title=["Four-author article"],
            **{"container-title": ["Journal of Politics"], "issued": {"date-parts": [[2022]]}},
            volume="84", issue="2", page="500-515",
        )
        self.assertEqual(
            "ROOD S R, WOLFE R E, SHERMAN F S, et al. Four-author article[J]. Journal of Politics, "
            "2022, 84(2): 500-515.",
            self.render(payload),
        )

    def test_translator_follows_type_mark(self) -> None:
        payload = message(
            type="book",
            author=[person("Bourdieu", "Pierre")],
            translator=[person("Nice", "Richard")],
            title=["Distinction"],
            **{"publisher-location": "Cambridge, MA", "issued": {"date-parts": [[1984]]}},
            publisher="Harvard University Press",
        )
        self.assertEqual(
            "BOURDIEU P. Distinction[M]. NICE R, trans. Cambridge, MA: Harvard University Press, 1984.",
            self.render(payload),
        )

    def test_edited_book_without_authors_uses_editors(self) -> None:
        payload = message(
            type="edited-book",
            editor=[person("Evans", "Peter B."), person("Rueschemeyer", "Dietrich"),
                    person("Skocpol", "Theda")],
            title=["Bringing the state back in"],
            **{"publisher-location": "Cambridge", "issued": {"date-parts": [[1985]]}},
            publisher="Cambridge University Press",
        )
        self.assertEqual(
            "EVANS P B, RUESCHEMEYER D, SKOCPOL T, eds. Bringing the state back in[M]. "
            "Cambridge: Cambridge University Press, 1985.",
            self.render(payload),
        )

    def test_default_citation_date_is_today(self) -> None:
        import datetime

        payload = message(type="posted-content", author=[person("Doe", "John")],
                          title=["Today"], DOI="10.1/x")
        self.assertIn(f"[{datetime.date.today().isoformat()}]", self.mod.gbt7714(payload))


if __name__ == "__main__":
    unittest.main()
