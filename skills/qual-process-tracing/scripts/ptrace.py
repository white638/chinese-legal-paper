#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ptrace.py — 过程追踪证据账本与推断助手（仅标准库）。

把 Collier(2011) 四类诊断检验的**推断规则**做成可执行：登记每条证据（属哪个假设、何种
检验、通过与否），自动按"必要/充分"非对称逻辑判定每个假设是被剔除/确证/仅存活。另含
**形式化贝叶斯更新**（Fairfield & Charman / Bennett 路线）作为可选的量化层——与 Collier 的
质性四检验**分层呈现**（四检验是原型贝叶斯，正式贝叶斯化是 2011 后发展）。

四类检验（Van Evera 原创，Collier 2011 系统化；"通过对肯定推断是否必要/充分"）：
  风向草 straw          (necessary=No , sufficient=No ) 通过略支持/不通过略弱，皆不决定
  箍圈   hoop           (necessary=Yes, sufficient=No ) **不通过→剔除假设**；通过不能确证
  冒烟枪 smoking_gun    (necessary=No , sufficient=Yes) **通过→强力确证**、实质削弱对弈；不通过不能拒绝
  双重决定 doubly_decisive(necessary=Yes, sufficient=Yes) 通过→确证并消除对弈；不通过→剔除

⚠ 诊断性依赖**先验知识**；起点应是事件时间线/扎实描述。证据出处见
empirical-research/references/qual-methods-evidence.md。

用法：
  python ptrace.py tests                                  # 四检验参考表
  python ptrace.py classify --test hoop --passed false    # 单条证据的推断含义
  python ptrace.py assess ledger.csv                      # 账本→逐假设状态
  python ptrace.py bayes --prior 0.3 --lr 4,0.5,8         # 形式化贝叶斯顺序更新
