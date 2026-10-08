#!/usr/bin/env python3
"""Regression tests for the reader-oriented academic-prose gate."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]


def load_module(name: str, filename: str):
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


prose = load_module("academic_prose_check", "academic_prose_check.py")


DISTINGUISHED_SECTIONS = """
## 增强登记表

| Location | Intellectual Move | Evidence Basis | Style Operation | Final Text | Fidelity Check | Status |
|---|---|---|---|---|---|---|
| 引言第一段 | 将一般话题改写为平台接入与响应差异之间的经验张力 | 工单分组结果和既有研究对平均效应的争议 | 用对照句压缩问题并以短句收束 | 平台接入并不自动带来更快回应，差异首先出现在责任配置方式上。 | 事实和范围条件均保留 | PASS |
| 结果第一节 | 把两组结果压缩为条件关系而非普遍因果 | 分组统计与过程材料只支持观察场景中的相关机制 | 先报告结果再用中句解释含义 | 在共享权限组中，响应时间更短；过程材料进一步显示责任配置可能解释这一差异。 | 数字和因果边界均保留 | PASS |
| 结论第一段 | 将局部发现提升为有范围条件的机制判断 | 单市材料、观察性设计和过程记录共同限定外推 | 以判断句回扣贡献并明确边界 | 因而，平台效应更适合被理解为一种受责任配置约束的条件机制。 | 局限和反证均保留 | PASS |

## 忠实性清单

| Item | Baseline Inventory | Revised Inventory | Loss Count | Evidence | Status |
|---|---|---|---:|---|---|
| Facts | 三项事实清单 | 三项事实清单 | 0 | 逐项比对正文位置 | PASS |
| Numbers | 两组统计数字 | 两组统计数字 | 0 | 结果表与正文复核 | PASS |
| Citations | 十二条正文引文 | 十二条正文引文 | 0 | 引用库键值比对 | PASS |
| Limitations | 单市与观察性限制 | 单市与观察性限制 | 0 | 结论限制段复核 | PASS |
| Counterevidence | 不支持结果一项 | 不支持结果一项 | 0 | 结果第二节复核 | PASS |
| Inference boundaries | 不作普遍因果外推 | 不作普遍因果外推 | 0 | 主张力度表复核 | PASS |

## 五维判决

| Dimension | Verdict | Evidence | Status |
|---|---|---|---|
| Insight | IMPROVED | 问题由背景话题转为可验证张力 | PASS |
| Thought | IMPROVED | 条件机制替代技术决定论概括 | PASS |
| Logic | MET | 结果、担保和边界已形成连续链条 | PASS |
| Elegance | IMPROVED | 判断句与解释句形成克制节奏 | PASS |
| Voice | SAME | 作者立场清楚但没有刻意强化 | PASS |
"""


def valid_audit(risk_rows: str = "", distinguished: bool = False) -> str:
    extra = DISTINGUISHED_SECTIONS if distinguished else ""
    return f"""# Academic Prose Audit

## 标题回环
| Checkpoint | Title | Problem/Claim/Evidence Links | Scope/Case/Time | Change Class | Revision Basis | Reader Recovery | Status |
|---|---|---|---|---|---|---|---|
| question_commitment | 责任配置如何约束数字平台的回应效应 | PO-01 | 单市部门；观察期内的平台回应 | establish；建立 | 从确认问题压缩标题，不预断机制成立 | 可复原待解释问题及单市观察范围 | PASS |
| post_execution | 责任配置如何约束数字平台的回应效应 | EXE-01；CLM-01；EV-01 | 单市部门；观察期内的平台回应 | none；无实质变更 | 执行证据支持原问题范围，不增添新结果承诺 | 可复原证据支持的回答、主张边界与单市范围 | PASS |
| final | 责任配置如何约束数字平台的回应效应 | PO-01；EXE-01；CLM-01；EV-01 | 单市部门；观察期内的平台回应 | none；无实质变更 | 定稿标题沿用证据校准标题 | 读者可从标题复原问题、回答与单市案例范围 | PASS |

## 外架构与章节角色
| Unit | Location | Role/Reader Question | Controlling Claim | Key Terms | Link to Whole/Previous | Revision Decision | Status |
|---|---|---|---|---|---|---|---|
| 中心主张 | 摘要末、引言末与结论首段 | 读者应接受什么核心判断 | 平台效果取决于责任配置而非技术接入本身 | 平台接入、责任配置、响应时间 | 统领全文各章并约束结论力度 | 统一三处贡献表述 | PASS |
| 引言 | 引言第一至三段 | 为什么相同平台产生不同响应结果 | 既有平均效应研究遗漏部门权责差异 | 平台效果、部门差异 | 从通常预期转入待解释异常 | 删除重复背景并在末段提出主张 | REVISED |
| 主体结构 | 文献、设计、结果与讨论各节首尾 | 各节如何逐步回答责任配置问题 | 文献提出竞争解释，设计提供判别，结果展示差异，讨论限定机制 | 技术接入、权限共享、条件机制 | 各节承接前一问题并推进同一证据链 | 合并无独特作用的综述段 | PASS |
| 结论 | 结论第一至二段 | 全文改变了什么认识并留下什么边界 | 平台效应应理解为受责任配置约束的条件关系 | 条件机制、观察场景 | 回答引言问题并收束单市观察边界 | 前置核心判断并集中说明边界 | PASS |

## 强抗辩与解释角色
| Explanation/Objection | Target Outcome/Stage | Same Outcome/Stage? | Distinct Empirical Expectation | Supporting Evidence | Contrary/Discriminating Evidence | Relation to Main Argument | Manuscript Role/Decision | Status |
|---|---|---|---|---|---|---|---|---|
| 技术接入本身即可提升响应速度 | 平台接入后的部门响应时间 | YES | 若技术接入起决定作用，同平台部门应出现相近改善 | 各部门使用同一平台功能 | 同平台下权限共享组与逐级审批组结果不同 | 竞争性解释 | 在讨论首段比较判别性证据并拒绝无条件技术解释 | PASS |

## 边界安置
| Boundary/Uncertainty | Why It Changes the Claim | Full-Statement Location | Downstream Handling | Repetition Removed | Status |
|---|---|---|---|---|---|
| 单市观察性材料未构造反事实 | 只能支持条件关系与机制一致性，不能支持普遍因果效应 | 讨论末段完整说明样本与识别边界 | 摘要和结论仅用“相关”并回指讨论 | 删除方法、结果与结论中三处整段重复 | REVISED |

## 叙事包装图
| Stage | Manuscript Location | Reader Question | Substantive Move | Evidence/Actor | Transition/Payoff | Status |
|---|---|---|---|---|---|---|
| 背景铺陈 | 引言第一段 | 平台研究已经知道什么 | 交代平台接入通常被视为治理能力提升手段 | 既有平台研究与部门工单 | 从普遍预期转入部门差异 | PASS |
| 张力上升 | 引言第二段 | 为什么接入同一平台却有不同结果 | 暴露平均效应解释不了的部门差异 | 相反文献结果与分组事实 | 把差异交给责任配置机制解释 | PASS |
| 核心回答 | 结果第一节 | 责任配置是否解释响应差异 | 展示共享权限组的响应结果与过程材料 | 部门人员、工单数据和制度记录 | 从发现转入替代解释比较 | PASS |
| 解释与边界 | 讨论第一节 | 为什么是责任配置而非技术接入本身 | 比较竞争解释并限定观察性证据 | 过程记录与研究设计边界 | 收束为有条件的机制判断 | PASS |
| 认识结局 | 结论第一段 | 接受本文后应修正什么认识 | 把平台效应改写为受责任配置约束 | 全文证据链与单市边界 | 读者不再把接入等同于有效 | PASS |

## 反向提纲与主线
| Unit ID | Location | Main Claim | Evidence/Reasoning | Contribution Link | Relation/Transition | Action | Status |
|---|---|---|---|---|---|---|---|
| U1 | 摘要 | 平台效果取决于责任配置 | 工单数据与制度材料共同支持条件关系 | 直接表达核心机制贡献 | 为全文提出待解释张力 | 重写摘要贡献句 | PASS |
| U2 | 引言 | 既有研究忽略权责条件 | 三组文献显示平均效应解释的边界 | 为机制增量腾出位置 | 从共识转入未解问题 | 合并重复综述 | REVISED |
| U3 | 结果第一节 | 权限共享改变响应时间 | 分组结果与过程材料相互印证 | 验证核心贡献的第一环 | 承接研究设计并导向机制 | 补写证据担保 | PASS |
| U4 | 结论 | 结论只适用于已观察场景 | 研究设计与样本边界限制外推 | 收束贡献并声明边界 | 回扣引言问题 | 删除普遍化表述 | JUSTIFIED |

