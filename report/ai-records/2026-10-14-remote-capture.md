# AI 协作记录：远程录音

- 日期：2026-10-14；板卡时钟错误（文件时间为 2025-05-04）。
- 基线：main，ebaa41d1965e6d5b1f453a6b534730cfe6d9cba7，有既存未提交修改。
- 用户要求：直接控制板子采集声音，随后确认“已登录”。本文是执行摘要，不是完整原始对话。
- 范围：已登录 Jupyter 的 Notebook 检查、备份、追加单元、5 秒 LINE_IN 录音和数值分析。

## 实际执行和证据

通过浏览器 File / Make a Copy 创建 audio_playback-Copy1.ipynb，原 Notebook 末尾追加两个单元，分别读取 record/save 的已安装 Python 源码，以及限时采集。复用 pAudio，没有重载 overlay。采集前提示音响关闭，等待 10 秒，选择 LINE_IN，record(5)，finally 中 deselect_inputs；没有调用 play/bypass。

浏览器输出 CAPTURE_COMPLETE。保存后回读 WAV，验证双声道 24 位 PCM，并以 2^23 为满幅进行符号扩展和电平统计。

- 路径：/home/xilinx/jupyter_notebooks/base/audio/shengdi_captures/linein_20250504_011108_1f7571bf.wav；同名 .json 保存指标。
- sample_rate=48000，frames=240000，duration_s=5.0，record_wall_s=4.931968564999806。
- 通道 0：peak_dbfs=-18.638045278309626，rms_dbfs=-35.626576502377674，dc=0.00027846676409244535。
- 通道 1：peak_dbfs=-18.600841708673123，rms_dbfs=-35.603380907644336，dc=0.0002554968973000844。
- 两通道 near_fullscale_fraction（abs>=0.999）=0，nonzero_fraction=1。

只验证采集、WAV 格式和电平；没有听辨或确认此次包含人声，没有测量信噪比、声学反馈、稳定增益、自定义 PL 或算法性能。5 秒是样本目标，驱动异常下不能保证硬超时。物理音响开关状态由现场负责，AI 无法目视核实。录音保留板上，没有上传或提交私人音频。

## 恢复和下一步

Notebook 已点击保存；备份可供对照恢复，新增单元位于末尾。不要 Run All，原文件包含播放与 bypass 单元。下一步先标记接线、增益、距离及安静/讲话条件；再单独安排低音量限时直通，由现场人员掌握音响断电。未提交或推送本轮本地修改。
