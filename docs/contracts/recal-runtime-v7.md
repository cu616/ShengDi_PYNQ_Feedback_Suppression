# C 上电配置与显式 CAL 恢复 v7

状态：C软件已修复并模拟验证；A目录绑定8799f40b已交，待本包上板复核。
生产方：C编排 / A输出路径；消费方：A / C；B数值接口不变。
最后变更：2026-11-02；沿用[v6](recal-runtime-v6.md)的唯一入口、模型事务与回包格式。

## 上电顺序

第一动作仍mute，默认静音待CAL。配置初始化前，AUX原始寄存器可为上电0x00，aux_db可如实unknown/None；C保存原快照，configuration_ready=false，暂不比较aux_db/aux_raw_left/aux_raw_right与部署配置。驱动、位流、hwh、helper身份及其余部署字段仍按既有规则校验；没有模型可启动。

CAL后由A现有prepare按cfg写AUX。只有completed的prepare返回中三个AUX字段均与部署配置一致，C才设置configuration_ready=true并开始讲话/激励；后续漂移仍拒绝。每个新scene重走此门槛。A不需新增构造写寄存器或人工上电脚本；0x00不得伪报为已核验0dB。

## 失败恢复

数据不足、模型拒收、输入保护和普通采集/数值HARDWARE_ERROR终止本scene并确认abort；不恢复旧模型。静音/旧任务停止已确认后，用户长按BTN0至少1秒可建立新scene，清空尝试与讲话重说计数，重新prepare/验证；无需重启服务。旧调用未返回仍按既有stopping等待，禁止并发启动。

代码/位流/算法身份混搭，以及无法确认mute/quiescent的故障仍锁定，CAL不能绕过；运行不会自动重启。B的cause与原回复保留，恢复仅由显式CAL触发，不改B阈值。

## 原件与时序

C每次调用提供唯一request.run_dir。A的ProductHardwareV2.perform须在分派前执行self.run_dir = request.get('run_dir') or self.run_dir，特别是cue+input；这样同一scene内B有限重说不会再次写同一个NPZ。不能删除原件后重试或放宽驱动独占创建。

quiet_seconds改4；speech_seconds保留2.5。当前嵌入cue的source长度为int(seconds*48828.125)-2，RAM上限131072；4秒需195310帧，超过上限。2.5秒是包含提示音的总调用长度，用户听完三连音后持续讲话至安静灯；本轮不改B判据或扩建RTL。

准确启动与重试操作见[操作单](../ref/recal-product.md)。
