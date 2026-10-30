# 可复用排查经验

提交候选的最小可运行技能入口：[audio-evidence](audio-evidence/SKILL.md)。复用已有身份检查、黄金参考和源激活窗口用例，限离线核对；来源、正常/失败命令与失效边界均在该入口。交付复核见 [C材料清单](../materials/work/c/release-checklist.md)。

近期Jupyter协作、现场试音和数据评价经验见 [音频协作经验](audio-collaboration-lessons.md)。以下保留早期麦克风排查适用范围，不要求在当前已验证链路上重复全部排查。

依据 ../docs/log/experiments/2026-10-audio-debug.md。先确认已知 WAV 播放，再用成功耳麦核对 MIC 输入、MAX4466 核对 LINE_IN，最后逐项比较待测组合。

适用范围：PYNQ-Z2、base overlay、AudioADAU1761。输入选择必须与实际接口一致，重载 overlay 后重新选择输入。三段/四段数量不能证明触点兼容，噪声也不等于人声。

失效边界：没有导通和带载偏置测量时，不能将稳定噪声直接定性为放大不足、偏置不足或转接线损坏。以上是早期硬件经验，不是本轮候选的验收入口。
