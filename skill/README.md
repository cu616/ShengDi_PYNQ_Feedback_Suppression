# 可复用排查经验

| 技能 | 适用场景 | 已验证效果 | 失效条件 |
|---|---|---|---|
| [audio-evidence](audio-evidence/SKILL.md) | 离线核对 FPGA 音频交付的位流/驱动/模型身份、黄金参考、源激活窗口与幅度单位 | `verify_candidate.py` 十项 `payload_checks` 全 true；换旧版文件必须退出 2 并报 `v3 identity mismatch` | 无跨板实测；ASG、听感、端到端延迟不能由离线检查得到 |
| [complex-response-audit](complex-response-audit/SKILL.md) | 判断一份声学/电声辨识结果的复频响表能否自洽，以及相位误差在目标频段被放大多少 | 在真实报告上抓出六行里五行不自洽（8350 Hz 报 −152°/0.815，余弦定理应得 2.286）；群延迟拟合在本地数据测出 −0.43 帧 | 缺复数、表为低精度舍入值、增益不明时不能定案；不能靠平移数据凑结论 |

提交候选的最小可运行技能入口：[audio-evidence](audio-evidence/SKILL.md)。复用已有身份检查、黄金参考和源激活窗口用例，限离线核对；来源、正常/失败命令与失效边界均在该入口。交付复核见 [C材料清单](../materials/work/c/release-checklist.md)。

近期Jupyter协作、现场试音和数据评价经验见 [音频协作经验](audio-collaboration-lessons.md)。以下保留早期麦克风排查适用范围，不要求在当前已验证链路上重复全部排查。

依据 ../docs/log/experiments/2026-10-audio-debug.md。先确认已知 WAV 播放，再用成功耳麦核对 MIC 输入、MAX4466 核对 LINE_IN，最后逐项比较待测组合。

适用范围：PYNQ-Z2、base overlay、AudioADAU1761。输入选择必须与实际接口一致，重载 overlay 后重新选择输入。三段/四段数量不能证明触点兼容，噪声也不等于人声。

失效边界：没有导通和带载偏置测量时，不能将稳定噪声直接定性为放大不足、偏置不足或转接线损坏。以上是早期硬件经验，不是本轮候选的验收入口。
