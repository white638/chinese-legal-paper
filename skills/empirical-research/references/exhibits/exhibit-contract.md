# 社科实证表图工件合同

本组件是 `empirical-research` 的可选 execution 适配器。它不创建阶段、状态、收据或结果注册表；
`cnki-paper` 仍是唯一控制面，`method_execution.json` 仍是执行与数字的唯一机器事实源。

## 激活

仅当一个 v3 Action 的 `parameter_snapshot.content.exhibit_spec.schema_version` 为
`avereth-exhibit-spec/v1` 时激活。纯人文路线、没有表图动作的实证路线以及未要求重建表图的旧工作区
不增加新门禁。表图动作必须在 confirmed v4 design 的 execution blueprint 中有独立 STEP，且在来源
结果之后执行。

## 两条闭合链

科学结果链保持：

`Claim → Result → accepted estimation Action → numeric Artifact`

展示链另行闭合：

`ExhibitSpec → accepted rendering Action → ExhibitData Artifact → PDF/SVG/PNG Artifact`

`source_result_ids` 把展示链连回科学结果链。渲染 Action 必须读取每个来源 Result 中精确绑定所用
numeric locator 的哈希 Artifact；来源 Result 必须由该 operation 的当前 accepted Action 产生。
展示 Artifact 必须精确登记这些来源 Action、来源 Result、spec SHA、样式、位置和论证角色。图片不
取得数值权威，`avereth-exhibit-data/v1` companion data 只投影已登记数字和语义。

## Action 参数快照

`parameter_snapshot` 继续使用 `canonical-json/v1`。其 `content.exhibit_spec` 放
`avereth-exhibit-spec/v1`，`content` 同时保留 operation/procedure 快照，并由既有
`parameter_snapshot_sha256` 冻结。关键字段包括：

- `exhibit_id`、`kind`、`placement`、`argument_role`；
- `source_result_ids`、`quantity`、`unit`、`confidence_levels`；
- 事件研究的基期、参考值和处理边界；
- 非线性结果的 response scale，以及明确区分连续横轴与有序类别横轴的 `x_scale`；
- `style_profile`、解析后的 style/recipe SHA、`formats` 与自足图注所需信息；
- 可选的 `x_label`／`y_label`：非空字符串时覆盖坐标轴文字；缺省时纵轴为 `quantity (unit)`，
  事件研究横轴取 style profile `labels.relative_period`（中文社科为"相对期"），其余横轴留空。

首批 recipe 为 coefficient forest、event study、marginal effects、predicted probability、
trend/binscatter 和 regression/balance table。地图、RDD、合成控制与规格曲线留给后续版本。
事件研究与 trend/binscatter 的横轴必须是有限数值；边际效应与预测概率必须用
`x_scale=continuous|ordered_category` 明确声明横轴语义，数字编码的有序类别不会自动改作连续变量。

## Artifact 扩展

表图相关 Artifact 的 `role` 使用：`plot_data`、`table_data`、`main_figure`、
`appendix_figure`、`figure_preview`、`main_table`、`appendix_table`、`render_log`。
这些 Artifact 继续位于 `runs[].artifacts`，不另建 manifest 权威。除既有 `id/path/sha256/role` 外，
登记 `exhibit_id`、`kind`、`source_result_ids`、`source_action_ids`、`plot_data_artifact_id`、
`renderer`、`native_adapter`、`style_profile`、`spec_sha256`、`format`、`placement`、
`argument_role` 与自动 `render_checks`。

## Companion data

JSON 形式服从 `avereth-exhibit-data/v1` schema；CSV 形式使用同名字段，每行重复
`schema_version=avereth-exhibit-data/v1`。非参考点必须用 `source_numeric_locator` 回指来源 Result
已经登记的 `numeric_values[].locator`，验证器据此核对 estimate。被绘制的 numeric value 还必须在
`exhibit_semantics` 登记 quantity、unit、estimand、confidence level、vcov type、cluster level，
非线性结果另登记 response scale；这些字段与 companion row 逐项相等。基期等结构性零值可在
`is_reference=true` 时不声明 locator，但须由 ExhibitSpec 明确声明 reference period/value。
CSV 数值服从普通十进制/科学计数法词法，不接受下划线等 Python 专用写法。`panel_label` 必须全空或
全非空；同一 model/group 系列跨面板保持相同颜色、线型和点型，且声明值必须来自所选 style profile。

## 渲染环境与写入

渲染命令必须传入预先分配的 `software_environment_id`：

```text
python scripts/exhibits/exhibit.py render --spec SPEC.json --data DATA.csv --out NEW_DIR --environment-id ENV-EXHIBIT-001
```

R 后端把实际 R、包版本、请求字体、**实际解析到的字体**以及 backend/style/recipe SHA 写入 render log 的
`software_environment`，同时输出其 canonical SHA。登记 accepted Action 前，把同一对象写入对应
`software_environments[].exhibit_renderer`；验证器强制 Action、环境记录与 hash-bound render log
完全一致。render log 还绑定 canonical ExhibitSpec、companion data、style、recipe、backend 输入 SHA，
以及每个 PDF/SVG/PNG 输出 SHA；数据或图形任一变化都会使旧展示链失效。`--out` 必须是不存在的新目录，
全部声明文件验证通过后才以一次目录替换提交；命令只把
派生清单打印到标准输出，不另写未登记的 bundle manifest。论文复现环境应按该捕获记录锁定；CI 的
R job 是当前依赖兼容性检查，不代替论文自己的环境锁。