"""
from __future__ import annotations

import argparse
import csv
import sys

# (necessary_for_inference, sufficient_for_inference)
TESTS = {
    "straw": (False, False),
    "hoop": (True, False),
    "smoking_gun": (False, True),
    "doubly_decisive": (True, True),
}
ALIASES = {
    "straw-in-the-wind": "straw", "straw_in_the_wind": "straw", "风向草": "straw",
    "hoop": "hoop", "箍圈": "hoop",
    "smoking-gun": "smoking_gun", "smokinggun": "smoking_gun", "冒烟枪": "smoking_gun",
    "doubly-decisive": "doubly_decisive", "doubly_decisive": "doubly_decisive",
    "双重决定性": "doubly_decisive", "双重决定": "doubly_decisive",
}


def canon_test(name: str) -> str:
    key = name.strip().lower().replace(" ", "_")
    if key in TESTS:
        return key
    if name.strip() in ALIASES:
        return ALIASES[name.strip()]
    if key in ALIASES:
        return ALIASES[key]
    raise ValueError("未知检验类型：%r（应为 straw/hoop/smoking_gun/doubly_decisive）" % name)


def parse_passed(v) -> bool:
    s = str(v).strip().lower()
    if s in ("true", "1", "yes", "y", "pass", "passed", "通过", "是"):
        return True
    if s in ("false", "0", "no", "n", "fail", "failed", "不通过", "否"):
        return False
    raise ValueError("无法解析通过与否：%r" % v)


def implication(test: str, passed: bool) -> dict:
    """返回该证据对**焦点假设**与**对弈假设**的推断含义。
    focal ∈ {confirmed, eliminated, supported, weakened, survives}。"""
    t = canon_test(test)
    nec, suf = TESTS[t]
    if t == "straw":
        return ({"focal": "supported", "rival": "slightly_weakened", "decisive": False, "strength": "弱"}
                if passed else
                {"focal": "weakened", "rival": "slightly_strengthened", "decisive": False, "strength": "弱"})
    if t == "hoop":  # 必要不充分：不通过=剔除；通过=存活但未确证
        return ({"focal": "survives", "rival": "somewhat_weakened", "decisive": False, "strength": "中"}
                if passed else
                {"focal": "eliminated", "rival": "n/a", "decisive": True, "strength": "强（证伪）"})
    if t == "smoking_gun":  # 充分不必要：通过=确证；不通过=不能拒绝
        return ({"focal": "confirmed", "rival": "substantially_weakened", "decisive": True, "strength": "强"}
                if passed else
                {"focal": "survives", "rival": "unchanged", "decisive": False, "strength": "弱"})
    # doubly_decisive：通过=确证并消除对弈；不通过=剔除
    return ({"focal": "confirmed", "rival": "eliminated", "decisive": True, "strength": "强"}
            if passed else
            {"focal": "eliminated", "rival": "n/a", "decisive": True, "strength": "强（证伪）"})


def read_ledger(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def assess(rows) -> dict:
    """按假设聚合证据账本，返回 {hypothesis: {status, detail}}。
    需列：hypothesis, test, passed（可选 id/note）。"""
    by_h = {}
    for row in rows:
        h = (row.get("hypothesis") or "").strip()
        if not h:
            continue
        imp = implication(row["test"], parse_passed(row["passed"]))
        rec = by_h.setdefault(h, {"eliminated": [], "confirmed": [], "support": 0, "evidence": []})
        eid = (row.get("id") or "?").strip()
        rec["evidence"].append((eid, canon_test(row["test"]), parse_passed(row["passed"]), imp["focal"]))
        if imp["focal"] == "eliminated":
            rec["eliminated"].append(eid)
        elif imp["focal"] == "confirmed":
            rec["confirmed"].append(eid)
        elif imp["focal"] == "supported":
            rec["support"] += 1
        elif imp["focal"] == "weakened":
            rec["support"] -= 1
    out = {}
    for h, rec in by_h.items():
        if rec["eliminated"] and rec["confirmed"]:
            status = "⚠ 矛盾（既被箍圈/双重决定剔除又被冒烟枪确证）——须复查证据或假设表述"
        elif rec["eliminated"]:
            status = "已剔除（不通过箍圈/双重决定检验：%s）" % ",".join(rec["eliminated"])
        elif rec["confirmed"]:
            status = "已确证（通过冒烟枪/双重决定检验：%s）" % ",".join(rec["confirmed"])
        else:
            status = "存活（净弱支持 %+d）" % rec["support"]
        out[h] = {"status": status, "evidence": rec["evidence"]}
    return out


def bayes_update(prior: float, lrs) -> float:
    """形式化贝叶斯顺序更新：posterior odds = prior odds × ΠLR。lr=P(E|H)/P(E|¬H)。"""
    if not (0.0 < prior < 1.0):
        raise ValueError("先验须在 (0,1) 开区间")
    odds = prior / (1 - prior)
    for lr in lrs:
        if lr < 0:
            raise ValueError("似然比须非负")
        odds *= lr
    return odds / (1 + odds)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def cmd_tests(args):
    print("Collier(2011) 四类诊断检验：")
    print("%-16s %-8s %-8s %s" % ("检验", "必要?", "充分?", "通过/不通过的推断含义"))
    desc = {
        "straw": "通过略支持；不通过略弱（皆不决定）",
        "hoop": "通过=存活未确证；不通过=剔除焦点假设（证伪）",
        "smoking_gun": "通过=确证、实质削弱对弈；不通过=不能拒绝",
        "doubly_decisive": "通过=确证并消除对弈；不通过=剔除",
    }
    for t, (nec, suf) in TESTS.items():
        print("%-16s %-8s %-8s %s" % (t, "是" if nec else "否", "是" if suf else "否", desc[t]))
    return 0


def cmd_classify(args):
    imp = implication(args.test, parse_passed(args.passed))
    print("检验=%s 通过=%s →" % (canon_test(args.test), parse_passed(args.passed)))
    print("  对焦点假设：%s（力度 %s%s）" % (imp["focal"], imp["strength"], "，决定性" if imp["decisive"] else ""))
    print("  对对弈假设：%s" % imp["rival"])
    return 0


def cmd_assess(args):
    res = assess(read_ledger(args.ledger))
    print("逐假设状态：")
    for h, r in res.items():
        print("• %s：%s" % (h, r["status"]))
        for eid, t, p, focal in r["evidence"]:
            print("    - %s [%s, %s] → %s" % (eid, t, "通过" if p else "不通过", focal))
    return 0


def cmd_bayes(args):
    lrs = [float(x) for x in args.lr.split(",")]
    post = args.prior
    print("形式化贝叶斯顺序更新（先验 %.3f）：" % args.prior)
    cur = args.prior
    for i, lr in enumerate(lrs, 1):
        cur = bayes_update(cur, [lr])
        print("  第%d条证据 LR=%.3f → 后验 %.4f" % (i, lr, cur))
    print("最终后验 P(H|证据) = %.4f" % cur)
    print("⚠ LR 由研究者据证据论证给出；这是形式化贝叶斯层，与 Collier 质性四检验分开报告。")
    return 0


def build_parser():
    ap = argparse.ArgumentParser(description="过程追踪证据账本与推断助手（仅标准库）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("tests", help="四检验参考表").set_defaults(func=cmd_tests)
    p = sub.add_parser("classify", help="单条证据推断含义")
    p.add_argument("--test", required=True)
    p.add_argument("--passed", required=True)
    p.set_defaults(func=cmd_classify)
    p = sub.add_parser("assess", help="证据账本 CSV → 逐假设状态")
    p.add_argument("ledger")
    p.set_defaults(func=cmd_assess)
    p = sub.add_parser("bayes", help="形式化贝叶斯顺序更新")
    p.add_argument("--prior", type=float, required=True)
    p.add_argument("--lr", required=True, help="逗号分隔的似然比，如 4,0.5,8")
    p.set_defaults(func=cmd_bayes)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
