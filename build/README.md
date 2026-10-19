# 工程重建

`scripts/`已有Vivado2018.3工程创建、综合/实现、仿真及约束排查脚本，`audio_bringup.xdc`是共用音频约束。`work/`保存本机生成工程和运行产物，已被Git忽略；正式验证证据另归档到report/verification。

例如create_audio_calibrate.tcl可创建标定工程，传入build参数会继续综合实现。运行前核对工具和板卡定义；脚本包含create_project -force，不应随意覆盖正在编辑的生成工程。已有本机构建成功记录不等于另一队员完成了干净环境复现。

源码、产物与板卡文件关系见 [工作区系统框图](../docs/workspace-architecture.md)。
