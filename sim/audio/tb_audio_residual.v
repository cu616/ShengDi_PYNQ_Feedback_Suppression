`timescale 1ns/1ps
module tb_audio_residual;
reg clk=0; always #5 clk=~clk;
reg resetn=0,sdata_i=0;
reg [31:0] control=0,capture_cmd=0,coefficient_cmd=0;
wire sdata_o,bclk,lrclk,active;
wire [31:0] frame_count,capture_status,coefficient_status;
wire [23:0] capture_left,capture_right;
audio_pl_residual #(.CAPTURE_FRAMES(16)) dut(.*);
reg prev_lr=0;
integer bit_index=0;
reg [23:0] source_word;
always @(negedge bclk) begin
    if(lrclk!=prev_lr) begin bit_index=0;prev_lr=lrclk;end
    else bit_index=bit_index+1;
    source_word=lrclk ? 24'hfedcba : 24'h123456;
    #50;sdata_i=(bit_index>=1 && bit_index<=24) ? source_word[24-bit_index] : 0;
end
reg monitor_lr=0;
integer monitor_bit=0,observed=0;
reg [23:0] ml=0,mr=0;
reg signed [23:0] words[0:63];
always @(posedge bclk) begin
    if(lrclk!=monitor_lr) begin monitor_bit=0;monitor_lr=lrclk;end
    else monitor_bit=monitor_bit+1;
    if(monitor_bit>=1 && monitor_bit<=24) begin
        if(!lrclk) ml={ml[22:0],sdata_o}; else mr={mr[22:0],sdata_o};
        if(lrclk && monitor_bit==24 && active) begin
            if(ml!==mr) $fatal(1,"DAC stereo mismatch");
            words[observed]=ml;observed=observed+1;
        end
    end
end
task reset_device;
begin
    @(negedge clk);control=0;resetn=0;coefficient_cmd=0;
    repeat(10) @(posedge clk);@(negedge clk);resetn=1;
    repeat(10) @(posedge clk);
end endtask
task load_coefficients;
integer j;
begin
    @(negedge clk);coefficient_cmd=coefficient_cmd^(1<<25);
    repeat(4) @(posedge clk);
    for(j=0;j<256;j=j+1) begin
        if(!coefficient_status[0]) $fatal(1,"coefficient not ready");
        @(negedge clk);
        coefficient_cmd=(coefficient_cmd & 32'h03000000) | (j==0 ? 24'h080000 : j==2 ? 24'h040000 : 0);
        coefficient_cmd=coefficient_cmd^(1<<24);
        repeat(4) @(posedge clk);
    end
    #1;if(!coefficient_status[3] || coefficient_status[19:4]!=256) $fatal(1,"load incomplete");
end endtask
integer run,i;
reg signed [63:0] acc,expected;
initial begin
    reset_device();
    // Unloaded coefficients must never enable stimulus.
    @(negedge clk);control=13;
    repeat(5000) @(posedge clk);
    if(active || sdata_o || !capture_status[18]) $fatal(1,"unloaded start accepted");
    reset_device();
    for(run=0;run<2;run=run+1) begin
        load_coefficients();
        @(negedge clk);observed=0;control=(run<<8)|13;
        repeat(4) @(posedge clk); // Arm edge clears the preceding run's retained done flag.
        wait(capture_status[0]);repeat(4) @(posedge clk);
        if(capture_status[16:1]!=16 || capture_status[20:17]!=0 || observed!=16)
            $fatal(1,"count/fault mismatch %h observed=%0d",capture_status,observed);
        for(i=0;i<16;i=i+1) begin
            @(negedge clk);capture_cmd=i;
            repeat(4) @(posedge clk);#1;
            if(capture_left!==words[i] || capture_right!==24'h123456)
                $fatal(1,"input alignment %0d",i);
            // Hand-derived h[0]=1/2, h[2]=1/4, zero history each run.
            acc=0;
            if(i>=1) acc=acc+$signed(words[i-1])*64'sd524288;
            if(i>=3) acc=acc+$signed(words[i-3])*64'sd262144;
            expected=acc<0 ? -((-acc+524288)>>>20) : (acc+524288)>>>20;
            @(negedge clk);capture_cmd=(1<<16)|i;
            repeat(4) @(posedge clk);#1;
            if($signed(capture_left)!==expected || $signed(capture_right)!==(64'sh123456-expected))
                $fatal(1,"residual alignment %0d pred=%d expected=%d",i,$signed(capture_left),expected);
        end
        repeat(5000) @(posedge clk);
        if(active || sdata_o || observed!=16) $fatal(1,"DAC not bounded");
        @(negedge clk);control=0;repeat(10) @(posedge clk);
    end
    // Fresh coefficients required even after a successful prior run.
    @(negedge clk);control=13;repeat(5000) @(posedge clk);
    if(active || sdata_o || !capture_status[18]) $fatal(1,"stale history accepted");
    reset_device();load_coefficients();
    force dut.rx_valid=0;
    @(negedge clk);observed=0;control=13;
    repeat(2048*19) @(posedge clk);
    if(active || sdata_o || observed!=16 || capture_status[16:0]!=0) $fatal(1,"ADC failure bypassed bound");
    release dut.rx_valid;
    reset_device();load_coefficients();
    @(negedge clk);control=13;wait(active);
    @(negedge clk);coefficient_cmd=coefficient_cmd^(1<<24);
    repeat(4) @(posedge clk);#1;
    if(sdata_o || !capture_status[18]) $fatal(1,"armed coefficient change not muted");
    reset_device();load_coefficients();
    @(negedge clk);control=13;wait(active);
    // Receiver fault produces back-to-back sample requests while FIR is busy.
    force dut.rx_valid=1;
    repeat(5) @(posedge clk);#1;
    if(sdata_o || !capture_status[18]) $fatal(1,"busy input did not latch fault/mute");
    release dut.rx_valid;
    reset_device();load_coefficients();
    @(negedge clk);control=13;wait(active);
    @(negedge clk);control=0;#1;
    if(sdata_o) $fatal(1,"manual stop not immediate");
    repeat(3000) @(posedge clk);
    reset_device();load_coefficients();
    @(negedge clk);control=13;wait(active);
    @(negedge clk);resetn=0;#1;
    if(sdata_o) $fatal(1,"reset mute failed");
    $display("AUDIO_RESIDUAL_PASS: 256 taps, two seeds, pin/reference/mic/prediction/residual alignment, fresh load, no-ADC bound, coefficient/busy fault, stop, reset");
    $finish;
end
initial begin #15000000;$fatal(1,"timeout");end
endmodule
