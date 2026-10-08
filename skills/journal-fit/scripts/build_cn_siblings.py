#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rebuild the first two bullets of "## 路由防误投" in every cn-broad journal profile.

Data source: references/cn-journal-channels.json — one record per slug with
``channel`` (one of the eleven fixed channels below) and ``subfield`` (a finer
direction used to pick sister journals). The list order in that file is the
priority order inside a channel: earlier entries are preferred when a sibling
slot has to be filled from the wider channel.

For each profile that exists on disk (packs/cn-broad/skills/<slug>/SKILL.md)
the script rewrites:

  bullet 1  - 本刊快速定位属于“<channel>”通道；只有当稿件的核心贡献满足“<条件>”时，才把 《刊名》 作为首选。
  bullet 2  - 相近 profile 先比较：`slug`（《刊名》） / ... 。<原有的“若这些刊物的读者对象更贴近……”句>

Sibling selection: same channel only, ordered by (same subfield) > (longest
common prefix of the subfield strings) > list order; 3–4 entries, all of which
must exist on disk. If the channel cannot supply three, a small fallback chain
(FALLBACK_CHANNELS) tops the list up. Slugs registered in the JSON but absent
on disk are never listed and never written.

Condition text: the existing text inside the quotes is kept verbatim, except
when it is one of the legacy channel-template sentences (LEGACY_CONDITIONS)
and the journal now sits in a channel that template does not describe — then
a sentence is generated from the new channel/subfield instead.

Everything after bullet 2 (常见误投 …) is left untouched. Files are written back
as UTF-8 without BOM, preserving the file's own line-ending style.

Usage:
  python build_cn_siblings.py --check [--show slug1,slug2]
  python build_cn_siblings.py --write [--skip slug1,slug2]
Standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_CHANNELS = HERE.parent / "references" / "cn-journal-channels.json"
DEFAULT_PROFILES = HERE.parent / "packs" / "cn-broad" / "skills"

CHANNELS = (
    "经济学理论与宏观",
    "产业区域与农业经济",
    "财政金融",
    "国际经济",
    "管理科学与工商管理",
    "会计审计与财务",
    "公共管理与社会政策",
    "政治学与国际关系",
    "社会学",
    "历史学",
    "综合社科",
)

# Where to look when a channel cannot supply enough on-disk siblings.
FALLBACK_CHANNELS = {
    "综合社科": ["社会学", "公共管理与社会政策"],
}
DEFAULT_FALLBACK = ["综合社科"]

MAX_SIBLINGS = 4
MIN_SIBLINGS = 3

