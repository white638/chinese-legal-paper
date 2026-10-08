#!/usr/bin/env python3
"""Regression tests for the research-quality design-matching gate."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent


def load_module():
    path = HERE / "research_quality_check.py"
    spec = importlib.util.spec_from_file_location("research_quality_check", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


quality = load_module()


def universal_rows(
    claim: str,
    maturity: str = "发展期：已有竞争解释但机制证据仍不完整",
    question_type: str | None = None,
) -> list[tuple[str, str, str]]:
    if question_type is None:
        if "规范" in claim:
            question_type = "规范性"
        elif "描述" in claim or "理论" in claim or "综述" in claim:
            question_type = "描述性"
        else:
            question_type = "解释性"

    question_cards = {
        "描述性": (
            "2012—2025年地方政策执行结果呈现何种结构与演变特征？",
            "O=地方政策执行过程；T=2012—2025年；I=政策执行；P=公共管理的制度分析；R=弱关系：还原执行结果的结构与演变",
            [("描述增量与还原边界", "重建现有统计未能区分的执行类型及其跨时演变。", "统一分类规则、时间窗和材料纳入边界。")],
        ),
        "解释性": (
            "相似制度条件下为何会形成方向相反的执行结果？",
            "O=同类地方政策过程；T=2012—2025年；I=政策执行差异；P=制度激励理论；R=强关系：资源约束调节制度激励对执行结果的作用",
            [("待解释关系与区分性预期", "解释制度激励在资源约束下为何产生相反结果，并区分领导偏好机制。", "两种机制对关键时序和负例产生不同预期。")],
        ),
        "规范性": (
            "地方政府是否应当以程序公平优先约束政策执行效率？",
            "O=地方政府政策执行；T=现行制度阶段；I=程序公平与行政效率；P=公共伦理与规范政治理论；R=弱关系：评价执行行为与公平原则的正当性联系",
            [],
        ),
        "预测性": (
            "到2030年，资源约束下的地方政策执行差异将如何变化？",
            "O=地方政策执行结果；T=2026—2030年；I=政策执行趋势；P=制度激励与情景预测；R=强关系：资源约束和制度激励共同影响未来执行差异",
            [
                ("预测对象、时域与基线", "预测2026—2030年地方执行差异，以2021—2025年趋势为基线。", "历史序列和制度情景共同限定时域与基线。"),
                ("不确定性、验证与更新", "报告情景区间，并用年度新数据校验和更新预测。", "预设年度回测与模型修订规则。"),
            ],
        ),
        "操作性": (
            "地方政府如何在财政约束下改善政策执行一致性？",
            "O=地方政府执行部门；T=当前政策周期；I=政策执行改进；P=公共管理与组织设计；R=弱关系：行动主体在约束下运用治理杠杆实现一致性目标",
            [
                ("行动主体、目标与约束", "地方执行部门以提高执行一致性为目标，并受财政与权限约束。", "主体、目标和约束均可由制度文件核对。"),
                ("行动杠杆、可行性与评价标准", "以流程校准和资源调度为杠杆，用跨地区执行偏差评价成败。", "既有机制证据支持杠杆，并登记成本和风险。"),
            ],
        ),
    }
    question, otipr, question_branch = question_cards[question_type]
    rows = [
        ("已知命题与可信程度", "既有研究反复发现制度激励与执行结果相关，但结论具有条件性。", "S01、S02；sota_gap_map.md"),
        ("未知、争议或经验异常", "相似制度条件下仍出现方向相反的执行结果，现有研究未解释差异。", "S03、S04；sota_gap_map.md"),
        (
            "空白真实性与低研究替代解释",
            "Status=corroborated；Primary Locus=theory-explanation；Obstruction=inconsistent-or-incomparable；Gap Claim=在相同制度压力下，现有理论仍不能区分资源约束何时改变执行机制；Evidence Basis=SYN-GAP-1 综合了支持、负例与可比性判断；Rival Explanations=已检查发表时滞、术语错配、相邻覆盖及仅因对象新而低命中；Research Responsibility=比较同一结果并检验两种解释的区分性预期；Withdrawal Condition=若差异完全由统计口径或不可比时期造成则撤回该空白",
            "SYN-GAP-1；S01—S04；sota_gap_map.md",
        ),
        ("知识成熟度", maturity, "概念与基本描述较稳定，但解释环节仍有争议。"),
        ("研究问题", question, "由 S03 与 S04 的经验冲突直接推出。"),
        ("研究问题主类型", question_type, f"合格答案必须完成{question_type}问题规定的认识任务，而不是按“如何”字面分类。"),
        ("O-T-I-P-R 研究问题卡", otipr, "五要素共同限定问题范围、答案形态和设计边界。"),
        ("预期新增知识", "识别情境触发机制并说明既有平均关系为何在部分场景失效。", "回应现有文献未处理的条件差异。"),
        ("主张类型", claim, "研究目标决定主张类型，而非按方法标签排序。"),
        ("理论视角与核心概念", "以制度激励为理论视角，区分正式规则、执行诱因与行动策略。", "概念边界来自 S01、S02 的定义比较。"),
        ("分析单位、对象与可比性", "以同类地方政策过程为单位，统一时间窗并核查制度功能等价性。", "语义同名项目需经规则与执行功能双重核验。"),
        ("范围条件与边界", "结论限于同类制度和资源约束下的地方执行场景。", "样本与材料不支持跨制度体系普遍化。"),
        ("设计选择及匹配理由", "采用比较案例与过程追踪，逐环节核对机制预测和关键事件。", "该设计能观察机制，不把方法名当作充分理由。"),
        ("变异、比较或反事实", "比较结果相反的案例，并使用同案跨时段变化形成观察值。", "跨案例与跨时段变异共同提供比较基准。"),
        ("替代解释或反对论证", "资源禀赋和领导偏好可能独立造成差异，将用匹配与过程证据区分。", "若替代解释更符合关键时序则保留而非强行排除。"),
        ("可证伪或修订条件", "若机制环节在关键节点缺乏过程证据，或竞争机制预测更吻合，则收缩主张。", "预先登记失败和改写条件。"),
        ("推断上限", "最多主张机制在所比较场景获得支持，不估计跨地区平均效应。", "受案例范围和过程材料等级约束。"),
        ("设计局限及补救", "反事实仍依赖案例可比性，将增加负例并收缩外推范围。", "补充负例或降低主张强度。"),
    ]
    return rows + question_branch


def write_matrix(path: Path, rows: list[tuple[str, str, str]]) -> None:
    body = ["# Knowledge Design Matrix", "", "| 字段 | 内容 | 证据/理由 |", "|---|---|---|"]
    body.extend(f"| {field} | {content} | {evidence} |" for field, content, evidence in rows)
    path.write_text("\n".join(body) + "\n", encoding="utf-8")


class ResearchQualityTests(unittest.TestCase):
    def test_valid_causal_mechanism_protocol_passes(self) -> None:
        rows = universal_rows("因果机制") + [
            ("机制链与可观察含义", "制度信号改变执行预期，进而改变资源投入并产生差异结果。", "每个环节均对应可定位的会议、文件或行动证据。"),
            ("过程证据", "收集关键节点前后的文件、访谈和行动记录并进行时间排序。", "多源材料对同一环节做三角互证。"),
            ("竞争机制", "区分资源压力机制与领导偏好机制，比较其时序和独有预测。", "负例和关键节点证据用于区分竞争机制。"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "knowledge_design_matrix.md"
            write_matrix(path, rows)
            self.assertEqual([], quality.check_protocol(path))

    def test_missing_branch_field_fails(self) -> None:
        rows = universal_rows("因果机制") + [
            ("机制链与可观察含义", "制度信号改变预期并经资源投入影响结果。", "机制环节对应过程材料。"),
            ("过程证据", "按时间顺序核对文件、访谈与行动记录。", "多源材料互证。"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "knowledge_design_matrix.md"
            write_matrix(path, rows)
            issues = quality.check_protocol(path)
            self.assertTrue(any("competing mechanism" in issue for issue in issues))

    def test_noncausal_claim_families_are_first_class(self) -> None:
        branches = {
            "描述/概念": [
                ("概念与分类规则", "按制度约束和行动策略建立互斥且有理论意义的分类。", "分类边界由 S01、S02 和负例共同校准。"),
                ("比较基准与变异", "比较跨地区与跨时段的类型变化并登记反常单元。", "多个单位和时点提供真实变异。"),
            ],
            "诠释/理解": [
                ("行动者意义与语境", "重建行动者对规则、风险和正当性的情境化理解。", "访谈、文件和行动记录交叉核对。"),
                ("研究者位置与反身性", "公开理论视角、材料进入渠道和可能的解释偏向。", "研究日志记录选择与修订过程。"),
            ],
            "规范论证": [
                ("规范前提", "以平等保护和责任可归属为公开价值前提。", "前提与相邻规范原则明确区分。"),
                ("规范推理链", "由权利风险推出责任分配，再推出制度保障要求。", "每一步均列必要前提和反例。"),
                ("最强反方论证", "处理效率损失和责任过度扩张的最强反方。", "使用比例原则回应而非回避。"),
                ("经验与制度约束", "核对现行权责结构和执行能力，不提出不可实施义务。", "法条、案例和机构能力材料共同约束。"),
            ],
            "理论/综述": [
                ("语料范围与纳入规则", "限定核心期刊、时间窗和直接回答研究问题的纳入标准。", "检索式和排除理由写入 source_index.md。"),
                ("综合逻辑", "按竞争解释和范围条件组织文献，不按作者或年份罗列。", "综合单元对应 sota_gap_map.md 的争议轴。"),
                ("可检验命题或知识地图", "输出可区分的三类解释及其可观察预期和证据缺口。", "每个命题映射到候选证据与失败条件。"),
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            for number, (claim, branch_rows) in enumerate(branches.items()):
                path = Path(tmp) / f"matrix-{number}.md"
                write_matrix(path, universal_rows(claim) + branch_rows)
                self.assertEqual([], quality.check_protocol(path), claim)

    def test_predictive_and_operational_questions_have_first_class_design_fields(self) -> None:
        predictive = universal_rows("因果效应", question_type="预测性") + [
            ("原因、结果与方向", "制度激励与资源约束是预测因子，执行差异是预测结果。", "理论与历史序列共同给出方向。"),
            ("时间顺序", "预测因子均在年度执行结果之前测量。", "制度与预算数据带可核对时间戳。"),
            ("反事实与识别", "以相近地区和历史基线构造对照情景。", "对照用于检验预测增益而非宣称普遍因果。"),
            ("效应形式与异质性", "检验资源约束下的非线性和地区异质性。", "报告区间而非单点确定性结论。"),
        ]
        operational = universal_rows("因果机制", question_type="操作性") + [
            ("机制链与可观察含义", "流程校准改变协调预期，进而减少执行偏差。", "每个环节对应可观察的文件和行动。"),
            ("过程证据", "比较干预前后以及未采用流程校准的对照部门。", "多源过程材料支持杠杆判断。"),
            ("竞争机制", "区分资源增加与流程校准两条改进路径。", "成本和时序产生可区分预期。"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            for number, rows in enumerate((predictive, operational)):
                path = Path(tmp) / f"question-type-{number}.md"
                write_matrix(path, rows)
                self.assertEqual([], quality.check_protocol(path))

    def test_otipr_card_requires_all_five_elements(self) -> None:
        rows = universal_rows("因果机制") + [
            ("机制链与可观察含义", "制度信号改变预期并经资源投入影响结果。", "机制环节对应过程材料。"),
            ("过程证据", "按时间顺序核对文件、访谈与行动记录。", "多源材料互证。"),
            ("竞争机制", "比较资源压力与领导偏好的独有预测。", "负例与关键节点证据。"),
        ]
        rows[6] = (
            "O-T-I-P-R 研究问题卡",
            "O=同类地方政策过程；T=2012—2025年；I=政策执行差异；R=强关系：制度激励影响执行结果",
            "缺少分析视角。",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "knowledge_design_matrix.md"
            write_matrix(path, rows)
            issues = quality.check_protocol(path)
            self.assertTrue(any("missing a substantive perspective" in issue for issue in issues))

    def test_known_and_unknown_require_traceable_evidence(self) -> None:
        rows = universal_rows("因果机制") + [
            ("机制链与可观察含义", "制度信号改变预期并经资源投入影响结果。", "机制环节对应过程材料。"),
            ("过程证据", "按时间顺序核对文件、访谈与行动记录。", "多源材料互证。"),
            ("竞争机制", "比较资源压力与领导偏好的独有预测。", "负例与关键节点证据。"),
        ]
        rows[0] = (rows[0][0], rows[0][1], "多篇文献支持")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "knowledge_design_matrix.md"
            write_matrix(path, rows)
            issues = quality.check_protocol(path)
            self.assertTrue(any("known knowledge must cite" in issue for issue in issues))

    def test_exploratory_causal_effect_requires_staged_foundation(self) -> None:
        rows = universal_rows("因果效应", "探索期：概念和基本测量仍不稳定") + [
            ("原因、结果与方向", "制度变化是原因，执行绩效是结果，预期方向为正。", "理论命题给出方向预期。"),
            ("时间顺序", "制度变化先于绩效指标的观察窗口。", "政策日期与结果时间戳可核对。"),
            ("反事实与识别", "使用未实施地区构造对照并控制共同冲击。", "对照组提供未处理反事实。"),
            ("效应形式与异质性", "估计平均效应并按资源基础检验异质性。", "不把平均效应外推为普遍规律。"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "knowledge_design_matrix.md"
            write_matrix(path, rows)
            issues = quality.check_protocol(path)
            self.assertTrue(any("staged pilot" in issue for issue in issues))

    def test_single_case_effect_needs_real_variation(self) -> None:
        rows = universal_rows("因果效应") + [
            ("原因、结果与方向", "制度变化是原因，执行绩效是结果，预期方向为正。", "理论命题给出方向预期。"),
            ("时间顺序", "制度变化先于绩效指标的观察窗口。", "政策日期与结果时间戳可核对。"),
            ("反事实与识别", "以理论预期构造反事实并讨论识别局限。", "反事实依赖未观察情境。"),
            ("效应形式与异质性", "只讨论该场景中的方向，不估计总体平均效应。", "证据不足以外推。"),
        ]
        rows[12] = ("设计选择及匹配理由", "采用单案例研究估计制度变化的因果效应。", "材料集中且便于深入观察。")
        rows[13] = ("变异、比较或反事实", "只观察实施后的一个结果。", "没有其他可用观察值。")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "knowledge_design_matrix.md"
            write_matrix(path, rows)
            issues = quality.check_protocol(path)
            self.assertTrue(any("single-case causal-effect" in issue for issue in issues))

    def test_few_papers_alone_does_not_establish_gap_authenticity(self) -> None:
        rows = universal_rows("因果机制") + [
            ("机制链与可观察含义", "制度信号改变预期并经资源投入影响结果。", "机制环节对应过程材料。"),
            ("过程证据", "按时间顺序核对文件、访谈与行动记录。", "多源材料互证。"),
            ("竞争机制", "比较资源压力与领导偏好的独有预测。", "负例与关键节点证据。"),
        ]
        rows[2] = (
            "空白真实性与低研究替代解释",
            "Status=corroborated；Primary Locus=theory-explanation；Obstruction=insufficient-or-imprecise；Gap Claim=论文很少；Evidence Basis=SYN-GAP-1；Rival Explanations=该机构是新案例且精确题名尚未命中；Research Responsibility=继续搜索同名对象的论文；Withdrawal Condition=若检得更多论文就撤回空白",
            "SYN-GAP-1；S01；sota_gap_map.md",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "knowledge_design_matrix.md"
            write_matrix(path, rows)
            issues = quality.check_protocol(path)
            self.assertTrue(any("gap authenticity:" in issue for issue in issues), issues)

    def test_some_versus_some_question_requires_one_outcome_and_comparison(self) -> None:
        rows = universal_rows("因果机制") + [
            ("机制链与可观察含义", "制度适配、任务需求和创设能力依次收窄制度选项。", "每个环节对应过程材料。"),
            ("过程证据", "按时间顺序核对文件、谈判和组织创设记录。", "多源材料互证。"),
            ("竞争机制", "区分制度竞争与产业利益在不同决策阶段的解释作用。", "按结果和阶段比较独有预期。"),
        ]
        rows[4] = ("研究问题", "为什么有些全球治理倡议由既有机制承接，有些却形成条约型国际组织？", "由 S03 与 S04 的制度形式差异推出。")
        rows[10] = ("分析单位、对象与可比性", "只考察世界人工智能合作组织这一个新机构。", "材料集中。")
        rows[12] = ("设计选择及匹配理由", "采用单案例过程追踪。", "材料较易获得。")
        rows[13] = ("变异、比较或反事实", "只重建一个组织的创设过程。", "不设比较对象。")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "knowledge_design_matrix.md"
            write_matrix(path, rows)
            issues = quality.check_protocol(path)
            self.assertTrue(any("does not define one common outcome" in issue for issue in issues))
            self.assertTrue(any("lacks a comparative design" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
