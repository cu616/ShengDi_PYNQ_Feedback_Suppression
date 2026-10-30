# 交队长的一次性集成决策单

这是目录候选的处理建议，不是已合并结论。预演冲突集合沿用 facd3de 的 submission-plan.md；本地仅比较固定 A=facd3de 与 C=330e135 字节，没有git merge、ours/theirs、改历史或推main。完整双向上下文见 [conflict-context.diff](conflict-context.diff)（差异方向A→旧C，删除号通常代表若回退C会丢失的A能力）。行号均属于这两个固定提交。

| 路径 / 具体片段 | 双方作用与风险 | 建议提交队长的决定 | 定向验证 |
|---|---|---|---|
| `.gitattributes`：A→C差异hunk -7/+7、-20/+17 | A的现行身份文件字节策略与C旧包/JSON的-text规则不同，换行转换可能改变已冻结SHA | main保留progress的union；对十项载荷按A精确字节保护；C证据按需补规则，禁止全文件选C | Git blob→干净检出→导出目录三者十项SHA一致；特别检查.py与.sh换行 |
| `board/audio_replay/closed_tools.py`：常量/有效帧检查，hunk -8/+8 | 共用参数校验；旧C的采样率或判断可能退回旧约定 | 运行依赖取A v3 manifest中的a95265b9…；C测评扩展只在独立消费者里保留 | trial_parameters边界及A/B/C导入，采样率48828.125精确一致 |
| `board/audio_replay/replay_trial.py`：A16–102 / C16–24附近；verify_paired_bitstream、runtime_stop、decode_counts、保存失败副车 | A79c4d9f7含位流拒绝、bit22输入满幅停声、packed计数解码、0.25秒Codec等待；C旧驱动缺这些 | 原样保留A79c4d9f7，C不覆盖。C当前评价逻辑在evaluation/model_comparison中选入 | 十项manifest、独立混搭拒绝与运行停声纯函数用例；硬件字节未改无需重复上板 |
| `board/audio_replay/replay_tools.py`：A77–134 / C77–94的verify_replay | A从实际记录prediction重建宽残差，计算prefix并用非对称rail；C旧helper从24位residual增益会回退错误 | 保留Abba22102；C消费者按v3分派，拒绝helper混搭 | 原黄金参考与C消费者；截断前史、skip+2、正负rail、零输出、宽残差反例 |
| `src/rtl/audio_pl_replay.v`：A76–96、106、139–165附近；并注意`feedback_fir.v`的宽输出依赖 | A有residual_wide、增益前25位、bit22独立输入计数；旧C截断/状态语义不同 | 顶层与FIR、Tcl/XDC、bit/HWH整套取A，不单独拼RTL；候选已固定A字节 | RTL SHA对evidence；本轮不重新综合或操板；若队长改源码才重新仿真/构建 |
| `board/audio_replay/README.md`：A1–51 / C1–85 | A新入口明确根位流旧版、v3正式绑定；C老使用说明带旧操作 | A入口保留，增加C候选与Skill链接；旧说明保留历史位置，不能恢复成默认入口 | README给出的目录及manifest可读；不要把旧root bit打进候选 |
| `report/verification/audio-replay/2026-10-22-512-taps.md`：A236/274/294及399以后 | A包含后续更正，C有历史测评补记；整份覆盖会丢成功/失败史 | 队长保留双方按日期/来源可辨的原记录；新编辑结论只链接claims和STATE，不重写历史 | 核322Hz、增益/手机与真人条件、尾窗撤回；原记录哈希仍可追溯 |
| 同目录`README.md`：A55/136附近 | 证据入口与旧报告链接差异 | 按A现行结构补C独立验收链接，逐链接合并，不恢复旧运行命令 | check_docs及引用存在性 |
| `docs/STATE.md`：三线相邻段、关键数字与下一步 | C330仍是旧全局状态；A已汇总10/30冻结与新回包 | 队长从A最新版起，覆盖本次C段，B段由B确认；不要把C整份STATE覆盖A | 数字链接到同一证据，ASG未测、四项I/O缺口和零系数长时标签保留 |
| `docs/REQUESTS.md`：A侧已归档 / C仍有旧开放表 | 恢复会把废弃派活渠道和旧任务重新激活 | main继续A的归档决定；本次缺件在材料清单由人转发，不新增REQUESTS派活 | 现行入口无旧表回链，旧历史仍可追溯 |

main+A、main+B、A+B的STATE冲突也按责任段处理。具体Git合入由队长完成；上述是建议，C目录候选只选本线有权导出的无冲突固定文件，未批准任何main覆盖。

还需A交硬件清单与最终现场入口，B交模型/依赖清单；本轮查到的两个远端均无这两份integration.json。候选从实际源码逐文件生成白名单，不把缺清单解释成算法或硬件失败。报告章节可先行，最终冻结待清单确认。
