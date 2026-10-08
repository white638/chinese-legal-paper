#!/usr/bin/env python3
"""Regenerate references/pack-index.md from the vendored packs.

Usage: python build_pack_index.py [--write]
Without --write, prints the index to stdout. Standard library only.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
PACKS = SKILL_DIR / "packs"
OUT = SKILL_DIR / "references" / "pack-index.md"

# Deep packs: local dir -> (journal display name, discipline)
DEEP = {
    "apsr": ("American Political Science Review (APSR)", "政治学"),
    "ajps": ("American Journal of Political Science (AJPS)", "政治学"),
    "jop": ("The Journal of Politics (JOP)", "政治学"),
    "world-politics": ("World Politics", "国际关系"),
    "international-organization": ("International Organization (IO)", "国际关系"),
    "asr": ("American Sociological Review (ASR)", "社会学"),
    "ajs-sociology": ("American Journal of Sociology (AJS)", "社会学"),
    "social-forces": ("Social Forces", "社会学"),
    "spq": ("Social Psychology Quarterly (SPQ)", "社会心理学"),
    "jmf": ("Journal of Marriage and Family (JMF)", "家庭社会学"),
    "criminology": ("Criminology", "犯罪学"),
    "demography": ("Demography", "人口学"),
    "jpsp": ("Journal of Personality and Social Psychology (JPSP)", "心理学"),
    "psychological-bulletin": ("Psychological Bulletin", "心理学"),
    "psychological-science": ("Psychological Science", "心理学"),
    "journal-of-communication": ("Journal of Communication", "传播学"),
    "poq": ("Public Opinion Quarterly (POQ)", "舆论/调查"),
    "aerj": ("American Educational Research Journal (AERJ)", "教育学"),
    "ahr": ("The American Historical Review (AHR)", "历史学"),
    "art-bulletin": ("The Art Bulletin", "艺术史"),
    "mind": ("Mind", "哲学"),
    "pmla": ("PMLA", "文学/语言"),
    "critical-inquiry": ("Critical Inquiry", "批评理论"),
    "jaar": ("Journal of the American Academy of Religion (JAAR)", "宗教学"),
    "sociological-studies": ("《社会学研究》", "社会学（中文）"),
    "social-sciences-in-china": ("《中国社会科学》", "综合社科（中文）"),
    "chinese-public-administration": ("《中国行政管理》", "公共管理（中文）"),
}


def read_head(path: Path) -> tuple[str, str, str]:
    """Return (frontmatter name, first CJK 《title》 or H1, description)."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    name = ""
    desc = ""
    m = re.search(r"^name:\s*(.+)$", text, re.MULTILINE)
    if m:
        name = m.group(1).strip()
    m = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
    if m:
        desc = m.group(1).strip()
    title = ""
    m = re.search(r"《[^》]+》", text)
    if m:
        title = m.group(0)
    else:
        m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        if m:
            title = re.sub(r"[（(][a-z0-9-]+[）)]\s*$", "", m.group(1)).strip()
    return name, title, desc


def broad_rows(pack: str) -> list[str]:
    rows = []
    for d in sorted((PACKS / pack / "skills").iterdir()):
        f = d / "SKILL.md"
        if not d.is_dir() or not f.exists():
            continue
        name, title, desc = read_head(f)
        if name.endswith("-workflow"):
            continue  # routers listed separately
        short = re.sub(r"\s+", " ", desc)
        short = re.sub(r"^Use when targeting\s*", "", short)
        short = short[:110] + ("…" if len(short) > 110 else "")
        rows.append(f"| {title or name} | `{name}` | {short} |")
    return rows


def main() -> None:
    lines: list[str] = []
    lines.append("# Journal Pack 索引")
    lines.append("")
    lines.append("由 `scripts/build_pack_index.py` 生成；上游来源与裁剪规则见 `../packs/PROVENANCE.md`。")
    lines.append("路径规则：深度包 `packs/<dir>/skills/<子技能>/SKILL.md`；广度 profile "
                 "`packs/cn-broad|en-broad/skills/<slug>/SKILL.md`；路由 skill 分别为 "
                 "`cn-broad/skills/cn-journal-workflow`、`en-broad/skills/en-journal-workflow`。")
    lines.append("")
    lines.append("## 深度包（单刊全流程，约 12 技能/包）")
    lines.append("")
    lines.append("| 期刊 | 学科 | 本地目录 |")
    lines.append("|---|---|---|")
    for d, (title, disc) in DEEP.items():
        if (PACKS / d).is_dir():
            lines.append(f"| {title} | {disc} | `packs/{d}/` |")
    lines.append("")
    lines.append("## 中文广度合集 cn-broad（102 刊 profile，经管为主 + 公管/社会学/综合）")
    lines.append("")
    lines.append("| 期刊 | slug | 定位（截取） |")
    lines.append("|---|---|---|")
    lines.extend(broad_rows("cn-broad"))
    lines.append("")
    lines.append("## 英文广度合集 en-broad（100 刊 profile，经管/商科）")
    lines.append("")
    lines.append("| 期刊 | slug | 定位（截取） |")
    lines.append("|---|---|---|")
    lines.extend(broad_rows("en-broad"))
    lines.append("")
    out = "\n".join(lines) + "\n"
    if "--write" in sys.argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(out, encoding="utf-8")
        print(f"wrote {OUT} ({len(out)} chars)")
    else:
        sys.stdout.write(out)


if __name__ == "__main__":
    main()
