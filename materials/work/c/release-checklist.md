# C交付与最终核验清单

本轮固定输入A=facd3de、B=86061a7、C=330e135；[逐文件白名单](integration.json)、[冲突决策建议](conflicts.md)、[引用口径](claims.md)、[报告正文](technical-report.md)。机器执行结果以 [validation.json](validation.json) 为准。

## 本轮目录与命令

候选目录以integration.json的destination为准，正式冻结使用 `materials/staging/tmp/submission-candidate-r3/`。r1/r2为保留的首次检查样本；r3修正文档历史引用及C测试对“旧helper”的隐式路径依赖，运行载荷字节未变。旧helper仅在sim/feedback/fixtures中作固定反例，不放运行目录。临时导出放在tmp子目录，避免仓库文档检查将副本当另一套现行文档。从固定Git对象白名单导出，包含源码、模型、构建、验证、许可及证据；没有合并main。用 `python materials/work/c/assemble_candidate.py --local-ref <C源提交> --output <全新目录>` 重建，C源提交见integration.json的c_delivery_commit；已有目录拒绝覆盖。然后运行 `python materials/work/c/verify_candidate.py --candidate <全新目录>`。

报告排版源是 `render_report.py` 与 `technical-report.md`；运行 `python materials/work/c/render_report.py` 生成 `materials/final/shengdi-report.pdf`。这是一份待官方模板与A/B片段校订的审阅初稿，文件名沿用约定，不表示已经最终批准。PDF、候选、原片、授权书和RAR均不自动进Git。收件人本地复建后核同一integration哈希；此设备未访问队长的D:\OCadence_Project路径，不能声称已复制到队长电脑。

## 需人转发的缺件与决定

| 项 | 负责方 | 完成判据 |
|---|---|---|
| A integration.json / hardware.md | A | v3源码、部署与构建依赖清单；最终现场入口和恢复步骤，经A确认 |
| B integration.json / algorithm.md | B | 当前模型、输入/训练验证划分、算法依赖与黄金参考清单；不增加候选或重训 |
| 10类合并片段 | 队长 | 按conflicts.md逐项决定，在独立工作树合main；本轮C不执行 |
| 官方报告模板 | 队长/赛事页面 | 取得实际模板后套版；无模板时不杜撰官方页数限制 |
| 真RAR工具 | C设备/队长电脑 | 可执行rar/WinRAR，能生成RAR格式并独立解压核验；不能用ZIP改名 |
| 视频/照片、参与者展示确认 | A/用户 | 成片与素材编号、真实配置、匿名和授权确认；C只审核字幕和格式 |
| 本队开源协议与仓库可见性 | 用户 | 保留BSD第三方声明，用户办理，不自动改变远端 |

## 最终发布门禁（未到货项保持待检）

- 报告：真实模板、A/B片段、引用/匿名复核、所有页面可读；PDF≤50MB。未测ASG/端到端延迟不得出现实测值。
- 工程：固定目录载荷十项SHA、每文件来源、模型Q20、干净目录导入/黄金参考通过；A/B依赖确认；RAR魔数为RAR4或RAR5且≤200MB，真正独立解压后再跑核验。候选通过不自动等于最终可发。
- 视频：仅A编辑时间线。取得成片后ffprobe核MP4、H.264/AVC、时长≤180秒、≤300MB；从头到尾看/听，学校账号路径匿名、两臂标签与统计窗匹配、没有分别响度归一化或配音冒充现场。
- 照片：全貌最多1张、板卡最多4张，JPG/PNG每张≤10MB；授权书PDF≤50MB由用户单独处理；选交海报PDF/PPT≤50MB，决赛另需AMD模板一页英文海报。
- 全包：英文文件名，无凭据/私人录音/授权书/缓存/.git/worktree/重复ZIP；保留必要失败与纠错来源，未选旧载荷说明原因。教程模拟和实测标签分开。

内部收口日期：10/31候选与报告初稿，11/1干净目录/匿名/格式复核，11/2最终报告、RAR和清单。日期是团队内部排期。本轮不创建自动提醒，也不替代外部官方截止确认。