# Sentence used for bullet 1 when the condition has to be (re)generated.
CHANNEL_CONDITION = {
    "经济学理论与宏观": "经济学问题意识、机制解释和可外推的理论/政策贡献必须成立",
    "产业区域与农业经济": "产业组织、企业行为、区域发展或农业农村经济的机制解释必须是主线",
    "财政金融": "金融机构、资本市场、监管、公司金融、财政税收或财贸政策机制必须是主线",
    "国际经济": "开放经济、国际贸易、GVC、汇率、FDI或国别比较必须是主贡献",
    "管理科学与工商管理": "组织、战略、创新管理、管理科学模型、系统工程或企业管理机制必须是核心贡献",
    "会计审计与财务": "会计确认、审计监督、披露、内控或资本市场会计问题必须是核心贡献",
    "公共管理与社会政策": "政府治理、公共服务、行政改革、社会保障或数字政府机制必须是主线",
    "政治学与国际关系": "政治理论、比较政治、国际关系或中国政治的理论与经验贡献必须是核心贡献",
    "社会学": "社会学理论、社会结构、社会过程或社会政策的经验与理论解释必须是核心贡献",
    "历史学": "史料考订、历史叙事与历史解释必须是核心贡献",
    "综合社科": "社会科学理论命题、社会结构或跨学科原创解释必须是核心贡献",
}
# Finer sentences keyed by subfield (take precedence over CHANNEL_CONDITION).
SUBFIELD_CONDITION = {
    "劳动经济": "劳动就业、工资、人力资本、社保或劳动市场制度必须是核心贡献",
    "政治经济学": "政治经济学的理论命题、制度分析或中国经济制度解释必须是核心贡献",
    "政治经济学与经管交叉": "政治经济学或制度视角下的经济与管理问题必须是核心贡献",
    "宏观经济与改革政策": "宏观经济运行、体制改革或发展政策的机制解释必须是主线",
    "宏观质量与质量经济": "质量测度、质量治理或质量经济的机制解释必须是核心贡献",
    "综合经济学（数量方法）": "数量经济方法、计量识别或技术经济分析必须是核心贡献",
    "产业经济": "产业组织、企业行为、创新、数字经济或区域产业政策必须是主线",
    "产业经济与经管交叉": "产业、企业或城市层面的经管实证机制必须是主线",
    "区域经济与管理": "区域发展、产业升级或企业管理的机制解释必须是主线",
    "流通与商业经济": "商业流通、消费、平台服务或营销供应链机制必须是主线",
    "农业与农村经济": "农业、农村、农民、土地、乡村治理或农业技术经济必须是核心场景",
    "农业技术经济": "农业、农村、农民、土地、乡村治理或农业技术经济必须是核心场景",
    "金融学（综合）": "金融机构、资本市场、监管、公司金融或国际金融机制必须是主线",
    "金融市场与公司金融": "资本市场、证券定价或公司金融机制必须是主线",
    "金融监管": "金融监管、金融稳定或金融机构风险机制必须是主线",
    "金融机构与银行": "银行与金融机构经营、货币金融政策或金融市场机制必须是主线",
    "国际金融": "汇率、跨境资本流动、国际货币体系或全球金融监管机制必须是主线",
    "财政税收": "财政、税收、预算、地方债、公共支出或财贸政策必须是主问题",
    "财政与财贸政策": "财政税收、流通体系或财贸政策的制度机制必须是主问题",
    "管理科学与工程": "管理科学模型、系统工程或优化决策方法必须是核心贡献",
    "管理科学与决策分析": "决策科学、政策评估或系统分析模型必须是核心贡献",
    "科技政策与创新管理": "科技政策、创新体系、研发管理或科技治理机制必须是核心贡献",
    "科技战略与智库决策": "科技战略、科技政策或智库型决策研究必须是核心贡献",
    "组织与人力资源": "组织行为、人力资源或组织理论机制必须是核心贡献",
    "会计": "会计确认、披露、内控或资本市场会计问题必须是核心贡献",
    "审计": "审计监督、审计质量或国家审计与内部控制问题必须是核心贡献",
    "公共管理与治理": "政府治理、公共服务、行政改革或公共政策机制必须是主线",
    "数字政府与电子政务": "数字政府、政务数据治理或电子政务机制必须是主线",
    "人口与社会保障": "社会保障、养老医保、社会救助或人口与社会政策机制必须是主线",
    "综合社会学": "社会学理论、社会结构、社会过程或社会政策的经验与理论解释必须是核心贡献",
    "制度与体制比较": "经济社会体制比较、制度变迁或跨国制度经验的解释必须是核心贡献",
    "软科学与科技政策": "科技治理、创新战略或政策研究的跨学科解释必须是核心贡献",
}

# Legacy channel-template sentences -> where they still hold. Each entry is a
# channel name, or "channel:subfield-prefix" to restrict it to part of a channel.
LEGACY_CONDITIONS = {
    "农业、农村、农民、土地、乡村治理或农业技术经济必须是核心场景": {"产业区域与农业经济:农业"},
    "产业组织、企业行为、创新、数字经济或区域产业政策必须是主线": {"产业区域与农业经济", "管理科学与工商管理"},
    "会计确认、审计监督、披露、内控或资本市场会计问题必须是核心贡献": {"会计审计与财务"},
    "政府治理、公共服务、行政改革、社会保障或数字政府机制必须是主线": {"公共管理与社会政策"},
    "劳动就业、工资、人力资本、社保或劳动市场制度必须是核心贡献": {"经济学理论与宏观", "公共管理与社会政策"},
    "开放经济、国际贸易、GVC、汇率、FDI或国别比较必须是主贡献": {"国际经济"},
    "组织、战略、创新管理、管理科学模型、系统工程或企业管理机制必须是核心贡献": {"管理科学与工商管理"},
    "社会科学理论命题、社会结构或跨学科原创解释必须是核心贡献": {"综合社科"},
    "经济学问题意识、机制解释和可外推的理论/政策贡献必须成立": {"经济学理论与宏观"},
    "财政、税收、预算、地方债、公共支出或财贸政策必须是主问题": {"财政金融:财政"},
    "金融机构、资本市场、监管、公司金融或国际金融机制必须是主线": {"财政金融:金融", "财政金融:国际金融"},
}


