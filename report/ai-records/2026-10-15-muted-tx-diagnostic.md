# 静音数字输出诊断：协作与验证记录

- 任务 / 日期 / 负责人：两次限时自定义直通未听到声音后的 PL 内部输出诊断；2026-10-15；AI 实现与操作，现场听感由用户提供，队员姓名未知。
- 可见模型：Codex，具体模型版本未在项目记录中确认。
- 基线：`main`，起始 HEAD `ebaa41d`；工作区已有大量其他未提交修改，本轮未提交或推送。
- 资料：本仓库 README、`docs/progress.md`、团队规范、既有 `audio_probe` 源码与板上 Notebook；ADAU1761 Rev. F 数据手册和 PYNQ 官方 `audio_adau1761.cpp`。
- 原始对话：当前 Codex 会话；本文件仅为工作摘要，不冒充完整逐字导出。

## 提示与纠错

用户原文关键反馈：“完全没听到声音”（第二次约 −63 dB 总衰减直通）；“我的音响没有外部可调旋钮调节音量”；此前指出麦克风在箱内，不可能按“距麦克风 20 cm”指示讲话，并指出现场讲话期间 AI 仍在准备代码造成等待。AI 接受纠错，改为先备齐代码，用箱外固定循环声源进行第二次 2 秒测试，随后停止盲目增加增益。

第二次直通板上返回 `hp_volume=30`、`hp_db=-27`、`pl_shift=6`、计划 2.0 秒、实测 2.003 秒、帧计数增加 97786、`muted_at_end=True`、`PL_CONTROL_MUTED True`、`STOCK_BASE_RESTORED`、`STOCK_PLL_READBACK 0271023c2103`。现场用户仍反馈完全没听到声音。−63 dB 是 Codec 与 PL 数字衰减估算，不是实际声压测量；本轮箱外手机声源进入箱内麦克风的电平没有同步测量。

## 本轮诊断交付

- 新增独立的 `src/rtl/audio_pl_diag.v` 和 `audio_tx_status` GPIO，保持旧 `audio_probe` 不变。控制位 4 使外部 `sdata_o` 强制为低电平，内部帧通路和串行器继续运行。接口定义见 `docs/interfaces/audio-diag-v1.md`。
- 新增匹配的 Vivado 构建脚本、仿真和 `board/audio_diag/audio_diag.bit/.hwh`、`muted_tx_diag.py`。bit SHA256 `DCC3DEE7279A22F11F8B4489EF263A63FBB159165C08E382E50708B2768C1D58`，hwh SHA256 `907F7DFBCA743732E36A66B3134BF4A037CECB8AF60003633963B613C616AE2C`。
- 依据用户对这三个文件的明确授权，上传到板卡 `base/audio/audio_diag/`；在板上独立 Notebook `base/audio/audio_bringup_muted_smoke_2026-10-15.ipynb` 执行 `%run audio_diag/muted_tx_diag.py` 并保存。

## 实际验证及边界

- Vivado 2018.3 运行 `test_audio_diag.tcl`，结果 `AUDIO_DIAG_PASS`；测试在诊断模式中检查计数增加和外部 pin 仿真持续为低。测试激励来源为仓库 `sim/audio/tb_audio_diag.v`，非独立实测波形。
- Vivado 2018.3 综合、实现并生成 bitstream；实现 DRC 0 违规，WNS 3.456 ns、WHS 0.034 ns，但外部 I/O 时序约束仍不完整，不构成板级时序签核。Python 文件用 bundled Python `ast.parse` 检查语法通过。
- 板上约 1 秒返回帧数 48890、非零处理输出帧数 48884、内部串行器 1 位边沿数 1181037；`PL_CONTROL_MUTED True`、`STOCK_BASE_RESTORED`、`STOCK_PLL_READBACK 0271023c2103`。脚本打印的 `physical_sdata_forced_low=True` 是依据控制模式和 RTL 的陈述，**未用示波器独立测量物理引脚**。
- 这些数据支持“PL 内部处理输出非零、内部串行器活动”，不支持“DAC 收到正确数据”“音响已经有声”“啸叫已抑制”。Codec 恢复后只读寄存器状态已记入 `docs/progress.md`，不能代表短时开启期间读值。
- 本轮没有保存录音，未运行进一步有声实验。恢复方式：脚本 `finally` 先清零 PL 控制并静音 Codec，再加载官方 `base.bit`、恢复并核对原 PLL。板卡最终报告为官方 base 配置。

下一步：使用官方 base 播放一段幅度已知、时长受限的测试音，数字方式标定无实体旋钮音响的可听阈值；再在自定义 PL 下以相同可比的输出设置和已测 ADC 输入电平做对照。现场不需要在 AI 编码期间持续讲话。
