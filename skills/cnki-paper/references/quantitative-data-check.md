# Quantitative Data Check

本能力只在定量、计算、混合方法或明确的数据可行性任务中加载。它检查一个已经取得的文件，
不扫描目录，不建立跨项目数据库，不从用户“拥有什么数据”反向生成选题，也不自动匹配问题与
变量。

## 触发条件

满足任一项才触发：

- 用户明确要求定量、计算或混合方法研究；
- 候选问题将提出变量、样本、统计估计、因果识别或结构化文本测量；
- 用户要求判断一个数据驱动选题是否可做；
- 正式分析前需要核验已经取得的样本、代码本或字段。

理论、历史、规范、解释性文本和普通文献综述默认不加载本文件，也不因缺少数据卡而阻塞。

## 唯一输出

形成一张 `avereth-quantitative-data-check/v1` 可行性卡。核心字段是：

```yaml
data_feasibility:
  status: unverified | metadata_verified | sample_verified | ready
  candidate_sources:
    - name:
      access_route: local_file | public_download | public_api | registration |
                    application | institutional_subscription | commercial |
                    unavailable | unknown
      official_or_user_source:
  unit_of_analysis:
  temporal_and_spatial_coverage:
  required_variables:
  variation_or_identification_requirements:
  linkage_or_panel_requirements:
  legal_ethics_and_license:
  main_risks:
  next_cheapest_verification:
```

`local_file` 只是访问方式之一，不获得优先权。来源比较只看问题适配、覆盖、变量、取得成本、
法律伦理和可复现性。

## 强度与门禁

| 决策点 | 最低要求 |
|---|---|
| 选题发散 | 只列合理来源路线，不阻塞 |
| 候选比较 | 至少说明存在何种可核验的取得路线 |
| 定量设计确认 | 至少核验元数据、问卷、代码本或字段 |
| 正式分析前 | 至少核验真实样本或真实查询结果 |
| 结果写作 | 只使用已执行分析及其实际结果 |

脚本只能自动给出 `unverified`、`metadata_verified` 或 `sample_verified`。`ready` 必须由具体研究
设计、链接与变异要求、法律伦理条件和真实执行证据共同确认，不能由文件可读或字段存在自动取得。

## 读取已取得文件

```powershell
$Check = Join-Path $AverethHome 'skills\cnki-paper\scripts\optional\quantitative_data\quantitative_data_check.py'
& $Python -X utf8 $Check .\sample.csv `
  --source-name '已取得样本' `
  --access-route public_download `
  --official-or-user-source official `
  --required-variable id `
  --required-variable outcome `
  --header-confirmed
```

输出只含字段名、聚合诊断、文件哈希和可行性边界，不含原始行或本地绝对路径。CSV、TSV、
XLSX、XLSM 只有确认首行是字段名时才使用 `--header-confirmed`。DTA 可读取自带字典元数据；
运行时没有受控解析器的格式保持 `unverified`。

## 科学底线

- “听说有这个数据库”不等于可实施；正式设计至少需要真实元数据或代码本。
- 文件可打开不等于关键变量、分析单位、时间空间覆盖、链接键或识别变异成立。
- `sample_verified` 只证明取得的小样本与声明字段相符，不证明完整数据质量、代表性或因果识别。
- Writer 只接收当前章节需要的数据名称、样本、变量、方法、结果和必要限制；不接收路径、候选目录、获取日志或未选来源。
