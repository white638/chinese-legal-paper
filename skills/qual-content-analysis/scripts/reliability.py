#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""reliability.py — 内容分析的校正偶合一致性（仅标准库）。

计算百分比一致、Cohen's κ、Scott's π、Krippendorff's α（名义/nominal），并对照
Lombard et al. (2002) 的分层惯例阈值给出提示。

⚠ 方法学共识（硬规则）：**不得单独用百分比一致**——它受偶合膨胀、偏宽松。须用校正偶合的
指数（κ / π / α）。⚠ 阈值（.90/.80/.70）是**惯例**（需论证、非绝对；O'Connor & Joffe 2020 等
有争议）。出处见 empirical-research/references/qual-methods-evidence.md。

输入：CSV，首行=研究运行或编码者列名，每行=一个编码单位，单元格=类目（任意字符串），空=缺失。
  unit,coderA,coderB
  u1,1,1
  u2,2,3
  ...

用法：
  python reliability.py data.csv                      # 全部系数
  python reliability.py data.csv --coders coderA,coderB   # 指定两列算 κ/π
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict

# Lombard et al. (2002) 分层惯例阈值（非绝对，须论证）
TIERS = [(0.90, "≥.90 几乎总可接受"),
         (0.80, "≥.80 多数情形可接受"),
         (0.70, ".70 仅限探索性研究/保守指标")]


def tier_note(v):
    if v != v:  # nan
        return "无法判定"
    for thr, note in TIERS:
        if v >= thr:
            return note
    return "<.70 通常不可接受"


# --------------------------------------------------------------------------- #
# 两编码者系数（缺失任一则该单位不计）
# --------------------------------------------------------------------------- #
def _paired(a, b):
    return [(x, y) for x, y in zip(a, b) if x is not None and y is not None]


def percent_agreement(a, b):
    pairs = _paired(a, b)
    if not pairs:
        return float("nan")
    return sum(1 for x, y in pairs if x == y) / len(pairs)


def _marginals(values):
    d = defaultdict(int)
    for v in values:
        d[v] += 1
    n = len(values)
    return {k: c / n for k, c in d.items()}, n


def cohen_kappa(a, b):
    pairs = _paired(a, b)
    n = len(pairs)
    if not n:
        return float("nan")
    po = sum(1 for x, y in pairs if x == y) / n
    ma, _ = _marginals([x for x, _ in pairs])
    mb, _ = _marginals([y for _, y in pairs])
    cats = set(ma) | set(mb)
    pe = sum(ma.get(k, 0) * mb.get(k, 0) for k in cats)
    return (po - pe) / (1 - pe) if pe != 1 else float("nan")


def scott_pi(a, b):
    pairs = _paired(a, b)
    n = len(pairs)
    if not n:
        return float("nan")
    po = sum(1 for x, y in pairs if x == y) / n
    joint = defaultdict(int)
    for x, y in pairs:
        joint[x] += 1
        joint[y] += 1
    pe = sum((c / (2 * n)) ** 2 for c in joint.values())
    return (po - pe) / (1 - pe) if pe != 1 else float("nan")


# --------------------------------------------------------------------------- #
# Krippendorff's α（名义；≥2 编码者；容缺失）—— 重合矩阵法
# --------------------------------------------------------------------------- #
def krippendorff_alpha_nominal(units):
    """units: 列表，每元素是该单位各编码者的取值列表（None=缺失）。"""
    o = defaultdict(float)
    for codings in units:
        vals = [v for v in codings if v is not None]
        m = len(vals)
        if m < 2:
            continue  # 不可配对单位跳过
        w = 1.0 / (m - 1)
        for i in range(m):
            for j in range(m):
                if i != j:
                    o[(vals[i], vals[j])] += w
    if not o:
        return float("nan")
    cats = set()
    for c, k in o:
        cats.add(c)
        cats.add(k)
    n = sum(o.values())
    n_c = {c: sum(o.get((c, k), 0.0) for k in cats) for c in cats}
    Do = sum(v for (c, k), v in o.items() if c != k) / n
    De = sum(n_c[c] * n_c[k] for c in cats for k in cats if c != k) / (n * (n - 1))
    if De == 0:
        return float("nan")  # 仅单一类目，无离散度
    return 1.0 - Do / De


# --------------------------------------------------------------------------- #
# CSV
# --------------------------------------------------------------------------- #
def read_matrix(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        coders = header[1:]  # 第一列假定为单位 id
        cols = {c: [] for c in coders}
        units = []
        for row in reader:
            if not row:
                continue
            cells = row[1:]
            vals = [(c.strip() if c.strip() != "" else None) for c in cells]
            units.append(vals)
            for name, v in zip(coders, vals):
                cols[name].append(v)
    return coders, cols, units


def cmd_report(args):
    coders, cols, units = read_matrix(args.csv)
    run_semantics = args.semantics == "run-consistency"
    actor_label = "研究运行" if run_semantics else "编码者"
    print("%s：%s  单位数：%d" % (actor_label, ", ".join(coders), len(units)))
    a = krippendorff_alpha_nominal(units)
    alpha_note = "运行稳定性；不等于外部准确率" if run_semantics else tier_note(a)
    print("Krippendorff's α（名义，%d %s，容缺失）= %.4f  → %s" % (len(coders), actor_label, a, alpha_note))

    if args.coders:
        pick = [c.strip() for c in args.coders.split(",")]
    else:
        pick = coders[:2]
    if len(pick) == 2 and all(p in cols for p in pick):
        A, B = cols[pick[0]], cols[pick[1]]
        pa = percent_agreement(A, B)
        ck = cohen_kappa(A, B)
        sp = scott_pi(A, B)
        print("两%s（%s, %s）：" % (actor_label, pick[0], pick[1]))
        print("  百分比一致 = %.4f  ⚠ 不可单独使用（偏宽松、受偶合膨胀）" % pa)
        coefficient_note = "运行一致性；不等于外部准确率" if run_semantics else tier_note(ck)
        pi_note = "运行一致性；不等于外部准确率" if run_semantics else tier_note(sp)
        print("  Cohen's κ  = %.4f  → %s" % (ck, coefficient_note))
        print("  Scott's π  = %.4f  → %s" % (sp, pi_note))
    elif len(coders) > 2:
        print("（κ/π 仅适用两编码者；%d 编码者请以 α 为准，或 --coders 指定两列）" % len(coders))
    if run_semantics:
        print("⚠ 当前语义为运行一致性；报告须给指数、运行数、单位数与运行 provenance，不得写成准确率。")
    else:
        print("⚠ 阈值为惯例（须论证，非绝对）；报告须给指数名、值、编码者数与单位数。")
    return 0


def build_parser():
    ap = argparse.ArgumentParser(description="内容分析的校正偶合一致性（仅标准库）")
    ap.add_argument("csv")
    ap.add_argument("--coders", help="指定两列算 κ/π，如 coderA,coderB")
    ap.add_argument(
        "--semantics",
        choices=("run-consistency", "intercoder-reliability"),
        default="run-consistency",
        help="模型研究运行默认报告 run-consistency；仅实际人际编码研究选 intercoder-reliability",
    )
    ap.set_defaults(func=cmd_report)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
