# 参赛材料工作入口

本目录按队长 2026-10-30 要求建立，用来汇总制作过程和最终可提交材料。
技术状态、有效结论及数字只查 [最新 A 分支 STATE](https://github.com/cu616/ShengDi_PYNQ_Feedback_Suppression/blob/A/docs/STATE.md)。队长电脑对应 `_a_work/wt-a/docs/STATE.md`；根目录旧 main 的同名文件尚未集成，不能据它回退结论。

- [制作安排、指南要求与代码集成](planning/submission-plan.md)
- [视频分镜、拍摄方法和采购建议](planning/video-plan.md)
- 可直接转发的任务：[A](prompts/a.txt)、[B](prompts/b.txt)、[C](prompts/c.txt)
- C 本轮交付：[核验与缺件清单](work/c/release-checklist.md)、[报告正文](work/c/technical-report.md)、[测量引用表](work/c/claims.md)、[冲突建议](work/c/conflicts.md)、[协作纠错记录](work/c/session-record.md)。

## 放在哪里

| 路径 | 用途 | 负责人 |
|---|---|---|
| `planning/`、`prompts/` | 本轮制作方案与人工转发文本，不作为最终上传材料 | 队长 |
| `work/a/` | 硬件说明、拍摄配置、素材目录、硬件文件交付清单 | A |
| `work/b/` | 算法报告片段、动画、模型交付清单 | B |
| `work/c/` | 集成清单、测量复核、技术报告编辑源与提交检查 | C |
| `learning/` | B 制作的离线 HTML 入门教程及素材，供学习与讲解使用 | B |
| `raw/` | 原始拍摄素材，默认仅本地保存，不进 Git | A |
| `private/` | 授权书等含身份信息的文件，仅本地保存，不进 Git | 用户 |
| `staging/` | 尚未确认可提交的工程包或导出文件，不进 Git | C |
| `final/` | 用户审核后确定上传的成片、报告、RAR、照片、海报，不自动进 Git | 各项负责人 |

上表是路径约定，未交付的文件不创建空白成品占位。文件名用英文小写、数字、下划线或连字符；项目说明 `README.md` 沿用指南示例。

队长电脑的收件目录是 `D:\OCadence_Project\Flushbonading_FPGA_Contest\materials`。
A 工作树内也有受 Git 管理的同名目录。两者不是自动同步目录：本轮队长会复制说明和提示词到收件目录；未来成品由接收人核对后放入 `final/`。
其他设备使用自己仓库根目录下的 `materials/`，通过分支、提交和附件交接，不假定队长的绝对路径在别人的电脑上存在。

## 成品收件名

视频 `final/shengdi-demo.mp4`；报告 `final/shengdi-report.pdf`；工程 `final/shengdi-source.rar`；
全貌图 `final/shengdi-overview.jpg`；板卡照片 `final/shengdi-board-01.jpg` 至 `04.jpg`；
选交海报 `final/shengdi-poster.pdf`。授权书由用户保存在 `private/` 后单独上传，不打入公开源码包。

工程版本、实测配置和引用证据由交付清单绑定。教程动画中的合成信号不能当实测；一份文件放进 `final/` 也不表示已经上传后台。
