`timescale 1ns/1ps

module tb_audio_probe_dynamic;
reg clk = 0;
always #5 clk = ~clk;
reg resetn = 0;
reg [31:0] control = 0;
reg sdata_i = 0;
wire sdata_o, bclk, lrclk, active;
wire [31:0] frame_count;
wire [23:0] sample_left, sample_right;
audio_pl_probe dut(.*);

function [23:0] left_word(input integer n);
    case (n % 4)
        0: left_word = 24'h123456;
        1: left_word = 24'hf23456;
        2: left_word = 24'h600001;
        default: left_word = 24'h800123;
    endcase
endfunction
function [23:0] right_word(input integer n);
    case (n % 4)
        0: right_word = 24'hfedcba;
        1: right_word = 24'h0abcde;
        2: right_word = 24'h900007;
        default: right_word = 24'h700321;
    endcase
endfunction

integer source_frame = -1;
integer source_bit = 0;
reg source_lr = 0;
reg [23:0] source_word;
// Change both channel words every frame. Include positive, negative and
// large-magnitude values to reveal channel swaps and one-frame slips.
always @(negedge bclk) begin
    if (lrclk != source_lr) begin
        source_bit = 0;
        source_lr = lrclk;
        if (!lrclk) source_frame = source_frame + 1;
    end else source_bit = source_bit + 1;
    source_word = lrclk ? right_word(source_frame) : left_word(source_frame);
    #50;
    if (source_bit >= 1 && source_bit <= 24)
        sdata_i = source_word[24-source_bit];
    else sdata_i = 0;
end

integer monitor_bit = 0;
integer checked = 0;
reg monitor_lr = 0;
reg [23:0] decoded = 0;
always @(posedge bclk) begin
    if (lrclk != monitor_lr) begin
        monitor_bit = 0;
        monitor_lr = lrclk;
        decoded = 0;
    end else monitor_bit = monitor_bit + 1;
    if (monitor_bit >= 1 && monitor_bit <= 24)
        decoded = {decoded[22:0], sdata_o};
    // The DAC serializer latches the preceding complete ADC frame at the
    // next left-channel boundary. Skip startup before the first full frame.
    if (monitor_bit == 24 && source_frame >= 2 && control[0]) begin
        if (lrclk && decoded !== right_word(source_frame-1))
            $fatal(1, "dynamic right mismatch frame=%0d got=%h expected=%h",
                   source_frame, decoded, right_word(source_frame-1));
        if (!lrclk && decoded !== left_word(source_frame-1))
            $fatal(1, "dynamic left mismatch frame=%0d got=%h expected=%h",
                   source_frame, decoded, left_word(source_frame-1));
        checked = checked + 1;
    end
end

initial begin
    repeat (10) @(posedge clk);
    #1;
    resetn = 1;
    control = 1; // no digital attenuation
    wait (checked >= 24);
    control = 0;
    #1;
    if (sdata_o !== 0) $fatal(1, "serial output not muted");
    $display("I2S_DYNAMIC_PASS: %0d changing channel words checked", checked);
    $finish;
end
initial begin
    #1000000;
    $fatal(1, "dynamic I2S simulation timed out");
end
endmodule
