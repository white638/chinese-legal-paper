#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""qca_check.py — QCA/fsQCA 集合论参数计算（仅标准库）。

从已**校准到 [0,1]** 的隶属分数表（CSV，列=条件与结果），计算充分性/必要性的
一致性、覆盖度、PRI、RoN，并对照**约定俗成的惯例阈值**给出提示（非硬性要求）。

公式（Ragin；Schneider & Wagemann 2012；与 R 的 QCA 包一致）：
  充分性一致性  Cons(X≤Y) = Σ min(Xi,Yi) / Σ Xi
  充分性原始覆盖 Cov       = Σ min(Xi,Yi) / Σ Yi
  PRI = [Σ min(Xi,Yi) − Σ min(Xi,Yi,1−Yi)] / [Σ Xi − Σ min(Xi,Yi,1−Yi)]
  必要性一致性  Cons(Y≤X) = Σ min(Xi,Yi) / Σ Yi
  必要性覆盖    Cov       = Σ min(Xi,Yi) / Σ Xi
  RoN（必要性相关度）      = Σ(1−Xi) / Σ(1−min(Xi,Yi))

条件可为单列，或配置式（`*`=逻辑与/取 min，`~`=非/取 1−x），如 `A*~B`。

⚠ 阈值为**惯例**（需在论文中为所选值辩护），非普适硬规则。校准锚点本工具**不内置**
（deep-research 未能核实其权威数值）——校准请查 Ragin 2008 / Schneider & Wagemann 2012 原文。
证据基础见 empirical-research/references/qual-methods-evidence.md。

用法：
  python qca_check.py suff data.csv --condition "A*~B" --outcome Y
  python qca_check.py nec  data.csv --condition A --outcome Y
  python qca_check.py scan data.csv --outcome Y [--conditions A,B,C]
