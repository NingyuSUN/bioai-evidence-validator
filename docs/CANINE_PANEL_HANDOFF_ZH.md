# Canine 专用验证分支交接

本地分支 `canine-panel-validation` 从 bioevidence 0.8.0 的
`a6258f0aa2f78850a9c1bfeb39a83965409206c6` 建立。先完成犬 panel 的专用核对；
通用抽象留给后续。这一轮未推送、发布或合并。

## 已实现及用途

新增 `bioevidence canine-panel`，读取完整变异表达、固定版本参考片段和文件哈希。
它核对两端坐标、实际 REF、已知插入字母、未知插入长度、方向及完整上下文。
原描述、更正候选、冲突和暂停原因分开保存。程序始终保持实验验证、可报告和
探针可下单为 false；通用证据准入逻辑没有加入犬专用判断。

修复旧参考版本解析：CanFam3.1 和 UU_Cfam_GSD_1.0 的小数部分不再丢失。
独立代码复查发现的超长数字异常、复合事件声明未明确标注两处问题已修复。
复合事件提供的 REF/ALT 现在保留，并明确要求完整等位基因重构。

## 实际执行结果

- 564 项完整测试通过；总体代码覆盖率 98.83%。ruff、mypy 及独立安装 wheel
  验收通过。这些是软件检查，不能换算为疾病检测准确率。
- 分支内实际病例为 6 个来源候选：5 段 201 bp、1 段 214 bp，合计 1,219 bp。
  六段来源/目标完整上下文一致；4 条工程通过、2 条继续复核。ABCB1 类型冲突、
  DLL3 原描述缺 `g.` 保留。另有 9 个明确标为人工制造的错误控制，没有独立临床标签。
- Canine 工作区另外执行了 FLCN、RBM20、CMO 三个新来源案例。连同上述六条，
  合计 9 条/10,915 bp 上下文一致、4 条工程通过/5 条复核。该整合报告位于
  `cnv_sv_followup_20261006/validation`，没有将三条额外实例伪装成分支内的六条。

## 重放入口

```bash
uv sync --frozen --extra dev
uv run --frozen python examples/canine_panel/run.py --output /tmp/canine-replay
uv run --frozen bioevidence canine-panel examples/canine_panel/panel.json \
  --snapshot-dir examples/canine_panel/sources --output /tmp/canine-report.json
```

最后一条应返回 2，表示有明确保留的复核项。返回 0 只代表这一层工程核对通过。
原始源字节、哈希、公开 NCBI 版本、提取历史和许可说明都保存在例子目录。

## 边界与下一步

目标参考片段的收据依赖可信生产者；本命令没有独立重算整套犬基因组，也没有
证明断点唯一性、HGVS 3′ 规范化、转录本等价、复合相位、疾病致病性、犬种范围
或实验检出能力。真实样本和阳性/阴性对照仍需验证。后续先扩展犬专用的插入边界
旋转、接头及剂量对照核对，再根据实际重复需求抽象通用组件。

YELLOW：你对“参考序列一致与实验检测能力”的理解尚未评估。需要能够解释：
两端位置和整段序列匹配为什么仍不能证明接头唯一、PCR 成功或疾病诊断成立。
本轮没有需要你决定的事项。
