# 设计源码

`rtl/`保存自定义音频通路、诊断及开环标定模块；`vendor/pynq_v2_4/`保存厂商I2S收发及许可证；`feedback/`保存路径拟合与定点软件参考。当前尚无已完成的实时啸叫抵消模块。

模块依赖和数据流见 [工作区系统框图](../docs/ref/workspace-architecture.md)，逐文件阅读顺序见 [核心代码指南](../docs/ref/code-reading-guide.md)。