## 承重段落审计
| Location | Claim | Evidence | Warrant/Analysis | Boundary/Implication | Action | Status |
|---|---|---|---|---|---|---|
| 引言第二段 | 平均效应不能解释情境差异 | 文献呈现相反结果 | 权责配置可能改变技术作用路径 | 只提出待检验机制 | 补写担保 | PASS |
| 结果第一节 | 共享权限与较短响应时间相关 | 分组统计与政策记录 | 两类材料在同一时间窗口一致 | 不写成无条件因果 | 校准措辞 | REVISED |
| 结论第一段 | 责任配置是可能机制 | 结果与过程证据形成链条 | 机制解释比技术决定论更符合材料 | 限于观察地区和年份 | 明示边界 | PASS |

## 句子信息结构与术语
| Location | Old/Context | Subject-Verb/Action | New/Stress | Term Consistency | Revision/Justification | Status |
|---|---|---|---|---|---|---|
| 摘要第二句 | 数字平台 | 本文检验 | 责任配置条件 | 统一使用数字平台 | 将研究动作移入谓语 | PASS |
| 引言第一段 | 平台接入 | 既有研究发现 | 结果方向不一致 | 区分平台接入与平台使用 | 句末落在争议 | REVISED |
| 结果第一节 | 共享权限 | 分组结果显示 | 响应时间差异 | 统一使用响应时间 | 删除名词化外壳 | PASS |
| 结论第一句 | 前述结果 | 本文支持 | 条件机制解释 | 核心概念保持同名 | 从旧结果导向新含义 | PASS |

## 主张力度校准
| Location | Claim | Evidence/Design | Allowed Wording | Forbidden Wording | Final Wording | Status |
|---|---|---|---|---|---|---|
| 结果第一节 | 平台改善回应能力 | 观察性工单数据 | 与响应时间缩短相关 | 证明平台导致改善 | 平台接入与响应时间缩短相关 | REVISED |
| 结论 | 责任配置具有普遍作用 | 单市材料与过程证据 | 可能构成已观察场景中的机制 | 普遍适用于所有地区 | 责任配置可能构成该场景中的作用机制 | PASS |

## 对话与声音审计
| Manuscript Location | Prior/Source Position | Attribution/Voice Boundary | Author Response | Strongest Countervoice Handling | Reader Recovery | Status |
|---|---|---|---|---|---|---|
| 摘要末句 | 既有研究强调平台接入的平均改善 | 先归属既有研究，再以“本文发现”切换作者声音 | 将平均效应限定为受责任配置约束 | 摘要不展开，但不写成反方已被彻底推翻 | 读者能复原前人判断、本文回应和条件边界 | PASS |
| 引言第二至三段 | 一类研究强调信息整合，另一类强调技术能力 | 每组判断均紧邻文献归属，段末另起作者问题 | 接受技术可能有效但追问何时有效 | 公允呈现技术充分说，并说明可区分经验预期 | 读者能说清谁主张什么及本文增加什么 | PASS |
| 结果第一节 | 两类立场对同平台部门差异有不同预期 | 结果事实与文献声音分句呈现 | 用分组结果判别两种解释 | 保留不支持条件机制的一项结果并限定解释 | 读者能指出最强证据与尚未解决之处 | PASS |
| 结论第一段 | 平均效应说解释了信息整合的一部分作用 | 明示让步属于作者判断而非原文引语 | 收束为有范围的条件机制 | 承认技术是必要条件但拒绝充分条件推断 | 读者能复原回应、反方边界与双重意义 | PASS |

## 实质性修改差异
| Discovery | Initial Claim/Location | Revised Claim | Source/Evidence Recheck | Propagated Changes | Boundary/Implication Fixed | Status |
|---|---|---|---|---|---|---|
| 同平台部门仍有明显差异 | 引言末段原称平台接入改善回应 | 平台作用受责任配置约束 | 复核两组文献、分组统计和过程材料 | 摘要末句；引言末段；讨论首段；结论首段 | 删除技术决定论与普遍因果暗示，并恢复单市边界 | REVISED |

## 风险表达处置
| Trigger | Location | Decision | Boundary ID | Anchor ID | Claim ID | Claim Delta | Placement | Dedup Record | Reason | Final Text | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
{risk_rows}

## 双读者复述
| Field | Content | Evidence/Location |
|---|---|---|
| Reader roles and branches | 外行读者来自比较政治，内行读者来自公共管理，均为不同上下文的隔离读者 | context 记录见 review_prompts/reader_contexts.md |
| Outsider reader: question and stakes | 同一平台为何在不同部门回应差异很大，关系到技术投入能否换来治理改进 | 引言第一、二段 |
| Outsider reader: sit-up moment | 共享权限的部门回应率反而低于未共享的部门 | 结果第一节表 2 |
| Insider reader: one thing not previously known | 责任配置而非接入水平决定平台效应，此前公管文献默认接入即改善 | 结果第一节与讨论首段 |
| Central contribution recovered | 平台效应取决于部门责任配置而非接入本身 | 摘要末句与结论首段 |
| Strongest evidence recovered | 共享权限分组结果与过程材料相互印证 | 结果第一节 |
| Inference boundary recovered | 观察性单市材料不支持普遍因果外推 | 结果限制与结论 |
| Largest logic gap | 引言原稿未解释权责条件为何连接平台与响应 | 引言第二段已补担保 |
| Revision disposition | 已补机制担保并收窄因果与外推措辞 | 引言第二段和结论 |
| Narrative path recovered | 从平台有效的通常预期进入部门差异，再由责任配置解释并限定边界 | 引言、结果、讨论与结论 |
| Reader payoff recovered | 不再把技术接入直接等同于治理改进，而会追问责任如何配置 | 结论第一段 |
| First reread / reading friction | 初读在引言第二段需要回读，因为原稿没有解释责任配置为何相关 | 引言第二段已补中间前提 |

## 定性表达评价
| Dimension | Verdict | Manuscript Evidence | Reader Feedback | Revision/Decision | Status |
|---|---|---|---|---|---|
| Narrative continuity | REVISED | 引言差异直接由结果中的责任配置证据回答 | 读者能按问题到回答再到边界复述全文 | 合并原先并列的技术背景段 | PASS |
| Language economy | MET | 重复背景与两处局限复述已经合并 | 读者未发现不承担论证功能的段落 | 保留必要样本和识别限定 | PASS |
| Reader readability | REVISED | 各承重节首句标明当前问题并在段末交接 | 读者只在原引言第二段发生一次回读 | 补出责任配置的中间前提 | PASS |
| Actor/action visibility | MET | 结果明确写出部门人员如何分配和移交工单 | 读者能说清谁在何种权限下采取行动 | 过程描述保留主动主体 | PASS |
| Show-explain balance | MET | 分组统计后紧接过程材料及其机制解释 | 读者既能指出最强证据也能说明其含义 | 保留数据并压缩逐格复述 | PASS |
{extra}
Overall Status: PASS
"""


def title_rhetorical_audit(*, resonance: str = "metaphor", body_move: str = "MOVE-INTRO-PHENOMENON") -> str:
    lines = valid_audit().splitlines()
    in_title = False
    for index, line in enumerate(lines):
        if line.startswith("| Checkpoint | Title |"):
            lines[index] = line[:-1] + "| Resonance Device | Body Explanation Move |"
            in_title = True
            continue
        if in_title and line.startswith("|---"):
            lines[index] = line[:-1] + "|---|---|"
            continue
        if in_title and line.startswith(("| question_commitment |", "| post_execution |", "| final |")):
            lines[index] = line[:-1] + f"| {resonance} | {body_move} |"
            continue
        if in_title and not line.strip():
            break
    return "\n".join(lines) + "\n"


def write_config(base: Path, scene: str, prose_mode: str | None = None) -> None:
    payload = {"scene": scene}
    if prose_mode is not None:
        payload["prose_mode"] = prose_mode
    (base / "workflow_config.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def write_title_contract(
    base: Path,
    *,
    working_title: str = "责任配置如何约束数字平台的回应效应",
    calibrated_title: str = "责任配置如何约束数字平台的回应效应",
) -> None:
    (base / "confirmed_motivation.md").write_text(
        """# Confirmed Motivation

