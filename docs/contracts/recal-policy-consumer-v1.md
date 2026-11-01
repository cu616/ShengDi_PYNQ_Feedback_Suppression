# C重标定判定消费接口 v1

状态：实现待验证；B于2026-11-01交付判定库，用户要求C确认并接入。
生产方：C编排 / B数值库；消费方：C状态机、A/B产品适配。
最后变更：2026-11-01；原因：承接B的四类cause、本轮延迟和强制独立验收，不改变B阈值。

本接口是[recal-product-v1](recal-product-v1.md)的可选数值回执扩展，标识`recal-policy-consumer-v1`。C拥有`board/audio_replay/recal_policy_consumer.py`；B拥有[recalibration-policy-v1](recalibration-policy-v1.md)及`src/feedback/recal_policy.py`，C只按固定提交原样接入，不改判据。唯一入口仍由C维护，A/B不改`recal_entry.sh`。

## 调用及缺项

C消费器调用B的check_capture、plan_excitation、select_probe_frequencies、check_fit、check_three_point、decide。返回供现有evaluate包装器合并的`decision/cause/reason/policy_contract/policy_result`；policy_result完整保留B原回执。它不代替实际捕获解析、拟合或现场三臂采集；只有判定库不能宣称实体流程已完成。

`final(capture,fit,three_point)`显式调用`decide(...,require_three_point=True)`；另要求capture=OK、fit=DEPLOYABLE_FIT及three_point=PASS均实际提供。缺任一项为data_insufficient，永不以NOT_RUN当通过。fit阶段只调用check_fit，不能把预检当可启用模型。

`fit`的lag_evidence必须含`estimator:"estimate_lag",scene_id,captures:[{capture_id,sha256}],lag_frames`；scene及捕获身份须等于本轮训练请求。expected_peak_tap只取该lag_frames，禁止传base_peak_tap或旧模型峰位作后备。C检查来源绑定，不重新制定延迟估计或阈值。

采集不合格时调用B的plan_excitation。仅当RAISE_EXCITATION与下一项预封装激励的kind/target_rms_dbfs/achieved_rms_dbfs/peak/sha256/frames全部相符，且attempt仍在B界内，才返回retry；未封装就以数据不足结束，不临场扩档。削顶直接input_overload，不自动调AUX、增益或重试。选点调用只接开环H/freqs/coherence/gain_db，输出在采cancel前冻结，不能按cancel结果重选。

## 四类原因及状态机

| B cause | C outcome | 处置 |
|---|---|---|
| HARDWARE_ERROR | hardware_error | 立即停声，禁止自动重试；本服务锁定等待维护 |
| MEASUREMENT_INAPPLICABLE | measurement_inapplicable | inconclusive并静音；提示本次条件无法评价，不宣布模型成败，不自动增益扫描 |
| MODEL_UNQUALIFIED | model_rejected | 停声且拒收候选；不安装、不恢复旧场景模型 |
| DATA_INSUFFICIENT | data_insufficient | inconclusive并静音；只有上述已封装B规则可有限重采，否则提示重新标定 |

result.json另存cause与algorithm_receipts；听感仍独立。无cause的旧模拟回执保持兼容；携带任何上述cause的valid_pass也会阻止安装。未知cause拒绝为data_insufficient并保留原文，不猜成某一类硬件或模型问题。

## 最小样例

本轮延迟：`{"estimator":"estimate_lag","scene_id":"s1","captures":[{"capture_id":"t1","sha256":"<训练原件SHA>"}],"lag_frames":128}`。

无法评价：`{"decision":"measurement_inapplicable","cause":"MEASUREMENT_INAPPLICABLE","reason":"本轮条件无法评价","policy_contract":"recal-policy-consumer-v1","policy_result":{"schema_version":1,"status":"INCONCLUSIVE","cause":"MEASUREMENT_INAPPLICABLE","points":[],"reasons":["三臂source身份不一致"]}}`。

evaluate包装器仍须补齐recal-product-v1的contract/request_id/scene_id；最终通过另须model_sha256、validation_ids、qualifies_cancellation及evidence。包装器/拟合与A真实硬件适配尚未因此自动就绪，按[产品操作单](../ref/recal-product.md)交接。
