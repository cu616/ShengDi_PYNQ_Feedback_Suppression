# 官网工程RAR候选交付与核验

本轮只整理外层包；正式运行件固定为resume3原ZIP及41文件，未重建ZIP、未改源码/算法/参数/位流、未操板。

## 文件与身份

- 最终RAR：`materials/final/shengdi-source.rar`，实际 **4765996字节**，严格小于200,000,000字节；格式为RAR5。
- RAR SHA256：`a7866e1c25c597b3f6831b140d847563cdec09136a512cb81e1c8ce7e77b6d5a`。
- 外层清单SHA256：`813f9697813f43796465845cd9b243e7d58927eaf1095ca8fe735b73f63ef6bd`。
- 本机交付副本：`D:/Flushbonading_Contest/ShengDi_PYNQ_Feedback_Suppression/materials/final/shengdi-source.rar`；开发克隆也保留同哈希副本。
- 原冻结ZIP SHA256：`b167d0b579df94e76065b067ada8feb2b3e050f7c44aa3541f57a47319d615b4`。
- product-manifest SHA256：`beb36216d26b6cbb510f6f211d139424943863693e48fee44511ad200d62d9ef`；release=`beb36216d26b6cbb`。
- RAR大文件未推Git；Git提交小型工具、逐文件来源及核验记录。

## 六项交付

1. 真正RAR及同名`.rar.sha256`在上述路径；RAR自检退出0，未改名伪装ZIP。
2. [冻结核验](official-source-frozen-check.json)：原ZIP/41文件/四个历史源一致；包内`--check`输出identity_ok=true、deployment_ready=true、missing=[]。
3. [逐文件来源JSON](official-source-file-sources.json)、[CSV](official-source-file-sources.csv)：仓库路径、完整commit:path或“仅包内，由C组装”。两份包内文档与Git只有行尾差异，不声称有完全相同的原始Git字节。
4. [与main的差异](official-source-vs-main.json)、[源码文本差异](official-source-vs-main.patch)：对比main快照faab273；4份程序内容不同，另有2份文档仅行尾不同。配置等包内生成件不重建。
5. [完整外层清单](official-source-manifest.json)与[解压回执](official-source-candidate.json)：独立UnRAR解压后887文件全部核验通过，正式目录恰为41文件。
6. 跨设备将RAR及.sha256作为文件直接转发，保持原字节；不通过复制网页文本或改后缀传包。接收方执行下面复核。

## 接收方复核

先用系统哈希工具或PowerShell `Get-FileHash .\shengdi-source.rar -Algorithm SHA256`，与本页64位RAR哈希逐字比对。
再用支持RAR5的工具解压，进入其中`shengdi-source`目录：

```text
python -B tools/submission/verify_official_source.py .
python -B board/audio_replay/recal_product.py --base board/audio_replay --check
```

首条要求ok=true、frozen_files=41；第二条要求identity_ok=true、deployment_ready=true、missing=[]。
外层upload_ready=false反映设计报告/环境缺项，不表示冻结运行包身份失败。不要把该候选直接当成最终上传批准。

## 实现报告与边界

[原件/交付副本核验](official-source-implementation-copies.json)采用A提交faab273。九份技术报告保留日期、原构建/补导出阶段、技术数值及全部告警；仅脱敏主机名、用户名和机器专属路径。
DCP原件哈希核验通过但默认不入RAR，仓库位置与哈希保留。原件SHA清单不能用于核对脱敏副本；副本有自己的SHA清单。
原件清单另列logs/runme.log，该日志未随所提供Git提交入库，本轮只保留其来源哈希引用，未宣称C独立核验。

采用口径：已施加的时序约束全部满足；DRC无Error。保留时钟定义与部分I/O延迟约束告警。
具体数值、来源与副本哈希以实现报告核验JSON为准；旧v3资源报告仅作历史记录。

## 尚未关闭项

[缺项清单](official-source-missing-items.json)：设计报告按队长确认继续为审阅稿，等待终稿替换；板上软件精确版本与外部board_part定义尚未完整锁定。
已收录同稿review DOCX/PDF，未另写不同设计报告、未用空文件或其他版本报告冒充。

重新组外层包的工具：[assemble_official_source.py](../../../materials/work/c/assemble_official_source.py)、[verify_official_source.py](../../../materials/work/c/verify_official_source.py)，工具提交1e2a6ef4a48ca9378adefa9f27cbc3bcaf8e85b4。
工具依赖官方RARLAB RAR，不随包分发；运行文件只从指定ZIP读取，依完整SHA校验，补件快照固定faab273。

## 提交入口修订与参考数据

修订data/src/models/report及根目录五份面向评审的说明，移除开发占位和分工交接口吻；内部STATE不随RAR提交。历史注册表只整理说明字段，模型条目/数值未变。按指南需要保留的协作提示与纠错记录明确归档，不作为当前操作指令。

data/reference现在含普通样本、合法负满幅、截断前缀越界三组CSV及参数/预期结果清单，均来自既有v3软件用例，明确标记合成数据。它们不是现场录音，不用于声学收益结论。

[入口说明审查](official-source-publication-audit.json)、[参考数据复核](official-source-reference-check.json)均通过；原7项算术检查也通过。解压后可执行：

```text
python -B tools/submission/submission_reference.py --root . --verify
```

旧RAR的SHA256已被本页新值替换；冻结安装ZIP及41个运行文件的SHA不变。
