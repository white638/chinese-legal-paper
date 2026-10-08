#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""textstat.py — 中文文本即数据的基础量化（核心仅标准库；分词为可选前端）。

设计：**最易错、最该自动化**的计算环节（词频 / TF-IDF / 关键词 / 共现网络）走标准库、
可单测；**中文分词**是唯一需第三方的环节（jieba），做成**可选前端**——装了就自动分词，
没装就吃"预分词输入"（空格分隔的词），并提示 `pip install jieba`。

⚠ 文本即数据铁律（Grimmer & Stewart 2013）：自动化文本方法**必须验证**——任何词频/主题/
情感结果都要对冻结的任务型参照复算并说明语义有效性；模型参照一致率不得写成外部准确率。
本工具只做描述性表示层，**不替代验证**。
主题模型(LDA/STM)、词向量等重型分析见 SKILL.md 的工具指引（gensim / sklearn / R stm）。

输入二选一：
  --input FILE   每行一个文档（词以空格分隔；或加 --segment 用 jieba 分原文）
  --dir DIR      目录下每个 .txt 为一个文档

用法：
  python textstat.py freq    --input docs.txt --top 30 [--segment --stopwords sw.txt --min-len 2]
  python textstat.py tfidf   --input docs.txt --top 30
  python textstat.py keywords --dir corpus/ --top 10
  python textstat.py cooc    --input docs.txt --window 2 --min-count 3 --out edges.csv
  python textstat.py segment --input raw.txt --out tokens.txt        # 需 jieba
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import Counter
from pathlib import Path


# --------------------------------------------------------------------------- #
# 分词（可选前端）
# --------------------------------------------------------------------------- #
def have_jieba():
    try:
        import jieba  # noqa: F401
        return True
    except ImportError:
        return False


def segment_text(text: str):
    """用 jieba 分词；未安装则抛出带指引的错误。"""
    try:
        import jieba
    except ImportError as e:
        raise RuntimeError(
            "中文分词需要 jieba：pip install jieba；"
            "或改用预分词输入（词以空格分隔，不加 --segment）。") from e
    return [w for w in jieba.lcut(text) if w.strip()]


def tokenize(line: str, segment: bool):
    return segment_text(line) if segment else line.split()


# --------------------------------------------------------------------------- #
# 语料加载
# --------------------------------------------------------------------------- #
def load_stopwords(path):
    if not path:
        return set()
    return {w.strip() for w in Path(path).read_text(encoding="utf-8").splitlines() if w.strip()}


def _clean(tokens, stop, min_len):
    return [t for t in tokens if t not in stop and len(t) >= min_len]


def load_docs(input_file=None, dir_=None, segment=False, stopwords=None, min_len=1):
    """返回 list[list[str]]：每个文档一个词列表。"""
    stop = load_stopwords(stopwords)
    docs = []
    if dir_:
        for p in sorted(Path(dir_).glob("*.txt")):
            toks = tokenize(p.read_text(encoding="utf-8"), segment)
            docs.append(_clean(toks, stop, min_len))
    elif input_file:
        for line in Path(input_file).read_text(encoding="utf-8").splitlines():
            if line.strip():
                docs.append(_clean(tokenize(line, segment), stop, min_len))
    else:
        raise ValueError("需 --input 或 --dir")
    return docs


# --------------------------------------------------------------------------- #
# 核心统计（纯标准库，可单测）
# --------------------------------------------------------------------------- #
def term_freq(docs):
    c = Counter()
    for d in docs:
        c.update(d)
    return c


def doc_freq(docs):
    df = Counter()
    for d in docs:
        df.update(set(d))
    return df


def tfidf(docs):
    """每文档 {term: tf*idf}；tf=词频计数，idf=ln(N/df)。返回 list[dict]。"""
    n = len(docs)
    df = doc_freq(docs)
    out = []
    for d in docs:
        tf = Counter(d)
        out.append({t: tf[t] * math.log(n / df[t]) for t in tf})
    return out


