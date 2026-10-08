#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""textstat 单测（仅标准库；不依赖 jieba）。期望值均为手算。运行：python test_textstat.py"""
import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import textstat as t  # noqa: E402

DOCS = [["a", "a", "b"], ["b", "c"]]  # N=2; df: a=1 b=2 c=1


class TestFreq(unittest.TestCase):
    def test_term_freq(self):
        c = t.term_freq(DOCS)
        self.assertEqual((c["a"], c["b"], c["c"]), (2, 2, 1))

    def test_doc_freq(self):
        df = t.doc_freq(DOCS)
        self.assertEqual((df["a"], df["b"], df["c"]), (1, 2, 1))


class TestTfidf(unittest.TestCase):
    def test_per_doc(self):
        per = t.tfidf(DOCS)
        # doc1: a=2*ln2, b=1*ln1=0
        self.assertAlmostEqual(per[0]["a"], 2 * math.log(2), places=6)
        self.assertAlmostEqual(per[0]["b"], 0.0, places=6)
        # doc2: c=1*ln2, b=0
        self.assertAlmostEqual(per[1]["c"], math.log(2), places=6)
        self.assertAlmostEqual(per[1]["b"], 0.0, places=6)

    def test_corpus_agg(self):
        agg = t.tfidf_corpus(DOCS)
        self.assertAlmostEqual(agg["a"], 2 * math.log(2), places=6)
        self.assertAlmostEqual(agg["c"], math.log(2), places=6)
        self.assertAlmostEqual(agg["b"], 0.0, places=6)

    def test_term_in_all_docs_has_zero_idf(self):
        # 出现在所有文档的词 idf=0 → tfidf=0（高频但无区分度）
        docs = [["x", "y"], ["x", "z"]]
        self.assertAlmostEqual(t.tfidf_corpus(docs)["x"], 0.0, places=6)


class TestCooccurrence(unittest.TestCase):
    def test_window1(self):
        c = t.cooccurrence(["a", "b", "c", "a"], window=1)
        self.assertEqual(c[("a", "b")], 1)
        self.assertEqual(c[("b", "c")], 1)
        self.assertEqual(c[("a", "c")], 1)  # (c,a) 排序去向
        self.assertEqual(len(c), 3)

    def test_window2(self):
        c = t.cooccurrence(["a", "b", "c", "a"], window=2)
        self.assertEqual(c[("a", "b")], 2)
        self.assertEqual(c[("a", "c")], 2)
        self.assertEqual(c[("b", "c")], 1)

    def test_skips_identical_adjacent(self):
        c = t.cooccurrence(["x", "x", "y"], window=1)
        self.assertEqual(c[("x", "y")], 1)
        self.assertNotIn(("x", "x"), c)

    def test_corpus(self):
        c = t.cooccurrence_corpus([["a", "b"], ["a", "b"]], window=1)
        self.assertEqual(c[("a", "b")], 2)


class TestLoadDocs(unittest.TestCase):
    def test_stopwords_and_minlen(self):
        tmp = Path(tempfile.mkdtemp()) / "d.txt"
        tmp.write_text("的 政策 改革 了\nbb a ccc\n", encoding="utf-8")
        docs = t.load_docs(input_file=str(tmp), stopwords=None)
        self.assertEqual(docs[0], ["的", "政策", "改革", "了"])
        # 停用词
        sw = Path(tempfile.mkdtemp()) / "sw.txt"
        sw.write_text("的\n了\n", encoding="utf-8")
        docs2 = t.load_docs(input_file=str(tmp), stopwords=str(sw))
        self.assertEqual(docs2[0], ["政策", "改革"])
        # 最小词长
        docs3 = t.load_docs(input_file=str(tmp), min_len=2)
        self.assertEqual(docs3[1], ["bb", "ccc"])  # "a" 被滤

    def test_dir_loading(self):
        d = Path(tempfile.mkdtemp())
        (d / "01.txt").write_text("a b", encoding="utf-8")
        (d / "02.txt").write_text("b c", encoding="utf-8")
        docs = t.load_docs(dir_=str(d))
        self.assertEqual(sorted(docs), [["a", "b"], ["b", "c"]])


class TestCli(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "docs.txt"
        self.tmp.write_text("a a b\nb c\n", encoding="utf-8")

    def test_freq_tfidf_cooc_run(self):
        self.assertEqual(t.main(["freq", "--input", str(self.tmp), "--top", "5"]), 0)
        self.assertEqual(t.main(["tfidf", "--input", str(self.tmp), "--top", "5"]), 0)
        self.assertEqual(t.main(["keywords", "--input", str(self.tmp), "--top", "3"]), 0)

    def test_cooc_to_csv(self):
        out = self.tmp.with_name("edges.csv")
        rc = t.main(["cooc", "--input", str(self.tmp), "--window", "1", "--min-count", "1", "--out", str(out)])
        self.assertEqual(rc, 0)
        self.assertTrue(out.exists())
        text = out.read_text(encoding="utf-8")
        self.assertIn("source,target,weight", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
