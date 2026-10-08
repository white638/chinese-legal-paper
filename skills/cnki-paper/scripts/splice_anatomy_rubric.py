#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 top-journal-anatomy §4 作为补充诊断拼进 contribution 评审提示词。

背景：`structured_review.py --dispatch` 生成的 review_prompts/contribution_reviewer.md
使用严格 v2 五列 rubric，不读 anatomy 文件。中文顶刊目标仍可用 anatomy §4 的 0/1/2
量规做补充诊断，但它不得替代、改写或弱化 v2 rubric、Finding block 或 Venue Fit
适用性合同。本脚本只自动注入该补充层并保持幂等（重跑替换标记块内容，anatomy
更新后重跑即同步）。

用法（在 structured_review.py --dispatch 之后、发 contribution 评审代理之前）：

    python splice_anatomy_rubric.py <output_dir> [--anatomy PATH] [--check]

<output_dir> 即 paper_rewriting_output；目标文件为
<output_dir>/review_prompts/contribution_reviewer.md。--check 只报告状态不写盘。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BEGIN = "<!-- ANATOMY-RUBRIC BEGIN -->"
END = "<!-- ANATOMY-RUBRIC END -->"

DEFAULT_ANATOMY = Path(__file__).resolve().parent.parent / "references" / "top-journal-anatomy.md"

# 补充诊断纪律跟量规一起注入。v2 五列表、Finding block 与 Venue Fit 合同仍由
# structured_review.py 生成的主提示词独占；这里不能建立第二套完成语义。
PROTOCOL = """\
### 补充诊断纪律（与上表配套）

1. **本 0/1/2 anatomy 量规仅作补充诊断，绝不取代 v2 rubric**：主提示词要求的唯一五列表
   （`Dimension ID | Applicability | Score | Reason | Manuscript Location`）原样保留、先完成，
   不得删除、改名、合并或替换任何 v2 Dimension ID，不得把 anatomy 的 0/1/2 分数填入 v2 的 1-5 Score。
   anatomy 诊断另列在 `## Supplemental Anatomy Diagnostic` 下，逐维打 0/1/2 并给一句证据句与稿内位置；
   它不产生另一套 Review Verdict、完成门或评审事实源。任何 material issue 都必须进入标准 v2
   `### Finding N` block 并填写其全部 exact labelled lines（从 `Finding ID:` 到 `Net Word Delta:`），
   anatomy 表格、分数或评语不能替代 Finding block；没有 material issue 时仍可按 v2 合法输出 PASS 和零 finding。
2. **Venue Fit 的 Applicability 只由主提示词中的已核验 target contract 决定**：逐字采用
   Verified Venue Contract 声明的 APPLICABLE、NOT_APPLICABLE 或 BLOCKED；anatomy 分数、目标刊名称或一般刊性印象都不能新建、升级或覆盖该适用性。
3. **承重四维**（3.1 问题意识 / 3.3 贡献形态 / 3.4 论证主线 / 3.5 材料-理论接口）任一为 0 → 补充诊断记为退稿档；
   构成 material issue 时转成标准 v2 Finding，由其 Severity、Repair Kind 和 Owner Stage 统一处置，不能由
   anatomy 分数单独裁决 Review Verdict。
   升格规则照量规下方说明（目标刊加码维升承重、命名式贡献时 3.6 自动升承重）。
4. **价值优先、两分法止战**：凡打 0 或 1 的维度必须附一条**抬档路径**（重做论证 / 补证据 / 收窄主张，三选一给具体动作），
   只有毙稿理由没有出路的意见视为未完成评审；不得以方法标签压分或毙稿，方法批评只问真实未知、设计能否制造所需证据、
   推断是否越限，判准见 `three-questions-standard.md` §8–§9。
5. **定性反馈不折算机械分数**：按量规的定性反馈面板逐项评价叙事连续性、语言凝练度、读者可读性、行动主体可见性和
   展示—解释平衡，引用稿内位置并指出第一次阅读受阻处；仍为 WEAK/NEEDS REVISION 且构成 material issue 时转成 v2 Finding，
   不能建立 anatomy 专属回退门。最终推荐（Accept / Minor / Major / Reject）须与 v2 Finding 严重度一致，
   不得用 anatomy 平均分抵消 Critical 或 Major Finding，并点名影响最大的 1-2 个 anatomy 维度。"""


def extract_rubric(anatomy_text: str) -> str:
    """取 anatomy 的 `## 4.` 节正文（到下一个 `## ` 为止，去掉尾部分隔线）。"""
    m = re.search(r"^## 4\..*?$", anatomy_text, re.M)
    if not m:
        raise ValueError("anatomy 文件中找不到 `## 4.` 量规节")
    rest = anatomy_text[m.start():]
    nxt = re.search(r"^## \d", rest[1:], re.M)
    body = rest[: nxt.start() + 1] if nxt else rest
    # 去掉尾部的 --- 分隔线与空行
    return re.sub(r"(\n-{3,}\s*)+$", "", body.rstrip()) + "\n"


def build_block(rubric: str) -> str:
    return (
        f"{BEGIN}\n"
        "## 中文顶刊补充诊断（top-journal-anatomy §4，不替代 v2 rubric）\n\n"
        f"{rubric}\n"
        f"{PROTOCOL}\n"
        f"{END}\n"
    )


def splice(target: Path, anatomy: Path, check_only: bool = False) -> str:
    """返回状态：applied / updated / unchanged / would-apply / would-update。"""
    rubric = extract_rubric(anatomy.read_text(encoding="utf-8"))
    block = build_block(rubric)
    text = target.read_text(encoding="utf-8")
    if BEGIN in text:
        new = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?",
                     lambda _m: block, text, count=1, flags=re.DOTALL)
        if new == text:
            return "unchanged"
        if check_only:
            return "would-update"
        target.write_text(new, encoding="utf-8")
        return "updated"
    if check_only:
        return "would-apply"
    target.write_text(text.rstrip() + "\n\n" + block, encoding="utf-8")
    return "applied"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output_dir", nargs="?", default="paper_rewriting_output")
    ap.add_argument("--anatomy", default=str(DEFAULT_ANATOMY),
                    help="top-journal-anatomy.md 路径（默认取本技能 references/ 下的）")
    ap.add_argument("--check", action="store_true", help="只报告状态，不写盘")
    args = ap.parse_args()

    anatomy = Path(args.anatomy)
    if not anatomy.exists():
        print(f"[ERROR] anatomy 文件不存在：{anatomy}", file=sys.stderr)
        return 2
    target = Path(args.output_dir) / "review_prompts" / "contribution_reviewer.md"
    if not target.exists():
        print(f"[ERROR] 找不到 {target} —— 先跑 structured_review.py --dispatch",
              file=sys.stderr)
        return 2
    try:
        status = splice(target, anatomy, check_only=args.check)
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 2
    print(f"[{status}] {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
