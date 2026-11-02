# C 维护自检开放范围 v5

状态：按用户2026-11-02任务开放A维护；正式流程须满足既有验收。
生产方：C；消费方：A / C；B接口不变。
最后变更：2026-11-02；沿用[v4](recal-runtime-v4.md)的模型事务、运行证据和取消要求。

唯一入口仍为recal_entry.sh。adapter_check_allowed按每份冻结包单独授权，与deployment_ready独立；用户已要求A=5939ee5的新包开启维护自检。该授权允许维护者主动执行既有短链路，不等于正式重标定或声学效果验收。

维护者显式提供板上当前模型路径和完整SHA；在创建硬件前核SHA，并按已核文件的fixture_id创建硬件对象。不开启旧场景模型的自动恢复；维护检查不提交产品current指针，finally执行abort。模型、包、原件和步骤回执仍按既有规则保存。

A=5939ee5的training/validation/input/install/run取消回调已接入；父类prepare/_capture仍遗漏Event/回调。因此本包adapter_check_allowed=true，deployment_ready=false，field_trial_allowed=false，missing只保留这个实际缺口。旧包的install/运行路径缺口与泛化integration not approved不沿用。正式入口、服务安装和受控现场继续由实际门槛控制，不通过改布尔值冒充已修复。

操作与准确板卡路径见[操作单](../ref/recal-product.md)。
