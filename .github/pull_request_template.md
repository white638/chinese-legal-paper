## 变更目标

说明本 PR 要解决的具体问题，以及为什么应在当前版本处理。

## 影响边界

- [ ] 未引入第二套 Skill、状态机、完成权威或收据体系
- [ ] 未改变八阶段的名称、顺序和 fail-closed 语义
- [ ] 未绕过 workflow registry、方法合同、Artifact ID 或摘要绑定
- [ ] 未删除仍承担来源说明义务的第三方声明或许可证
- [ ] 兼容性、迁移和回滚影响已说明

## 验证证据

列出实际执行的命令及结果；不要只写“测试通过”。

```text
python tools/smoke_check.py .
python tools/check_workflow_registry.py --check
python -m unittest discover -s skills/cnki-paper/scripts -p "test_*.py"
python -m unittest discover -s skills/empirical-research/scripts -p "test_*.py"
python -m unittest discover -s evals/researcher-collaboration -p "test_*.py"
python -m unittest discover -s tools -p "test_*.py"
```

涉及运行时、方法合同或学术写作行为时，补充相应 eval、隔离安装和 parity 结果。

## 风险与回滚

说明最可能的失败方式、受影响工件，以及可执行的回滚步骤。
