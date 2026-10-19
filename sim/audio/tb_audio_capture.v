`timescale 1ns/1ps
module tb_audio_capture;
reg clk = 0;
always #5 clk = ~clk;
reg resetn = 0;
reg [31:0] control = 0;
reg [31:0] capture_cmd = 0;
reg sdata_i = 0;
wire sdata_o, bclk, lrclk, active;
wire [31:0] frame_count, capture_status;
wire [23:0] capture_left, capture_right;
audio_pl_capture #(.CAPTURE_FRAMES(16)) dut(.*);

reg prev_lr = 0;
integer bit_index = 0;
reg [23:0] source_word;
always @(negedge bclk) begin
    if (lrclk != prev_lr) begin bit_index = 0; prev_lr = lrclk; end
    else bit_index = bit_index + 1;
    source_word = lrclk ? 24'hfedcba : 24'h123456;
    #50;
    if (bit_index >= 1 && bit_index <= 24)
        sdata_i = source_word[24-bit_index];
    else sdata_i = 0;
end

initial begin
    repeat (10) @(posedge clk);
    #1;
    resetn = 1;
    capture_cmd = 32'h00010000;
    wait (capture_status[0]);
    if (capture_status[13:1] !== 13'd16)
        $fatal(1, "capture count mismatch %h", capture_status);
    if (sdata_o !== 0) $fatal(1, "capture should remain muted");
    capture_cmd = 32'h0001000a;
    repeat (4) @(posedge clk);
    if (capture_left !== 24'h123456 || capture_right !== 24'hfedcba)
        $fatal(1, "captured words mismatch left=%h right=%h",
               capture_left, capture_right);
    $display("AUDIO_CAPTURE_PASS: 16 simulated frames, readback, muted output");
    $finish;
end
initial begin
    #90000000;
    $fatal(1, "capture test timed out");
end
endmodule