| Field | Content |
|---|---|
| Working Title | """ + working_title + """ |
""",
        encoding="utf-8",
    )
    (base / "confirmed_contribution.md").write_text(
        "# Confirmed Contribution\n\n## Calibration Receipt\n\n"
        "| Field | Content |\n|---|---|\n"
        f"| Evidence-Calibrated Title | {calibrated_title} |\n",
        encoding="utf-8",
    )


def write_material_identities(base: Path) -> None:
    (base / "claim_register.md").write_text(
        "# Claims\n\n- CLM-001: bounded manuscript claim\n",
        encoding="utf-8",
    )
    (base / "evidence_bank.md").write_text(
        "# Material anchors\n\n- SRC-001: verified source\n- EVD-001: observed evidence\n"
        "- ETH-001: ethics boundary\n- RESP-001: author responsibility\n",
        encoding="utf-8",
    )
    registry = base / "reference_materials" / "literature_registry.json"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(
        json.dumps(
            {
                "schema_version": "cnki-acquisition/v1",
                "sources": [{"id": "SRC-001", "title": "Verified fixture source"}],
            }
        ),
        encoding="utf-8",
    )
    (base / "research_design.json").write_text(
        json.dumps(
            {
                "schema_version": "cnki-research-design/v4",
                "design_id": "DESIGN-001",
                "claims": [{"id": "CLM-001", "source_ids": ["SRC-001"]}],
                "evidence": [{"id": "EVD-001", "source_ids": ["SRC-001"]}],
                "ethics": [{"id": "ETH-001"}],
                "responsibilities": [{"id": "RESP-001"}],
            }
        ),
        encoding="utf-8",
    )
    (base / "method_execution.json").write_text(
        json.dumps({"execution_id": "EXE-001"}), encoding="utf-8"
    )


def material_risk_row(
    trigger: str,
    location: str,
    final_text: str,
    *,
    boundary_id: str = "B-001",
    anchor_id: str = "EVD-001",
    claim_delta: str = "该材料把 CLM-001 的范围限定到实际观察到的对象和时段",
    reason: str = "该句承担可核验的证据边界，删除后会使当前主张超过材料能力",
    placement: str = "主张之后仅此处完整说明一次",
    dedup: str = "仅此一处；其他重复说明已删除",
    decision: str = "KEEP-WITH-MATERIAL-ANCHOR",
) -> str:
    return (
        f"| {trigger} | {location} | {decision} | {boundary_id} | {anchor_id} | CLM-001 | "
        f"{claim_delta} | {placement} | {dedup} | {reason} | {final_text} | JUSTIFIED |"
    )
class AcademicProseTests(unittest.TestCase):
    def test_capability_cases_surface_expected_triggers(self) -> None:
        cases_path = REPO_ROOT / "evals" / "academic-prose" / "cases.json"
        if not cases_path.exists():
            self.skipTest("repository-level academic-prose eval cases are not bundled into an installed skill")
        cases = json.loads(cases_path.read_text(encoding="utf-8"))
        for case in cases:
            with self.subTest(case=case["id"]):
                keys = {hit.key for hit in prose.scan_risks(case["text"])}
                self.assertEqual(set(case["expected_triggers"]), keys)

    def test_flags_each_exact_user_reported_phrase(self) -> None:
        for phrase in ("止步处", "最靠前的一层", "三层文献叠起来"):
            with self.subTest(phrase=phrase):
                keys = {hit.key for hit in prose.scan_risks(phrase)}
                self.assertIn("scaffold-layer-metaphor", keys)

    def test_flags_overcautious_qualification_cluster(self) -> None:
        text = (
            "明确的机构创设表述可以确定时间联系；不同文书中关键表述的延续"
            "则只能说明政策内容具有连续性，不能单独确定理念的因果作用。"
        )
        keys = {hit.key for hit in prose.scan_risks(text)}
        self.assertIn("qualification-cluster", keys)

    def test_flags_contrastive_and_authorial_negation_without_banning_plain_claims(self) -> None:
        contrast = "这一判断不是结论复述，而是对关系功能的解释。"
        authorial = "本文并不把既有内容视为新发现。"
        direct = "本文以既有研究为起点，解释两类功能之间的关系。"
        self.assertIn(
            "contrastive-negation",
            {hit.key for hit in prose.scan_risks(contrast)},
        )
        self.assertIn(
            "authorial-intent-negation",
            {hit.key for hit in prose.scan_risks(authorial)},
        )
        self.assertEqual([], prose.scan_risks(direct))

    def test_flags_hypothetical_disclaimer_and_self_undermining_contribution(self) -> None:
        disclaimer = "为避免误解，需要澄清的是，这并不意味着制度设计决定全部执行结果。"
        self_undermining = "尽管样本范围有限，本文仍为解释部门响应差异提供了一项推进。"
        precise_boundary = "访谈用于形成机制假设，档案用于检验各环节；两类材料分开编码。"
        self.assertIn(
            "hypothetical-objection-disclaimer",
            {hit.key for hit in prose.scan_risks(disclaimer)},
        )
        self.assertIn(
            "self-undermining-contribution",
            {hit.key for hit in prose.scan_risks(self_undermining)},
        )
        self.assertEqual([], prose.scan_risks(precise_boundary))

    def test_flags_scaffold_audit_and_compressed_labels(self) -> None:
        text = (
            "现有研究的止步处仍是政策阐释，最靠前的一层未处理组织问题，三层文献叠起来也没有回答组织问题。"
            "本文以理念库、议题选址和设计转译展开，并逐项核验材料，最后作出机制对弈判定。"
            "相关安排分别表现为条款化、承诺化和正式化不透明。"
        )
        keys = {hit.key for hit in prose.scan_risks(text)}
        self.assertTrue(
            {
                "scaffold-layer-metaphor",
                "workflow-scaffold-label",
                "audit-judicial-register",
                "compressed-coinage",
            }.issubset(keys)
        )

    def test_flags_internal_process_log_without_flagging_material_condition(self) -> None:
        backstage = "表2显示来源获取失败，接口运行报错。"
        frontstage = "现存网页只提供机构概览，相关数字因此不进入跨期比较。"
        keys = {hit.key for hit in prose.scan_risks(backstage)}
        self.assertIn("internal-process-log", keys)
        self.assertEqual([], prose.scan_risks(frontstage))

    def test_does_not_flag_plain_literature_review_language(self) -> None:
        text = (
            "第一类研究讨论制度含义，第二类研究关注组织路径，第三类研究考察成员构成。"
            "综合来看，既有成果尚未解释倡议主张如何进入具体制度安排。"
        )
        self.assertEqual([], prose.scan_risks(text))

    def test_prefers_editable_markdown_over_generated_tex(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "manuscript.md").write_text("最终正文", encoding="utf-8")
            final_dir = base / "final_paper"
            final_dir.mkdir()
            (final_dir / "main.tex").write_text("陈旧生成稿", encoding="utf-8")
            located = prose.locate_manuscript(base, None)
            self.assertEqual((base / "manuscript.md").resolve(), located)

    def test_mastery_eval_cases_cover_positive_and_adversarial_behavior(self) -> None:
        cases_path = REPO_ROOT / "evals" / "academic-prose" / "mastery_cases.json"
        if not cases_path.exists():
            self.skipTest("repository-level mastery cases are not bundled into an installed skill")
        cases = json.loads(cases_path.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(cases), 23)
        outcomes = {case["expected"] for case in cases}
        self.assertEqual({"candidate_preferred", "baseline_preferred"}, outcomes)
        focus = {item for case in cases for item in case["focus"]}
        self.assertTrue(
            {
                "insight",
                "thought",
                "logic",
                "elegance",
                "voice",
                "fidelity",
                "phrase_copying",
                "narrative_continuity",
                "language_economy",
                "reader_readability",
                "actor_visibility",
                "show_explain",
                "boundary_concentration",
                "explanation_roles",
                "object_foregrounding",
                "backstage_control",
                "framework_demotion",
                "author_responsibility",
                "anti_defensive_function",
                "claim_arrival",
                "epistemic_calibration",
                "protected_boundary",
                "problem_arc",
                "thought_movement",
                "epistemic_hook",
                "context_anchor",
                "source_voice",
                "closure",
                "title_body_fulfillment",
            }.issubset(focus)
        )
        by_id = {case["id"]: case for case in cases}
        self.assertEqual(
            "candidate_preferred",
            by_id["frozen-demand-response-object-before-defense"]["expected"],
        )
        self.assertEqual(
            "baseline_preferred",
            by_id["necessary-author-responsibility-is-retained"]["expected"],
        )
        self.assertEqual(
            "candidate_preferred",
            by_id["claim-first-contribution-with-scope"]["expected"],
        )
        self.assertEqual(
            "baseline_preferred",
            by_id["positive-meta-rewording-is-not-a-revision"]["expected"],
        )
        self.assertEqual(
            "baseline_preferred",
            by_id["ethical-boundary-survives-confidence-edit"]["expected"],
        )
        self.assertIn(
            "no-national-average-effect boundary",
            by_id["frozen-demand-response-object-before-defense"]["guardrail"],
        )
        for case_id in (
            "frozen-demand-response-object-before-defense",
            "countervoice-pressure-stays-backstage",
            "framework-remains-an-analytic-tool",
        ):
            case = by_id[case_id]
            for protected in case["protected_items"]:
                self.assertIn(protected, case["baseline"])
                self.assertIn(protected, case["candidate"])
        responsibility = by_id["necessary-author-responsibility-is-retained"]
        for protected in responsibility["protected_items"]:
            self.assertIn(protected, responsibility["baseline"])
            self.assertNotIn(protected, responsibility["candidate"])
        for case_id in (
            "claim-first-contribution-with-scope",
            "hedge-pile-becomes-sourced-uncertainty",
        ):
            case = by_id[case_id]
            for protected in case["protected_items"]:
                self.assertIn(protected, case["baseline"])
                self.assertIn(protected, case["candidate"])
        for case_id in (
            "positive-meta-rewording-is-not-a-revision",
            "ethical-boundary-survives-confidence-edit",
        ):
            case = by_id[case_id]
            for protected in case["protected_items"]:
                self.assertIn(protected, case["baseline"])
                self.assertNotIn(protected, case["candidate"])

    def test_complete_audit_passes_before_final_manuscript_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "academic_prose_audit.md").write_text(valid_audit(), encoding="utf-8")
            result = prose.check_academic_prose(base)
            self.assertTrue(result.ok, result.issues)

    def test_journal_scene_defaults_to_distinguished_and_requires_enhancement_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_config(base, "journal")
            (base / "academic_prose_audit.md").write_text(valid_audit(), encoding="utf-8")
            result = prose.check_academic_prose(base)
            self.assertEqual(result.prose_mode, "distinguished")
            self.assertFalse(result.ok)
            self.assertTrue(any("Enhancement Log" in issue for issue in result.issues))
            self.assertTrue(any("Fidelity Inventory" in issue for issue in result.issues))
            self.assertTrue(any("Dimension Synthesis" in issue for issue in result.issues))

    def test_report_scene_defaults_to_clear(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_config(base, "report_review")
            (base / "academic_prose_audit.md").write_text(valid_audit(), encoding="utf-8")
            result = prose.check_academic_prose(base)
            self.assertEqual(result.prose_mode, "clear")
            self.assertTrue(result.ok, result.issues)

    def test_valid_distinguished_audit_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_config(base, "journal", "distinguished")
            (base / "academic_prose_audit.md").write_text(
                valid_audit(distinguished=True),
                encoding="utf-8",
            )
            result = prose.check_academic_prose(base)
            self.assertTrue(result.ok, result.issues)
            self.assertEqual(result.coverage["enhancement_moves"], 3)
            self.assertEqual(result.coverage["fidelity_items"], 6)
            self.assertEqual(result.coverage["dimension_verdicts"], 4)
            self.assertEqual(result.coverage["architecture_units"], 4)
            self.assertEqual(result.coverage["explanation_roles"], 1)
            self.assertEqual(result.coverage["boundary_placements"], 1)
            self.assertEqual(result.coverage["narrative_stages"], 5)
            self.assertEqual(result.coverage["qualitative_dimensions"], 5)

    def test_missing_outer_architecture_unit_blocks_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            audit = valid_audit().replace(
                "| 结论 | 结论第一至二段 | 全文改变了什么认识并留下什么边界 | 平台效应应理解为受责任配置约束的条件关系 | 条件机制、观察场景 | 回答引言问题并收束单市观察边界 | 前置核心判断并集中说明边界 | PASS |\n",
                "",
            )
            (base / "academic_prose_audit.md").write_text(audit, encoding="utf-8")
            result = prose.check_academic_prose(base)
            self.assertFalse(result.ok)
            self.assertTrue(
                any(
                    "Outer Architecture is missing unit: conclusion" in issue
                    for issue in result.issues
                )
            )

    def test_unclassified_explanation_role_blocks_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            audit = valid_audit().replace(
                "| 竞争性解释 | 在讨论首段比较判别性证据并拒绝无条件技术解释 | PASS |",
                "| 另作说明 | 在讨论首段比较判别性证据并拒绝无条件技术解释 | PASS |",
            )
            (base / "academic_prose_audit.md").write_text(audit, encoding="utf-8")
            result = prose.check_academic_prose(base)
            self.assertFalse(result.ok)
            self.assertTrue(
                any(
                    "does not classify its relation to the main argument" in issue
                    for issue in result.issues
                )
            )

    def test_different_stage_cannot_be_labeled_competing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            audit = valid_audit().replace(
                "| 平台接入后的部门响应时间 | YES | 若技术接入起决定作用",
                "| 组织成立后的外部定位 | NO | 若技术接入起决定作用",
            )
            (base / "academic_prose_audit.md").write_text(audit, encoding="utf-8")
            result = prose.check_academic_prose(base)
            self.assertFalse(result.ok)
            self.assertTrue(
                any(
                    "labels different outcomes/stages as competing" in issue
                    for issue in result.issues
                )
            )

    def test_missing_narrative_stage_blocks_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            audit = valid_audit().replace(
                "| 认识结局 | 结论第一段 | 接受本文后应修正什么认识 | 把平台效应改写为受责任配置约束 | 全文证据链与单市边界 | 读者不再把接入等同于有效 | PASS |\n",
                "",
            )
            (base / "academic_prose_audit.md").write_text(audit, encoding="utf-8")
            result = prose.check_academic_prose(base)
            self.assertFalse(result.ok)
            self.assertTrue(any("Narrative Wrap is missing stage: resolution" in issue for issue in result.issues))

    def test_weak_qualitative_feedback_blocks_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            audit = valid_audit().replace(
                "| Reader readability | REVISED | 各承重节首句标明当前问题并在段末交接 | 读者只在原引言第二段发生一次回读 | 补出责任配置的中间前提 | PASS |",
                "| Reader readability | WEAK | 各承重节首句标明当前问题并在段末交接 | 仍然难读 | 待修 | OPEN |",
            )
            (base / "academic_prose_audit.md").write_text(audit, encoding="utf-8")
            result = prose.check_academic_prose(base)
            self.assertFalse(result.ok)
            self.assertTrue(
                any(
                    "qualitative prose feedback is incomplete, weak, or unresolved: reader readability"
                    in issue
                    for issue in result.issues
                )
            )

    def test_missing_reading_friction_feedback_blocks_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            audit = valid_audit().replace(
                "| First reread / reading friction | 初读在引言第二段需要回读，因为原稿没有解释责任配置为何相关 | 引言第二段已补中间前提 |\n",
                "",
            )
            (base / "academic_prose_audit.md").write_text(audit, encoding="utf-8")
            result = prose.check_academic_prose(base)
            self.assertFalse(result.ok)
            self.assertTrue(
                any(
                    "independent reader test is missing field: reading friction"
                    in issue
                    for issue in result.issues
                )
            )

    def test_distinguished_audit_blocks_fidelity_loss(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            audit = valid_audit(distinguished=True).replace(
                "| Facts | 三项事实清单 | 三项事实清单 | 0 |",
                "| Facts | 三项事实清单 | 两项事实清单 | 1 |",
            )
            (base / "academic_prose_audit.md").write_text(audit, encoding="utf-8")
            result = prose.check_academic_prose(base, prose_mode="distinguished")
            self.assertFalse(result.ok)
            self.assertTrue(any("records loss: facts" in issue for issue in result.issues))

    def test_distinguished_audit_blocks_dimension_regression(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            audit = valid_audit(distinguished=True).replace(
                "| Logic | MET | 结果、担保和边界已形成连续链条 | PASS |",
                "| Logic | REGRESSED | 增强后担保链被修辞打断 | FAIL |",
            )
            (base / "academic_prose_audit.md").write_text(audit, encoding="utf-8")
            result = prose.check_academic_prose(base, prose_mode="distinguished")
            self.assertFalse(result.ok)
            self.assertTrue(any("records regression: logic" in issue for issue in result.issues))

    def test_explicit_clear_mode_overrides_journal_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_config(base, "journal", "clear")
            (base / "academic_prose_audit.md").write_text(valid_audit(), encoding="utf-8")
            result = prose.check_academic_prose(base)
            self.assertEqual(result.prose_mode, "clear")
            self.assertTrue(result.ok, result.issues)

    def test_risky_manuscript_requires_contextual_disposition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            final = base / "final_paper"
            final.mkdir()
            (final / "main.tex").write_text(
                "在数字治理时代背景下，基层治理效能提升具有重要意义。",
                encoding="utf-8",
            )
            (base / "academic_prose_audit.md").write_text(valid_audit(), encoding="utf-8")
            result = prose.check_academic_prose(base, require_manuscript=True)
            self.assertFalse(result.ok)
            self.assertTrue(any("generic-background" in issue for issue in result.issues))
            self.assertTrue(any("significance-cliche" in issue for issue in result.issues))

    def test_risky_manuscript_passes_after_disposition(self) -> None:
        final_text = "既有研究以“首次提出”标示贡献，但尚未提供系统撞车检索。"
        risk_rows = material_risk_row(
            "novelty-claim",
            "文献综述第二段",
            final_text,
            anchor_id="SRC-001",
            claim_delta="忠实归属 SRC-001 的自我定位，避免把来源声音误写为 CLM-001 的首创宣称",
            reason="该措辞是 SRC-001 的被分析对象，删去会改变来源立场和作者批评之间的声音边界",
        )
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_material_identities(base)
            final = base / "final_paper"
            final.mkdir()
            (final / "main.tex").write_text(
                final_text,
                encoding="utf-8",
            )
            (base / "academic_prose_audit.md").write_text(
                valid_audit(risk_rows),
                encoding="utf-8",
            )
            result = prose.check_academic_prose(base, require_manuscript=True)
            self.assertTrue(result.ok, result.issues)

    def test_qualification_cluster_is_review_trigger_not_automatic_ban(self) -> None:
        text = (
            "档案材料只能支持组织在公开会议后调整了规则，"
            "不能识别闭门协商中每位参与者的具体动机。"
        )
        risk_rows = material_risk_row(
            "qualification-cluster",
            "方法第三段",
            text,
            anchor_id="EVD-001",
            claim_delta="EVD-001 把 CLM-001 从参与者动机收窄为公开会议后的规则调整",
        )
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_material_identities(base)
            (base / "manuscript.md").write_text(text, encoding="utf-8")
            (base / "academic_prose_audit.md").write_text(
                valid_audit(risk_rows),
                encoding="utf-8",
            )
            result = prose.check_academic_prose(base, require_manuscript=True)
            self.assertTrue(result.ok, result.issues)

    def test_each_qualification_cluster_requires_its_own_disposition(self) -> None:
        first = (
            "档案材料只能支持组织在公开会议后调整了规则，"
            "不能识别闭门协商中每位参与者的具体动机。"
        )
        second = (
            "成员名单只能显示最终签署结果，"
            "无法还原每个受邀国在谈判阶段的权衡。"
        )
        risk_rows = material_risk_row(
            "qualification-cluster",
            "方法第三段",
            first,
            anchor_id="EVD-001",
            claim_delta="EVD-001 把 CLM-001 从参与者动机收窄为公开会议后的规则调整",
        )
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_material_identities(base)
            (base / "manuscript.md").write_text(
                f"{first}\n{second}",
                encoding="utf-8",
            )
            (base / "academic_prose_audit.md").write_text(
                valid_audit(risk_rows),
                encoding="utf-8",
            )
            result = prose.check_academic_prose(base, require_manuscript=True)
            self.assertFalse(result.ok)
            self.assertEqual(len(result.hits), 2)
            self.assertTrue(
                any(
                    "qualification-cluster occurrence 2" in issue
                    for issue in result.issues
                )
            )

    def test_zero_explanation_rows_are_valid_when_no_countervoice_qualifies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            audit = valid_audit()
            audit = audit.replace(
                "| 技术接入本身即可提升响应速度 | 平台接入后的部门响应时间 | YES | 若技术接入起决定作用，同平台部门应出现相近改善 | 各部门使用同一平台功能 | 同平台下权限共享组与逐级审批组结果不同 | 竞争性解释 | 在讨论首段比较判别性证据并拒绝无条件技术解释 | PASS |\n",
                "",
            )
            (base / "academic_prose_audit.md").write_text(audit, encoding="utf-8")
            result = prose.check_academic_prose(base)
        self.assertTrue(result.ok, result.issues)
        self.assertEqual(0, result.coverage["explanation_roles"])

    def test_zero_explanation_rows_do_not_allow_reported_counterevidence_loss(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            audit = valid_audit(distinguished=True).replace(
                "| 技术接入本身即可提升响应速度 | 平台接入后的部门响应时间 | YES | 若技术接入起决定作用，同平台部门应出现相近改善 | 各部门使用同一平台功能 | 同平台下权限共享组与逐级审批组结果不同 | 竞争性解释 | 在讨论首段比较判别性证据并拒绝无条件技术解释 | PASS |\n",
                "",
            )
            audit = audit.replace(
                "| Counterevidence | 不支持结果一项 | 不支持结果一项 | 0 |",
                "| Counterevidence | 不支持结果一项 | 已删除不支持结果 | 1 |",
            )
            (base / "academic_prose_audit.md").write_text(audit, encoding="utf-8")
            result = prose.check_academic_prose(base, prose_mode="distinguished")
        self.assertEqual(0, result.coverage["explanation_roles"])
        self.assertFalse(result.ok)
        self.assertTrue(any("records loss: counterevidence" in issue for issue in result.issues))

    def test_keep_with_reason_name_no_longer_self_authorizes_retained_risk(self) -> None:
        text = "档案只能显示公开会议后的调整，不能识别闭门协商的具体动机。"
        risk_rows = material_risk_row(
            "qualification-cluster",
            "方法第三段",
            text,
            decision="KEEP-WITH-REASON",
        )
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_material_identities(base)
            (base / "manuscript.md").write_text(text, encoding="utf-8")
            (base / "academic_prose_audit.md").write_text(
                valid_audit(risk_rows), encoding="utf-8"
            )
            result = prose.check_academic_prose(base, require_manuscript=True)
        self.assertFalse(result.ok)
        self.assertTrue(
            any("must use KEEP-WITH-MATERIAL-ANCHOR" in issue for issue in result.issues)
        )

    def test_unregistered_anchor_cannot_authorize_retained_risk(self) -> None:
        text = "档案只能显示公开会议后的调整，不能识别闭门协商的具体动机。"
        risk_rows = material_risk_row(
            "qualification-cluster", "方法第三段", text, anchor_id="EVD-999"
        )
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_material_identities(base)
            (base / "manuscript.md").write_text(text, encoding="utf-8")
            (base / "academic_prose_audit.md").write_text(
                valid_audit(risk_rows), encoding="utf-8"
            )
            result = prose.check_academic_prose(base, require_manuscript=True)
        self.assertFalse(result.ok)
        self.assertTrue(any("registered material Anchor ID" in issue for issue in result.issues))

    def test_real_method_evidence_ethics_and_responsibility_boundaries_survive(self) -> None:
        cases = (
            (
                "qualification-cluster",
                "档案材料只能支持公开会议后的规则调整，不能识别闭门协商中的具体动机。",
                "DESIGN-001",
                "方法第三段",
            ),
            (
                "audit-boundary-broadcast",
                "本文材料所能支持的是观察期内的责任配置关系。",
                "EVD-001",
                "结果第一段",
            ),
            (
                "hypothetical-objection-disclaimer",
                "为避免误解，本研究不公开可识别的访谈片段。",
                "ETH-001",
                "方法伦理说明",
            ),
            (
                "authorial-intent-negation",
                "本文不把未经核验的陈述归属于受访者。",
                "RESP-001",
                "材料责任说明",
            ),
        )
        for trigger, text, anchor_id, location in cases:
            with self.subTest(trigger=trigger):
                risk_rows = material_risk_row(
                    trigger,
                    location,
                    text,
                    anchor_id=anchor_id,
                    claim_delta="该真实边界把 CLM-001 限定到可负责归属和公开的材料范围",
                    reason="该登记锚点承担方法、证据、伦理或作者责任，删除后会改变主张权限",
                )
                with tempfile.TemporaryDirectory() as tmp:
                    base = Path(tmp)
                    write_material_identities(base)
                    (base / "manuscript.md").write_text(text, encoding="utf-8")
                    (base / "academic_prose_audit.md").write_text(
                        valid_audit(risk_rows), encoding="utf-8"
                    )
                    result = prose.check_academic_prose(base, require_manuscript=True)
                self.assertTrue(result.ok, result.issues)

    def test_generic_misunderstanding_reason_cannot_activate_boundary(self) -> None:
        text = "为避免误解，需要说明的是，责任配置与响应时间相关。"
        rows = []
        for trigger in ("hypothetical-objection-disclaimer", "hypothetical-objection-disclaimer"):
            rows.append(
                material_risk_row(
                    trigger,
                    "结果第一段",
                    text,
                    reason="为了避免读者误解并保持谨慎，所以保留这句说明",
                )
            )
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_material_identities(base)
            (base / "manuscript.md").write_text(text, encoding="utf-8")
            (base / "academic_prose_audit.md").write_text(
                valid_audit("\n".join(rows)), encoding="utf-8"
            )
            result = prose.check_academic_prose(base, require_manuscript=True)
        self.assertFalse(result.ok)
        self.assertTrue(any("cannot activate retained prose" in issue for issue in result.issues))

    def test_same_anchor_may_support_distinct_boundary_ids(self) -> None:
        first = "档案只能显示公开会议后的调整，不能识别闭门协商的具体动机。"
        second = "成员名单只能显示最终签署结果，无法还原谈判阶段的具体权衡。"
        risk_rows = "\n".join(
            (
                material_risk_row(
                    "qualification-cluster", "方法第三段", first, boundary_id="B-001"
                ),
                material_risk_row(
                    "qualification-cluster", "方法第四段", second, boundary_id="B-002"
                ),
            )
        )
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_material_identities(base)
            (base / "manuscript.md").write_text(first + "\n" + second, encoding="utf-8")
            (base / "academic_prose_audit.md").write_text(
                valid_audit(risk_rows), encoding="utf-8"
            )
            result = prose.check_academic_prose(base, require_manuscript=True)
        self.assertTrue(result.ok, result.issues)

    def test_same_boundary_id_cannot_repeat_across_distinct_locations(self) -> None:
        first = "档案只能显示公开会议后的调整，不能识别闭门协商的具体动机。"
        second = "成员名单只能显示最终签署结果，无法还原谈判阶段的具体权衡。"
        risk_rows = "\n".join(
            (
                material_risk_row(
                    "qualification-cluster", "方法第三段", first, boundary_id="B-001"
                ),
                material_risk_row(
                    "qualification-cluster", "讨论第四段", second, boundary_id="B-001"
                ),
            )
        )
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_material_identities(base)
            (base / "manuscript.md").write_text(first + "\n" + second, encoding="utf-8")
            (base / "academic_prose_audit.md").write_text(
                valid_audit(risk_rows), encoding="utf-8"
            )
            result = prose.check_academic_prose(base, require_manuscript=True)
        self.assertFalse(result.ok)
        self.assertTrue(any("more than one full retained" in issue for issue in result.issues))

    def test_retained_boundary_requires_stable_boundary_id(self) -> None:
        text = "档案只能显示公开会议后的调整，不能识别闭门协商的具体动机。"
        risk_rows = material_risk_row(
            "qualification-cluster", "方法第三段", text, boundary_id="boundary-one"
        )
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_material_identities(base)
            (base / "manuscript.md").write_text(text, encoding="utf-8")
            (base / "academic_prose_audit.md").write_text(
                valid_audit(risk_rows), encoding="utf-8"
            )
            result = prose.check_academic_prose(base, require_manuscript=True)
        self.assertFalse(result.ok)
        self.assertTrue(any("stable B-* Boundary ID" in issue for issue in result.issues))

    def test_writing_only_revision_cannot_have_positive_net_growth(self) -> None:
        baseline_text = "The evidence supports a bounded association."
        current_text = (
            baseline_text
            + " This revision adds broad explanatory prose without any new registered evidence."
        )
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            snapshot = base / "revision_baseline" / "baseline.md"
            snapshot.parent.mkdir()
            snapshot.write_text(baseline_text, encoding="utf-8")
            (base / "manuscript.md").write_text(current_text, encoding="utf-8")
            (base / "revision_contract.json").write_text(
                json.dumps(
                    {
                        "baseline": {"snapshot_path": "revision_baseline/baseline.md"},
                        "requested_changes": [
                            {"change_id": "CH-001", "change_class": "surface"}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (base / "academic_prose_audit.md").write_text(
                valid_audit(), encoding="utf-8"
            )
            result = prose.check_academic_prose(base, require_manuscript=True)
        self.assertFalse(result.ok)
        self.assertTrue(any("surface-only revision" in issue for issue in result.issues))
        self.assertGreater(result.coverage["revision_net_growth"], 0)

    def test_registered_evidence_claim_and_reader_deltas_allow_material_growth(self) -> None:
        baseline_text = "The evidence supports a bounded association."
        current_text = (
            baseline_text
            + " Newly registered interviews explain which responsibility transfer preceded the observed change."
        )
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_material_identities(base)
            snapshot = base / "revision_baseline" / "baseline.md"
            snapshot.parent.mkdir()
            snapshot.write_text(baseline_text, encoding="utf-8")
            (base / "manuscript.md").write_text(current_text, encoding="utf-8")
            (base / "revision_contract.json").write_text(
                json.dumps(
                    {
                        "baseline": {"snapshot_path": "revision_baseline/baseline.md"},
                        "requested_changes": [
                            {"change_id": "CH-001", "change_class": "evidence"}
                        ],
                        "expression_budget": {
                            "evidence_delta": "EVD-001",
                            "claim_delta": "CLM-001",
                            "reader_update": "Readers can now distinguish the observed sequence from a generic association.",
                        },
                    }
                ),
                encoding="utf-8",
            )
            (base / "academic_prose_audit.md").write_text(
                valid_audit(), encoding="utf-8"
            )
            result = prose.check_academic_prose(base, require_manuscript=True)
        self.assertTrue(result.ok, result.issues)
        self.assertGreater(result.coverage["revision_net_growth"], 0)

    def test_argument_growth_requires_grounded_clarity_actions(self) -> None:
        baseline_text = "The evidence supports a bounded association."
        current_text = baseline_text + " The sequence explains how responsibility changes waiting time."
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_material_identities(base)
            snapshot = base / "revision_baseline" / "baseline.md"
            snapshot.parent.mkdir()
            snapshot.write_text(baseline_text, encoding="utf-8")
            (base / "manuscript.md").write_text(current_text, encoding="utf-8")
            (base / "revision_contract.json").write_text(
                json.dumps(
                    {
                        "baseline": {"snapshot_path": "revision_baseline/baseline.md"},
                        "requested_changes": [
                            {"change_id": "CH-001", "change_class": "argument"}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (base / "academic_prose_audit.md").write_text(
                valid_audit(), encoding="utf-8"
            )
            result = prose.check_academic_prose(base, require_manuscript=True)
        self.assertFalse(result.ok)
        self.assertTrue(any("clarity_actions" in issue for issue in result.issues))

    def test_grounded_bridge_allows_argument_growth_and_reports_soft_warning(self) -> None:
        baseline_text = "The evidence supports a bounded association."
        current_text = baseline_text + " The sequence explains how responsibility changes waiting time."
        delta = prose.prose_unit_count(current_text) - prose.prose_unit_count(baseline_text)
        action = {
            "action": "BRIDGE",
            "prose_delta": delta,
            "claim_id": "CLM-001",
            "source_kind": "warrant",
            "source_anchor": "warrant",
            "reader_understanding": "Readers can connect the sequence to the bounded association.",
            "no_new_fact": True,
            "no_new_citation": True,
            "no_inference_strengthening": True,
        }
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_material_identities(base)
            snapshot = base / "revision_baseline" / "baseline.md"
            snapshot.parent.mkdir()
            snapshot.write_text(baseline_text, encoding="utf-8")
            (base / "manuscript.md").write_text(current_text, encoding="utf-8")
            contract = {
                "baseline": {"snapshot_path": "revision_baseline/baseline.md"},
                "requested_changes": [
                    {"change_id": "CH-001", "change_class": "argument"}
                ],
                "expression_budget": {
                    "clarity_scope": "paragraph",
                    "clarity_actions": [action],
                    "registered_terms": [],
                },
            }
            (base / "revision_contract.json").write_text(
                json.dumps(contract),
                encoding="utf-8",
            )
            (base / "academic_prose_audit.md").write_text(
                valid_audit(), encoding="utf-8"
            )
            result = prose.check_academic_prose(base, require_manuscript=True)
            contract["expression_budget"]["clarity_growth_soft_limits"] = {
                "section_ratio": 1.25,
                "paragraph_ratio": 1.50,
            }
            (base / "revision_contract.json").write_text(
                json.dumps(contract), encoding="utf-8"
            )
            custom = prose.check_academic_prose(base, require_manuscript=True)
        self.assertTrue(result.ok, result.issues)
        self.assertTrue(any("soft 15%" in warning for warning in result.warnings))
        self.assertTrue(custom.ok, custom.issues)
        self.assertEqual([], custom.warnings)

    def test_argument_clarity_rejects_invalid_growth_soft_limits(self) -> None:
        baseline_text = "The evidence supports a bounded association."
        current_text = baseline_text + " The sequence explains how responsibility changes waiting time."
        delta = prose.prose_unit_count(current_text) - prose.prose_unit_count(baseline_text)
        action = {
            "action": "BRIDGE",
            "prose_delta": delta,
            "claim_id": "CLM-001",
            "source_kind": "warrant",
            "source_anchor": "warrant",
            "reader_understanding": "Readers can connect the sequence to the bounded association.",
            "no_new_fact": True,
            "no_new_citation": True,
            "no_inference_strengthening": True,
        }
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_material_identities(base)
            snapshot = base / "revision_baseline" / "baseline.md"
            snapshot.parent.mkdir()
            snapshot.write_text(baseline_text, encoding="utf-8")
            (base / "manuscript.md").write_text(current_text, encoding="utf-8")
            (base / "revision_contract.json").write_text(
                json.dumps(
                    {
                        "baseline": {"snapshot_path": "revision_baseline/baseline.md"},
                        "requested_changes": [
                            {"change_id": "CH-001", "change_class": "argument"}
                        ],
                        "expression_budget": {
                            "clarity_scope": "paragraph",
                            "clarity_actions": [action],
                            "registered_terms": [],
                            "clarity_growth_soft_limits": {
                                "section_ratio": 0.30,
                                "paragraph_ratio": 0.20,
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            (base / "academic_prose_audit.md").write_text(
                valid_audit(), encoding="utf-8"
            )
            result = prose.check_academic_prose(base, require_manuscript=True)
        self.assertFalse(result.ok)
        self.assertTrue(any("cannot exceed" in issue for issue in result.issues))

    def test_argument_clarity_ledger_rejects_positive_replace_and_delta_mismatch(self) -> None:
        baseline_text = "The evidence supports a bounded association."
        current_text = baseline_text + " A warrant connects the sequence to the claim."
        delta = prose.prose_unit_count(current_text) - prose.prose_unit_count(baseline_text)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_material_identities(base)
            snapshot = base / "revision_baseline" / "baseline.md"
            snapshot.parent.mkdir()
            snapshot.write_text(baseline_text, encoding="utf-8")
            (base / "manuscript.md").write_text(current_text, encoding="utf-8")
            (base / "revision_contract.json").write_text(
                json.dumps(
                    {
                        "baseline": {"snapshot_path": "revision_baseline/baseline.md"},
                        "requested_changes": [
                            {"change_id": "CH-001", "change_class": "argument"}
                        ],
                        "expression_budget": {
                            "clarity_actions": [
                                {"action": "REPLACE", "prose_delta": delta - 1}
                            ],
                            "registered_terms": [],
                        },
                    }
                ),
                encoding="utf-8",
            )
            (base / "academic_prose_audit.md").write_text(
                valid_audit(), encoding="utf-8"
            )
            result = prose.check_academic_prose(base, require_manuscript=True)
        self.assertFalse(result.ok)
        self.assertTrue(any("only BRIDGE or DEFINE" in issue for issue in result.issues))
        self.assertTrue(any("does not match actual delta" in issue for issue in result.issues))

    def test_registered_term_clarity_anchor_must_match_canonical_term_list(self) -> None:
        baseline_text = "The evidence supports a bounded association."
        current_text = baseline_text + " Here, bounded means limited to the observed departments."
        delta = prose.prose_unit_count(current_text) - prose.prose_unit_count(baseline_text)
        action = {
            "action": "DEFINE",
            "prose_delta": delta,
            "claim_id": "CLM-001",
            "source_kind": "registered_term",
            "source_anchor": "fabricated construct",
            "reader_understanding": "Readers know the empirical scope of the term.",
            "no_new_fact": True,
            "no_new_citation": True,
            "no_inference_strengthening": True,
        }
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_material_identities(base)
            snapshot = base / "revision_baseline" / "baseline.md"
            snapshot.parent.mkdir()
            snapshot.write_text(baseline_text, encoding="utf-8")
            (base / "manuscript.md").write_text(current_text, encoding="utf-8")
            contract = {
                "baseline": {"snapshot_path": "revision_baseline/baseline.md"},
                "requested_changes": [
                    {"change_id": "CH-001", "change_class": "argument"}
                ],
                "expression_budget": {
                    "clarity_actions": [action],
                    "registered_terms": ["bounded association"],
                },
            }
            (base / "revision_contract.json").write_text(
                json.dumps(contract), encoding="utf-8"
            )
            (base / "academic_prose_audit.md").write_text(
                valid_audit(), encoding="utf-8"
            )
            invalid = prose.check_academic_prose(base, require_manuscript=True)
            contract["expression_budget"]["clarity_actions"][0][
                "source_anchor"
            ] = "bounded association"
            (base / "revision_contract.json").write_text(
                json.dumps(contract), encoding="utf-8"
            )
            valid = prose.check_academic_prose(base, require_manuscript=True)
        self.assertFalse(invalid.ok)
        self.assertTrue(any("registered_terms" in issue for issue in invalid.issues))
        self.assertTrue(valid.ok, valid.issues)

    def test_unresolved_row_blocks_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            audit = valid_audit().replace(
                "| U3 | 结果第一节 | 权限共享改变响应时间 | 分组结果与过程材料相互印证 | 验证核心贡献的第一环 | 承接研究设计并导向机制 | 补写证据担保 | PASS |",
                "| U3 | 结果第一节 | 权限共享改变响应时间 | 分组结果与过程材料相互印证 | 验证核心贡献的第一环 | 承接研究设计并导向机制 | 补写证据担保 | OPEN |",
            )
            (base / "academic_prose_audit.md").write_text(audit, encoding="utf-8")
            result = prose.check_academic_prose(base)
            self.assertFalse(result.ok)
            self.assertTrue(any("unresolved" in issue for issue in result.issues))

    def test_missing_dialogue_voice_audit_blocks_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            audit = valid_audit()
            start = audit.index("## 对话与声音审计")
            end = audit.index("## 实质性修改差异", start)
            audit = audit[:start] + audit[end:]
            (base / "academic_prose_audit.md").write_text(audit, encoding="utf-8")
            result = prose.check_academic_prose(base)
            self.assertFalse(result.ok)
            self.assertTrue(any("对话与声音审计" in issue for issue in result.issues))

    def test_unresolved_substantive_revision_blocks_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            audit = valid_audit().replace(
                "删除技术决定论与普遍因果暗示，并恢复单市边界 | REVISED |",
                "删除技术决定论与普遍因果暗示，并恢复单市边界 | OPEN |",
            )
            (base / "academic_prose_audit.md").write_text(audit, encoding="utf-8")
            result = prose.check_academic_prose(base)
            self.assertFalse(result.ok)
            self.assertTrue(
                any(
                    "实质性修改差异 row 1 has unresolved" in issue
                    for issue in result.issues
                )
            )

    def test_pass_prefix_cannot_hide_unresolved_suffix(self) -> None:
        for mixed_status in (
            "PASS; TODO later",
            "REVISED - VERIFY against manuscript",
            "已修订，仍待核",
        ):
            with self.subTest(status=mixed_status):
                self.assertFalse(prose.status_ok(mixed_status))

    def test_final_audit_can_require_manuscript(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "academic_prose_audit.md").write_text(valid_audit(), encoding="utf-8")
            result = prose.check_academic_prose(base, require_manuscript=True)
            self.assertFalse(result.ok)
            self.assertTrue(any("no final manuscript" in issue for issue in result.issues))

    def test_bibliography_and_comments_do_not_create_false_triggers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            final = base / "final_paper"
            final.mkdir()
            (final / "main.tex").write_text(
                r"""\documentclass{article}
