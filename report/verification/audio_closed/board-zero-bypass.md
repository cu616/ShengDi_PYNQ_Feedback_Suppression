# 首次板上零模型旁路：用户返回结果

证据来源：用户粘贴的完整控制台输出和metadata，AI未连接板卡或读取原始PCM。用户仅执行zero_bypass；zero_cancel及真实模型A/B尚未执行，现场听感未提供。

- capture_id：64ba6930-2ec6-40ac-bacb-c08ae53e66b6
- 文件：zero_bypass_20250505_191708_174887.npz（文件名为板卡时间，不据此认定实际实验日期）
- fixture_id：box_v1_20261016；bypass=true，zero_coeff=true。
- Q12增益65（−35.98893182649838dB），hp_volume40，48828.125Hz，PLL回读000000002803。
- 完成24414帧，名义0.49999872秒；保留末尾16384帧，first_frame8030。
- bit_exact=true；预测、残差、实际输出mismatch均0；评价16128帧；三种饱和计数均0。
- mic RMS −35.152964257028934 dBFS，peak −18.477412087301946 dBFS，满幅样本0。
- bit SHA256：4d49dfbe53180536f0c2302a19ed6ead23e3336e959dd50567dc647473635316。
- model SHA256：4f0422c333a45438b69b02c5399d1f329685c51cef3e105c9d0fffd01a5b1414；本次实际系数为全零。
- 输出包含STOCK_BASE_RESTORED_AND_CODEC_MUTED，官方PLL回读0271023c2103。

结论仅为零模型旁路的本次板上数字核对通过，脚本报告恢复静音；不能认定抵消模式已验证或测得ASG。下一项同参数zero_cancel。

用户指出原说明缺少每格目的、具体操作与执行顺序。已重写README与Notebook说明为代码格1～6，注明当前继续点及通过/停止条件；未改变代码格、驱动或bitstream。
