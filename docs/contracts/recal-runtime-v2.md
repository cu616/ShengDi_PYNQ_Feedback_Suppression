# C整机编排扩展 v2

状态：实现待验证；实体组合待A适配，禁止以静态capabilities代替现场语义。
生产方：C编排 / A硬件 / B数值；消费方：A / B / C。
最后变更：2026-11-01；原因：接A c49662d及B 0bdf7fa，区分讲话检查、激励资格和独立预测验证。

本扩展保留唯一recal_entry.sh及recal-product-v1消息信封；配置runtime_profile=b-heldout-v1。C拥有recal_runtime.py和recal_product.py，B的recal_algorithm.py保持原字节；A仅改hw_api/驱动适配，不改C入口。旧recal-policy-consumer-v1的三点验收仍保留原语义，不把新预测判据冒称三臂实测。

## B适配

C worker模块为recal_runtime，包装B的evaluate。配置compute_timeout_seconds=30（fit不得低于15）；请求另带attempts_total。三档顺序固定-22.0/-19.3/-16.5 dBFS，每档training为6段、validation为2段，各16384帧、白噪、peak_cap=0.80。每段独立seed，生成前调用B的white_noise_pcm16；不可达必须停止，不缩放、不换参数冒称达成。C封装实际源SHA/RMS/峰值与seed供A落地，源有效16384帧，训练/验证源身份不得重复。

流程为：准备→提示讲话→讲话完整性/满幅检查→安静→训练采集→B input激励资格→B fit→独立validation→B validate→静音安装核身份→就绪。B的input检查参考宽带性及参考/麦克风相干，不能用于无数字激励的人声窗。C的speech检查仅完整性、有限值、数字静音和满幅，复用B最小帧数/满幅常量；不做语音识别、信噪评价或抵消判断。

retry只允许input/fit且还有预封装下一档；B承诺input仅激励/相干不足、fit仅REJECT_SCALE，validate及speech禁止retry。保留B原回复，不按reason字符串猜数值原因。input retry重新训练，不再叫用户讲话。失败和取消均不启用候选，不恢复旧场景。

validate必须带policy=recalibration-algorithm-v1、not_asg=true、meaning及同一model_sha256/validation_ids/qualifies_cancellation。含义仅300–460Hz独立段预测抑制，不能改写成MSG/ASG、闭环三点收益或听感。结果另存validation_kind=heldout_prediction；听感仍独立。

## A原子cue_input（C同意A实施）

当前prepared_capture=False仍阻塞v1正式运行。允许以单次驱动调用的提示音+尾部讲话捕获替代overlay复用；不改算法/寄存器语义。配置input_mode=cue_input时，须提供capability cue_input_ready_event=true，才可替代prepared_capture。不能只翻旧标志。

prepare完成后C调用perform(op=cue_input)。A先完成下载/Codec/源握手，再开环播放三连音；原PCM、帧计数、提示尾声与有效窗同域。尾声结束且讲话捕获已准备时，poll只读/队列返回一次事件：

`{kind:"input_ready",request_id:"本次cue_input请求",scene_id:"本轮",frame_domain:"本次源域",cue_end_frame:1000,tail_frames:200,valid_first_frame:1200}`。

C收到匹配事件才进speaking。最终cue_input回复含相同frame_domain、valid_first_frame及captures，不能遗漏ready事件或把提示音/尾声算入有效窗。取消优先于ready，迟到旧scene事件无效。A可用driver before_start取消检查/源帧进度实现；取消后旧调用不得再次arm，只有工作线程已停止写硬件才quiescent=true。

LED采用A四位图例：待标定0000，准备/计算/安装0001，讲话0010，安静/采集0100，就绪/运行1000，失败/保护/无法评价1111。色彩不作为实际硬件承诺。armed时C延后LED写，A的indicate也须在armed时拒绝/延后，避免读写竞态。A仍需提供实际抵消/旁路的独立实体指示，软件mode读回不能代替它。

事件名recalibrate/start/stop/cancel/confirm_quiet/mode兼容。C忽略recalibrate,value=short_ignored；BTN1由C按当前running状态解释开始/停止，避免采集中armed误判。BTN3始终优先停声。

## 打包与运行身份

A交product-adapter.json：contract/kind=hardware/source_commit/hash表、expected_identity全部字段、allowed_gain_q12、allowed_calibration_gain_q12、capabilities实测回执、physical-controls.json及未完成blockers。run_dir直接用每个request.run_dir，不落到程序目录/自建product_runs；capture_id包含scene/attempt/phase/segment；first_frame另明确NPZ本地源坐标与cue_input帧域。

开环driver direct_only强制gain_q12=0，应在allowed_calibration_gain_q12显式批准0，不能冒充运行1631；运行增益允许集合仍为A四项。mute必须保留配置增益及LED，只关闭音频；否则安装后运行身份核对会失败。install/model_sha256为模型文件SHA，coefficients_sha256为小端int32 Q20 SHA，二者不得混填。run另返实际音频帧时长和模型/Q20身份，初始化耗时另列wall_seconds。C将run超时预算包含准备开销，不把该开销当连续扩声时长。

B交product-adapter.json：kind=algorithm、source_commit、recal_algorithm.py哈希与本契约版本；C生成策略与源清单。真实部署检查同时核A能力与blockers；--product-review可组装原样A/B供离线审阅，但deployment_ready=false且禁止真实启动。缺件模拟包仍使用两端mock，不把模拟数据传入A硬件。

操作见[统一操作单](../ref/recal-product.md)。本扩展的输入健康检查不替代A的真实输入保护，B的预测验收不替代最终闭环现场报告。
