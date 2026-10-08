#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""docx_normalize 单测。

置顶三项是 Word 输出链路的关键不变量：
  CRIT-1  弯引号必须按语境拆 run 并路由到 eastAsia/default
  CRIT-2  含 w:drawing 的段绝不能 clear_runs（否则丢图）
  CRIT-3  脚注 id 顺序必须 == 引用顺序

运行：python test_docx_normalize.py     （仅需 lxml）
"""
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lxml import etree  # noqa: E402
import docx_normalize as dn  # noqa: E402

W, A = dn.NS["w"], dn.NS["a"]
DECL = (
    'xmlns:w="%s" xmlns:a="%s" xmlns:r="%s" xmlns:wp="%s" xmlns:pic="%s"'
    % (dn.NS["w"], dn.NS["a"], dn.NS["r"], dn.NS["wp"], dn.NS["pic"])
)


def doc(body_xml: str):
    return etree.fromstring(
        "<w:document %s><w:body>%s</w:body></w:document>" % (DECL, body_xml)
    )


def frag(xml: str):
    return etree.fromstring("<root %s>%s</root>" % (DECL, xml))[0]


def hint_of(run):
    rf = run.find(dn.qn("w:rPr") + "/" + dn.qn("w:rFonts"))
    return None if rf is None else rf.get(dn.qn("w:hint"))


# ===========================================================================
# CRIT-1：引号语境路由与安全拆 run
# ===========================================================================
class TestQuoteFontRouting(unittest.TestCase):
    @staticmethod
    def runs(root):
        return list(root.iter(dn.qn("w:r")))

    @staticmethod
    def texts(root):
        return [dn._run_text(run) for run in TestQuoteFontRouting.runs(root)]

    def test_chinese_quote_pair_uses_eastasia_and_splits(self):
        d = doc('<w:p><w:r><w:t>他说：“制度有效。”</w:t></w:r></w:p>')
        report = dn.normalize_quote_fonts(d)
        runs = self.runs(d)
        self.assertEqual(self.texts(d), ["他说：", "“", "制度有效。", "”"])
        self.assertEqual([hint_of(run) for run in runs if dn._run_text(run) in "“”"],
                         ["eastAsia", "eastAsia"])
        self.assertEqual(report["runs_split"], 1)

    def test_english_quote_pair_uses_default(self):
        d = doc('<w:p><w:r><w:t>Smith wrote “institutional trust”.</w:t></w:r></w:p>')
        dn.normalize_quote_fonts(d)
        quote_runs = [run for run in self.runs(d) if dn._run_text(run) in "“”"]
        self.assertEqual([hint_of(run) for run in quote_runs], ["default", "default"])

    def test_pure_quote_runs_use_surrounding_chinese_context(self):
        d = doc('<w:p><w:r><w:t>他说：</w:t></w:r><w:r><w:t>“</w:t></w:r>'
                '<w:r><w:t>制度有效。</w:t></w:r><w:r><w:t>”</w:t></w:r></w:p>')
        dn.normalize_quote_fonts(d)
        quote_runs = [run for run in self.runs(d) if dn._run_text(run) in "“”"]
        self.assertEqual([hint_of(run) for run in quote_runs], ["eastAsia", "eastAsia"])

    def test_explicit_english_language_overrides_chinese_content(self):
        d = doc('<w:p><w:r><w:rPr><w:lang w:val="en-US"/></w:rPr><w:t>“</w:t></w:r>'
                '<w:r><w:rPr><w:lang w:val="en-US"/></w:rPr><w:t>公共价值</w:t></w:r>'
                '<w:r><w:rPr><w:lang w:val="en-US"/></w:rPr><w:t>”</w:t></w:r></w:p>')
        dn.normalize_quote_fonts(d)
        quote_runs = [run for run in self.runs(d) if dn._run_text(run) in "“”"]
        self.assertEqual([hint_of(run) for run in quote_runs], ["default", "default"])

    def test_english_apostrophe_is_default_and_split(self):
        d = doc('<w:p><w:r><w:t>O’Connor researchers’</w:t></w:r></w:p>')
        report = dn.normalize_quote_fonts(d)
        apostrophes = [run for run in self.runs(d) if dn._run_text(run) == "’"]
        self.assertEqual([hint_of(run) for run in apostrophes], ["default", "default"])
        self.assertEqual(report["apostrophes_routed"], 2)

    def test_apostrophe_inside_single_quoted_english_does_not_close_pair(self):
        d = doc('<w:p><w:r><w:t>Smith wrote ‘O’Connor’s account’.</w:t></w:r></w:p>')
        dn.normalize_quote_fonts(d)
        targeted = [run for run in self.runs(d) if dn._run_text(run) in {"‘", "’"}]
        self.assertEqual([hint_of(run) for run in targeted], ["default", "default", "default", "default"])

    def test_hyperlink_container_is_preserved(self):
        d = doc('<w:p><w:hyperlink r:id="rId1"><w:r><w:t>“public value”</w:t></w:r>'
                '</w:hyperlink></w:p>')
        dn.normalize_quote_fonts(d)
        hyperlink = d.find(".//" + dn.qn("w:hyperlink"))
        self.assertIsNotNone(hyperlink)
        self.assertEqual("".join(t.text or "" for t in hyperlink.iter(dn.qn("w:t"))), "“public value”")

    def test_non_text_run_is_skipped_without_losing_drawing(self):
        d = doc('<w:p><w:r><w:t>“制度”</w:t><w:drawing/></w:r></w:p>')
        report = dn.normalize_quote_fonts(d)
        self.assertEqual(report["unsafe_runs_skipped"], 2)
        self.assertIsNotNone(d.find(".//" + dn.qn("w:drawing")))
        self.assertEqual(self.texts(d), ["“制度”"])

    def test_second_pass_is_idempotent(self):
        d = doc('<w:p><w:r><w:t>他说：“制度有效。” Smith wrote “trust”.</w:t></w:r></w:p>')
        dn.normalize_quote_fonts(d)
        before = etree.tostring(d)
        report = dn.normalize_quote_fonts(d)
        self.assertEqual(etree.tostring(d), before)
        self.assertEqual(report["quotes_routed"], 0)
        self.assertEqual(report["apostrophes_routed"], 0)
        self.assertEqual(report["runs_split"], 0)

    def test_ambiguous_unpaired_quote_is_unchanged(self):
        d = doc('<w:p><w:r><w:rPr><w:rFonts w:hint="default"/></w:rPr><w:t>“</w:t></w:r></w:p>')
        report = dn.normalize_quote_fonts(d)
        self.assertEqual(report["ambiguous_skipped"], 1)
        self.assertEqual(hint_of(self.runs(d)[0]), "default")

    def test_all_reader_visible_word_parts_are_routed(self):
        parts = {
            "word/document.xml": ("document", "body"),
            "word/footnotes.xml": ("footnotes", "footnote"),
            "word/endnotes.xml": ("endnotes", "endnote"),
            "word/comments.xml": ("comments", "comment"),
            "word/header1.xml": ("hdr", None),
            "word/footer1.xml": ("ftr", None),
        }
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "parts.docx"
            with zipfile.ZipFile(path, "w") as archive:
                for name, (root_name, container) in parts.items():
                    inner = '<w:p><w:r><w:t>他说：“制度有效。”</w:t></w:r></w:p>'
                    if container:
                        inner = f'<w:{container}>{inner}</w:{container}>'
                    archive.writestr(
                        name,
                        f'<w:{root_name} xmlns:w="{W}">{inner}</w:{root_name}>',
                    )
            package = dn.Docx(path)
            dn.normalize(package, {"quote_fonts"})
            self.assertEqual(set(package.text_part_names()), set(parts))
            for name in parts:
                quote_runs = [
                    run for run in package.tree(name).iter(dn.qn("w:r"))
                    if dn._run_text(run) in "“”"
                ]
                self.assertEqual([hint_of(run) for run in quote_runs], ["eastAsia", "eastAsia"], name)


# ===========================================================================
# CRIT-2：含 w:drawing 的段不能 clear_runs
# ===========================================================================
class TestClearRunsGuard(unittest.TestCase):
    def test_clear_runs_refuses_on_drawing(self):
        p = frag('<w:p><w:r><w:drawing/></w:r></w:p>')
        ok = dn.clear_runs(p)
        self.assertFalse(ok, "含 w:drawing 的段应拒绝 clear_runs")
        self.assertIsNotNone(p.find(".//" + dn.qn("w:drawing")), "图被误删了！")

    def test_clear_runs_works_without_drawing(self):
        p = frag('<w:p><w:r><w:t>abc</w:t></w:r><w:r><w:t>def</w:t></w:r></w:p>')
        ok = dn.clear_runs(p)
        self.assertTrue(ok)
        self.assertEqual(len(p.findall(dn.qn("w:r"))), 0)

    def test_set_para_text_skips_drawing(self):
        p = frag('<w:p><w:r><w:drawing/></w:r></w:p>')
        self.assertFalse(dn._set_para_text(p, "x"))
        self.assertIsNotNone(p.find(".//" + dn.qn("w:drawing")))

    def test_superscript_skips_drawing_paragraph(self):
        d = doc('<w:p><w:r><w:t>[1]</w:t></w:r><w:r><w:drawing/></w:r></w:p>')
        dn.superscript_citations(d)
        self.assertIsNotNone(d.find(".//" + dn.qn("w:drawing")))


# ===========================================================================
# CRIT-3：脚注 id 顺序 == 引用顺序
# ===========================================================================
FOOTNOTES_XML = (
    '<w:footnotes %s>'
    '<w:footnote w:type="separator" w:id="-1"><w:p/></w:footnote>'
    '<w:footnote w:type="continuationSeparator" w:id="0"><w:p/></w:footnote>'
    '<w:footnote w:id="1"><w:p><w:r><w:t>A</w:t></w:r></w:p></w:footnote>'
    '<w:footnote w:id="2"><w:p><w:r><w:t>B</w:t></w:r></w:p></w:footnote>'
    '<w:footnote w:id="3"><w:p><w:r><w:t>C</w:t></w:r></w:p></w:footnote>'
    '</w:footnotes>'
) % DECL


class TestFootnoteOrder(unittest.TestCase):
    def _build(self, ref_order):
        body = "".join(
            '<w:p><w:r><w:footnoteReference w:id="%d"/></w:r></w:p>' % i
            for i in ref_order
        )
        return doc(body), etree.fromstring(FOOTNOTES_XML)

    def test_reorder_matches_reference_order(self):
        """文档里引用顺序为 3,1,2 → 重排后引用变 1,2,3 且定义 id 升序与之一致。"""
        d, fns = self._build([3, 1, 2])
        dn.reorder_footnotes(d, fns)

        ref_ids = [el.get(dn.qn("w:id"))
                   for el in d.iter(dn.qn("w:footnoteReference"))]
        self.assertEqual(ref_ids, ["1", "2", "3"], "引用未按出现顺序重编号")

        content_defs = [fn for fn in fns.findall(dn.qn("w:footnote"))
                        if fn.get(dn.qn("w:type")) is None]
        def_ids = [fn.get(dn.qn("w:id")) for fn in content_defs]
        self.assertEqual(def_ids, ["1", "2", "3"], "定义未按新 id 升序排列")

        # 内容随之搬正确：最先被引用的（原 C）现在是 id 1
        first = content_defs[0]
        self.assertEqual(first.find(".//" + dn.qn("w:t")).text, "C",
                         "脚注内容与新 id 错配 —— 这正是 id 顺序≠引用顺序的后果")

    def test_separators_preserved(self):
        d, fns = self._build([2, 1, 3])
        dn.reorder_footnotes(d, fns)
        sep_ids = sorted(
            fn.get(dn.qn("w:id")) for fn in fns.findall(dn.qn("w:footnote"))
            if fn.get(dn.qn("w:type")) is not None
        )
        self.assertEqual(sep_ids, ["-1", "0"], "分隔符脚注 id 被误改")

    def test_validate_passes_after_reorder(self):
        d, fns = self._build([3, 1, 2])
        dn.reorder_footnotes(d, fns)
        issues = [i for i in dn.validate(d, fns, None) if "脚注" in i]
        self.assertEqual(issues, [])


# ===========================================================================
# 结构顺序：schema 不变量
# ===========================================================================
class TestOrdering(unittest.TestCase):
    def test_ind_before_jc(self):
        ppr = frag('<w:pPr><w:jc w:val="center"/><w:ind w:firstLine="480"/></w:pPr>')
        dn.reorder_children(ppr, dn.PPR_ORDER)
        names = [dn.local(c) for c in ppr]
        self.assertLess(names.index("ind"), names.index("jc"),
                        "w:ind 必须排在 w:jc 之前")

    def test_border_order(self):
        b = frag('<w:tcBorders>'
                 '<w:right w:val="single"/><w:bottom w:val="single"/>'
                 '<w:left w:val="single"/><w:top w:val="single"/>'
                 '</w:tcBorders>')
        dn.reorder_children(b, dn.BORDER_ORDER)
        self.assertEqual([dn.local(c) for c in b],
                         ["top", "left", "bottom", "right"])

    def test_rpr_rfonts_before_sz(self):
        rpr = frag('<w:rPr><w:sz w:val="24"/><w:rFonts w:ascii="Times"/></w:rPr>')
        dn.reorder_children(rpr, dn.RPR_ORDER)
        names = [dn.local(c) for c in rpr]
        self.assertLess(names.index("rFonts"), names.index("sz"))


# ===========================================================================
# 字体：补 eastAsia（只补不覆盖）
# ===========================================================================
class TestFonts(unittest.TestCase):
    def test_adds_eastasia_when_missing(self):
        d = doc('<w:p><w:r><w:rPr><w:rFonts w:ascii="Times New Roman" '
                'w:hAnsi="Times New Roman"/></w:rPr><w:t>x</w:t></w:r></w:p>')
        dn.ensure_eastasia_fonts(d, None)
        rf = d.find(".//" + dn.qn("w:rFonts"))
        self.assertEqual(rf.get(dn.qn("w:eastAsia")), "SimSun")

    def test_does_not_override_existing_eastasia(self):
        d = doc('<w:p><w:r><w:rPr><w:rFonts w:ascii="Times" '
                'w:eastAsia="KaiTi"/></w:rPr><w:t>x</w:t></w:r></w:p>')
        dn.ensure_eastasia_fonts(d, None)
        rf = d.find(".//" + dn.qn("w:rFonts"))
        self.assertEqual(rf.get(dn.qn("w:eastAsia")), "KaiTi")


# ===========================================================================
# 引号转换
# ===========================================================================
class TestQuotes(unittest.TestCase):
    def test_straight_to_curly(self):
        d = doc('<w:p><w:r><w:t>他说："x" 和 \'y\'</w:t></w:r></w:p>')
        dn.smart_quotes(d)
        self.assertEqual(d.find(".//" + dn.qn("w:t")).text,
                         "他说：“x” 和 ‘y’")

    def test_apostrophes_are_english_and_primes_are_preserved(self):
        d = doc('<w:p><w:r><w:t>don\'t O\'Connor \'90s x\' 5\'10&quot;</w:t></w:r></w:p>')
        dn.smart_quotes(d)
        self.assertEqual(d.find(".//" + dn.qn("w:t")).text,
                         "don’t O’Connor ’90s x' 5'10\"")

    def test_character_conversion_and_font_routing_are_separate(self):
        d = doc('<w:p><w:r><w:t>"English"</w:t></w:r></w:p>')
        dn.smart_quotes(d)
        self.assertEqual(d.find(".//" + dn.qn("w:t")).text, "“English”")
        self.assertIsNone(hint_of(next(d.iter(dn.qn("w:r")))))
        dn.normalize_quote_fonts(d)
        quote_runs = [run for run in d.iter(dn.qn("w:r")) if dn._run_text(run) in "“”"]
        self.assertEqual([hint_of(run) for run in quote_runs], ["default", "default"])


# ===========================================================================
# 引注合并 + 移位
# ===========================================================================
class TestCitations(unittest.TestCase):
    def test_compress_nums(self):
        self.assertEqual(dn._compress_nums([8, 9, 10, 12]), "8-10,12")
        self.assertEqual(dn._compress_nums([8, 9]), "8-9")
        self.assertEqual(dn._compress_nums([3, 5, 7]), "3,5,7")

    def test_merge_consecutive(self):
        d = doc('<w:p><w:r><w:t>见[8][9]</w:t></w:r></w:p>')
        dn.merge_citations(d)
        self.assertEqual(d.find(".//" + dn.qn("w:t")).text, "见[8-9]")

    def test_move_after_punctuation(self):
        d = doc('<w:p><w:r><w:t>结论[5]。</w:t></w:r></w:p>')
        dn.merge_citations(d)
        self.assertEqual(d.find(".//" + dn.qn("w:t")).text,
                         "结论。[5]")

    def test_superscript_splits_run(self):
        d = doc('<w:p><w:r><w:t>看[5]。</w:t></w:r></w:p>')
        dn.superscript_citations(d)
        vas = d.findall(".//" + dn.qn("w:vertAlign"))
        self.assertTrue(any(v.get(dn.qn("w:val")) == "superscript" for v in vas))
        # 前后文本保留
        full = "".join(t.text or "" for t in d.iter(dn.qn("w:t")))
        self.assertEqual(full, "看[5]。")


# ===========================================================================
# 三线表
# ===========================================================================
TABLE_XML = (
    '<w:tbl>'
    '<w:tblPr><w:tblStyle w:val="Grid"/><w:shd w:fill="CCCCCC"/>'
    '<w:tblBorders><w:top w:val="single"/><w:left w:val="single"/>'
    '<w:bottom w:val="single"/><w:right w:val="single"/>'
    '<w:insideH w:val="single"/><w:insideV w:val="single"/></w:tblBorders>'
    '</w:tblPr>'
    '<w:tr><w:tblPrEx><w:tblBorders><w:top w:val="single"/></w:tblBorders></w:tblPrEx>'
    '<w:tc><w:tcPr><w:shd w:fill="EEEEEE"/>'
    '<w:tcBorders><w:top w:val="single"/><w:left w:val="single"/></w:tcBorders>'
    '</w:tcPr><w:p><w:r><w:t>h</w:t></w:r></w:p></w:tc></w:tr>'
    '<w:tr><w:tc><w:tcPr/><w:p><w:r><w:t>d</w:t></w:r></w:p></w:tc></w:tr>'
    '</w:tbl>'
)


class TestThreeLineTable(unittest.TestCase):
    def setUp(self):
        self.d = doc(TABLE_XML)
        dn.make_three_line_tables(self.d)

    def test_table_style_removed(self):
        self.assertEqual(self.d.findall(".//" + dn.qn("w:tblStyle")), [])

    def test_shading_removed(self):
        self.assertEqual(self.d.findall(".//" + dn.qn("w:shd")), [])

    def test_row_tblprex_removed(self):
        self.assertEqual(self.d.findall(".//" + dn.qn("w:tblPrEx")), [])

    def test_table_borders_only_top_bottom(self):
        tb = self.d.find(".//" + dn.qn("w:tblPr") + "/" + dn.qn("w:tblBorders"))
        sides = [dn.local(c) for c in tb]
        self.assertEqual(sides, ["top", "bottom"], "三线表表级应只剩 top/bottom")

    def test_header_row_has_bottom_border(self):
        rows = self.d.findall(".//" + dn.qn("w:tr"))
        head_tc = rows[0].find(dn.qn("w:tc"))
        tcb = head_tc.find(dn.qn("w:tcPr") + "/" + dn.qn("w:tcBorders"))
        self.assertIsNotNone(tcb)
        self.assertIsNotNone(tcb.find(dn.qn("w:bottom")))


# ===========================================================================
# 图：灰度 + lineRule
# ===========================================================================
class TestImages(unittest.TestCase):
    def test_grayscale_inserted_once(self):
        d = doc('<w:p><w:r><w:drawing><a:blip r:embed="x"/></w:drawing></w:r></w:p>')
        dn.grayscale_images(d)
        dn.grayscale_images(d)  # 第二次不应重复插入
        blip = d.find(".//" + dn.qn("a:blip"))
        self.assertEqual(len(blip.findall(dn.qn("a:grayscl"))), 1)

    def test_linerule_exact_relaxed_on_drawing_para(self):
        d = doc('<w:p><w:pPr><w:spacing w:line="240" w:lineRule="exact"/></w:pPr>'
                '<w:r><w:drawing/></w:r></w:p>')
        dn.fix_drawing_line_spacing(d)
        sp = d.find(".//" + dn.qn("w:spacing"))
        self.assertEqual(sp.get(dn.qn("w:lineRule")), "auto")


# ===========================================================================
# 段落首行缩进
# ===========================================================================
class TestIndent(unittest.TestCase):
    def test_firstline_to_chars(self):
        d = doc('<w:p><w:pPr><w:ind w:firstLine="480"/></w:pPr>'
                '<w:r><w:t>正文</w:t></w:r></w:p>')
        dn.firstline_chars(d)
        ind = d.find(".//" + dn.qn("w:ind"))
        self.assertEqual(ind.get(dn.qn("w:firstLineChars")), "200")
        self.assertIsNone(ind.get(dn.qn("w:firstLine")))


# ===========================================================================
# 文件名合法化
# ===========================================================================
class TestSanitize(unittest.TestCase):
    def test_illegal_to_fullwidth(self):
        out = dn.sanitize_filename('规模": a/b*c?.docx')
        for bad in '"/:*?<>|\\':
            self.assertNotIn(bad, out, "残留非法字符 %r" % bad)

    def test_strip_trailing_dot_space(self):
        self.assertEqual(dn.sanitize_filename("name.  "), "name")

    def test_nfc_normalization(self):
        import unicodedata
        decomposed = unicodedata.normalize("NFD", "é")  # e + 组合重音
        self.assertEqual(dn.sanitize_filename(decomposed), "é")


# ===========================================================================
# 端到端：默认集跑完后不变量校验通过
# ===========================================================================
class TestEndToEndInvariants(unittest.TestCase):
    def test_default_ops_keep_invariants(self):
        d = doc('<w:p><w:pPr><w:jc w:val="both"/><w:ind w:firstLine="480"/></w:pPr>'
                '<w:r><w:rPr><w:sz w:val="24"/>'
                '<w:rFonts w:ascii="Times New Roman"/></w:rPr>'
                '<w:t>他说"你好"。</w:t></w:r></w:p>')
        dn.ensure_eastasia_fonts(d, None)
        dn.smart_quotes(d)
        dn.normalize_quote_fonts(d)
        dn.firstline_chars(d)
        dn.reorder_all(d)
        issues = dn.validate(d, None, None)
        self.assertEqual(issues, [], "默认集跑完仍违反不变量：%s" % issues)


if __name__ == "__main__":
    unittest.main(verbosity=2)