def tfidf_corpus(docs):
    """跨文档汇总 TF-IDF（按 term 求和），用于全语料关键词排名。"""
    agg = Counter()
    for scores in tfidf(docs):
        for t, s in scores.items():
            agg[t] += s
    return agg


def cooccurrence(tokens, window=2):
    """同一文档内、词距 ≤ window 的无向共现计数（pair 排序去向）。"""
    c = Counter()
    n = len(tokens)
    for i in range(n):
        for j in range(i + 1, min(i + window + 1, n)):
            a, b = tokens[i], tokens[j]
            if a == b:
                continue
            c[tuple(sorted((a, b)))] += 1
    return c


def cooccurrence_corpus(docs, window=2):
    c = Counter()
    for d in docs:
        c.update(cooccurrence(d, window))
    return c


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _add_common(p):
    p.add_argument("--input")
    p.add_argument("--dir")
    p.add_argument("--segment", action="store_true", help="用 jieba 分词（需安装）")
    p.add_argument("--stopwords")
    p.add_argument("--min-len", type=int, default=1)


def _load(args):
    return load_docs(args.input, args.dir, args.segment, args.stopwords, args.min_len)


def cmd_freq(args):
    c = term_freq(_load(args))
    for t, n in c.most_common(args.top):
        print("%s\t%d" % (t, n))
    return 0


def cmd_tfidf(args):
    agg = tfidf_corpus(_load(args))
    for t, s in agg.most_common(args.top):
        print("%s\t%.4f" % (t, s))
    return 0


def cmd_keywords(args):
    docs = _load(args)
    per = tfidf(docs)
    for i, scores in enumerate(per):
        top = sorted(scores.items(), key=lambda kv: -kv[1])[:args.top]
        print("doc%d: %s" % (i, "  ".join("%s(%.2f)" % (t, s) for t, s in top)))
    return 0


def cmd_cooc(args):
    c = cooccurrence_corpus(_load(args), window=args.window)
    edges = [(a, b, w) for (a, b), w in c.items() if w >= args.min_count]
    edges.sort(key=lambda e: -e[2])
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="") as f:
            wr = csv.writer(f)
            wr.writerow(["source", "target", "weight"])
            wr.writerows(edges)
        print("共现边 %d 条（min-count=%d, window=%d）→ %s" % (len(edges), args.min_count, args.window, args.out))
    else:
        for a, b, w in edges[:args.top]:
            print("%s -- %s\t%d" % (a, b, w))
    print("⚠ 共现网络是描述性表示；解读须验证（语义有效性），勿当因果。")
    return 0


def cmd_segment(args):
    if not have_jieba():
        print("需要 jieba：pip install jieba", file=sys.stderr)
        return 2
    lines = Path(args.input).read_text(encoding="utf-8").splitlines()
    out = "\n".join(" ".join(segment_text(ln)) for ln in lines if ln.strip())
    if args.out:
        Path(args.out).write_text(out + "\n", encoding="utf-8")
        print("已分词 → %s" % args.out)
    else:
        print(out)
    return 0


def build_parser():
    ap = argparse.ArgumentParser(description="中文文本即数据基础量化（核心仅标准库）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn, extra in (("freq", cmd_freq, "top"), ("tfidf", cmd_tfidf, "top"),
                            ("keywords", cmd_keywords, "top")):
        p = sub.add_parser(name)
        _add_common(p)
        p.add_argument("--top", type=int, default=30)
        p.set_defaults(func=fn)
    p = sub.add_parser("cooc")
    _add_common(p)
    p.add_argument("--window", type=int, default=2)
    p.add_argument("--min-count", type=int, default=2)
    p.add_argument("--top", type=int, default=50)
    p.add_argument("--out")
    p.set_defaults(func=cmd_cooc)
    p = sub.add_parser("segment")
    p.add_argument("--input", required=True)
    p.add_argument("--out")
    p.set_defaults(func=cmd_segment)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
