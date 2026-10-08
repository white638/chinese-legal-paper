#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ptrace 单测（仅标准库）。核验 Collier 四检验推断规则。运行：python test_ptrace.py"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ptrace as p  # noqa: E402


class TestInferenceRules(unittest.TestCase):
    """Collier(2011) 非对称推断逻辑——技能正确性的核心。"""

    def test_hoop_fail_eliminates(self):
        self.assertEqual(p.implication("hoop", False)["focal"], "eliminated")

    def test_hoop_pass_does_not_confirm(self):
        # 通过箍圈≠确证（只是存活）
        self.assertEqual(p.implication("hoop", True)["focal"], "survives")
        self.assertNotEqual(p.implication("hoop", True)["focal"], "confirmed")

    def test_smoking_gun_pass_confirms(self):
        imp = p.implication("smoking_gun", True)
        self.assertEqual(imp["focal"], "confirmed")
        self.assertEqual(imp["rival"], "substantially_weakened")

    def test_smoking_gun_fail_does_not_reject(self):
        # 不通过冒烟枪≠拒绝（焦点假设仍存活）
        self.assertEqual(p.implication("smoking_gun", False)["focal"], "survives")

    def test_doubly_decisive(self):
        self.assertEqual(p.implication("doubly_decisive", True)["focal"], "confirmed")
        self.assertEqual(p.implication("doubly_decisive", True)["rival"], "eliminated")
        self.assertEqual(p.implication("doubly_decisive", False)["focal"], "eliminated")

    def test_straw_is_not_decisive(self):
        self.assertFalse(p.implication("straw", True)["decisive"])
        self.assertFalse(p.implication("straw", False)["decisive"])

    def test_necessity_sufficiency_table(self):
        self.assertEqual(p.TESTS["hoop"], (True, False))
        self.assertEqual(p.TESTS["smoking_gun"], (False, True))
        self.assertEqual(p.TESTS["doubly_decisive"], (True, True))
        self.assertEqual(p.TESTS["straw"], (False, False))


class TestAliasesAndParsing(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(p.canon_test("smoking-gun"), "smoking_gun")
        self.assertEqual(p.canon_test("冒烟枪"), "smoking_gun")
        self.assertEqual(p.canon_test("Straw-in-the-Wind"), "straw")

    def test_passed_parsing(self):
        self.assertTrue(p.parse_passed("通过"))
        self.assertFalse(p.parse_passed("fail"))
        self.assertTrue(p.parse_passed("1"))

    def test_unknown_test_raises(self):
        with self.assertRaises(ValueError):
            p.canon_test("magic")


class TestAssess(unittest.TestCase):
    def test_elimination_overrides_weak_support(self):
        rows = [
            {"id": "e1", "hypothesis": "H1", "test": "straw", "passed": "true"},
            {"id": "e2", "hypothesis": "H1", "test": "hoop", "passed": "false"},
        ]
        res = p.assess(rows)
        self.assertIn("已剔除", res["H1"]["status"])

    def test_confirmation(self):
        rows = [{"id": "e1", "hypothesis": "H2", "test": "smoking_gun", "passed": "true"}]
        res = p.assess(rows)
        self.assertIn("已确证", res["H2"]["status"])

    def test_contradiction_flagged(self):
        rows = [
            {"id": "e1", "hypothesis": "H3", "test": "hoop", "passed": "false"},
            {"id": "e2", "hypothesis": "H3", "test": "smoking_gun", "passed": "true"},
        ]
        res = p.assess(rows)
        self.assertIn("矛盾", res["H3"]["status"])

    def test_alive_with_weak_support(self):
        rows = [
            {"id": "e1", "hypothesis": "H4", "test": "straw", "passed": "true"},
            {"id": "e2", "hypothesis": "H4", "test": "straw", "passed": "true"},
        ]
        res = p.assess(rows)
        self.assertIn("存活", res["H4"]["status"])
        self.assertIn("+2", res["H4"]["status"])


class TestBayes(unittest.TestCase):
    def test_single_update(self):
        # 先验 0.5, LR 4 → odds 4 → 0.8
        self.assertAlmostEqual(p.bayes_update(0.5, [4.0]), 0.8, places=6)

    def test_sequential(self):
        # 0.5, [4, 0.5] → odds 1*4*0.5=2 → 2/3
        self.assertAlmostEqual(p.bayes_update(0.5, [4.0, 0.5]), 2 / 3, places=6)

    def test_lr_one_is_noop(self):
        self.assertAlmostEqual(p.bayes_update(0.3, [1.0]), 0.3, places=6)

    def test_invalid_prior(self):
        with self.assertRaises(ValueError):
            p.bayes_update(0.0, [2.0])


class TestCli(unittest.TestCase):
    def test_classify_and_tests_and_bayes(self):
        self.assertEqual(p.main(["tests"]), 0)
        self.assertEqual(p.main(["classify", "--test", "hoop", "--passed", "false"]), 0)
        self.assertEqual(p.main(["bayes", "--prior", "0.3", "--lr", "4,0.5,8"]), 0)

    def test_assess_cli(self):
        tmp = Path(tempfile.mkdtemp()) / "led.csv"
        tmp.write_text("id,hypothesis,test,passed,note\n"
                       "e1,H1,hoop,false,机制环节缺失\n"
                       "e2,H2,smoking_gun,true,直接证据\n", encoding="utf-8")
        self.assertEqual(p.main(["assess", str(tmp)]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
