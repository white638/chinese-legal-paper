#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""reliability 单测（仅标准库）。期望值均为手算。运行：python test_reliability.py"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reliability as r  # noqa: E402

# 手算基准数据（2 编码者，二类，10 单位，8 同意 2 不同意）
# A=[1,1,1,1,1,0,0,0,0,1] B=[1,1,1,1,1,0,0,0,1,0]
# Po=0.8；边际各 6/4 → Cohen Pe=0.52 κ=0.5833；Scott π=0.5833
# α: o11=10,o00=6,o01=2,o10=2; n=20,n1=12,n0=8; Do=0.2,De=192/380 → α=0.6042
A = ["1", "1", "1", "1", "1", "0", "0", "0", "0", "1"]
B = ["1", "1", "1", "1", "1", "0", "0", "0", "1", "0"]
UNITS = [[a, b] for a, b in zip(A, B)]


class TestTwoCoder(unittest.TestCase):
    def test_percent(self):
        self.assertAlmostEqual(r.percent_agreement(A, B), 0.8, places=6)

    def test_cohen(self):
        self.assertAlmostEqual(r.cohen_kappa(A, B), 0.28 / 0.48, places=4)  # 0.58333

    def test_scott(self):
        self.assertAlmostEqual(r.scott_pi(A, B), 0.28 / 0.48, places=4)


class TestAlpha(unittest.TestCase):
    def test_nominal_alpha_handcalc(self):
        self.assertAlmostEqual(r.krippendorff_alpha_nominal(UNITS), 1 - 76 / 192, places=4)  # 0.60417

    def test_perfect_agreement_alpha_one(self):
        units = [["1", "1"], ["2", "2"], ["1", "1"], ["3", "3"]]
        self.assertAlmostEqual(r.krippendorff_alpha_nominal(units), 1.0, places=6)

    def test_handles_missing(self):
        # 含缺失：不可配对单位被跳过，不应抛错
        units = [["1", "1"], ["2", None], [None, None], ["1", "2"]]
        a = r.krippendorff_alpha_nominal(units)
        self.assertEqual(a, a)  # 非 nan（有可配对单位）

    def test_three_coders(self):
        # 三编码者完全一致 → α=1
        units = [["a", "a", "a"], ["b", "b", "b"], ["a", "a", "a"]]
        self.assertAlmostEqual(r.krippendorff_alpha_nominal(units), 1.0, places=6)


class TestCoefficientOrdering(unittest.TestCase):
    def test_chance_corrected_below_percent(self):
        # 校正偶合的系数应低于百分比一致（这正是不可单用百分比一致的原因）
        self.assertLess(r.cohen_kappa(A, B), r.percent_agreement(A, B))
        self.assertLess(r.krippendorff_alpha_nominal(UNITS), r.percent_agreement(A, B))


class TestTierNote(unittest.TestCase):
    def test_tiers(self):
        self.assertIn("几乎总", r.tier_note(0.95))
        self.assertIn("多数情形", r.tier_note(0.82))
        self.assertIn("探索性", r.tier_note(0.72))
        self.assertIn("不可接受", r.tier_note(0.50))


class TestCsvCli(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "rel.csv"
        lines = ["unit,A,B"] + ["u%d,%s,%s" % (i, a, b) for i, (a, b) in enumerate(zip(A, B))]
        self.tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_read_matrix(self):
        coders, cols, units = r.read_matrix(str(self.tmp))
        self.assertEqual(coders, ["A", "B"])
        self.assertEqual(cols["A"], A)
        self.assertEqual(len(units), 10)

    def test_cli_runs(self):
        self.assertEqual(r.main([str(self.tmp)]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
