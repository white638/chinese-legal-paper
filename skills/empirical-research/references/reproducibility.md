# 可复现性与 repro_pack.py 手册

把 cnki-paper 的"绝不伪造 / 页码分级证据"理念落到实证：**证据可追溯，断言才成立**。
`scripts/repro_pack.py` 仅依赖 Python 标准库，跨平台。

## 复现包结构

`repro_pack.py init` 生成：

```
项目根/
├─ data/raw/         原始数据（只读，登记 sha256）
├─ data/clean/       清洗后数据（由脚本生成）
├─ scripts/          全部分析脚本（每个落稿数字的来源）
├─ output/tables/    导出的表（docx/xlsx/tex）
├─ output/figures/   导出的图（png 300dpi）
├─ docs/             设计文档、预注册、决策说明
└─ repro/            ← 元数据（机器可校验）
   ├─ provenance.json     数据来源登记（文件/哈希/行列/获取信息）
   ├─ sample_log.json     样本构造链（每步排除 n_before→n_after）
   ├─ decisions.jsonl     决策日志（计划 vs 实际）
   ├─ numbers.jsonl       从 method_execution.json 派生的只读兼容视图
   ├─ environment.txt     环境冻结（pip freeze）
   └─ REPRODUCIBILITY.md  自动汇总的人读总入口
```

## 命令速查

| 命令 | 作用 |
|---|---|
| `init [dir]` | 建上述结构与空元数据 |
| `add-source --file F [--source-url U --access-date D --note N]` | 登记数据来源：算 sha256、数 csv 行列；同名更新不重复 |
| `exclude --step S --n-before X --n-after Y` | 记一步样本排除（即 AER footnote 4） |
| `decision --date D --what W [--why Y]` | 记一条方法决策（防事后编故事） |
| `number ...` | 已弃用并失败关闭；禁止创建第二份数字真相 |
| `freeze` | `pip freeze` → environment.txt（R/Stata 版本手记） |
| `check` | 审计：来源与哈希、执行合同中的数字—Evidence—Artifact—locator 链、环境冻结；不过退出码 1 |
| `manifest` | 重新生成 REPRODUCIBILITY.md |

## 三条铁律的操作化

1. **识别先于估计** → 设计与识别假设写进 `docs/`，`decision` 记录任何偏离；statspai 的
   `IdentificationPlan` 先 freeze 再 estimate。
2. **数字皆可复现** → 杜绝手敲统计量。每个进正文/表的数字都只在 `method_execution.json`
   登记值、Evidence ID、哈希 Artifact ID、JSON Pointer/CSV 行列 locator 与重现命令；安全
   validator 从工件重新取值核对。`numbers.jsonl` 仅为自动派生兼容视图，不能手写。
3. **来源全程留痕** → 每个数据文件 `add-source`（哈希锁定，被改动会在 check 报警）；
   每步样本排除 `exclude`；定性数据另留编码审计轨迹与代表性引用的原文定位。

## 典型流程

```bash
python repro_pack.py init .
python repro_pack.py add-source --file data/raw/city_panel.csv --source-url "知网/统计年鉴" --access-date 2026-06-14
python repro_pack.py exclude --step "删缺失因变量" --n-before 5000 --n-after 4731
python repro_pack.py exclude --step "限定 2010-2020" --n-before 4731 --n-after 3980
# ……运行受控分析并把结果写入哈希工件，再由 method_execution.json 登记 locator……
python repro_pack.py decision --date 2026-06-14 --what "主回归改用城市聚类SE" --why "组内序列相关"
python repro_pack.py freeze
python repro_pack.py check        # 投稿前过审计
```

## 与 page-evidence 的同构

`page_evidence_audit.py` 审"每处页码引注是否有分级证据"；`repro_pack.py check` 审"每个落稿数字
是否来自执行合同绑定的哈希工件位置"。二者是同一纪律在**文献侧**与**数据侧**的两个落点。

## R / Stata 用户

`freeze` 目前只抓 python 环境。R 用 `renv::snapshot()` 或 `sessionInfo()`、Stata 记 `version` 与
`which <命令>`，手动补进 `repro/environment.txt`。来源、样本和决策登记语言无关；数字仍统一
进入 `method_execution.json`，任意重现命令只登记、不由 gate 自动执行。
