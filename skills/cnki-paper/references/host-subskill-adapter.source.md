# 下游适配器协议

`cnki-paper` 持有工作区的全部阶段与完成语义。下游 Skill、脚本和外部工具只
提供一次受限动作或结构化事实；它们不是工作流入口。

## 调用合同

每次调用必须明确：

1. 当前八状态与 publication track；
2. 允许读取的输入路径和稳定身份；
3. 允许生成的工件或返回字段；
4. 不得改变的标题、主张、范围、证据和用户授权；
5. 失败、权限不足、验证码或登录时如何返回；
6. 动作后由哪个本地 validator 复核。

适配器返回后必须回到主控制器。不得直接写 status/receipt，不得创建另一份来源、
设计或执行事实表，不得用搜索结果数量、工具成功退出或 reviewer 意见代替 gate。

## 浏览器与权限

CNKI/Scholar 的登录、机构权限、验证码、下载确认及真实网页操作留在主线程。
后台/隔离 reviewer 遇到这些动作时返回 `PRIMARY_THREAD_ACTION_REQUIRED`，包含
当前阶段、查询或 URL 和需要用户完成的动作；不得模拟成功或换用未授权浏览器。

## 获取适配器

- 搜索/导出结果始终是 candidate-only；
- 只有控制器核验身份、内容、权限、角色、文件和 SHA 后才能升级；
- DOI、URL、题名—作者—年份精确命中时复用 Source ID；
- 国际轨不经过中文数据库例外，中文轨也不能用国际元数据替代其明确合同。

## 方法适配器

方法工具只检查问题—推断—设计适配和真实执行记录。它不能因自身擅长某方法就
选择方法，不能把规范/历史/理论研究伪装成实验，也不能隐藏负面结果或偏离。

## 评审适配器

methods、contribution、clarity 三个 reviewer 只读且输入隔离。只有三个不同真实
context ID、三份不同输出和通过本地 validator 时才可登记 independent；否则准确
登记 single_agent。评审内容仍须经过唯一 audit action graph。

## 输出工具

Pandoc、LaTeX、Word/LibreOffice 和 PDF 解析器只是 render/QA 工具。缺少工具是
BLOCKED；已有文件不是渲染完成的替代。output 只接受 audit receipt 的规范稿
path+SHA，并在 staging、守卫、视觉 QA、事务发布和签收全部成功后推进。