% 在数字治理背景下具有重要意义
\begin{document}
本文结果只支持限定场景中的相关关系。
\begin{thebibliography}{9}
\bibitem{x} 某文：首次提出一个开创性框架。
\end{thebibliography}
\end{document}
""",
                encoding="utf-8",
            )
            (base / "academic_prose_audit.md").write_text(valid_audit(), encoding="utf-8")
            result = prose.check_academic_prose(base, require_manuscript=True)
            self.assertTrue(result.ok, result.issues)

    def test_source_faithful_contrastive_negation_can_be_justified(self) -> None:
        text = "原典指出，其区别不在于另立特殊利益，而在于承担推动作用。"
        risk_rows = material_risk_row(
            "contrastive-negation",
            "理论部分原典转述",
            "不在于另立特殊利益，而在于",
            anchor_id="SRC-001",
            claim_delta="SRC-001 的原始概念对比界定 CLM-001 的解释对象与谓词范围",
            reason="该结构忠实呈现 SRC-001 的概念区分，删去会把来源立场改成作者自我辩解",
        )
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_material_identities(base)
            (base / "manuscript.md").write_text(text, encoding="utf-8")
            (base / "academic_prose_audit.md").write_text(
                valid_audit(risk_rows),
                encoding="utf-8",
            )
            result = prose.check_academic_prose(base, require_manuscript=True)
            self.assertTrue(result.ok, result.issues)

    def test_simulated_reviewer_rebuttal_requires_disposition(self) -> None:
        text = "最强的反对意见认为，该解释只是对既有结论的重新排列。这一质疑部分成立。"
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "manuscript.md").write_text(text, encoding="utf-8")
            (base / "academic_prose_audit.md").write_text(
                valid_audit(),
                encoding="utf-8",
            )
            result = prose.check_academic_prose(base, require_manuscript=True)
            self.assertFalse(result.ok)
            self.assertEqual(
                ["simulated-reviewer-rebuttal", "simulated-reviewer-rebuttal"],
                [hit.key for hit in result.hits],
            )
            self.assertTrue(
                any("simulated-reviewer-rebuttal occurrence 2" in issue for issue in result.issues)
            )

    def test_audit_boundary_broadcast_requires_disposition(self) -> None:
        text = (
            "本文材料所能支持的是规范关系和制度条件。"
            "因此，本文把结论限定为组织条件的形成，不推断具体治理绩效。"
        )
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "manuscript.md").write_text(text, encoding="utf-8")
            (base / "academic_prose_audit.md").write_text(
                valid_audit(),
                encoding="utf-8",
            )
            result = prose.check_academic_prose(base, require_manuscript=True)
            self.assertFalse(result.ok)
            keys = [hit.key for hit in result.hits]
            self.assertEqual(3, keys.count("audit-boundary-broadcast"))
            self.assertTrue(
                any("audit-boundary-broadcast occurrence 3" in issue for issue in result.issues)
            )

    def test_identical_boundary_broadcast_twice_cannot_hide_behind_duplicate_rows(self) -> None:
        sentence = "本文材料所能支持的是规范关系和制度条件。"
        row = material_risk_row(
            "audit-boundary-broadcast",
            "讨论末段",
            sentence,
        )
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_material_identities(base)
            (base / "manuscript.md").write_text(sentence + sentence, encoding="utf-8")
            (base / "academic_prose_audit.md").write_text(
                valid_audit(row + "\n" + row),
                encoding="utf-8",
            )
            result = prose.check_academic_prose(base, require_manuscript=True)
        self.assertFalse(result.ok)
        self.assertTrue(
            any("more than one full retained text/location" in issue for issue in result.issues)
        )

    def test_title_loop_matches_upstream_contract_and_manuscript(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_title_contract(base)
            (base / "manuscript.md").write_text(
                "# 责任配置如何约束数字平台的回应效应\n\n正文。",
                encoding="utf-8",
            )
            (base / "academic_prose_audit.md").write_text(valid_audit(), encoding="utf-8")
            result = prose.check_academic_prose(base, require_manuscript=True)
            self.assertTrue(result.ok, result.issues)
            self.assertEqual(3, result.coverage["title_checkpoints"])

    def test_title_loop_accepts_research_design_evd_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_title_contract(base)
            (base / "manuscript.md").write_text(
                "# 责任配置如何约束数字平台的回应效应\n\n正文。",
                encoding="utf-8",
            )
            audit = (
                valid_audit()
                .replace("PO-01", "问题PO-01")
                .replace("EXE-01", "执行证据EXE-01")
                .replace("CLM-01", "主张CLM-01")
                .replace("EV-01", "证据EVD-001")
            )
            (base / "academic_prose_audit.md").write_text(audit, encoding="utf-8")
            result = prose.check_academic_prose(base, require_manuscript=True)
            self.assertTrue(result.ok, result.issues)
            self.assertEqual(3, result.coverage["title_checkpoints"])

    def test_title_resonance_requires_a_body_explanation_move(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_title_contract(base)
            (base / "manuscript.md").write_text(
                "# 责任配置如何约束数字平台的回应效应\n\n正文。",
                encoding="utf-8",
            )
            (base / "academic_prose_audit.md").write_text(
                title_rhetorical_audit(),
                encoding="utf-8",
            )
            result = prose.check_academic_prose(base, require_manuscript=True)
            self.assertTrue(result.ok, result.issues)

            (base / "academic_prose_audit.md").write_text(
                title_rhetorical_audit(body_move="待定"),
                encoding="utf-8",
            )
            result = prose.check_academic_prose(base, require_manuscript=True)
            self.assertTrue(
                any("AP.TITLE.BODY_ANCHOR_MISSING" in issue for issue in result.issues),
                result.issues,
            )

    def test_direct_quote_requires_content_verified_context_anchor_and_locator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_title_contract(base)
            write_material_identities(base)
            manuscript = (
                "# 责任配置如何约束数字平台的回应效应\n\n"
                "档案指出：“权限共享仅改变等待环节”（档案卷 2，第 4 页）。"
            )
            (base / "manuscript.md").write_text(manuscript, encoding="utf-8")
            (base / "academic_prose_audit.md").write_text(valid_audit(), encoding="utf-8")
            bank = base / "evidence_bank.md"
            bank.write_text(
                bank.read_text(encoding="utf-8") + "\n## Context Anchors\n",
                encoding="utf-8",
            )
            result = prose.check_academic_prose(base, require_manuscript=True)
            self.assertTrue(
                any("AP.QUOTE.CONTEXT_MISSING" in issue for issue in result.issues),
                result.issues,
            )

            (base / "evidence_bank.md").write_text(
                """# Evidence Bank

