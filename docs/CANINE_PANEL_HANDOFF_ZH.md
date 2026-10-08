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

## 新增：154 条捕获要求回放（2026-10-06）

后续新增 `canine-capture`，与上述 `canine-panel` 分开使用。它直接读取第五版
154 条要求的冻结快照：151 个 genomic 候选、2 个 RNA-only、1 个病灶/体细胞来源。
154 条要求与原始来源一致；这不等于154个疾病、样本或已经完成设计的位点。

25 条上下文记录中，19 条实际执行序列比较：8 完整一致，11 保留差异，6 缺锚点。
两端各100bp局部比较为16一致、3差异、6未执行。6 条 WT 参考模板重新拼接一致；
12 条拟议突变模板的插入序列未独立重建，继续复核。两个原始空参考编号使用了
明确的后续断言，但 assembly 映射未独立验收，原空值和完整窗口差异保持。

新增保护检查覆盖倒位不能仅用剂量判断、组成及相位要求、未知插入序列标记、
RNA/体细胞不能提升为生殖系、共享 FGF4 读段不能确定插入位置、PE300不保证600bp、
缓存 TSD 接受不能掩盖实际端点错误、局部一致不能清除完整窗口差异。

接口和复现说明见 [捕获要求合同](CANINE_CAPTURE_VALIDATION.md) 与
[真实来源开发例子](../examples/canine_capture/README.md)。最终测试、安装包和
154条回放收据保存在 `canine_capture_checks_20261006/`；之前的564项结果保留为历史。
94份压缩快照是开发资料，无独立临床金标准或实验样本；科学准入、探针订购和
可报告标志均为false。通用能力的抽象尚未实施，也未推送或发布。

## 最新：接入前的分支完善（2026-10-08）

VERIFIED：新增 `canine-preflight` 命令，输入契约与适用范围见
[CANINE_PREFLIGHT.md](CANINE_PREFLIGHT.md)。本轮只修改bioevidence专用分支，
没有接入或改写canine当前629事件的主稿、参考文件或位点政策。

新增能力：

- 用明确的事件目录约束分母；遗漏事件、缺少检查逐条显示，重复和越界ID拒绝。
- 对支持的简单变异及非重叠复合变异重建整段源侧突变序列，保留两侧和中间未变序列；
  可核对完整突变快照及目标参考上的单个VCF编辑。复合相位仍未验证。
- 核对旧报告对当前事件输入和实现的适用性。当前轻量检查仍实际重算，旧状态不直接继承。
- 捕获特异性、剂量、相位及样本实验表现仍明确 `not_assessed`；候选位点不冻结。

VERIFIED：已用测试先复现CLI缺少入口、浮点坐标导致崩溃、旧复合重建提示过时三个问题，
再完成实现/修正。浮点坐标现在返回输入错误；原始诊断保存在旧诊断字段，当前结果只消除
已经由实际重建解决的限制，不消除来源冲突或相位缺口。同一Codex团队进行了只读代码复核，
不是外部模型审查或独立生物学验收。

验证命令（分支根目录，Python 3.12环境）：

```bash
.venv/bin/python -m pytest --cov --cov-report=term -p no:cacheprovider
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy
/home/ningyu/.local/bin/uv build --offline --out-dir /tmp/canine-preflight-dist
.venv/bin/python -m bioevidence_validator.cli canine-preflight \
  examples/canine_preflight/panel.json --snapshot-dir examples/canine_panel/sources \
  --output /tmp/canine-preflight-example.json
```

最后一条预期exit 2：示例6条源侧重建通过，但未提供目标VCF编辑，不能提升目标等价状态。
完整最终结果、实现哈希与安装包验证方式保存在 `canine_preflight_checks_20261008/validation.json`。

已确认的环境问题：直接离线创建隔离环境时，缓存不包含全部依赖，解析失败。
处理方式是将构建的wheel无依赖安装到临时环境，只从现有已用环境提供依赖路径；
验证脚本会确认被测包来自安装目录而非源码。这证明本次wheel与已有依赖环境能配合工作，
不等于全新联网安装或跨平台CI已完成。

PROPOSED 下一步：canine侧适配器导出当前完整事件目录、按检测路线声明必要检查，
绑定可用源序列和目标等位。缺坐标的61条保留缺证据状态；多个候选等位/重复状态需明确
身份与各自覆盖，不能用一个代表性等位宣称整个来源事件全部通过。已有专项计算结果的
导入和实际收据重验仍需后续实现，不能将生产者的布尔标志直接当作本工具验证结果。


## 用户指定Fable 5.1审核尝试（2026-10-08）

VERIFIED：通过Windows PowerShell实际调用Claude Code 2.1.285，审核代码提交为
`8a96a19d4e84e7f2f403572d52e4a30cbfcace69`。运行时初始化与assistant消息均记录
`claude-fable-5-1`，工具为空。此次只做静态审核，模型没有执行测试。

VERIFIED：服务方安全分类器停止了回复，未提供具体触发原因。CLI自身显示续答一次的
提示；观察到拦截后已终止本次调用。没有人工重试、改写请求、换模型或调整付费设置。

NOT VERIFIED：未取得最终审核报告，不计为Fable审核通过。没有根据本次调用修改库代码；
此前722项测试结果仍只是工程验证。详细记录见
[审核结果](claude_fable_review_20261008_8a96a19/RESULT_ZH.md)。不要自动重试这个已被拦截的请求。