def legacy_holds(allowed: set[str], me: "Journal") -> bool:
    for rule in allowed:
        channel, _, prefix = rule.partition(":")
        if channel == me.channel and me.subfield.startswith(prefix):
            return True
    return False

DEFAULT_TAIL = "若这些刊物的读者对象更贴近，不要因为名称、地区或变量相似而强行投本刊。"

SECTION_HEADING = "## 路由防误投"
BULLET1_RE = re.compile(
    r"^- 本刊快速定位属于“(?P<channel>[^”]*)”通道；"
    r"只有当稿件的核心贡献满足“(?P<cond>[^”]*)”时，才把 《(?P<name>[^》]*)》 作为首选。\s*$"
)
BULLET2_RE = re.compile(r"^- 相近 profile 先比较：(?P<list>.*?)。(?P<tail>若.*)$")


class Journal:
    __slots__ = ("slug", "name", "channel", "subfield", "order", "on_disk")

    def __init__(self, rec: dict, order: int):
        self.slug = rec["slug"]
        self.name = rec["name"]
        self.channel = rec["channel"]
        self.subfield = rec["subfield"]
        self.order = order
        self.on_disk = False


def load_channels(path: Path) -> list[Journal]:
    data = json.loads(path.read_text(encoding="utf-8"))
    journals, seen = [], set()
    for i, rec in enumerate(data):
        for key in ("slug", "name", "channel", "subfield"):
            if not rec.get(key):
                sys.exit(f"{path}: record {i} lacks '{key}'")
        if rec["channel"] not in CHANNELS:
            sys.exit(f"{path}: {rec['slug']} has unknown channel {rec['channel']!r}")
        if rec["slug"] in seen:
            sys.exit(f"{path}: duplicate slug {rec['slug']}")
        seen.add(rec["slug"])
        journals.append(Journal(rec, i))
    return journals


def common_prefix_len(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def pick_siblings(me: Journal, journals: list[Journal]) -> list[Journal]:
    pool = [j for j in journals if j.on_disk and j.slug != me.slug]
    same = [j for j in pool if j.channel == me.channel]
    same.sort(key=lambda j: (0 if j.subfield == me.subfield else 1,
                             -common_prefix_len(j.subfield, me.subfield),
                             j.order))
    chosen = same[:MAX_SIBLINGS]
    if len(chosen) < MIN_SIBLINGS:
        for fb in FALLBACK_CHANNELS.get(me.channel, DEFAULT_FALLBACK):
            for j in sorted((j for j in pool if j.channel == fb), key=lambda j: j.order):
                if j not in chosen:
                    chosen.append(j)
                if len(chosen) >= MIN_SIBLINGS:
                    break
            if len(chosen) >= MIN_SIBLINGS:
                break
    return chosen


def condition_for(me: Journal, original: str | None) -> tuple[str, str]:
    """Return (condition, how) where how is 'kept' | 'generated'."""
    if original:
        allowed = LEGACY_CONDITIONS.get(original)
        if allowed is None or legacy_holds(allowed, me):
            return original, "kept"
    return SUBFIELD_CONDITION.get(me.subfield, CHANNEL_CONDITION[me.channel]), "generated"


def build_bullets(me: Journal, siblings: list[Journal], cond: str, tail: str) -> tuple[str, str]:
    b1 = (f"- 本刊快速定位属于“{me.channel}”通道；只有当稿件的核心贡献满足“{cond}”时，"
          f"才把 《{me.name}》 作为首选。")
    listing = " / ".join(f"`{j.slug}`（《{j.name}》）" for j in siblings)
    b2 = f"- 相近 profile 先比较：{listing}。{tail}"
    return b1, b2


def rewrite(text: str, me: Journal, journals: list[Journal]) -> tuple[str | None, dict]:
    lines = text.split("\n")
    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip() == SECTION_HEADING)
    except StopIteration:
        return None, {"error": "no 路由防误投 section"}
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    bullets = [i for i in range(start + 1, end) if lines[i].startswith("- ")]
    if len(bullets) < 2:
        return None, {"error": "fewer than two bullets in section"}
    i1, i2 = bullets[0], bullets[1]

    m1 = BULLET1_RE.match(lines[i1])
    original_cond = m1.group("cond") if m1 else None
    old_channel = m1.group("channel") if m1 else None
    m2 = BULLET2_RE.match(lines[i2])
    tail = m2.group("tail") if m2 else DEFAULT_TAIL

    cond, how = condition_for(me, original_cond)
    siblings = pick_siblings(me, journals)
    b1, b2 = build_bullets(me, siblings, cond, tail)
    changed = (lines[i1] != b1) or (lines[i2] != b2)
    lines[i1], lines[i2] = b1, b2
    info = {
        "old_channel": old_channel,
        "channel_changed": old_channel != me.channel,
        "condition": how,
        "siblings": [j.slug for j in siblings],
        "short": len(siblings) < MIN_SIBLINGS,
        "bullet1": b1,
        "bullet2": b2,
        "changed": changed,
    }
    return "\n".join(lines), info


