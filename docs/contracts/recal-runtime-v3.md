# C整机接入扩展 v3：冻结算法与维护链路

状态：实现待验证；普通使用者正式流程仍须满足讲话窗口准备条件。
生产方：C编排 / A适配 / B算法；消费方：A / B / C。
最后变更：2026-11-01；原因：接A a3f516f、B 2ccf746，身份和实际调用字段统一。

唯一正式入口仍为recal_entry.sh，消息信封仍为recal-product-v1。正式算法只用B recal_algorithm.evaluate，具体版本及文件SHA由包清单identity固定，本轮接recal-algorithm-2026-11-01.1。旧三点Consumer及v2包装只用于历史复核/模拟，不与此路径竞争。

## B冻结身份与策略

config.attempts直接深拷贝B ATTEMPTS，三档顺序及字段不改。compute_timeout_seconds=30，最低15。包manifest、每次run收据、每个计算请求/回复保存identity()原始JSON内容；version/file_sha256必须与包内实际B文件一致，混搭在调用evaluate之前拒绝。文件名和时间戳不作为身份。

input是B的讲话检查，ref=0仍可通过；C不再另写讲话阈值。训练后直接fit，独立捕获后validate。讲话重说保持同一激励档，最多重试len(ATTEMPTS)-1次；fit retry才前进下一档。validate不重试。C不按中文reason猜数值结论，保留B原回复及EXIT_REASONS。

只有C的原件身份、已知硬件过载、独立性/缺段、事务和版本检查可先行拒绝；数值阈值和模型资格仍由B判断。qualifies_cancellation的scope是独立段预测抑制，not_asg/meaning必须保留；不得改写为整机抗啸叫、ASG或听感。

## 通用采集计划与原件接入

B数值请求保留canonical attempts/plan。config可另带capture_plans作为适配传输计划，C按当前attempt/op取值给perform；每段capture_id加scene/attempt/op/index。A a3f516f接受flat plan.captures、level_dbfs、seed/validation_seed，每段需显式给level_dbfs，避免回退stimulus_dbfs=-22。训练seed4242，验证4243，仅为传输映射，B ATTEMPTS原字典不改。

若A落盘在配置run_dir_root而非request.run_dir，C仅接入capture_import_root白名单内、SHA吻合的原件，复制到本scene目录，保留original_path与原SHA，不改PCM/metadata/source坐标。这是格式适配，不要求重采。C不把16382补零伪装16384，也不自行删除首段异常数据；帧数裁决和预热按A/B正式回执执行。

## 同一入口的维护检查

recal_entry.sh --adapter-check --model <A已核对模型>执行create_product→capabilities→prepare→training(1段)→install→run(3秒)→abort；这是A维护者主动执行的短链路，不运行普通人声重标定、不启用新候选。C只在离线替换PYNQ/Codec/驱动叶子后执行原A工厂验证字段；真实板卡仍由A唯一操作。

维护检查要求包清单允许adapter_check；默认模型须列入包清单并匹配SHA。A使用当前板上已核对模型时，须同时显式给--model与--model-sha256，先核完整SHA再创建硬件对象，回执记为operator_supplied_current_model；不默认恢复仓库旧模型。无论成功、失败或取消，finally均abort并保存逐步请求/回复。它不放宽默认常驻入口的prepared_capture检查，也不将applies_at=next_capture登记当作实际PL系数已生效。正式模型事务在得到实际装载回读之前不得提交eligible current。

维护install字段为model_path/run_gain_q12，回复model_sha256为文件SHA、coefficients_sha256为小端Q20 SHA；run携带seconds/gain_q12/bypass/model_path，记录elapsed_seconds原值，不用墙钟值冒充音频时长。poll事件名维持recalibrate/start/stop/cancel/confirm_quiet/mode；短按BTN0过滤及BTN1切换由C兼容。

## 仍需分开的事实

prepared_capture=false时，先prepare再input仍会再次下载位流；只有prepare本身完成不能证明讲话提示后无初始化。A建议的“明确等待”不等于已实现原子讲话窗。默认正式运行保持阻塞，维护链路可以单独交给A。

A a3f516f保护字段由A解释，C不从saturation诊断字段自行触发停声。后续A版本若修正保护语义，须单独固定来源，不能静默混入a3f516f。16382有效帧、首段异常及B冻结代码的已知诊断应在回执中如实保留。

操作和A/B回传见[统一操作单](../ref/recal-product.md)。

## 2026-11-01 收口补充

收到A 22c88bb的嵌入提示音路径时，C按op=input/cue=true/seconds=2.5调用；听到提示音后讲话，准备和采集属于同一次调用。返回marker只作原件窗校验，C从原NPZ取得真实first_frame/end_frame/source SHA，保留A原字段；不强迫A改成C旧poll事件形式。每次硬件请求使用独立输出目录，各档plan.levels只封装当前B档位，避免硬件端重新扫档或覆盖旧原件。

停止分“已停声”和“驱动调用已返回”：旧硬件调用未返回时进入stopping，轮询和STOP仍可用，禁止并发新硬件任务；可记录一次明确CAL请求，收尾后才执行，STOP可撤销它。C不要求A为19秒返回强杀线程，但A必须传播cancel_event并在driver before_start检查，禁止旧任务再次arm。

--field-trial只供A同一完整现场窗口，通过包清单field_trial_allowed逐版本开放，要求显式当前模型/SHA及嵌入cue路径；回执标field_trial=true。默认正式运行不放宽prepared_capture。存在确定执行错误的A版本不开放该参数，也不开放维护运行；重组审阅和原件复核可独立完成。
