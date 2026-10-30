`timescale 1ns/1ps
module tb_audio_replay;
reg clk=0; always #5 clk=~clk;
reg resetn=0,sdata_i=0;
reg [31:0] control=0,capture_cmd=0,coefficient_cmd=0,frame_limit=32;
reg [31:0] source_cmd=0, source_length=12;
wire [31:0] source_status,mix_clip_count;
function signed [23:0] injected(input integer n);
    injected=n<12 ? ((n%2) ? -24'sd25600 : 24'sd51200) : 0;
endfunction
wire sdata_o,bclk,lrclk,active;
wire [31:0] frame_count,capture_status,coefficient_status,completed_count,gain_clip_count,saturation_counts;
wire [23:0] capture_left,capture_right;
audio_pl_replay #(.SOURCE_FRAMES(16),.CAPTURE_FRAMES(16),.MAX_RUN_FRAMES(64)) dut(.*);
reg prev_lr=0;
integer bit_index=0;
reg [23:0] source_word;
reg zero_coeff=1;
reg loud=0;
always @(negedge bclk) begin
    if(lrclk!=prev_lr) begin bit_index=0;prev_lr=lrclk;end
    else bit_index=bit_index+1;
    source_word=lrclk ? 24'hfedcba : loud ? 24'h600000 : (dut.scheduled[0] ? -24'sd12345 : 24'sd23456);
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
    @(negedge clk);control=0;resetn=0;coefficient_cmd=0;source_cmd=0;source_length=12;
    repeat(10) @(posedge clk);@(negedge clk);resetn=1;
    repeat(10) @(posedge clk);
end endtask
task load_coefficients;
integer j;
begin
    @(negedge clk);coefficient_cmd=coefficient_cmd^(1<<25);
    repeat(4) @(posedge clk);
    // The RTL default is 512 taps (production bitstream); the loader must fill exactly TAPS
    // coefficients or `fresh` never sets, so this loop follows the default.
    for(j=0;j<512;j=j+1) begin
        if(!coefficient_status[0]) $fatal(1,"coefficient not ready");
        @(negedge clk);
        coefficient_cmd=(coefficient_cmd & 32'h03000000) | (zero_coeff ? 0 : j==0 ? 24'h080000 : j==2 ? 24'h040000 : 0);
        coefficient_cmd=coefficient_cmd^(1<<24);
        repeat(4) @(posedge clk);
    end
    @(negedge clk);source_cmd=source_cmd^(1<<17);
    repeat(4) @(posedge clk);
    for(j=0;j<12;j=j+1) begin
        @(negedge clk);source_cmd=(source_cmd & 32'h30000)|((j%2) ? 16'hff9c : 16'd200);
        source_cmd=source_cmd^(1<<16);repeat(4) @(posedge clk);
    end
    #1;if(source_status!==32'h5208000c) $fatal(1,"source load status %h",source_status);
    #1;if(!coefficient_status[3] || coefficient_status[19:4]!=512) $fatal(1,"load incomplete");
end endtask
integer run,i,j;
reg signed [63:0] acc,expected,expected_res;
reg signed [23:0] baseline[0:31];
reg signed [23:0] mic_words[0:63], predictions[0:63], residuals[0:63];
reg modes[0:63];
integer output_cycles[0:63];
integer input_cycles[0:63],result_cycles[0:63],cycle=0,received=0,produced=0;
always @(posedge clk) begin
    cycle=cycle+1;
    if(resetn && dut.divider==2047 && dut.run_ok && dut.scheduled<frame_limit)
        output_cycles[dut.scheduled]=cycle;
    if(resetn && dut.sample_valid) begin
        input_cycles[received]=cycle;
        modes[received]=control[1];
        mic_words[received]=dut.scheduled[0] ? -24'sd12345 : 24'sd23456;
        if(loud) mic_words[received]=24'h600000;
        received=received+1;
    end
    if(resetn && dut.fir_valid && dut.session && !dut.fault) begin
        result_cycles[produced]=cycle;
        predictions[produced]=dut.prediction;
        residuals[produced]=dut.residual;
        produced=produced+1;
    end
end
initial begin
    for(run=0;run<3;run=run+1) begin
        reset_device();zero_coeff=(run<2);load_coefficients();
        @(negedge clk);observed=0;received=0;produced=0;frame_limit=32;
        control=(4096<<16)|1|(run==1 ? 2 : 0);
        // Nonzero model switches bypass in-place. History must follow pin output throughout.
        if(run==2) begin
            wait(completed_count==8);@(negedge clk);control=control|2;
            wait(completed_count==16);@(negedge clk);control=control & ~2;
        end
        wait(capture_status[0]);repeat(5) @(posedge clk);#1;
        if(completed_count!=32 || observed!=32 || produced!=32 || capture_status[21:17]!=0)
            $fatal(1,"run status %h produced=%0d observed=%0d",capture_status,produced,observed);
        for(i=0;i<32;i=i+1) begin
            acc=0;
            if(!zero_coeff && i>=1) acc=acc+$signed(words[i-1])*64'sd524288;
            if(!zero_coeff && i>=3) acc=acc+$signed(words[i-3])*64'sd262144;
            expected=acc<0 ? -((-acc+524288)>>>20) : (acc+524288)>>>20;
            expected_res=modes[i] ? $signed(mic_words[i]) : $signed(mic_words[i])-expected;
            if($signed(predictions[i])!==expected || $signed(residuals[i])!==expected_res)
                $fatal(1,"history/reference mismatch run=%0d frame=%0d",run,i);
            if(i<2) begin if(words[i]!==injected(i)) $fatal(1,"startup source mismatch");end
            else if($signed(words[i])!==$signed(residuals[i-2])+$signed(injected(i))) $fatal(1,"DAC not delayed residual frame=%0d",i);
            if(run==0) baseline[i]=words[i];
            if(run==1 && words[i]!==baseline[i]) $fatal(1,"zero coefficients A/B differs");
        end
        // Circular RAM must contain last 16 aligned records, not first 16.
        for(i=16;i<32;i=i+1) begin
            @(negedge clk);capture_cmd=i%16;repeat(4) @(posedge clk);#1;
            if(capture_left!==words[i] || capture_right!==mic_words[i]) $fatal(1,"ring inputs");
            @(negedge clk);capture_cmd=(1<<16)|(i%16);repeat(4) @(posedge clk);#1;
            if(capture_left!==predictions[i] || capture_right!==residuals[i]) $fatal(1,"ring results");
        end
        $display("CLOSED_TIMING: ADC-valid-to-observed-FIR=%0d clocks; ADC-valid-to-TX-load=%0d clocks; played[n+2]=source[n+2]+residual[n]",result_cycles[0]-input_cycles[0],output_cycles[2]-input_cycles[0]);
        repeat(4096) @(posedge clk);if(active || sdata_o) $fatal(1,"budget failed");
    end
    reset_device();zero_coeff=1;load_coefficients();loud=1;
    @(negedge clk);observed=0;received=0;produced=0;frame_limit=16;control=(32768<<16)|3;
    wait(capture_status[0]);#1;
    if(gain_clip_count==0 || mix_clip_count==0 || !capture_status[21] || words[2]!==24'h7fffff) $fatal(1,"gain/mix clip not observable");
    loud=0;
    reset_device();load_coefficients();
    force dut.rx_valid=0;
    @(negedge clk);observed=0;received=0;produced=0;frame_limit=32;control=(4096<<16)|1;
    repeat(2048*5) @(posedge clk);#1;
    if(sdata_o || !capture_status[18]) $fatal(1,"stall not muted");
    release dut.rx_valid;
    reset_device();load_coefficients();
    @(negedge clk);received=0;produced=0;control=(4096<<16)|1;wait(active);
    @(negedge clk);control=0;#1;if(sdata_o) $fatal(1,"manual stop failed");
    reset_device();load_coefficients();
    @(negedge clk);received=0;produced=0;control=(4096<<16)|1;wait(active);
    @(negedge clk);coefficient_cmd=coefficient_cmd^(1<<24);
    repeat(4) @(posedge clk);#1;if(sdata_o || !capture_status[18]) $fatal(1,"coefficient fault");
    reset_device();
    @(negedge clk);control=(4096<<16)|1;
    repeat(10) @(posedge clk);#1;if(sdata_o || !capture_status[18]) $fatal(1,"unloaded start");

    reset_device();load_coefficients();
    @(negedge clk);source_cmd=source_cmd^(1<<17);repeat(4) @(posedge clk);
    @(negedge clk);control=(4096<<16)|1;
    repeat(10) @(posedge clk);#1;
    if(sdata_o || !capture_status[18]) $fatal(1,"missing source accepted");
    reset_device();load_coefficients();
    @(negedge clk);observed=0;received=0;produced=0;control=(4096<<16)|1;wait(active);
    @(negedge clk);source_cmd=source_cmd^(1<<16);
    repeat(4) @(posedge clk);#1;
    if(sdata_o || !capture_status[18]) $fatal(1,"source write while armed accepted");
    reset_device();load_coefficients();
    @(negedge clk);observed=0;received=0;produced=0;control=(4096<<16)|1;wait(active);
    @(negedge clk);source_length=11;
    repeat(4) @(posedge clk);#1;
    if(sdata_o || !capture_status[18]) $fatal(1,"source length mutation accepted");
    $display("AUDIO_REPLAY_PASS: zero model gain1 A/B, actual DAC history, online bypass, ring buffer, gain clip, stall, budget, abort, unloaded/coeff fault");
    $finish;
end
initial begin #20000000;$fatal(1,"timeout");end
endmodule