"""
from __future__ import annotations

import argparse
import csv
import sys

# 约定俗成的惯例阈值（来源见 qual-methods-evidence.md；均非硬规则）
CONV = {
    "suff_consistency_min": 0.75,   # Ragin 2006 下限；0.80 常用
    "pri_min": 0.50,                # <0.50 无定论；经验法则约 ≥0.75
    "pri_pref": 0.75,
    "nec_consistency_min": 0.90,
    "nec_coverage_min": 0.60,
    "ron_min": 0.60,
}


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def read_table(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return rows


def membership(expr: str, row: dict) -> float:
    """配置式求隶属度：`*` 取 min（与），前缀 `~` 取 1−x（非）。单列直接取值。"""
    vals = []
    for term in expr.split("*"):
        term = term.strip()
        neg = term.startswith("~")
        col = term[1:].strip() if neg else term
        if col not in row:
            raise KeyError("列不存在：%r（可用列：%s）" % (col, ", ".join(row.keys())))
        x = _f(row[col])
        if x is None:
            raise ValueError("非数值隶属分：%r 列 %s" % (row[col], col))
        vals.append(1.0 - x if neg else x)
    return min(vals)


def vectors(rows, cond_expr, outcome):
    X, Y = [], []
    for r in rows:
        y = _f(r.get(outcome))
        if y is None:
            raise ValueError("结果列 %s 非数值：%r" % (outcome, r.get(outcome)))
        X.append(membership(cond_expr, r))
        Y.append(y)
    return X, Y


# --- 参数 ---
def _smin(X, Y):
    return sum(min(x, y) for x, y in zip(X, Y))


def suff_consistency(X, Y):
    s = sum(X)
    return _smin(X, Y) / s if s else float("nan")


def suff_coverage(X, Y):
    s = sum(Y)
    return _smin(X, Y) / s if s else float("nan")


def pri(X, Y):
    smin = _smin(X, Y)
    smin3 = sum(min(x, y, 1.0 - y) for x, y in zip(X, Y))
    denom = sum(X) - smin3
    return (smin - smin3) / denom if denom else float("nan")


def nec_consistency(X, Y):
    s = sum(Y)
    return _smin(X, Y) / s if s else float("nan")


def nec_coverage(X, Y):
    s = sum(X)
    return _smin(X, Y) / s if s else float("nan")


def ron(X, Y):
    denom = sum(1.0 - min(x, y) for x, y in zip(X, Y))
    return sum(1.0 - x for x in X) / denom if denom else float("nan")


def sufficiency(X, Y):
    return {"consistency": suff_consistency(X, Y), "raw_coverage": suff_coverage(X, Y), "PRI": pri(X, Y)}


def necessity(X, Y):
    return {"consistency": nec_consistency(X, Y), "coverage": nec_coverage(X, Y), "RoN": ron(X, Y)}


def _flag(ok):
    return "✓" if ok else "✗"


def _fmt(d):
    return "  ".join("%s=%.3f" % (k, v) for k, v in d.items())


def cmd_suff(args):
    rows = read_table(args.csv)
    X, Y = vectors(rows, args.condition, args.outcome)
    s = sufficiency(X, Y)
    print("充分性  %s → %s" % (args.condition, args.outcome))
    print("  " + _fmt(s))
    print("  对照惯例：consistency≥%.2f %s ；PRI>%.2f %s（宜≥%.2f %s）" % (
        CONV["suff_consistency_min"], _flag(s["consistency"] >= CONV["suff_consistency_min"]),
        CONV["pri_min"], _flag(s["PRI"] > CONV["pri_min"]),
        CONV["pri_pref"], _flag(s["PRI"] >= CONV["pri_pref"])))
    print("  ⚠ 阈值为惯例非硬规则；所选值须在论文中辩护。")
    return 0


def cmd_nec(args):
    rows = read_table(args.csv)
    X, Y = vectors(rows, args.condition, args.outcome)
    s = necessity(X, Y)
    print("必要性  %s ← %s" % (args.condition, args.outcome))
    print("  " + _fmt(s))
    ok = s["consistency"] >= CONV["nec_consistency_min"] and s["coverage"] >= CONV["nec_coverage_min"] and s["RoN"] >= CONV["ron_min"]
    print("  对照惯例：consistency≥%.2f %s 且 coverage≥%.2f %s 且 RoN≥%.2f %s → %s" % (
        CONV["nec_consistency_min"], _flag(s["consistency"] >= CONV["nec_consistency_min"]),
        CONV["nec_coverage_min"], _flag(s["coverage"] >= CONV["nec_coverage_min"]),
        CONV["ron_min"], _flag(s["RoN"] >= CONV["ron_min"]),
        "符合必要条件惯例" if ok else "未达必要条件惯例"))
    print("  ⚠ 高频误用：超集关系仅是必要性第一步而非证明；出现在所有解路径≠必要；")
    print("     两个各自'通常必要'的条件相组合，联合必要性可能跌破 0.90。")
    return 0


def cmd_scan(args):
    rows = read_table(args.csv)
    cols = [c for c in rows[0].keys()] if rows else []
    if args.conditions:
        conds = [c.strip() for c in args.conditions.split(",")]
    else:
        conds = [c for c in cols if c != args.outcome]
    print("逐条件扫描（结果=%s）：" % args.outcome)
    print("%-16s %10s %10s %8s | %10s %8s %8s" %
          ("条件", "充分一致", "充分覆盖", "PRI", "必要一致", "必要覆盖", "RoN"))
    for c in conds:
        X, Y = vectors(rows, c, args.outcome)
        su, ne = sufficiency(X, Y), necessity(X, Y)
        print("%-16s %10.3f %10.3f %8.3f | %10.3f %8.3f %8.3f" % (
            c, su["consistency"], su["raw_coverage"], su["PRI"],
            ne["consistency"], ne["coverage"], ne["RoN"]))
    print("⚠ 阈值为惯例；必要性须配 RoN 防平凡必要；充分性须看 PRI。校准请查原典。")
    return 0


def build_parser():
    ap = argparse.ArgumentParser(description="QCA/fsQCA 集合论参数（仅标准库）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn, help_ in (("suff", cmd_suff, "充分性"), ("nec", cmd_nec, "必要性")):
        p = sub.add_parser(name, help=help_)
        p.add_argument("csv")
        p.add_argument("--condition", required=True, help='单列或配置式，如 "A*~B"')
        p.add_argument("--outcome", required=True)
        p.set_defaults(func=fn)
    p = sub.add_parser("scan", help="逐单条件扫描充分性+必要性")
    p.add_argument("csv")
    p.add_argument("--outcome", required=True)
    p.add_argument("--conditions", help="逗号分隔；省略=除结果外所有列")
    p.set_defaults(func=cmd_scan)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