def read_file(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    newline = "\r\n" if b"\r\n" in raw else "\n"
    return raw.decode("utf-8").replace("\r\n", "\n"), newline


def write_file(path: Path, text: str, newline: str) -> None:
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="report what would change; write nothing")
    mode.add_argument("--write", action="store_true", help="rewrite the profiles in place")
    ap.add_argument("--channels", type=Path, default=DEFAULT_CHANNELS)
    ap.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    ap.add_argument("--skip", default="", help="comma-separated slugs to leave untouched")
    ap.add_argument("--only", default="", help="comma-separated slugs to process (others are ignored)")
    ap.add_argument("--show", default="", help="comma-separated slugs whose new bullets are printed")
    ap.add_argument("--examples", type=int, default=3, help="how many changed files to sample in --check")
    args = ap.parse_args(argv)

    journals = load_channels(args.channels)
    by_slug = {j.slug: j for j in journals}
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    show = {s.strip() for s in args.show.split(",") if s.strip()}

    on_disk = sorted(d.name for d in args.profiles.iterdir() if (d / "SKILL.md").exists())
    unregistered = []
    for slug in on_disk:
        if slug in by_slug:
            by_slug[slug].on_disk = True
        elif (args.profiles / slug / "SKILL.md").read_text(encoding="utf-8").find(SECTION_HEADING) >= 0:
            unregistered.append(slug)
    absent = [j.slug for j in journals if not j.on_disk]

    results = []
    for j in journals:
        if not j.on_disk or (only and j.slug not in only):
            continue
        path = args.profiles / j.slug / "SKILL.md"
        text, newline = read_file(path)
        new_text, info = rewrite(text, j, journals)
        info["slug"] = j.slug
        info["skipped"] = j.slug in skip
        if new_text is None:
            results.append(info)
            continue
        results.append(info)
        if args.write and info["changed"] and not info["skipped"]:
            write_file(path, new_text, newline)

    errors = [r for r in results if "error" in r]
    changed = [r for r in results if r.get("changed") and not r["skipped"]]
    skipped = [r for r in results if r.get("changed") and r["skipped"]]
    short = [r for r in results if r.get("short")]
    relabelled = [r for r in results if r.get("channel_changed")]
    regenerated = [r for r in results if r.get("condition") == "generated"]

    verb = "written" if args.write else "would change"
    print(f"profiles on disk: {len(results)}  registered-but-absent: {len(absent)}  "
          f"unregistered-on-disk: {len(unregistered)}")
    print(f"{verb}: {len(changed)}  skipped (--skip): {len(skipped)}  "
          f"channel label changed: {len(relabelled)}  condition regenerated: {len(regenerated)}  "
          f"fewer than {MIN_SIBLINGS} siblings: {len(short)}  errors: {len(errors)}")
    if unregistered:
        print("  unregistered profiles (left untouched):", ", ".join(unregistered))
    for r in errors:
        print(f"  ERROR {r['slug']}: {r['error']}")
    for r in short:
        print(f"  SHORT {r['slug']}: {r['siblings']}")

    if args.check:
        sample = [r for r in changed if r["slug"] in show] or changed[: args.examples]
        for r in sample:
            print(f"\n[{r['slug']}] {r['old_channel']} -> {by_slug[r['slug']].channel} "
                  f"(condition {r['condition']})")
            print(r["bullet1"])
            print(r["bullet2"])
    elif show:
        for r in results:
            if r["slug"] in show and "bullet1" in r:
                print(f"\n[{r['slug']}]")
                print(r["bullet1"])
                print(r["bullet2"])
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
