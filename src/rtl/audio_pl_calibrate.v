// Independent open-loop stimulus/capture. ADC NEVER feeds DAC.
// Matching frame pairs: actual serializer input, ADC left. See interface v1.
module audio_pl_calibrate #(
    // 开环测量：产生DAC激励→同帧参考和ADC入RAM→PS读回；ADC不回送DAC。
    parameter integer CAPTURE_FRAMES = 32768
)(
    input wire clk, resetn,
    input wire [31:0] control, capture_cmd,
    // control[0]启动，[4:1]衰减右移量，[8]种子；capture_cmd[14:0]为读地址。
    input wire sdata_i,
    output wire sdata_o, bclk, lrclk,
    output reg [31:0] frame_count = 0,
    output wire active,
    output reg [23:0] capture_left = 0, capture_right = 0,
    // 命名沿用GPIO接口：left实际为DAC参考，right实际为ADC左声道，并非立体声。
    output wire [31:0] capture_status
);
    reg [10:0] divider = 0;
    (* ASYNC_REG = "TRUE" *) reg [1:0] adc_sync = 0;
    reg [31:0] rng = 1;
    reg [3:0] shift_latched = 6;
    reg arm_d = 0, frame_active = 0, done = 0;
    reg [15:0] captured = 0;
    reg [15:0] scheduled = 0;
    // scheduled是发声帧预算，captured是收到的帧数；ADC失效也必须按预算停声。
    reg [23:0] tx_word = 0;
    reg [47:0] memory [0:CAPTURE_FRAMES-1];
    // 每个RAM地址高24位存实际DAC参考，低24位存该帧ADC左声道。
    reg [47:0] read_word = 0;
    wire arm = control[0];
    wire config_ok = control[4:1] >= 4 && control[4:1] <= 10;
    wire [31:0] x1 = rng ^ (rng << 13);
    wire [31:0] x2 = x1 ^ (x1 >> 17);
    wire [31:0] next_rng = x2 ^ (x2 << 5);
    wire signed [23:0] random_signed = next_rng[23:0];
    wire [23:0] rx_left, rx_right;
    wire rx_valid, serial_out;
    assign bclk = divider[4];
    // 100MHz时BCLK=100MHz/32，LRCLK=100MHz/2048，即标称48828.125帧/秒。
    assign lrclk = divider[10];
    assign active = frame_active && arm && resetn;
    assign sdata_o = (resetn && arm) ? serial_out : 1'b0;
    assign capture_status = {14'd0, (arm && !config_ok), captured, done};
    // status[17]非法配置，[16:1]已捕获数量，[0]完成；数量不是最后一个地址。
    iis_deser receiver(.CLK_100MHZ(clk), .SCLK(bclk), .LRCLK(lrclk),
        .SDATA(adc_sync[1]), .EN(resetn), .LDATA(rx_left), .RDATA(rx_right), .VALID(rx_valid));
    iis_ser transmitter(.CLK_100MHZ(clk), .SCLK(bclk), .LRCLK(lrclk),
        .SDATA(serial_out), .EN(resetn), .LDATA(tx_word), .RDATA(tx_word));

    always @(posedge clk) begin
        if (!resetn) begin
            divider <= 0; adc_sync <= 0; frame_count <= 0;
            rng <= 1; shift_latched <= 6; arm_d <= 0;
            frame_active <= 0; done <= 0; captured <= 0; scheduled <= 0; tx_word <= 0;
            read_word <= 0; capture_left <= 0; capture_right <= 0;
        end else begin
            divider <= divider + 1'b1;
            adc_sync <= {adc_sync[0], sdata_i};
            arm_d <= arm;
            if (rx_valid) frame_count <= frame_count + 1'b1;
            if (!arm || !arm_d) begin
                // arm_d是上一拍arm；未启动或刚出现上升沿时清状态并锁存参数。
                // 采集中不要改control：shift虽锁存，config_ok仍读取实时字段。
                rng <= control[8] ? 32'h6d2b79f5 : 32'h00000001;
                shift_latched <= control[4:1];
                frame_active <= 0; done <= 0; captured <= 0; scheduled <= 0; tx_word <= 0;
            end else begin
                // Update one clock before iis_ser sees falling LRCLK and latches.
                // scheduled bounds sound independently of ADC VALID/completion.
                if (divider == 2047) begin
                    // 非阻塞赋值先准备tx_word，下拍串行器检测到LRCLK下降沿时取新字。
                    if (config_ok && scheduled < CAPTURE_FRAMES) begin
                        rng <= next_rng;
                        tx_word <= random_signed >>> shift_latched;
                        frame_active <= 1;
                        scheduled <= scheduled + 1'b1;
                    end else begin
                        tx_word <= 0;
                        frame_active <= 0;
                    end
                end
                if (rx_valid && frame_active && !done) begin
                    // 接收完成时记录同帧的一对值；ADC右声道rx_right未用于本次标定。
                    memory[captured[14:0]] <= {tx_word, rx_left};
                    captured <= captured + 1'b1;
                    if (captured == CAPTURE_FRAMES-1) done <= 1;
                end
            end
            read_word <= memory[capture_cmd[14:0]];
            // 同步RAM读出后再经过输出寄存器，共两级延迟；PS需先写地址再读数据。
            // reset清计数和输出，不擦除整块RAM；只读本次捕获的有效范围。
            capture_left <= read_word[47:24];
            capture_right <= read_word[23:0];
        end
    end
endmodule