## Context Anchors

| Anchor ID | Authority Ref | Type | Locator | Exact Span/Known Details | Original Problem | Logical Context | Protected Qualifiers | Manuscript Function | Status |
|---|---|---|---|---|---|---|---|---|---|
| ANCHOR-ARCHIVE-01 | EVD-001 | quotation | 档案卷 2，第 4 页 | 权限共享仅改变等待环节 | 平台接入是否足以改变治理能力 | 该句限定权限共享能够解释的流程环节 | 仅 | 以来源声音限定机制范围 | content-verified |
""",
                encoding="utf-8",
            )
            result = prose.check_academic_prose(base, require_manuscript=True)
            self.assertTrue(result.ok, result.issues)
            self.assertEqual(1, result.coverage["context_anchors"])

            (base / "manuscript.md").write_text(
                manuscript.replace("（档案卷 2，第 4 页）", ""),
                encoding="utf-8",
            )
            result = prose.check_academic_prose(base, require_manuscript=True)
            self.assertTrue(
                any("AP.QUOTE.LOCATOR_MISSING" in issue for issue in result.issues),
                result.issues,
            )

    def test_current_profile_cannot_omit_context_anchor_table_but_legacy_can(self) -> None:
        for profile_version, expected in (("1.1.0", True), ("1.0.0", False)):
            with self.subTest(profile_version=profile_version), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                write_title_contract(base)
                write_material_identities(base)
                (base / "manuscript.md").write_text(
                    "# 责任配置如何约束数字平台的回应效应\n\n档案指出：“权限共享仅改变等待环节”。",
                    encoding="utf-8",
                )
                (base / "academic_prose_audit.md").write_text(
                    valid_audit(),
                    encoding="utf-8",
                )
                contract_path = base / ".avereth-prose" / "manuscript" / "manuscript_contract.json"
                contract_path.parent.mkdir(parents=True, exist_ok=True)
                contract_path.write_text(
                    json.dumps(
                        {
                            "schema_version": "avereth-manuscript-contract/v1",
                            "profile_version": profile_version,
                        }
                    ),
                    encoding="utf-8",
                )
                result = prose.check_academic_prose(base, require_manuscript=True)
                missing_context = any(
                    "AP.QUOTE.CONTEXT_MISSING" in issue for issue in result.issues
                )
                self.assertEqual(expected, missing_context, result.issues)

    def test_final_title_cannot_hide_substantive_change_in_prose_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_title_contract(base)
            changed = valid_audit().replace(
                "| final | 责任配置如何约束数字平台的回应效应 | PO-01；EXE-01；CLM-01；EV-01 | 单市部门；观察期内的平台回应 | none；无实质变更 | 定稿标题沿用证据校准标题 |",
                "| final | 责任配置决定数字平台回应效应的普遍机制 | PO-01；EXE-01；CLM-01；EV-01 | 单市部门；观察期内的平台回应 | evidence-substantive；实质改题 | 定稿时新增普遍机制结论 |",
            )
            (base / "manuscript.md").write_text(
                "# 责任配置决定数字平台回应效应的普遍机制\n\n正文。",
                encoding="utf-8",
            )
            (base / "academic_prose_audit.md").write_text(changed, encoding="utf-8")
            result = prose.check_academic_prose(base, require_manuscript=True)
            self.assertFalse(result.ok)
            self.assertTrue(
                any("checkpoint final must use change class" in issue for issue in result.issues)
            )

    def test_final_title_must_match_manuscript_title(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_title_contract(base)
            (base / "manuscript.md").write_text(
                "# 数字平台一定改善政府回应\n\n正文。",
                encoding="utf-8",
            )
            (base / "academic_prose_audit.md").write_text(valid_audit(), encoding="utf-8")
            result = prose.check_academic_prose(base, require_manuscript=True)
            self.assertFalse(result.ok)
            self.assertTrue(any("does not match the manuscript title" in issue for issue in result.issues))


if __name__ == "__main__":
    unittest.main()
