#!/usr/bin/env python3
"""Validate the reader-oriented academic-prose audit for Chinese manuscripts.

The checker deliberately avoids treating sentence length, active-voice ratios,
or lexical complexity as quality scores. It hard-gates audit coverage and
unresolved decisions. Lexical patterns only trigger contextual review.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from xml.etree import ElementTree
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from prose_packet import (
    ANCHOR_PREFIXES,
    BOUNDARY_ID_RE,
    CLARITY_ACTIONS,
    CLARITY_ACTION_KEYS,
    CLARITY_SOURCE_KINDS,
    CLAIM_PREFIXES,
    EVIDENCE_PREFIXES,
    FORBIDDEN_ACTIVATION_RE,
    IDENTITY_RE,
    POSITIVE_GROWTH_ACTIONS,
    ProsePacketError,
    compile_clarity_growth_soft_limits,
    discover_registered_ids,
)


GENERIC = {
    "",
    "-",
    "--",
    "n/a",
    "na",
    "none",
    "null",
    "todo",
    "tbd",
    "placeholder",
    "待填",
    "待定",
    "暂无",
    "无",
}

PASS_STATUS = re.compile(
    r"^\s*(?:PASS|REVISED|JUSTIFIED|通过|已修订|已改写|已修改|有据保留)\s*$",
    re.IGNORECASE,
)
UNRESOLVED_STATUS = re.compile(
    r"(?:\b(?:FAIL|OPEN|BLOCKED|TODO|TBD|VERIFY|NEEDS[- ]?REVIEW)\b|"
    r"失败|未通过|待修|待改|待核|未解决|阻塞)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RiskPattern:
    key: str
    label: str
    regex: re.Pattern[str]


@dataclass(frozen=True)
class RiskHit:
    key: str
    label: str
    snippet: str
    line: int
    unit_start: int = -1


@dataclass
class CheckResult:
    audit_path: Path
    manuscript_path: Path | None
    prose_mode: str
    issues: list[str]
    warnings: list[str]
    hits: list[RiskHit]
    coverage: dict[str, int]

    @property
    def ok(self) -> bool:
        return not self.issues


RISK_PATTERNS = (
    RiskPattern(
        "generic-background",
        "空泛背景句",
        re.compile(r"在[^。！？\n]{0,40}(?:背景|形势|时代)下"),
    ),
    RiskPattern(
        "significance-cliche",
        "意义套话",
        re.compile(r"具有(?:十分|非常|极其)?(?:重要)?(?:的)?(?:理论|现实|实践)?意义"),
    ),
    RiskPattern(
        "generic-borrowing",
        "借鉴套话",
        re.compile(r"提供了?(?:有益|重要|一定)?(?:的)?(?:参考|借鉴|启示)"),
    ),
    RiskPattern(
        "generic-contribution",
        "空泛贡献句",
        re.compile(r"(?:丰富|拓展|深化)了?[^。！？\n]{0,24}(?:研究|认识|理论)"),
    ),
    RiskPattern(
        "empty-gap",
        "空白式缺口",
        re.compile(r"(?:鲜有(?:学者|研究)|较少有研究|填补了?[^。！？\n]{0,20}空白)"),
    ),
    RiskPattern(
        "nominalization-shell",
        "空泛名词化",
        re.compile(r"(?:进行|开展)了?(?:较为|全面|深入|系统){0,4}(?:的)?(?:研究|分析|探讨|考察)"),
    ),
    RiskPattern(
        "process-padding",
        "过程垫话",
        re.compile(r"在[^。！？\n]{0,35}的过程中"),
    ),
    RiskPattern(
        "vague-hedge",
        "模糊限定",
        re.compile(r"(?:在一定程度上|某种意义上|较为显著地)"),
    ),
    RiskPattern(
        "qualification-cluster",
        "限制语簇拥",
        re.compile(
            r"(?:只能|仅能|不能|无法|尚不足以|难以)"
            r"[^。！？\n]{0,48}"
            r"(?:只能|仅能|不能|无法|尚不足以|难以)"
        ),
    ),
    RiskPattern(
        "contrastive-negation",
        "否定转折惯性",
        re.compile(
            r"(?:并不是|不是|并非|不在于)"
            r"[^。！？\n]{0,96}"
            r"(?:而是|而在于)"
        ),
    ),
    RiskPattern(
        "authorial-intent-negation",
        "作者意图否定",
        re.compile(
            r"(?:本文|本研究|本节|笔者)"
            r"[^。！？\n]{0,8}"
            r"(?:并非旨在|并非意在|无意|并不(?:把|将|试图|旨在|意在|主张|声称)|不(?:把|将|试图|旨在|意在|主张|声称))"
        ),
    ),
    RiskPattern(
        "hypothetical-objection-disclaimer",
        "预防误解式说明",
        re.compile(
            r"(?:为避免(?:误解|误读|歧义)|"
            r"(?:需要|有必要)(?:特别)?(?:说明|澄清)(?:的是)?|"
            r"这(?:并不|不)(?:意味着|代表|等于)|"
            r"(?:不应|不能)(?:据此)?(?:被)?(?:理解|解读|视)为)"
        ),
    ),
    RiskPattern(
        "self-undermining-contribution",
        "自我削弱式贡献",
        re.compile(
            r"(?:(?:尽管|虽然|诚然|固然)"
            r"[^。！？\n]{0,72}(?:局限|不足|限制|有限|不能|无法)|"
            r"(?:应当|必须)承认"
            r"[^。！？\n]{0,56}(?:局限|不足|限制|有限))"
            r"[^。！？\n]{0,72}(?:但|然而|不过|仍)"
            r"[^。！？\n]{0,56}(?:价值|贡献|意义|启示|推进|解释)"
        ),
    ),
    RiskPattern(
        "simulated-reviewer-rebuttal",
        "模拟审稿答辩",
        re.compile(
            r"(?:最强(?:的)?(?:反对意见|质疑)(?:认为|是)|"
            r"这一(?:质疑|反对意见)(?:部分)?成立)"
        ),
    ),
    RiskPattern(
        "audit-boundary-broadcast",
        "证据审计式自我限缩",
        re.compile(
            r"(?:本文材料所能支持的是|"
            r"现有材料(?:的)?(?:范围)?限于|"
            r"本文(?:把|将)(?:结论|贡献)(?:限定|限制)为|"
            r"本文的贡献限于|"
            r"不推断(?:具体)?[^。！？\n]{0,12}(?:绩效|效果|效能))"
        ),
    ),
    RiskPattern(
        "overclaim-proof",
        "证明式过强主张",
        re.compile(r"(?:充分|完全|有力)?证明了?"),
    ),
    RiskPattern(
        "overclaim-causality",
        "绝对因果主张",
        re.compile(r"(?:必然|一定会|一定能够|足以|完全由[^。！？\n]{0,18})[^。！？\n]{0,12}(?:导致|决定|造成|提高|改善)"),
    ),
    RiskPattern(
        "overclaim-scope",
        "过度外推",
        re.compile(r"(?:普遍适用于|适用于(?:所有|全部|不同)地区|在任何[^。！？\n]{0,12}(?:情境|地区|场景))"),
    ),
    RiskPattern(
        "novelty-claim",
        "首创性主张",
        re.compile(r"(?:首次提出|首创|开创性|颠覆性)"),
    ),
    RiskPattern(
        "scaffold-layer-metaphor",
        "空间层级式分析脚手架",
        re.compile(
            r"(?:止步处|最(?:靠前|前面)的?一层|"
            r"(?:[一二三四五六七八九十\d]+层)?(?:文献|研究|论证)"
            r"[^。！？\n]{0,16}(?:叠起来|堆起来|垒起来)|"
            r"(?:关键|主要|核心)?断点|"
            r"(?:制度化|理论|机制|分析)(?:落点|入口|出口))"
        ),
    ),
    RiskPattern(
        "workflow-scaffold-label",
        "分析流程脚手架",
        re.compile(
            r"(?:理念库|议题选址|设计转译|成员动员|理念兑现链|"
            r"单线孵化|静态测绘|逐项映射|框架的漏洞)"
        ),
    ),
    RiskPattern(
        "internal-process-log",
        "内部获取日志外泄",
        re.compile(
            r"(?:(?:来源|网页|全文|图片|链接|附件|数据|材料)?"
            r"(?:抓取|爬取|下载|获取|访问|解析|导出)"
            r"(?:来源|网页|全文|图片|链接|附件|数据|材料)?"
            r"(?:失败|异常|报错)|"
            r"(?:请求|连接)(?:失败|超时)|"
            r"(?:工具|接口|脚本)(?:不可用|无法访问|运行失败|报错))"
        ),
    ),
    RiskPattern(
        "audit-judicial-register",
        "审计司法语域外泄",
        re.compile(
            r"(?:核心裁决物|机制对弈|相合程度|核验状态|"
            r"未见或待核验|逐项核验|逐条核验|"
            r"核定|校验|审计|闭环|跑通|接口|底座|映射|"
            r"(?:本文|本节|据此|由此)[^。！？\n]{0,10}(?:判定|裁决)|"
            r"(?:判定|裁决)为|可核(?:定|材料|信息|内容|证据)|"
            r"(?:材料|文献|证据|命题)[^。！？\n]{0,8}核验)"
        ),
    ),
    RiskPattern(
        "compressed-coinage",
        "压缩式自造标签",
        re.compile(
            r"(?:(?:条款|承诺|宣示)化|正式化不透明|嵌入式制衡|"
            r"制度化落点|组织外壳|动员半径)"
        ),
    ),
)


TABLE_SPECS = {
    "title_loop": {
        "label": "标题回环",
        "minimum": 3,
        "columns": {
            "checkpoint": {"checkpoint", "校准节点", "节点"},
            "title": {"title", "标题"},
            "links": {
                "problem/claim/evidence links",
                "problem claim evidence links",
                "问题主张证据链接",
                "身份链接",
            },
            "scope": {"scope/case/time", "scope case time", "范围案例时间", "范围条件"},
            "change": {"change class", "change type", "变更类型", "改题类型"},
            "basis": {"revision basis", "change basis", "修订依据", "改题依据"},
            "recovery": {"reader recovery", "reader can recover", "读者复原", "读者可复原"},
            "status": {"status", "状态"},
        },
    },
    "architecture": {
        "label": "外架构与章节角色",
        "minimum": 4,
        "columns": {
            "unit": {"unit", "结构单元", "单元"},
            "location": {"location", "位置", "稿件位置"},
            "role": {
                "role/reader question",
                "role",
                "reader question",
                "作用读者问题",
                "章节作用",
            },
            "claim": {
                "controlling claim",
                "thesis",
                "控制性命题",
                "核心主张",
            },
            "terms": {"key terms", "核心术语", "关键术语"},
            "link": {
                "link to whole/previous",
                "link to whole",
                "relation to whole",
                "与全文前节关系",
                "与全文或前节关系",
            },
            "action": {
                "revision decision",
                "revision/action",
                "修改决定",
                "修改动作",
            },
            "status": {"status", "状态"},
        },
    },
    "explanation_roles": {
        "label": "强抗辩与解释角色",
        "minimum": 0,
        "columns": {
            "explanation": {
                "explanation/objection",
                "explanation",
                "objection",
                "解释抗辩",
                "解释或抗辩",
            },
            "target": {
                "target outcome/stage",
                "target outcome",
                "target stage",
                "目标结果阶段",
                "目标结果或阶段",
            },
            "same_target": {
                "same outcome/stage?",
                "same outcome/stage",
                "same target?",
                "是否同一结果阶段",
                "同一结果或阶段",
            },
            "expectation": {
                "distinct empirical expectation",
                "empirical expectation",
                "可区分经验预期",
                "独特经验预期",
            },
            "support": {
                "supporting evidence",
                "evidence for",
                "支持证据",
            },
            "discrimination": {
                "contrary/discriminating evidence",
                "discriminating evidence",
                "evidence against",
                "反向判别证据",
                "反证或判别证据",
            },
            "relation": {
                "relation to main argument",
                "relation",
                "与主论证关系",
                "解释关系",
            },
            "decision": {
                "manuscript role/decision",
                "manuscript role",
                "decision",
                "稿内作用决定",
                "稿内角色或决定",
            },
            "status": {"status", "状态"},
        },
    },
    "boundary_placement": {
        "label": "边界安置",
        "minimum": 1,
        "columns": {
            "boundary": {
                "boundary/uncertainty",
                "boundary",
                "uncertainty",
                "边界不确定性",
                "边界或不确定性",
            },
            "effect": {
                "why it changes the claim",
                "claim effect",
                "如何改变主张",
                "对主张的影响",
            },
            "location": {
                "full-statement location",
                "full statement location",
                "完整说明位置",
                "承重位置",
            },
            "downstream": {
                "downstream handling",
                "后续处理",
                "其他位置处理",
            },
            "removed": {
                "repetition removed",
                "removed repetition",
                "删除重复",
                "已移除重复",
            },
            "status": {"status", "状态"},
        },
    },
    "narrative_wrap": {
        "label": "叙事包装图",
        "minimum": 5,
        "columns": {
            "stage": {"stage", "故事阶段", "叙事阶段", "阶段"},
            "location": {"manuscript location", "location", "稿件位置", "位置"},
            "question": {"reader question", "读者问题", "此刻问题"},
            "move": {"substantive move", "academic move", "学术任务", "实质动作"},
            "evidence_actor": {
                "evidence/actor",
                "evidence or actor",
                "证据行动者",
                "证据或行动者",
            },
            "transition": {
                "transition/payoff",
                "transition",
                "payoff",
                "承接读者所得",
                "承接或读者所得",
            },
            "status": {"status", "状态"},
        },
    },
    "reverse_outline": {
        "label": "反向提纲与主线",
        "minimum": 4,
        "columns": {
            "location": {"location", "位置", "单元位置"},
            "claim": {"main claim", "claim", "核心主张", "本段主张"},
            "evidence": {"evidence/reasoning", "evidence", "reasoning", "证据推理", "证据或推理"},
            "contribution": {"contribution link", "贡献链接", "贡献关系"},
            "relation": {"relation/transition", "relation", "transition", "逻辑关系", "承接关系"},
            "action": {"action", "修改动作", "处理"},
            "status": {"status", "状态"},
        },
    },
    "paragraph": {
        "label": "承重段落审计",
        "minimum": 3,
        "columns": {
            "location": {"location", "位置"},
            "claim": {"claim", "主张"},
            "evidence": {"evidence", "证据"},
            "warrant": {"warrant/analysis", "warrant", "analysis", "担保分析", "分析解释"},
            "boundary": {"boundary/implication", "boundary", "implication", "边界含义", "边界或含义"},
            "action": {"action", "修改动作", "处理"},
            "status": {"status", "状态"},
        },
    },
    "sentence": {
        "label": "句子信息结构与术语",
        "minimum": 4,
        "columns": {
            "location": {"location", "位置"},
            "old": {"old/context", "old information", "旧信息语境", "旧信息或语境"},
            "verb": {"subject-verb/action", "subject verb", "action", "主谓动作", "主语谓语动作"},
            "new": {"new/stress", "new information", "新信息重点", "新信息或重点"},
            "term": {"term consistency", "术语一致性", "术语检查"},
            "revision": {"revision/justification", "revision", "justification", "修改理由", "改写或理由"},
            "status": {"status", "状态"},
        },
    },
    "claim_strength": {
        "label": "主张力度校准",
        "minimum": 2,
        "columns": {
            "location": {"location", "位置"},
            "claim": {"claim", "主张"},
            "evidence": {"evidence/design", "evidence", "design", "证据设计", "证据或设计"},
            "allowed": {"allowed wording", "允许措辞", "可用措辞"},
            "forbidden": {"forbidden wording", "禁止措辞", "不可用措辞"},
            "final": {"final wording", "最终措辞", "定稿措辞"},
            "status": {"status", "状态"},
        },
    },
    "dialogue_voice": {
        "label": "对话与声音审计",
        "minimum": 4,
        "columns": {
            "location": {"manuscript location", "location", "稿件位置", "位置"},
            "prior": {
                "prior/source position",
                "prior or source position",
                "前人来源立场",
                "前人或来源立场",
            },
            "attribution": {
                "attribution/voice boundary",
                "attribution and voice boundary",
                "归属声音边界",
                "归属与声音边界",
            },
            "response": {"author response", "作者回应", "作者推进"},
            "countervoice": {
                "strongest countervoice handling",
                "countervoice handling",
                "最强反方处置",
                "反方处置",
            },
            "recovery": {
                "reader recovery",
                "reader can recover",
                "读者复原",
                "读者能否复原",
            },
            "status": {"status", "状态"},
        },
    },
    "substantive_revision": {
        "label": "实质性修改差异",
        "minimum": 1,
        "columns": {
            "discovery": {"discovery", "new discovery", "新发现", "发现"},
            "initial": {
                "initial claim/location",
                "initial claim and location",
                "原主张位置",
                "初始主张与位置",
            },
            "revised": {"revised claim", "修订后主张", "新主张"},
            "recheck": {
                "source/evidence recheck",
                "source and evidence recheck",
                "来源证据复核",
                "来源与证据复核",
            },
            "propagation": {
                "propagated changes",
                "propagated locations",
                "传播修改",
                "联动修改",
            },
            "implication": {
                "boundary/implication fixed",
                "boundary and implication fixed",
                "边界含义修复",
                "边界与含义修复",
            },
            "status": {"status", "状态"},
        },
    },
}

READER_FIELDS = {
    "reader roles": {"reader roles and branches", "读者角色与分支", "读者角色"},
    "outsider question": {
        "outsider reader: question and stakes",
        "outsider reader question",
        "外行读者：问题与要紧处",
        "外行读者问题",
    },
    "outsider sit-up": {"outsider reader: sit-up moment", "outsider sit-up", "外行读者：坐直位置", "坐直位置"},
    "insider new thing": {
        "insider reader: one thing not previously known",
        "insider reader new",
        "内行读者：此前不知道的一件事",
        "内行新知",
    },
    "central contribution": {"central contribution recovered", "核心贡献复述", "中心贡献复述"},
    "strongest evidence": {"strongest evidence recovered", "最强证据复述", "最强证据"},
    "inference boundary": {"inference boundary recovered", "推断边界复述", "推断边界"},
    "largest logic gap": {"largest logic gap", "最大逻辑跳跃", "最大逻辑缺口"},
    "revision disposition": {"revision disposition", "修订处置", "处理决定"},
    "narrative path": {"narrative path recovered", "叙事路径复述", "认知路径复述"},
    "reader payoff": {"reader payoff recovered", "读者所得复述", "认识改变复述"},
    "reading friction": {
        "first reread / reading friction",
        "first reread",
        "reading friction",
        "首次回读位置",
        "阅读受阻位置",
    },
}

NARRATIVE_STAGES = {
    "background": {"background", "exposition", "背景铺陈", "背景", "已知"},
    "rising tension": {"rising tension", "rising action", "张力上升", "问题张力", "异常冲突"},
    "core answer": {"core answer", "climax", "核心回答", "高潮", "主要发现"},
    "explanation and boundary": {
        "explanation and boundary",
        "falling action",
        "解释与边界",
        "张力释放",
        "替代解释与边界",
    },
    "resolution": {"resolution", "denouement", "认识结局", "结局", "贡献结论"},
}

ARCHITECTURE_UNITS = {
    "core thesis": {"core thesis", "central claim", "中心主张", "全文主张", "核心论点"},
    "introduction": {"introduction", "引言", "导论"},
    "body structure": {"body structure", "body", "主体结构", "主体章节", "正文结构"},
    "conclusion": {"conclusion", "结论", "结语"},
}

TITLE_CHECKPOINTS = {
    "question_commitment": {
        "question_commitment",
        "question commitment",
        "problem commitment",
        "问题承诺",
        "研究问题确认",
    },
    "post_execution": {
        "post_execution",
        "post execution",
        "after execution",
        "执行后校准",
        "证据完成",
    },
    "final": {"final", "final audit", "定稿", "最终审计"},
}

TITLE_LINK_PATTERNS = {
    "problem": re.compile(
        r"(?<![A-Za-z0-9_.-])PO[-_]?\d{1,4}(?![A-Za-z0-9_.-])",
        re.IGNORECASE,
    ),
    "execution": re.compile(
        r"(?<![A-Za-z0-9_.-])EXE[-_]?\d{1,4}(?![A-Za-z0-9_.-])",
        re.IGNORECASE,
    ),
    "claim": re.compile(
        r"(?<![A-Za-z0-9_.-])(?:CLM|CLAIM)[-_]?\d{1,4}(?![A-Za-z0-9_.-])",
        re.IGNORECASE,
    ),
    "evidence": re.compile(
        r"(?<![A-Za-z0-9_.-])(?:EVIDENCE|EVD|EV)[-_]?\d{1,4}(?![A-Za-z0-9_.-])",
        re.IGNORECASE,
    ),
}

TITLE_RHETORICAL_COLUMNS = {
    "resonance": {
        "resonance device",
        "title resonance device",
        "标题共鸣装置",
        "标题修辞装置",
    },
    "body_move": {
        "body explanation move",
        "body explanation move ref",
        "正文解释 move",
        "正文兑现 move",
    },
}

CONTEXT_ANCHOR_COLUMNS = {
    "id": {"anchor id", "context anchor id", "锚点编号"},
    "authority": {"authority ref", "authority reference", "权威引用"},
    "type": {"type", "anchor type", "类型"},
    "locator": {"locator", "出处定位", "定位"},
    "content": {"exact span/known details", "exact span or known details", "原文或已知细节"},
    "problem": {"original problem", "原始问题"},
    "logic": {"logical context", "逻辑上下文"},
    "qualifiers": {"protected qualifiers", "受保护限定语"},
    "function": {"manuscript function", "稿件功能"},
    "status": {"status", "状态"},
}

CONTEXT_ANCHOR_TYPES = {"quotation", "scene", "case", "definition", "引语", "场景", "案例", "定义"}
DIRECT_QUOTE_RE = re.compile(r"[“「『\"]([^”」』\"\n]{2,})[”」』\"]")

EXPLANATION_RELATION = re.compile(
    r"(?:竞争|替代|互补|补充|阶段|条件|边界|抗辩|"
    r"rival|compet|alternat|complement|stage|condition|scope|objection)",
    re.IGNORECASE,
)
COMPETING_RELATION = re.compile(
    r"(?:竞争|替代|rival|compet|alternat)",
    re.IGNORECASE,
)
YES_VALUE = re.compile(r"^\s*(?:yes|y|true|是|同一)\s*$", re.IGNORECASE)
NO_VALUE = re.compile(r"^\s*(?:no|n|false|否|不同)\s*$", re.IGNORECASE)

QUALITATIVE_DIMENSIONS = {
    "narrative continuity": {"narrative continuity", "叙事连续性", "认知路径连续性"},
    "language economy": {"language economy", "语言凝练度", "表达凝练度"},
    "reader readability": {"reader readability", "读者可读性", "阅读可进入性"},
    "actor/action visibility": {
        "actor/action visibility",
        "actor action visibility",
        "行动主体可见性",
        "主体行动可见性",
    },
    "show-explain balance": {
        "show-explain balance",
        "show and explain balance",
        "展示解释平衡",
        "展示与解释平衡",
    },
}

QUALITATIVE_PASS_VERDICT = re.compile(
    r"(?:\bSTRONG\b|\bMET\b|\bREVISED\b|\bJUSTIFIED\b|"
    r"达标|有力|清楚|已修订|有据保留|通过)",
    re.IGNORECASE,
)
QUALITATIVE_FAIL_VERDICT = re.compile(
    r"(?:\bWEAK\b|\bFAIL\b|\bOPEN\b|\bNEEDS?\s+REVISION\b|\bREVISE\b|"
    r"不足|待修|待改|不达标|失败|未解决)",
    re.IGNORECASE,
)

PROSE_MODES = {"clear", "distinguished"}
DISTINGUISHED_SCENES = {"journal", "conference"}
MASTERY_DIMENSIONS = {
    "insight": {"insight", "洞见"},
    "thought": {"thought", "思想"},
    "logic": {"logic", "逻辑"},
    "elegance": {"elegance", "典雅", "文气", "典雅与文气"},
    "voice": {"voice", "辨识度", "作者声音"},
}
FIDELITY_ITEMS = {
    "facts": {"facts", "fact", "事实"},
    "numbers": {"numbers", "number", "数字", "数值"},
    "citations": {"citations", "citation", "引文", "引用"},
    "limitations": {"limitations", "limitation", "限制", "局限"},
    "counterevidence": {"counterevidence", "counter evidence", "反证", "不支持结果"},
    "boundaries": {"inference boundaries", "inference boundary", "推断边界", "范围条件"},
}


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value.lower())


def weak(value: str, minimum: int = 4) -> bool:
    cleaned = normalize(value)
    return not cleaned or cleaned in {normalize(item) for item in GENERIC} or len(cleaned) < minimum


def split_row(line: str) -> list[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|") and not text.endswith(r"\|"):
        text = text[:-1]
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in text:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            current.append(char)
            escaped = True
        elif char == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    cells.append("".join(current).strip())
    return cells


def separator(line: str) -> bool:
    cells = split_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)


def tables(text: str) -> list[tuple[list[str], list[list[str]]]]:
    lines = text.splitlines()
    found: list[tuple[list[str], list[list[str]]]] = []
    index = 0
    while index < len(lines) - 1:
        if lines[index].lstrip().startswith("|") and separator(lines[index + 1]):
            headers = split_row(lines[index])
            rows: list[list[str]] = []
            index += 2
            while index < len(lines) and lines[index].lstrip().startswith("|"):
                if not separator(lines[index]):
                    row = split_row(lines[index])
                    if len(row) < len(headers):
                        row += [""] * (len(headers) - len(row))
                    if any(cell.strip() for cell in row):
                        rows.append(row[: len(headers)])
                index += 1
            found.append((headers, rows))
            continue
        index += 1
    return found


def column(headers: list[str], aliases: set[str]) -> int | None:
    targets = {normalize(alias) for alias in aliases}
    for index, header in enumerate(headers):
        candidate = normalize(header)
        if candidate in targets:
            return index
    for index, header in enumerate(headers):
        candidate = normalize(header)
        if any(target in candidate or candidate in target for target in targets if target and candidate):
            return index
    return None


def find_table(
    text: str,
    columns: dict[str, set[str]],
) -> tuple[list[str], list[list[str]], dict[str, int]] | None:
    for headers, rows in tables(text):
        indexes = {name: column(headers, aliases) for name, aliases in columns.items()}
        if all(index is not None for index in indexes.values()):
            return headers, rows, {name: int(index) for name, index in indexes.items() if index is not None}
    return None


def status_ok(value: str) -> bool:
    return bool(PASS_STATUS.fullmatch(value)) and not UNRESOLVED_STATUS.search(value)


def negative(value: str) -> bool:
    return bool(re.search(r"^(?:no|none|false|0|无|否|没有|未发现|零)$", value.strip(), re.IGNORECASE))


def resolve_prose_mode(base: Path, explicit: str | None = None) -> str:
    if explicit in PROSE_MODES:
        return str(explicit)
    config: dict[str, object] = {}
    try:
        payload = json.loads((base / "workflow_config.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError):
        payload = {}
    if isinstance(payload, dict):
        config = payload
    configured = str(config.get("prose_mode") or "").strip().lower()
    if configured in PROSE_MODES:
        return configured
    scene = str(config.get("scene") or "").strip().lower()
    return "distinguished" if scene in DISTINGUISHED_SCENES else "clear"


def matching_named_row(
    rows: list[list[str]],
    index: int,
    aliases: set[str],
) -> list[str] | None:
    targets = {normalize(alias) for alias in aliases}
    return next(
        (
            row
            for row in rows
            if index < len(row)
            and any(
                target == normalize(row[index])
                or target in normalize(row[index])
                or normalize(row[index]) in target
                for target in targets
                if target and normalize(row[index])
            )
        ),
        None,
    )


def validate_distinguished_sections(text: str, issues: list[str]) -> dict[str, int]:
    """Validate the distinguished-mode sections inside academic_prose_audit.md.

    The enhancement pass, fidelity inventory, and five-dimension verdict live in
    the same audit artifact; independent aesthetic judgment is delegated to the
    audit-stage writing reviewer, so no separate blind-review artifacts exist.
    """
    coverage = {
        "enhancement_moves": 0,
        "fidelity_items": 0,
        "dimension_verdicts": 0,
    }

    enhancement = find_table(
        text,
        {
            "location": {"location", "位置"},
            "move": {"intellectual move", "思想动作", "认知动作"},
            "basis": {"evidence basis", "evidence/argument basis", "argument basis", "证据或推理依据", "证据依据"},
            "operation": {"style operation", "风格动作", "表达动作"},
            "final": {"final text", "最终文本", "定稿文本"},
            "fidelity": {"fidelity check", "忠实性核验", "保真核验"},
            "status": {"status", "状态"},
        },
    )
    if enhancement is None:
        issues.append("distinguished prose mode requires the Enhancement Log table in academic_prose_audit.md")
    else:
        _headers, rows, indexes = enhancement
        usable = [row for row in rows if any(not weak(cell, 1) for cell in row)]
        coverage["enhancement_moves"] = len(usable)
        if len(usable) < 3:
            issues.append(f"Enhancement Log has {len(usable)} usable rows; expected at least 3")
        for number, row in enumerate(usable, start=1):
            for name, index in indexes.items():
                value = row[index] if index < len(row) else ""
                if name == "status":
                    if not status_ok(value):
                        issues.append(f"Enhancement Log row {number} has unresolved status: {value or '<empty>'}")
                elif weak(value, 2 if name in {"location", "fidelity"} else 4):
                    issues.append(f"Enhancement Log row {number} has weak or placeholder {name}")

    fidelity = find_table(
        text,
        {
            "item": {"item", "项目"},
            "baseline": {"baseline inventory", "基线清单", "清单来源"},
            "revised": {"revised inventory", "增强版清单", "修订版清单"},
            "loss": {"loss count", "损失数", "丢失数"},
            "evidence": {"evidence", "证据"},
            "status": {"status", "状态"},
        },
    )
    if fidelity is None:
        issues.append("distinguished prose mode requires the Fidelity Inventory table in academic_prose_audit.md")
    else:
        _headers, rows, indexes = fidelity
        for label, aliases in FIDELITY_ITEMS.items():
            row = matching_named_row(rows, indexes["item"], aliases)
            if row is None:
                issues.append(f"Fidelity Inventory is missing item: {label}")
                continue
            loss = row[indexes["loss"]] if indexes["loss"] < len(row) else ""
            status = row[indexes["status"]] if indexes["status"] < len(row) else ""
            weak_fields = [
                name
                for name in ("baseline", "revised", "evidence")
                if indexes[name] >= len(row) or weak(row[indexes[name]], 3)
            ]
            if weak_fields or not negative(loss) or not status_ok(status):
                issues.append(f"Fidelity Inventory item is incomplete or records loss: {label}")
                continue
            coverage["fidelity_items"] += 1

    synthesis_columns = {
        "dimension": {"dimension", "维度"},
        "verdict": {"verdict", "结论"},
        "evidence": {"evidence", "证据"},
        "status": {"status", "状态"},
    }
    synthesis = None
    for headers, rows in tables(text):
        candidate_indexes = {
            name: column(headers, aliases)
            for name, aliases in synthesis_columns.items()
        }
        if not all(index is not None for index in candidate_indexes.values()):
            continue
        indexes = {
            name: int(index)
            for name, index in candidate_indexes.items()
            if index is not None
        }
        if any(
            matching_named_row(rows, indexes["dimension"], aliases) is not None
            for aliases in MASTERY_DIMENSIONS.values()
        ):
            synthesis = (headers, rows, indexes)
            break
    if synthesis is None:
        issues.append("distinguished prose mode requires the Dimension Synthesis table in academic_prose_audit.md")
    else:
        _headers, rows, indexes = synthesis
        satisfied = 0
        for label, aliases in MASTERY_DIMENSIONS.items():
            row = matching_named_row(rows, indexes["dimension"], aliases)
            if row is None:
                issues.append(f"Dimension Synthesis is missing dimension: {label}")
                continue
            verdict = row[indexes["verdict"]] if indexes["verdict"] < len(row) else ""
            evidence = row[indexes["evidence"]] if indexes["evidence"] < len(row) else ""
            status = row[indexes["status"]] if indexes["status"] < len(row) else ""
            if re.search(r"regress|worse|下降|退步", verdict, re.IGNORECASE):
                issues.append(f"Dimension Synthesis records regression: {label}")
            elif re.search(r"improv|better|met\b|提升|改进|达标|到位", verdict, re.IGNORECASE):
                satisfied += 1
            elif not re.search(r"same|equal|持平|不变", verdict, re.IGNORECASE):
                issues.append(f"Dimension Synthesis has invalid verdict for {label}: {verdict or '<empty>'}")
            if weak(evidence, 5) or not status_ok(status):
                issues.append(f"Dimension Synthesis is incomplete or unresolved: {label}")
        coverage["dimension_verdicts"] = satisfied
        if satisfied < 4:
            issues.append(f"only {satisfied} mastery dimensions are IMPROVED/MET; expected at least 4 of 5")
    return coverage


def validate_required_table(
    text: str,
    key: str,
    issues: list[str],
) -> tuple[list[list[str]], dict[str, int]] | None:
    spec = TABLE_SPECS[key]
    found = find_table(text, spec["columns"])
    if found is None:
        issues.append(f"academic_prose_audit.md is missing the {spec['label']} table")
        return None
    _headers, rows, indexes = found
    usable = [row for row in rows if any(not weak(cell, 1) for cell in row)]
    if len(usable) < int(spec["minimum"]):
        issues.append(
            f"{spec['label']} has {len(usable)} usable rows; expected at least {spec['minimum']}"
        )
    for number, row in enumerate(usable, start=1):
        for name, index in indexes.items():
            value = row[index] if index < len(row) else ""
            if name == "status":
                if not status_ok(value):
                    issues.append(f"{spec['label']} row {number} has unresolved or invalid status: {value or '<empty>'}")
            elif weak(
                value,
                1
                if name == "same_target"
                else 2
                if name in {"unit", "location", "action"}
                else 3,
            ):
                issues.append(f"{spec['label']} row {number} has weak or placeholder {name}")
    return usable, indexes


def canonical_title_change(value: str) -> str | None:
    patterns = (
        ("evidence-substantive", r"evidence[-_ ]?substantive|证据(?:性)?实质(?:性)?变更|实质改题"),
        ("surface", r"\bsurface\b|editorial|表层|编辑性|格式性"),
        ("establish", r"\bestablish(?:ed)?\b|建立|确立"),
        ("none", r"\bnone\b|no substantive change|无实质变更|未改题|不变"),
    )
    for label, pattern in patterns:
        if re.search(pattern, value, re.IGNORECASE):
            return label
    return None


def artifact_field_value(path: Path, aliases: set[str]) -> str:
    try:
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
    except OSError:
        return ""
    targets = {normalize(alias) for alias in aliases}
    for headers, rows in tables(text):
        field_index = column(headers, {"field", "字段", "项目"})
        content_index = column(headers, {"content", "内容"})
        if field_index is None or content_index is None:
            continue
        for row in rows:
            if max(field_index, content_index) >= len(row):
                continue
            field = normalize(row[field_index])
            if any(target in field or field in target for target in targets if target and field):
                return row[content_index].strip()
    return ""


def extract_manuscript_title(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        try:
            with zipfile.ZipFile(path) as archive:
                root = ElementTree.fromstring(archive.read("word/document.xml"))
        except (OSError, KeyError, zipfile.BadZipFile, ElementTree.ParseError):
            return ""
        paragraphs: list[tuple[str, str]] = []
        for paragraph in (node for node in root.iter() if node.tag.endswith("}p")):
            text = "".join(
                node.text or "" for node in paragraph.iter() if node.tag.endswith("}t")
            ).strip()
            if not text:
                continue
            style = ""
            for node in paragraph.iter():
                if node.tag.endswith("}pStyle"):
                    style = next(
                        (str(value) for key, value in node.attrib.items() if key.endswith("}val")),
                        "",
                    )
                    break
            paragraphs.append((style.lower(), text))
        titled = next((text for style, text in paragraphs if style in {"title", "标题"}), "")
        return titled or (paragraphs[0][1] if paragraphs else "")
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    if path.suffix.lower() in {".md", ".markdown"}:
        match = re.search(r"(?m)^#\s+(.+?)\s*$", text)
        return match.group(1).strip() if match else ""
    if path.suffix.lower() == ".tex":
        match = re.search(r"\\title(?:\[[^\]]*\])?\{(.+?)\}", text, re.DOTALL)
        if not match:
            return ""
        title = re.sub(r"\\(?:textbf|textit|emph|texorpdfstring)\*?\{([^{}]*)\}", r"\1", match.group(1))
        title = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?", " ", title)
        return re.sub(r"\s+", " ", title).strip()
    return ""


def validate_title_loop(
    base: Path,
    table: tuple[list[list[str]], dict[str, int]] | None,
    audit_text: str,
    manuscript_path: Path | None,
    issues: list[str],
) -> int:
    if table is None:
        return 0
    rows, indexes = table
    checkpoints: dict[str, list[str]] = {}
    for label, aliases in TITLE_CHECKPOINTS.items():
        row = matching_named_row(rows, indexes["checkpoint"], aliases)
        if row is None:
            issues.append(f"Title Revision Chain is missing checkpoint: {label}")
            continue
        checkpoints[label] = row

    def cell(row: list[str], key: str) -> str:
        index = indexes[key]
        return row[index].strip() if index < len(row) else ""

    raw_title_table = find_table(audit_text, TABLE_SPECS["title_loop"]["columns"])
    optional_indexes: dict[str, int] = {}
    if raw_title_table is not None:
        headers = raw_title_table[0]
        optional_indexes = {
            name: int(index)
            for name, aliases in TITLE_RHETORICAL_COLUMNS.items()
            if (
                index := next(
                    (
                        number
                        for number, header in enumerate(headers)
                        if normalize(header) in {normalize(alias) for alias in aliases}
                    ),
                    None,
                )
            ) is not None
        }
    if optional_indexes and set(optional_indexes) != set(TITLE_RHETORICAL_COLUMNS):
        issues.append(
            "AP.TITLE.BODY_ANCHOR_MISSING: Title Revision Chain must declare both Resonance Device and Body Explanation Move"
        )
    elif set(optional_indexes) == set(TITLE_RHETORICAL_COLUMNS):
        for label, row in checkpoints.items():
            resonance_index = optional_indexes["resonance"]
            body_index = optional_indexes["body_move"]
            resonance = row[resonance_index].strip() if resonance_index < len(row) else ""
            body_move = row[body_index].strip() if body_index < len(row) else ""
            no_resonance = bool(
                re.fullmatch(
                    r"\s*(?:none|n/?a|not[- ]applicable|无|不适用|无修辞装置)\s*",
                    resonance,
                    re.IGNORECASE,
                )
            )
            if not resonance:
                issues.append(
                    f"AP.TITLE.BODY_ANCHOR_MISSING: Title Revision Chain {label} has no Resonance Device disposition"
                )
            elif not no_resonance and not re.search(
                r"(?<![A-Za-z0-9_.-])MOVE-[A-Za-z0-9][A-Za-z0-9._-]*(?![A-Za-z0-9_.-])",
                body_move,
                re.IGNORECASE,
            ):
                issues.append(
                    f"AP.TITLE.BODY_ANCHOR_MISSING: Title Revision Chain {label} resonance is not fulfilled by a Body Explanation Move"
                )

    allowed_changes = {
        "question_commitment": {"establish"},
        "post_execution": {"none", "evidence-substantive"},
        "final": {"none", "surface"},
    }
    for label, row in checkpoints.items():
        change = canonical_title_change(cell(row, "change"))
        if change not in allowed_changes[label]:
            allowed = ", ".join(sorted(allowed_changes[label]))
            issues.append(f"Title Revision Chain checkpoint {label} must use change class: {allowed}")
        links = cell(row, "links")
        if label in {"question_commitment", "final"} and not TITLE_LINK_PATTERNS["problem"].search(links):
            issues.append(f"Title Revision Chain {label} must link a PO-* problem identity")
        if label in {"post_execution", "final"}:
            missing = [
                identity
                for identity in ("execution", "claim", "evidence")
                if not TITLE_LINK_PATTERNS[identity].search(links)
            ]
            if missing:
                issues.append(
                    f"Title Revision Chain checkpoint {label} lacks registered identities: "
                    + ", ".join(missing)
                )

    question_row = checkpoints.get("question_commitment")
    execution_row = checkpoints.get("post_execution")
    final_row = checkpoints.get("final")
    if question_row and execution_row:
        question_title = cell(question_row, "title")
        execution_title = cell(execution_row, "title")
        execution_change = canonical_title_change(cell(execution_row, "change"))
        same_semantic_title = normalize(question_title) == normalize(execution_title)
        if execution_change == "none" and not same_semantic_title:
            issues.append("post-execution title changed although its change class is none")
        if execution_change == "evidence-substantive" and same_semantic_title:
            issues.append("post-execution title is marked evidence-substantive but no substantive title change is recorded")
    if execution_row and final_row:
        execution_title = cell(execution_row, "title")
        final_title = cell(final_row, "title")
        final_change = canonical_title_change(cell(final_row, "change"))
        exact_same = execution_title.strip() == final_title.strip()
        if final_change == "none" and not exact_same:
            issues.append("final title changed although its change class is none")
        if final_change == "surface":
            basis = cell(final_row, "basis")
            if exact_same:
                issues.append("final title is marked surface change but no title change is recorded")
            if not (
                re.search(r"surface|editorial|punctuation|journal style|clarity|表层|编辑|标点|期刊格式|清晰", basis, re.IGNORECASE)
                and re.search(r"no substantive|does not change|不改变|未改变|不增添|不删除", basis, re.IGNORECASE)
            ):
                issues.append("a final surface title change must state the editorial operation and that problem, claim, and scope are unchanged")

    if final_row:
        recovery = cell(final_row, "recovery")
        recovery_requirements = (
            (r"problem|question|tension|问题|张力", "problem"),
            (r"answer|claim|finding|回答|主张|发现", "answer"),
            (r"scope|case|time|boundary|范围|案例|时间|边界", "scope"),
        )
        for pattern, label in recovery_requirements:
            if not re.search(pattern, recovery, re.IGNORECASE):
                issues.append(f"final title reader recovery does not recover the {label}")

    motivation_path = base / "confirmed_motivation.md"
    contribution_path = base / "confirmed_contribution.md"
    has_upstream_contract = motivation_path.exists() or contribution_path.exists()
    working_title = artifact_field_value(
        motivation_path,
        {"working title", "confirmed working title", "工作标题", "确认标题"},
    )
    calibrated_title = artifact_field_value(
        contribution_path,
        {"evidence-calibrated title", "evidence calibrated title", "证据校准标题", "执行后标题"},
    )
    if working_title and question_row and normalize(working_title) != normalize(cell(question_row, "title")):
        issues.append("Title Revision Chain question_commitment title does not match confirmed_motivation.md")
    if calibrated_title and execution_row and normalize(calibrated_title) != normalize(cell(execution_row, "title")):
        issues.append("Title Revision Chain post_execution title does not match confirmed_contribution.md")

    if has_upstream_contract and manuscript_path is not None and final_row:
        manuscript_title = extract_manuscript_title(manuscript_path)
        if not manuscript_title:
            issues.append("final manuscript source has no extractable title for Title Revision Chain comparison")
        elif normalize(manuscript_title) != normalize(cell(final_row, "title")):
            issues.append("Title Revision Chain final title does not match the manuscript title")
    return len(checkpoints)


def validate_context_anchor_bank(
    base: Path,
    manuscript_text: str,
    issues: list[str],
) -> int:
    """Validate the Context Anchor projection in the existing evidence bank.

    Source, Evidence, and Material registries remain authoritative. This check
    verifies that the evidence-bank projection is content-verified and recoverable.
    """

    bank_path = base / "evidence_bank.md"
    try:
        bank_text = bank_path.read_text(encoding="utf-8-sig", errors="ignore")
    except OSError:
        bank_text = ""
    found = find_table(bank_text, CONTEXT_ANCHOR_COLUMNS) if bank_text else None
    manuscript_quotes = [match.group(1).strip() for match in DIRECT_QUOTE_RE.finditer(manuscript_text)]
    if found is None:
        declared = bool(
            re.search(
                r"(?im)^#{1,6}\s*(?:Context Anchors?|上下文锚点|语境锚点)\s*$",
                bank_text,
            )
        )
        contract_path = base / ".avereth-prose" / "manuscript" / "manuscript_contract.json"
        try:
            contract = json.loads(contract_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError, UnicodeError):
            contract = {}
        current_profile = (
            isinstance(contract, dict)
            and str(contract.get("schema_version") or "").strip()
            == "avereth-manuscript-contract/v1"
            and str(contract.get("profile_version") or "").strip() == "1.1.0"
        )
        if manuscript_quotes and (declared or current_profile):
            issues.append(
                "AP.QUOTE.CONTEXT_MISSING: manuscript contains direct quotation(s) but evidence_bank.md has no Context Anchor table"
            )
        return 0
    _headers, rows, indexes = found
    registered = {str(value).upper() for value in discover_registered_ids(base)}
    seen: set[str] = set()
    quote_anchors: list[tuple[str, str, str]] = []
    for number, row in enumerate(rows, start=1):
        values = {
            label: row[index].strip() if index < len(row) else ""
            for label, index in indexes.items()
        }
        anchor_id = values.get("id", "").upper()
        if not re.fullmatch(r"ANCHOR-[A-Z0-9][A-Z0-9._-]*", anchor_id):
            issues.append(f"Context Anchor row {number} has invalid Anchor ID")
        elif anchor_id in seen:
            issues.append(f"Context Anchor row {number} repeats {anchor_id}")
        seen.add(anchor_id)
        anchor_type = normalize(values.get("type", ""))
        if anchor_type not in {normalize(value) for value in CONTEXT_ANCHOR_TYPES}:
            issues.append(f"Context Anchor {anchor_id or number} has unsupported type")
        authority = values.get("authority", "").upper()
        if authority not in registered:
            code = (
                "AP.QUOTE.CONTEXT_MISSING"
                if anchor_type in {"quotation", "definition", "引语", "定义"}
                else "AP.SCENE.UNBOUND"
            )
            issues.append(
                f"{code}: Context Anchor {anchor_id or number} has unregistered authority {authority or '<missing>'}"
            )
        for field_name in ("locator", "content", "problem", "logic", "function"):
            if weak(values.get(field_name, ""), 3):
                if anchor_type in {"quotation", "definition", "引语", "定义"}:
                    code = (
                        "AP.QUOTE.LOCATOR_MISSING"
                        if field_name == "locator"
                        else "AP.QUOTE.CONTEXT_MISSING"
                    )
                else:
                    code = "AP.SCENE.UNBOUND"
                issues.append(f"{code}: Context Anchor {anchor_id or number} has weak or empty {field_name}")
        if values.get("status", "").strip().lower() not in {"content-verified", "内容已核验"}:
            issues.append(f"Context Anchor {anchor_id or number} is not content-verified")
        if anchor_type in {"quotation", "引语", "definition", "定义"}:
            exact_span = values.get("content", "")
            quote_anchors.append((exact_span, values.get("locator", ""), values.get("qualifiers", "")))
            qualifiers = [
                item.strip()
                for item in re.split(r"[;；,，]", values.get("qualifiers", ""))
                if item.strip()
            ]
            missing_qualifiers = [item for item in qualifiers if item not in exact_span]
            if missing_qualifiers:
                issues.append(
                    f"AP.QUOTE.QUALIFIER_LOSS: Context Anchor {anchor_id or number} exact span omits protected qualifiers: "
                    + ", ".join(missing_qualifiers)
                )
    for quote in manuscript_quotes:
        matching = [item for item in quote_anchors if normalize(item[0]) == normalize(quote)]
        if not matching:
            issues.append(
                f"AP.QUOTE.CONTEXT_MISSING: manuscript quotation has no content-verified Context Anchor: {quote}"
            )
            continue
        locator = matching[0][1]
        if locator and normalize(locator) not in normalize(manuscript_text):
            issues.append(
                f"AP.QUOTE.LOCATOR_MISSING: manuscript quotation omits its registered locator: {locator}"
            )
    return len(rows)


def validate_narrative_stage_coverage(
    table: tuple[list[list[str]], dict[str, int]] | None,
    issues: list[str],
) -> int:
    if table is None:
        return 0
    rows, indexes = table
    covered = 0
    for label, aliases in NARRATIVE_STAGES.items():
        row = matching_named_row(rows, indexes["stage"], aliases)
        if row is None:
            issues.append(f"Narrative Wrap is missing stage: {label}")
            continue
        covered += 1
    return covered


def validate_architecture_coverage(
    table: tuple[list[list[str]], dict[str, int]] | None,
    issues: list[str],
) -> int:
    if table is None:
        return 0
    rows, indexes = table
    covered = 0
    for label, aliases in ARCHITECTURE_UNITS.items():
        row = matching_named_row(rows, indexes["unit"], aliases)
        if row is None:
            issues.append(f"Outer Architecture is missing unit: {label}")
            continue
        covered += 1
    return covered


def validate_explanation_role_classification(
    table: tuple[list[list[str]], dict[str, int]] | None,
    issues: list[str],
) -> int:
    if table is None:
        return 0
    rows, indexes = table
    classified = 0
    for number, row in enumerate(rows, start=1):
        relation = row[indexes["relation"]] if indexes["relation"] < len(row) else ""
        same_target = (
            row[indexes["same_target"]]
            if indexes["same_target"] < len(row)
            else ""
        )
        if not (YES_VALUE.search(same_target) or NO_VALUE.search(same_target)):
            issues.append(
                "Strong Objection/Explanation Role row "
                f"{number} must record Same Outcome/Stage? as YES or NO"
            )
            continue
        if not EXPLANATION_RELATION.search(relation):
            issues.append(
                "Strong Objection/Explanation Role row "
                f"{number} does not classify its relation to the main argument"
            )
            continue
        if NO_VALUE.search(same_target) and COMPETING_RELATION.search(relation):
            issues.append(
                "Strong Objection/Explanation Role row "
                f"{number} labels different outcomes/stages as competing"
            )
            continue
        classified += 1
    return classified


def validate_qualitative_feedback(text: str, issues: list[str]) -> int:
    found = find_table(
        text,
        {
            "dimension": {"dimension", "维度"},
            "verdict": {"verdict", "结论", "判决"},
            "evidence": {
                "manuscript evidence",
                "evidence",
                "稿件证据",
                "正文证据",
            },
            "feedback": {
                "reader feedback",
                "独立读者反馈",
                "读者反馈",
            },
            "decision": {
                "revision/decision",
                "revision",
                "decision",
                "修改处置",
                "修订或决定",
            },
            "status": {"status", "状态"},
        },
    )
    if found is None:
        issues.append(
            "academic_prose_audit.md is missing the qualitative prose-feedback table"
        )
        return 0
    _headers, rows, indexes = found
    covered = 0
    for label, aliases in QUALITATIVE_DIMENSIONS.items():
        row = matching_named_row(rows, indexes["dimension"], aliases)
        if row is None:
            issues.append(f"qualitative prose feedback is missing dimension: {label}")
            continue
        verdict = row[indexes["verdict"]] if indexes["verdict"] < len(row) else ""
        evidence = row[indexes["evidence"]] if indexes["evidence"] < len(row) else ""
        feedback = row[indexes["feedback"]] if indexes["feedback"] < len(row) else ""
        decision = row[indexes["decision"]] if indexes["decision"] < len(row) else ""
        status = row[indexes["status"]] if indexes["status"] < len(row) else ""
        if (
            QUALITATIVE_FAIL_VERDICT.search(verdict)
            or not QUALITATIVE_PASS_VERDICT.search(verdict)
            or weak(evidence, 5)
            or weak(feedback, 6)
            or weak(decision, 4)
            or not status_ok(status)
        ):
            issues.append(
                f"qualitative prose feedback is incomplete, weak, or unresolved: {label}"
            )
            continue
        covered += 1
    return covered


def validate_reader_test(text: str, issues: list[str]) -> int:
    found = find_table(
        text,
        {
            "field": {"field", "字段", "项目"},
            "content": {"content", "内容", "复述结果"},
            "evidence": {"evidence/location", "evidence", "location", "证据位置", "证据或位置"},
        },
    )
    if found is None:
        issues.append("academic_prose_audit.md is missing the independent reader-restatement table")
        return 0
    _headers, rows, indexes = found
    field_index = indexes["field"]
    content_index = indexes["content"]
    evidence_index = indexes["evidence"]
    normalized_rows = {
        normalize(row[field_index]): row
        for row in rows
        if field_index < len(row) and not weak(row[field_index], 1)
    }
    covered = 0
    for label, aliases in READER_FIELDS.items():
        targets = {normalize(alias) for alias in aliases}
        row = next(
            (
                candidate
                for field, candidate in normalized_rows.items()
                if any(target in field or field in target for target in targets if target and field)
            ),
            None,
        )
        if row is None:
            issues.append(f"independent reader test is missing field: {label}")
            continue
        content = row[content_index] if content_index < len(row) else ""
        evidence = row[evidence_index] if evidence_index < len(row) else ""
        if weak(content, 6) or weak(evidence, 3):
            issues.append(f"independent reader test has weak content or location: {label}")
            continue
        covered += 1
    return covered


def scan_risks(text: str) -> list[RiskHit]:
    hits: list[RiskHit] = []
    for pattern in RISK_PATTERNS:
        for match in pattern.regex.finditer(text):
            snippet = re.sub(r"\s+", " ", match.group(0)).strip()
            line = text.count("\n", 0, match.start()) + 1
            unit_start = max(
                text.rfind(delimiter, 0, match.start())
                for delimiter in ("。", "！", "？", ".", "!", "?", "\n")
            ) + 1
            hits.append(RiskHit(pattern.key, pattern.label, snippet, line, unit_start))
    return hits


MATERIAL_ANCHOR_PREFIXES = frozenset(
    prefix for prefixes in ANCHOR_PREFIXES.values() for prefix in prefixes
)
AFTER_CLAIM_RE = re.compile(
    r"(?:after(?:\s+the)?\s+claim|post[- ]claim|主张(?:之)?后|判断(?:之)?后)",
    re.IGNORECASE,
)
SINGLE_PLACEMENT_RE = re.compile(
    r"(?:once|single|only\s+here|deduplicat|no\s+duplicate|"
    r"一次|一处|唯一|仅此处|去重|无重复|删除重复)",
    re.IGNORECASE,
)


def _registered_identity(
    cell: str, *, allowed_prefixes: frozenset[str], registered_ids: frozenset[str]
) -> str | None:
    identities = {
        match.group(0).upper()
        for match in IDENTITY_RE.finditer(cell)
        if match.group(0).split("-", 1)[0].upper() in allowed_prefixes
    }
    if len(identities) != 1:
        return None
    identity = next(iter(identities))
    return identity if identity in registered_ids else None


def validate_risk_dispositions(
    base: Path, text: str, hits: list[RiskHit], issues: list[str]
) -> int:
    if not hits:
        return 0
    found = find_table(
        text,
        {
            "trigger": {"trigger", "risk trigger", "触发项", "风险表达"},
            "location": {"location", "位置"},
            "decision": {"decision", "处置", "决定"},
            "boundary": {"boundary id", "边界编号", "边界 id"},
            "anchor": {"anchor id", "material anchor", "材料锚点", "锚点编号"},
            "claim": {"claim id", "主张编号"},
            "claim_delta": {"claim delta", "主张变化", "命题变化"},
            "placement": {"placement", "full-statement location", "安置位置", "完整说明位置"},
            "dedup": {"dedup record", "deduplication", "去重记录", "重复处置"},
            "reason": {"reason", "理由"},
            "final": {"final text", "最终文本", "定稿文本"},
            "status": {"status", "状态"},
        },
    )
    if found is None:
        issues.append("manuscript has review-trigger phrases but academic_prose_audit.md lacks the risk-disposition table")
        return 0
    _headers, rows, indexes = found
    covered = 0
    used_rows: set[int] = set()
    registered_ids = discover_registered_ids(base)
    boundary_occurrences: dict[str, set[tuple[int, str, str]]] = {}
    for occurrence, hit in enumerate(hits, start=1):
        candidates: list[tuple[int, str, str, str]] = []
        matched_errors: list[str] = []
        for row_number, row in enumerate(rows):
            if row_number in used_rows:
                continue
            trigger = row[indexes["trigger"]] if indexes["trigger"] < len(row) else ""
            location = row[indexes["location"]] if indexes["location"] < len(row) else ""
            decision = row[indexes["decision"]] if indexes["decision"] < len(row) else ""
            boundary = row[indexes["boundary"]] if indexes["boundary"] < len(row) else ""
            anchor = row[indexes["anchor"]] if indexes["anchor"] < len(row) else ""
            claim = row[indexes["claim"]] if indexes["claim"] < len(row) else ""
            claim_delta = row[indexes["claim_delta"]] if indexes["claim_delta"] < len(row) else ""
            placement = row[indexes["placement"]] if indexes["placement"] < len(row) else ""
            dedup = row[indexes["dedup"]] if indexes["dedup"] < len(row) else ""
            reason = row[indexes["reason"]] if indexes["reason"] < len(row) else ""
            final = row[indexes["final"]] if indexes["final"] < len(row) else ""
            status = row[indexes["status"]] if indexes["status"] < len(row) else ""
            trigger_matches = (
                hit.key in trigger.lower()
                or (
                    normalize(hit.snippet)
                    and normalize(hit.snippet) in normalize(trigger)
                )
            )
            final_matches = (
                normalize(hit.snippet)
                and normalize(hit.snippet) in normalize(final)
            )
            if not (trigger_matches and final_matches):
                continue
            row_anchor = _registered_identity(
                anchor,
                allowed_prefixes=MATERIAL_ANCHOR_PREFIXES,
                registered_ids=registered_ids,
            )
            row_claim = _registered_identity(
                claim,
                allowed_prefixes=CLAIM_PREFIXES,
                registered_ids=registered_ids,
            )
            row_boundary = boundary.strip().upper()
            error = ""
            if decision.strip().upper() != "KEEP-WITH-MATERIAL-ANCHOR":
                error = "retained risk text must use KEEP-WITH-MATERIAL-ANCHOR"
            elif not BOUNDARY_ID_RE.fullmatch(row_boundary):
                error = "KEEP-WITH-MATERIAL-ANCHOR requires one stable B-* Boundary ID"
            elif row_anchor is None:
                error = "KEEP-WITH-MATERIAL-ANCHOR requires one registered material Anchor ID"
            elif row_claim is None:
                error = "KEEP-WITH-MATERIAL-ANCHOR requires one registered Claim ID"
            elif weak(claim_delta, 5) or normalize(claim_delta) in {"none", "n/a", "无", "不变"}:
                error = "KEEP-WITH-MATERIAL-ANCHOR requires a substantive Claim Delta"
            elif FORBIDDEN_ACTIVATION_RE.search(reason + " " + claim_delta):
                error = "imagined objections, comprehensiveness, and generic caution cannot activate retained prose"
            elif weak(location, 2) or weak(reason, 3) or weak(final, 3) or not status_ok(status):
                error = "retained risk row has weak content or unresolved status"
            elif not AFTER_CLAIM_RE.search(placement):
                error = "retained boundary must be placed after the claim it changes"
            elif not SINGLE_PLACEMENT_RE.search(placement + " " + dedup):
                error = "retained boundary must record one full-statement location and deduplication"
            if error:
                matched_errors.append(error)
                continue
            candidates.append(
                (row_number, row_boundary, normalize(final), normalize(location + " " + placement))
            )
        if not candidates:
            detail = matched_errors[0] if matched_errors else "no matching current-text row"
            issues.append(
                "risk trigger occurrence lacks a strict material-anchor disposition: "
                f"{hit.key} occurrence {occurrence}, manuscript line {hit.line}; {detail}"
            )
            continue
        row_number, boundary_id, final_key, location_key = candidates[0]
        used_rows.add(row_number)
        boundary_occurrences.setdefault(boundary_id, set()).add(
            (hit.unit_start, final_key, location_key)
        )
        covered += 1
    for boundary_id, occurrences in sorted(boundary_occurrences.items()):
        if len(occurrences) > 1:
            issues.append(
                f"boundary {boundary_id} has more than one full retained text/location"
            )
    return covered


def locate_manuscript(base: Path, explicit: Path | None) -> Path | None:
    if explicit is not None:
        candidate = explicit if explicit.is_absolute() else base / explicit
        return candidate.resolve() if candidate.exists() and candidate.is_file() else None
    candidates = (
        base / "revised_manuscript.md",
        base / "manuscript.md",
        base / "paper.md",
        base / "draft.md",
        base / "final_paper" / "main.tex",
        base / "final_paper" / "main.md",
        base / "final_paper" / "main.docx",
        base / "final_paper" / "manuscript.md",
        base / "final_paper" / "manuscript.docx",
        base / "final_paper" / "paper.tex",
    )
    for candidate in candidates:
        if candidate.exists() and candidate.is_file() and candidate.stat().st_size:
            return candidate.resolve()
    return None


def reader_text(path: Path) -> str:
    """Return reader-facing prose while excluding common source scaffolding."""
    if path.suffix.lower() == ".docx":
        try:
            with zipfile.ZipFile(path) as archive:
                root = ElementTree.fromstring(archive.read("word/document.xml"))
        except (OSError, KeyError, zipfile.BadZipFile, ElementTree.ParseError):
            return ""
        return "\n".join(
            node.text or ""
            for node in root.iter()
            if node.tag.endswith("}t") and (node.text or "").strip()
        )
    text = path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix.lower() == ".tex":
        text = re.sub(r"(?<!\\)%[^\n]*", "", text)
        if r"\begin{document}" in text:
            text = text.split(r"\begin{document}", 1)[1]
        for marker in (r"\begin{thebibliography}", r"\bibliography{", r"\printbibliography"):
            if marker in text:
                text = text.split(marker, 1)[0]
        text = re.sub(r"\\(?:cite|parencite|textcite|autocite|ref|label|url|href)\*?\{[^{}]*\}", " ", text)
        text = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?", " ", text)
        return text
    if path.suffix.lower() in {".md", ".markdown"}:
        fence = re.escape(chr(96) * 3)
        text = re.sub(fence + r".*?" + fence, " ", text, flags=re.DOTALL)
        text = re.split(r"(?im)^#{1,6}\s*(?:参考文献|references|bibliography)\s*$", text, maxsplit=1)[0]
    return text


def prose_unit_count(text: str) -> int:
    """Count reader-facing CJK characters plus Latin/digit word units deterministically."""
    cjk = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]+(?:['’-][A-Za-z]+)?|\d+(?:\.\d+)?", text))
    return cjk + latin


def _revision_clarity_action_issues(
    actions: object,
    *,
    expected_delta: int,
    registered_ids: frozenset[str],
    registered_terms: frozenset[str],
) -> list[str]:
    """Validate the revision-contract view of an argument clarity ledger."""
    found: list[str] = []
    if not isinstance(actions, list) or not actions:
        return ["clarity_actions must be a non-empty array"]
    ledger_delta = 0
    for index, record in enumerate(actions, start=1):
        field = f"clarity_actions[{index}]"
        if not isinstance(record, dict):
            found.append(f"{field} must be an object")
            continue
        unexpected = set(record) - CLARITY_ACTION_KEYS
        if unexpected:
            found.append(
                f"{field} has unsupported fields: " + ", ".join(sorted(unexpected))
            )
            continue
        action = str(record.get("action") or "").strip().upper()
        if action not in CLARITY_ACTIONS:
            found.append(f"{field}.action must be one of {sorted(CLARITY_ACTIONS)}")
        prose_delta = record.get("prose_delta")
        if not isinstance(prose_delta, int) or isinstance(prose_delta, bool):
            found.append(f"{field}.prose_delta must be an integer")
            continue
        ledger_delta += prose_delta
        if prose_delta > 0 and action not in POSITIVE_GROWTH_ACTIONS:
            found.append(f"{field}: only BRIDGE or DEFINE may record positive prose growth")
        if action not in POSITIVE_GROWTH_ACTIONS:
            continue
        claim_id = _registered_identity(
            str(record.get("claim_id") or ""),
            allowed_prefixes=CLAIM_PREFIXES,
            registered_ids=registered_ids,
        )
        if claim_id is None:
            found.append(f"{field}.claim_id must be a registered Claim ID")
        source_kind = str(record.get("source_kind") or "").strip().lower()
        source_anchor = str(record.get("source_anchor") or "").strip()
        if source_kind not in CLARITY_SOURCE_KINDS:
            found.append(
                f"{field}.source_kind must be one of {sorted(CLARITY_SOURCE_KINDS)}"
            )
        elif source_kind == "warrant" and source_anchor != "warrant":
            found.append(f"{field}.source_anchor must be warrant for source_kind=warrant")
        elif source_kind == "explanation_path" and not (
            re.fullmatch(r"explanation_path:[1-9]\d*", source_anchor)
            or source_anchor.upper() in registered_ids
        ):
            found.append(
                f"{field}.source_anchor must name an explanation_path step or registered identity"
            )
        elif source_kind == "registered_term" and source_anchor not in registered_terms:
            found.append(
                f"{field}.source_anchor must exactly match expression_budget.registered_terms"
            )
        if weak(str(record.get("reader_understanding") or ""), 6):
            found.append(f"{field}.reader_understanding must state the reader gain")
        for confirmation in (
            "no_new_fact",
            "no_new_citation",
            "no_inference_strengthening",
        ):
            if record.get(confirmation) is not True:
                found.append(f"{field}.{confirmation} must be true")
    if ledger_delta != expected_delta:
        found.append(
            f"clarity_actions prose_delta total ({ledger_delta}) does not match actual delta ({expected_delta})"
        )
    return found


def validate_revision_net_growth(
    base: Path,
    current_text: str,
    issues: list[str],
    warnings: list[str] | None = None,
) -> int:
    """Gate unsupported growth while allowing evidence-bound clarity additions."""
    contract_path = base / "revision_contract.json"
    if not contract_path.is_file():
        return 0
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return 0  # The controller's revision-contract validator owns malformed contracts.
    if not isinstance(contract, dict):
        return 0
    baseline = contract.get("baseline")
    changes = contract.get("requested_changes")
    if not isinstance(baseline, dict) or not isinstance(changes, list) or not changes:
        return 0
    snapshot_rel = str(baseline.get("snapshot_path") or "").strip()
    if not snapshot_rel:
        return 0
    snapshot = (base / snapshot_rel).resolve()
    try:
        snapshot.relative_to(base.resolve())
    except ValueError:
        return 0
    if not snapshot.is_file():
        return 0
    baseline_text = reader_text(snapshot)
    baseline_units = prose_unit_count(baseline_text)
    delta = prose_unit_count(current_text) - baseline_units
    if delta <= 0:
        return delta

    change_classes = {
        str(item.get("change_class") or "").strip().lower().replace("-", "_")
        for item in changes
        if isinstance(item, dict)
    }
    if change_classes == {"surface"}:
        issues.append(
            f"surface-only revision has positive net prose growth ({delta} units); "
            "DELETE, REPLACE, or MOVE until net growth is non-positive"
        )
        return delta

    budget = contract.get("expression_budget")
    registered_ids = discover_registered_ids(base)
    if change_classes and change_classes.issubset({"surface", "argument"}):
        if not isinstance(budget, dict):
            issues.append(
                f"argument revision has positive net prose growth ({delta} units) without "
                "expression_budget.clarity_actions"
            )
            return delta
        raw_registered_terms = budget.get("registered_terms", [])
        registered_terms = (
            frozenset(str(item).strip() for item in raw_registered_terms if str(item).strip())
            if isinstance(raw_registered_terms, list)
            else frozenset()
        )
        clarity_issues = _revision_clarity_action_issues(
            budget.get("clarity_actions"),
            expected_delta=delta,
            registered_ids=registered_ids,
            registered_terms=registered_terms,
        )
        if not isinstance(raw_registered_terms, list):
            clarity_issues.insert(0, "registered_terms must be an array when supplied")
        try:
            soft_limits = compile_clarity_growth_soft_limits(
                budget.get("clarity_growth_soft_limits")
            )
        except ProsePacketError as exc:
            clarity_issues.append(str(exc))
            soft_limits = None
        scope = str(
            budget.get("clarity_scope") or budget.get("scope") or "section"
        ).strip().lower()
        if scope not in {"paragraph", "section"}:
            clarity_issues.append("clarity_scope must be paragraph or section")
        issues.extend(
            f"argument revision clarity ledger: {issue}" for issue in clarity_issues
        )
        if not clarity_issues and warnings is not None and soft_limits is not None:
            threshold = soft_limits[f"{scope}_ratio"]
            growth_ratio = delta / baseline_units if baseline_units else 1.0
            if growth_ratio > threshold:
                warnings.append(
                    f"argument clarity {scope} growth ratio {growth_ratio:.1%} exceeds "
                    f"the soft {threshold:.0%} review threshold"
                )
        return delta

    if not isinstance(budget, dict):
        issues.append(
            f"revision has positive net prose growth ({delta} units) without an expression_budget"
        )
        return delta
    evidence_delta = _registered_identity(
        str(budget.get("evidence_delta") or ""),
        allowed_prefixes=EVIDENCE_PREFIXES,
        registered_ids=registered_ids,
    )
    claim_delta = _registered_identity(
        str(budget.get("claim_delta") or ""),
        allowed_prefixes=CLAIM_PREFIXES,
        registered_ids=registered_ids,
    )
    reader_update = str(budget.get("reader_update") or "").strip()
    if evidence_delta is None or claim_delta is None or weak(reader_update, 6):
        issues.append(
            f"revision has positive net prose growth ({delta} units); expression_budget must "
            "name registered evidence_delta and claim_delta identities plus a substantive reader_update"
        )
    return delta


def check_academic_prose(
    base: Path,
    manuscript: Path | None = None,
    *,
    require_manuscript: bool = False,
    prose_mode: str | None = None,
) -> CheckResult:
    base = base.resolve()
    audit_path = base / "academic_prose_audit.md"
    resolved_mode = resolve_prose_mode(base, prose_mode)
    issues: list[str] = []
    warnings: list[str] = []
    coverage: dict[str, int] = {}
    title_loop: tuple[list[list[str]], dict[str, int]] | None = None
    try:
        audit_text = audit_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        audit_text = ""
        issues.append("missing academic_prose_audit.md")

    if audit_text:
        if not re.search(r"Overall Status:\s*(?:\*\*)?PASS\b|总体状态[:：]\s*(?:\*\*)?通过", audit_text, re.IGNORECASE):
            issues.append("academic_prose_audit.md does not record Overall Status: PASS")
        title_loop = validate_required_table(audit_text, "title_loop", issues)
        architecture = validate_required_table(audit_text, "architecture", issues)
        coverage["architecture_units"] = validate_architecture_coverage(
            architecture,
            issues,
        )
        explanation_roles = validate_required_table(
            audit_text,
            "explanation_roles",
            issues,
        )
        coverage["explanation_roles"] = validate_explanation_role_classification(
            explanation_roles,
            issues,
        )
        boundary_placement = validate_required_table(
            audit_text,
            "boundary_placement",
            issues,
        )
        coverage["boundary_placements"] = (
            len(boundary_placement[0]) if boundary_placement else 0
        )
        narrative = validate_required_table(audit_text, "narrative_wrap", issues)
        coverage["narrative_stages"] = validate_narrative_stage_coverage(
            narrative,
            issues,
        )
        reverse = validate_required_table(audit_text, "reverse_outline", issues)
        for key in (
            "paragraph",
            "sentence",
            "claim_strength",
            "dialogue_voice",
            "substantive_revision",
        ):
            result = validate_required_table(audit_text, key, issues)
            coverage[key] = len(result[0]) if result else 0
        coverage["reverse_outline"] = len(reverse[0]) if reverse else 0
        if reverse:
            rows, indexes = reverse
            locations = {
                normalize(row[indexes["location"]])
                for row in rows
                if indexes["location"] < len(row) and not weak(row[indexes["location"]], 2)
            }
            if len(locations) < 3:
                issues.append("reverse outline must cover at least three distinct manuscript locations")
        coverage["reader_test"] = validate_reader_test(audit_text, issues)
        coverage["qualitative_dimensions"] = validate_qualitative_feedback(
            audit_text,
            issues,
        )
        if resolved_mode == "distinguished":
            coverage.update(validate_distinguished_sections(audit_text, issues))

    manuscript_path = locate_manuscript(base, manuscript)
    if audit_text:
        coverage["title_checkpoints"] = validate_title_loop(
            base,
            title_loop,
            audit_text,
            manuscript_path,
            issues,
        )
    hits: list[RiskHit] = []
    if manuscript_path is None:
        if require_manuscript:
            issues.append("no final manuscript source found for live prose review")
    else:
        body = reader_text(manuscript_path)
        coverage["context_anchors"] = validate_context_anchor_bank(base, body, issues)
        hits = scan_risks(body)
        coverage["risk_dispositions"] = validate_risk_dispositions(base, audit_text, hits, issues)
        coverage["revision_net_growth"] = validate_revision_net_growth(
            base, body, issues, warnings
        )

    return CheckResult(
        audit_path=audit_path,
        manuscript_path=manuscript_path,
        prose_mode=resolved_mode,
        issues=list(dict.fromkeys(issues)),
        warnings=list(dict.fromkeys(warnings)),
        hits=hits,
        coverage=coverage,
    )


def render_report(result: CheckResult) -> str:
    lines = [
        "# Academic Prose Check",
        "",
        f"Audit: {result.audit_path.name}",
        f"Prose mode: {result.prose_mode}",
        f"Manuscript: {result.manuscript_path if result.manuscript_path else 'not located'}",
        "",
        f"Status: {'PASS' if result.ok else 'FAIL'}",
        "",
        "## Audit Coverage",
    ]
    coverage_keys = [
        "title_checkpoints",
        "architecture_units",
        "explanation_roles",
        "boundary_placements",
        "narrative_stages",
        "reverse_outline",
        "paragraph",
        "sentence",
        "claim_strength",
        "dialogue_voice",
        "substantive_revision",
        "reader_test",
        "qualitative_dimensions",
        "risk_dispositions",
        "revision_net_growth",
        "context_anchors",
    ]
    if result.prose_mode == "distinguished":
        coverage_keys += ["enhancement_moves", "fidelity_items", "dimension_verdicts"]
    for key in coverage_keys:
        lines.append(f"- {key}: {result.coverage.get(key, 0)}")
    lines.extend(["", "## Contextual Review Triggers"])
    if result.hits:
        for hit in result.hits:
            lines.append(f"- {hit.key} ({hit.label}), line {hit.line}: {hit.snippet}")
    else:
        lines.append("- None detected in the located manuscript source.")
    if result.warnings:
        lines.extend(["", "## Non-blocking Diagnostics"])
        lines.extend(f"- {warning}" for warning in result.warnings)
    if result.issues:
        lines.extend(["", "## Blocking Issues"])
        lines.extend(f"- {issue}" for issue in result.issues)
        lines.extend(
            [
                "",
                "Return to the prose pass. Fix the manuscript or record a contextual, evidence-based justification, then rerun this check.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "The title-revision chain, outer architecture, explanation roles, boundary placement, Narrative Wrap, argument outline, load-bearing paragraphs, sentence information flow, claim strength, dialogue/voice audit, substantive-revision propagation, terminology decisions, qualitative prose feedback, and independent reader test are closed.",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="CNKI-Paper output directory")
    parser.add_argument("--manuscript", type=Path, help="Explicit manuscript path, absolute or relative to output directory")
    parser.add_argument("--require-manuscript", action="store_true", help="Fail when no final manuscript source can be located")
    parser.add_argument("--prose-mode", choices=sorted(PROSE_MODES), help="Override config-derived prose mode")
    parser.add_argument("--markdown", action="store_true", help="Compatibility flag; output is Markdown")
    parser.add_argument("--write", action="store_true", help="Write academic_prose_check.md into the output directory")
    args = parser.parse_args()

    result = check_academic_prose(
        args.path,
        args.manuscript,
        require_manuscript=args.require_manuscript,
        prose_mode=args.prose_mode,
    )
    report = render_report(result)
    print(report, end="")
    if args.write:
        args.path.resolve().mkdir(parents=True, exist_ok=True)
        (args.path.resolve() / "academic_prose_check.md").write_text(report, encoding="utf-8")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
