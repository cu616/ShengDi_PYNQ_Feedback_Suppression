# C本轮协作与纠错记录

日期：2026-10-30；角色：C；工具界面为Codex。本文件是工作摘要，不冒充完整逐字对话或隐藏推理。队长原始任务全文见 [c.txt](../../prompts/c.txt)，其源提交为facd3de。用户另明确要求只推C、不操板、不扩建平台、以A已验证v3组目录候选；本轮据此执行。

## 实际输入和采用决定

- 已先尝试git fetch origin，默认环境DNS失败，SSH联网重试未完成；使用命令级HTTPS映射成功fetch，未改origin配置。C执行pull --rebase origin C，原分支无未推提交，无冲突。
- 逐字读取facd3de的任务、submission-plan与video-plan，读A最新STATE；本地C的A/B全局段较旧，未跨线覆盖。没有恢复REQUESTS派活。
- 固定A facd3de、B86061a7、C330e135，以Git archive作只读源快照。A/B的integration和报告片段均未见；采用实际源码白名单先行，不宣称main集成完成。
- C原tone入口的板端回包取得，36项身份/窗口/差值算术一致；原PCM未到本机，明确审核层次，不让A重采或重复运行。

## 真实失败与修正

| 原现象 | 改动/依据 | 结论与保留证据 |
|---|---|---|
| 默认Python3.14无NumPy/PyYAML | 使用已安装的文档运行时做NumPy/PDF工作；Anaconda配-X utf8运行Skill validator | 不安装新平台；环境失败写入validation记录 |
| check_docs扫描独立导出副本，报告未选历史目标断链 | 导出副本转到materials/staging/tmp；导出文档对未选历史材料使用固定提交链接，运行载荷不改 | 开发仓库文档检查恢复0错误0警告；导出链接另核 |
| r2的C测试将当前运行helper导入为old_verify，正确A v3使“旧参考应不匹配”的断言失败 | 将C330e135旧数值helper固定到sim/feedback/fixtures，SHA e3c748e0…；测试显式加载，绝不放运行目录 | C本地受影响wide4项通过；候选后续回执见validation.json，原失败完整保存validation-initial.json |

9页PDF由正文和排版源生成，所有页渲染预览，未见重叠、裁切或缺字。摘要及图表注明派生/测点/共同窗，未将数字写为ASG。已读本地指南PDF23-25页，前人工作引用作者机构条目与PYNQ官方v2.4文档；没有借文献数字充作项目性能。

## 输出与边界

正文、排版源、白名单/导出及核验脚本、测量引用表、一次性冲突建议均在本目录。Skill入口在skill/audio-evidence；只包含身份绑定和黄金参考/窗口单位两项。旧经验文档保留。

报告PDF和候选/临时解压/坏例位于忽略路径，原片/授权书/私人录音没有加入Git。未连接板卡，未加载overlay，未更改A驱动/RTL/B算法；未合并或推main。RAR未找到工具，未生成伪RAR；最终模板、A/B片段、媒体及匿名/格式全检仍待到货。提交与实际检查证据见integration.json、validation.json和本线STATE/日志。


## A集成5c43d62后的定向修正（后续会话摘要）

用户人工转发A的5项失败：两个source_sha256与当前树不同，registry总数钉4。取得A e939bf0/B683493c/C51ebc38的集成快照并复现原五项，证明旧五项源哈希与be3200e及原冷启动ZIP完全一致。采用的是修正测试工作根，不重钉旧产物、不跳过hash。另修总数/旧文件hash约束，正向选择只在测试中显式批准；B当前catalog未含旧默认标定时生产选择仍拒绝。初次直接以baseline文件替换旧selected hash的尝试暴露此差异，已纠正，没有改变生产MODEL_SELECTION。

两个套件在C与独立集成副本均为7+13通过；原失败与最终计数、源码/载荷证明见integration-review-5c43d62.json。未声称本机跑过379全套；临时工作树路径含tmp导致集成文档检查扫0份，该结果不作为通过证据，正式检查交A既有计划。C自身文档实际126份零错误。原ZIP、旧manifest、A运行源码与B模型不改。接受03-metric三栏C版与A现行README链接方式。修复提交2e7c205单独可取，后续本线状态回执无需用来覆盖A的STATE汇总。
