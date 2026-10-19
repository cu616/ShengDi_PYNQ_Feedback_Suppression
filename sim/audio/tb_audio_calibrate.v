`timescale 1ns/1ps
module tb_audio_calibrate;
reg clk=0;
always #5 clk=~clk;
reg resetn=0;
reg [31:0] control=0, capture_cmd=0;
reg sdata_i=0;
wire sdata_o,bclk,lrclk,active;
wire [31:0] frame_count,capture_status;
wire [23:0] capture_left,capture_right;
audio_pl_calibrate #(.CAPTURE_FRAMES(16)) dut(.*);
reg prev_lr=0;
integer bit_index=0;
reg [23:0] source_word;
always @(negedge bclk) begin
    if(lrclk!=prev_lr) begin bit_index=0;prev_lr=lrclk;end
    else bit_index=bit_index+1;
    source_word=lrclk ? 24'hfedcba : 24'h123456;
    #50;
    sdata_i=(bit_index>=1 && bit_index<=24) ? source_word[24-bit_index] : 0;
end
// Independent pin-level decoder, not the production I2S receiver.
reg monitor_lr=0;
integer monitor_bit=0, observed=0;
reg [23:0] monitor_left=0,monitor_right=0;
reg [23:0] observed_words[0:63];
always @(posedge bclk) begin
    if(lrclk!=monitor_lr) begin monitor_bit=0;monitor_lr=lrclk;end
    else monitor_bit=monitor_bit+1;
    if(monitor_bit>=1 && monitor_bit<=24) begin
        if(!lrclk) monitor_left={monitor_left[22:0],sdata_o};
        else monitor_right={monitor_right[22:0],sdata_o};
        if(lrclk && monitor_bit==24 && active) begin
            if(monitor_left!==monitor_right) $fatal(1,"DAC channels mismatch");
            observed_words[observed]=monitor_left;
            observed=observed+1;
        end
    end
end
function [31:0] step_rng(input [31:0] v);
reg [31:0] a;
begin a=v^(v<<13);a=a^(a>>17);step_rng=a^(a<<5);end
endfunction
integer i,run;
reg [31:0] expected_rng;
reg signed [23:0] expected_word;
initial begin
    repeat(10) @(posedge clk); #1;resetn=1;
    repeat(5000) @(posedge clk);
    if(sdata_o!==0) $fatal(1,"reset default must mute");
    for(run=0;run<2;run=run+1) begin
        @(negedge clk);observed=0;control=(run<<8)|(6<<1)|1;
        wait(capture_status[0]);
        repeat(4) @(posedge clk);
        if(capture_status[16:1]!==16) $fatal(1,"capture count wrong");
        if(observed!=16) $fatal(1,"expected exactly 16 DAC frames, got %0d",observed);
        expected_rng=run ? 32'h6d2b79f5 : 1;
        for(i=0;i<16;i=i+1) begin
            expected_rng=step_rng(expected_rng);
            expected_word=$signed(expected_rng[23:0]) >>> 6;
            @(negedge clk);capture_cmd=i;
            repeat(4) @(posedge clk);#1;
            if(capture_left!==expected_word || capture_left!==observed_words[i])
                $fatal(1,"reference not actual serialized frame %0d",i);
            if(capture_right!==24'h123456) $fatal(1,"ADC left capture incorrect");
        end
        repeat(5000) @(posedge clk);
        if(active!==0 || sdata_o!==0 || observed!=16) $fatal(1,"stimulus did not self-stop");
        @(negedge clk);control=0;
        repeat(10) @(posedge clk);
    end
    // Invalid amplitude config cannot enable sound; count remains zero.
    @(negedge clk);control=1;
    repeat(5000) @(posedge clk);
    if(active!==0 || sdata_o!==0 || !capture_status[17]) $fatal(1,"bad config not rejected");
    @(negedge clk);control=0;
    repeat(10) @(posedge clk);
    @(negedge clk);control=13;
    wait(active);@(negedge clk);control=0;#1;
    if(sdata_o!==0) $fatal(1,"abort gate failed");
    repeat(5000) @(posedge clk);
    if(active!==0 || capture_status[16:0]!==0) $fatal(1,"abort cleanup failed");
    // Even a failed ADC receiver must not extend the emitted stimulus.
    force dut.rx_valid=0;
    @(negedge clk);observed=0;control=13;
    repeat(2048*19) @(posedge clk);
    if(active!==0 || sdata_o!==0 || observed!=16 || capture_status[16:0]!==0)
        $fatal(1,"ADC failure defeated independent DAC bound");
    release dut.rx_valid;
    @(negedge clk);control=0;
    repeat(10) @(posedge clk);
    @(negedge clk);control=13;
    wait(active);@(negedge clk);resetn=0;#1;
    if(sdata_o!==0) $fatal(1,"reset mute failed");
    repeat(10) @(posedge clk);
    $display("AUDIO_CALIBRATE_PASS: two seeds, aligned ADC/reference, DAC bound, abort, reset, ADC failure");
    $finish;
end
initial begin #90000000;$fatal(1,"timeout");end
endmodule
