# 仿真与验证

`audio/`保存RTL测试平台，由build/scripts/test_audio_*.tcl调用；`feedback/`保存路径拟合、定点参考及模拟硬件采集脚本的Python测试。

既有执行结果见 [证据索引](../report/evidence-index.md)。部分捕获仿真采用缩小帧数，软件模拟硬件也不能替代真实上板验证。文件关系见 [工作区系统框图](../docs/ref/workspace-architecture.md)。
