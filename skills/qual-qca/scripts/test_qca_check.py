#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""qca_check 单测（仅标准库）。期望值均为手算。运行：python test_qca_check.py"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qca_check as q  # noqa: E402

# 手算模糊例：X=[.9,.8,.3,.1] Y=[.8,.6,.7,.2]
# Σmin=1.8 ΣX=2.1 ΣY=2.3 ; Σmin(x,y,1-y)=1.0 ; Σ(1-x)=1.9 Σ(1-min)=2.2
FX = [0.9, 0.8, 0.3, 0.1]
FY = [0.8, 0.6, 0.7, 0.2]


class TestFuzzyMath(unittest.TestCase):
    def test_sufficiency(self):
        self.assertAlmostEqual(q.suff_consistency(FX, FY), 1.8 / 2.1, places=6)
        self.assertAlmostEqual(q.suff_coverage(FX, FY), 1.8 / 2.3, places=6)
        self.assertAlmostEqual(q.pri(FX, FY), 0.8 / 1.1, places=6)

    def test_necessity(self):
        self.assertAlmostEqual(q.nec_consistency(FX, FY), 1.8 / 2.3, places=6)
        self.assertAlmostEqual(q.nec_coverage(FX, FY), 1.8 / 2.1, places=6)
        self.assertAlmostEqual(q.ron(FX, FY), 1.9 / 2.2, places=6)


class TestCrispMath(unittest.TestCase):
    # X=[1,1,1,0,0] Y=[1,1,0,0,1] → Σmin=2 ΣX=3 ΣY=3
    CX = [1, 1, 1, 0, 0]
    CY = [1, 1, 0, 0, 1]

    def test_all(self):
        self.assertAlmostEqual(q.suff_consistency(self.CX, self.CY), 2 / 3, places=6)
        self.assertAlmostEqual(q.nec_consistency(self.CX, self.CY), 2 / 3, places=6)
        self.assertAlmostEqual(q.pri(self.CX, self.CY), 2 / 3, places=6)
        self.assertAlmostEqual(q.ron(self.CX, self.CY), 2 / 3, places=6)


class TestPerfectSubset(unittest.TestCase):
    def test_perfect_sufficiency(self):
        # X 严格 ⊆ Y（每个 x≤y）→ 充分性一致性=1
        X = [0.2, 0.4, 0.6]
        Y = [0.5, 0.7, 0.9]
        self.assertAlmostEqual(q.suff_consistency(X, Y), 1.0, places=6)
        self.assertAlmostEqual(q.pri(X, Y), 1.0, places=6)

    def test_perfect_necessity(self):
        # Y ⊆ X（每个 y≤x）→ 必要性一致性=1
        X = [0.5, 0.7, 0.9]
        Y = [0.2, 0.4, 0.6]
        self.assertAlmostEqual(q.nec_consistency(X, Y), 1.0, places=6)


class TestMembershipExpr(unittest.TestCase):
    def setUp(self):
        self.row = {"A": "0.9", "B": "0.2"}

    def test_single(self):
        self.assertAlmostEqual(q.membership("A", self.row), 0.9, places=6)

    def test_negation(self):
        self.assertAlmostEqual(q.membership("~A", self.row), 0.1, places=6)

    def test_conjunction_min(self):
        self.assertAlmostEqual(q.membership("A*~B", self.row), min(0.9, 0.8), places=6)

    def test_missing_col_raises(self):
        with self.assertRaises(KeyError):
            q.membership("Z", self.row)


class TestCsvAndCli(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "d.csv"
        self.tmp.write_text(
            "A,B,Y\n0.9,0.2,0.8\n0.8,0.4,0.6\n0.3,0.9,0.7\n0.1,0.5,0.2\n",
            encoding="utf-8")

    def test_vectors_from_csv(self):
        rows = q.read_table(str(self.tmp))
        X, Y = q.vectors(rows, "A", "Y")
        self.assertEqual(X, FX)
        self.assertEqual(Y, FY)

    def test_cli_scan_runs(self):
        # 仅验证不抛异常、返回 0
        rc = q.main(["scan", str(self.tmp), "--outcome", "Y"])
        self.assertEqual(rc, 0)

    def test_cli_suff_runs(self):
        rc = q.main(["suff", str(self.tmp), "--condition", "A*~B", "--outcome", "Y"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
