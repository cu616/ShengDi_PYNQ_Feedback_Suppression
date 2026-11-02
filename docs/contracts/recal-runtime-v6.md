# C 最终冻结与现场回包 v6

状态：冻结交付；实体效果由A现场回包复核。
生产方：C；消费方：A / C；B判据及A运行时字节不变。
最后变更：2026-11-02；沿用[v5](recal-runtime-v5.md)的唯一入口、维护模型身份与取消要求。

## 最终包与模型

A功能冻结b6107bc，取件提交7bd365b；只复制v3-io八项运行时文件和原manifest.json，逐项固定SHA，不包验证脚本。C在全部取消边界检查通过后生成deployment_ready=true、missing=[]、adapter_check_allowed=true的包。此标志表示允许部署统一软件流程，整机真人与声学效果仍按实际回执报告。

bootstrap-model.json是包内固定维护/静音初始化模型；512个零系数，bootstrap_only=true、eligible=false。A维护显式使用该文件和包内声明SHA，也可不传模型参数而使用清单diagnostic_model。正式流程不会把它当合格标定：CAL后拟合新模型、独立验证、装载回读，再原子提交models/current.json。现场实际模型文件名和SHA记录在status.json的bundle.model_path/model_sha256及每个scene结果中，无需人工猜模型。

## 单一回包

唯一命令仍为recal_entry.sh --state-dir <同一状态目录> --export <目标.zip>。包绑定相同product-manifest SHA的所有scene一并导出，旧包scene/计算回执留原处，避免混入其他包身份。现有目标文件不覆盖。

| 路径 | 内容 |
|---|---|
| return-manifest.json | 每个回包文件的SHA清单 |
| summary.json | 本包身份、所有scene状态/模式/数值/听感记录与原件映射 |
| results/<scene>.json | 每轮成功、失败、取消的完整结构化回执 |
| algorithm/*-request.json、*-reply.json | 本包scene的B请求/回复；人声input请求不导出 |
| captures/.../*.npz | 非人声训练/验证原件，原字节与SHA保留 |
| models/<scene>/<sha>/...json | 拟合原模型及实际安装副本 |
| maintenance/adapter-check.json | 同一状态目录的维护自检回执（存在时） |

人声PCM、运行人声捕获和未知来源音频留板；自动数值与听感仍分开，未推导ASG。新增维护JSON遵循同一清单哈希校验，旧解析器可按既有库存规则核验。

操作、准确路径、模型SHA及sudo执行顺序见[统一操作单](../ref/recal-product.md)。常驻服务沿用A实测的sudo权限环境，以root访问板卡硬件；日常只用实体按键，C不操板。