## 字体解析与回退链

style profile 的 `fonts.base` 是首选字体族，`font_fallbacks.base` 是按序声明的回退族
（中文社科：Noto Serif CJK SC → Source Han Serif SC → SimSun → STSong；国际政治学／政治经济学：
Liberation Serif → Times New Roman → TeX Gyre Termes → DejaVu Serif）。渲染器按序取第一个本机可用
的族，写入 render log 的 `resolved_fonts.base` 与 `render_checks.font_fallback_used`；整条链都不可用
才以 `EXHIBIT.RENDERER.R_FAILED` 终止。`requested_fonts_available=true` 表示解析到了 profile 声明的
某个族，不表示首选族在本机存在。

`resolved_fonts` 属于 `software_environment` 并参与其 canonical SHA：同一 spec 与数据在另一台解析到
不同字体的机器上会得到不同的环境身份，旧展示链随之失效，这是刻意的可复现语义，不是缺陷。验证器
拒绝 profile 未声明的解析族（`EXHIBIT.PROVENANCE.ENVIRONMENT_MISMATCH`），并要求
`font_fallback_used` 为显式布尔值。论文最终版应在 render log 中确认解析族是否为目标刊接受的字体；
中文稿件用 SimSun 回退渲染的图在投稿前仍需作者核对字形。

## 三线表投影（无需 R）

中文期刊要求可编辑的三线表，而不是表格的图片。`regression_or_balance_table` 的 companion data 可以
不经 R 直接投影为 Markdown 或 LaTeX（booktabs）文本：

```text
python scripts/exhibits/exhibit.py table --spec SPEC.json --data DATA.csv --out table.md [--format md|tex] [--digits 3]
```

投影只复制 companion rows 中已登记的数字：每个 term 占两行（估计值；括号内标准误，无标准误时用
方括号置信区间），末行为各模型的样本量，表注由行内 `vcov_type`、`cluster_level`、`confidence_level`、
`estimand`、`unit` 语义生成，列头与表注用语取自 style profile 的 `labels`。文件首行是 HTML／TeX
注释形式的溯源（exhibit_id、来源 Result、spec 与 data 的 SHA-256），不进入读者可见的表注。
命令拒绝覆盖已存在的输出文件。

该投影不是新的 Artifact role，也不改变数值权威：数字仍以来源 Result 与哈希绑定的 companion data 为准。
作者把投影粘入 Markdown／TeX 稿件后，Word 版由 `docx_normalize.py --tables` 规整为三线表；
需要把表格作为登记 Artifact 进入 render log 的，仍走 R 渲染路径。

## 派生图表地图

build 阶段的 `avereth_core/build/exhibit_map.py OUTDIR --write` 只更新 `figure_asset_map.md` 内的机器
预填标记区，绑定当前 execution SHA，并保留标记区外的作者判断。它不推进 build，也不签收据。
作者仍需确认论证功能、正文或附录位置、为何需要表图、
图注是否自足及保留/合并/拆分/删除处置。output 阶段仍负责逐页真实渲染检查。

## 失败码

- 来源：`EXHIBIT.PROVENANCE.RESULT_MISSING`、`ACTION_NOT_ACCEPTED`、
  `DATA_ARTIFACT_MISSING`、`HASH_MISMATCH`、`SELF_SOURCE`、`OUTPUT_DRIFT`、
  `NUMERIC_LOCATOR_AMBIGUOUS`、`SEMANTIC_MISMATCH`、`ENVIRONMENT_MISMATCH`、`RENDER_LOG_INVALID`、
  `EXHIBIT_ID_DUPLICATE`
- 合同：`EXHIBIT.CONTRACT.STEP_INVALID`、`PARAMETER_BINDING_INVALID`、`RESULT_FORBIDDEN`
- 数值：`EXHIBIT.NUMERIC.DRIFT`、`CI_MISMATCH`、`UNIT_MISMATCH`、`SAMPLE_MISMATCH`
- 语义：`EXHIBIT.SEMANTIC.REFERENCE_MISSING`、`BASELINE_MISMATCH`、
  `REFERENCE_INVALID`、`ESTIMAND_UNDECLARED`、`NONLINEAR_SCALE_UNDECLARED`、`UNCERTAINTY_UNDECLARED`、
  `CLUSTER_LEVEL_MISSING`
- 格式与视觉：`EXHIBIT.FORMAT.INVALID`、`ROLE_MISMATCH`、`EXHIBIT.VISUAL.FONT_TOO_SMALL`、
  `GRAYSCALE_COLLISION`、`TOO_MANY_SERIES`、`STYLE_INVALID`、`PANEL_LABEL_MIXED`、`RASTER_ONLY`、`FONT_UNAVAILABLE`
- 稿件：`EXHIBIT.MANUSCRIPT.ORPHAN_ASSET`、`MISSING_CAPTION`、`MISSING_NOTE`、
  `CAPTION_RESULT_MISMATCH`、`UNREFERENCED_ASSET`

确定性门禁只检查身份、文件格式、数值、明确语义、样式配置和可复现关系。裁切、字体替换、实际
灰度辨识度、表图是否真正帮助论证、版面是否清楚以及目标刊功能同构仍由作者判断、venue overlay
和最终逐页 QA 处理。
