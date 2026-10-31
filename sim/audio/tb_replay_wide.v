// Targeted testbench: the replay path must multiply the WIDE residual and clamp afterwards.
//
// The field failure this covers: prediction_saturations=0 but residual_saturations=8, i.e. the
// 24-bit difference `mic - pred` went past the rail while the prediction itself was fine. The
// old replay path multiplied the already-clamped 24-bit residual, so a 1.02x-full-scale
// difference was projected as if it were exactly full scale. Here the same shape is forced with
// a legitimate coefficient (h0 = -1.5 in Q20) and a microphone word of 8,000,000:
//
//   frame 2: pred = -6,000,000 (inside the rail, prediction_saturated = 0)
//            residual_pcm      = 0x7FFFFF  (clamped, residual_saturated = 1)
//            residual_wide_pcm = 14,000,000 (unclamped)
//            gain 0.5 -> played = 7,000,000   (old path would have played 4,194,303)
//
// Three cases, each with its own reset and full coefficient reload:
//   A  wide residual * 0.5 lands inside the post-gain rail: 7,000,000, no clamp, no prediction clip
//   B  the same wide residual * 1.0 exceeds the rail: the POST-gain clamp is the one that acts
//   C  input full scale is flagged on its own: zero coefficients make the residual equal to the
//      microphone, the residual counters stay at 0, and capture_status[22] still reports it
//
// Simulated with sim/audio/iis_sim_models.v; the same testbench is also run under xsim against
// the vendor VHDL by build/scripts/test_audio_replay_wide.tcl.
`timescale 1ns/1ps
module tb_replay_wide;
reg clk=0; always #5 clk=~clk;
    reg sw_bypass=0, sw_bypass_alt=0;   // physical switch: 0 keeps the old behaviour
reg resetn=0, sdata_i=0;
reg [31:0] control=0, capture_cmd=0, coefficient_cmd=0, frame_limit=8;
reg [31:0] source_cmd=0, source_length=4;
wire [31:0] source_status, mix_clip_count;
wire sdata_o, bclk, lrclk, active;
wire [31:0] frame_count, capture_status, coefficient_status, completed_count, gain_clip_count, saturation_counts;
wire [23:0] capture_left, capture_right;
audio_pl_replay #(.SOURCE_FRAMES(16), .CAPTURE_FRAMES(16), .MAX_RUN_FRAMES(64)) dut(.*);

// ---------------------------------------------------------------------------
// ADC side: left channel carries the microphone word, right channel is silent.
// Same driving pattern as tb_audio_replay (50 ns after the falling BCLK edge).
// ---------------------------------------------------------------------------
reg signed [23:0] mic_word = 24'sd0;
reg prev_lr=0;
integer bit_index=0;
reg [23:0] adc_word=0;
always @(negedge bclk) begin
    if (lrclk!=prev_lr) begin bit_index=0; prev_lr=lrclk; end
    else bit_index=bit_index+1;
    adc_word = lrclk ? 24'sd0 : mic_word;
    #50; sdata_i = (bit_index>=1 && bit_index<=24) ? adc_word[24-bit_index] : 1'b0;
end

// ---------------------------------------------------------------------------
// DAC side: rebuild the 24-bit words the design actually serialised.
// ---------------------------------------------------------------------------
reg monitor_lr=0;
integer monitor_bit=0, observed=0;
reg [23:0] ml=0, mr=0;
reg [23:0] words[0:63];
always @(posedge bclk) begin
    if (lrclk!=monitor_lr) begin monitor_bit=0; monitor_lr=lrclk; end
    else monitor_bit=monitor_bit+1;
    if (monitor_bit>=1 && monitor_bit<=24) begin
        if (!lrclk) ml={ml[22:0],sdata_o}; else mr={mr[22:0],sdata_o};
        if (lrclk && monitor_bit==24 && active) begin
            if (ml!==mr) $fatal(1,"DAC stereo mismatch");
            words[observed]=ml; observed=observed+1;
        end
    end
end

// ---------------------------------------------------------------------------
// Per-frame record of what the FIR produced and what the gain stage made of it.
// ---------------------------------------------------------------------------
integer ng=0;
reg signed [23:0] gain_seq[0:63];
reg signed [24:0] wide_seq[0:63];
reg signed [23:0] res_seq[0:63], pred_seq[0:63];
reg rsat_seq[0:63], psat_seq[0:63];
always @(posedge clk) begin
    if (resetn && dut.gain_valid && dut.run_ok) begin
        gain_seq[ng]=dut.gain_limited;
        wide_seq[ng]=dut.residual_wide;
        res_seq[ng]=dut.residual;
        pred_seq[ng]=dut.prediction;
        rsat_seq[ng]=dut.rsat;
        psat_seq[ng]=dut.psat;
        ng=ng+1;
    end
end

task reset_device;
begin
    @(negedge clk);control=0;resetn=0;coefficient_cmd=0;source_cmd=0;source_length=4;
    repeat(10) @(posedge clk);@(negedge clk);resetn=1;
    repeat(10) @(posedge clk);
end endtask

reg zero_coeff=1;
reg signed [23:0] tap0_coeff=0;
task load_all;
integer j;
begin
    @(negedge clk);coefficient_cmd=coefficient_cmd^(1<<25);
    repeat(4) @(posedge clk);
    for(j=0;j<512;j=j+1) begin
        if(!coefficient_status[0]) $fatal(1,"coefficient not ready");
        @(negedge clk);
        coefficient_cmd=(coefficient_cmd & 32'h03000000) | (zero_coeff ? 24'd0 : j==0 ? tap0_coeff : 24'd0);
        coefficient_cmd=coefficient_cmd^(1<<24);
        repeat(4) @(posedge clk);
    end
    @(negedge clk);source_cmd=source_cmd^(1<<17);
    repeat(4) @(posedge clk);
    for(j=0;j<4;j=j+1) begin
        @(negedge clk);source_cmd=(source_cmd & 32'h30000)|16'd0;
        source_cmd=source_cmd^(1<<16);repeat(4) @(posedge clk);
    end
    #1;if(source_status!==32'h52080004) $fatal(1,"source load status %h",source_status);
    #1;if(!coefficient_status[3] || coefficient_status[19:4]!=512) $fatal(1,"load incomplete");
end endtask

task start_run(input [15:0] gain_q12);
begin
    @(negedge clk);observed=0;ng=0;
    control=(gain_q12<<16)|1;   // armed, cancellation mode
end endtask

reg signed [63:0] expect_wide_gain, old_clamped_gain;
initial begin
    // The DAC word of frame k is the gain applied to residual[k-2] (the MAC finishes after the
    // frame has already been prepared), so the first wide overflow shows up at index 3 and must
    // reach the output as words[5].
    // ---- case A: wide residual at 0.5 gain stays inside the post-gain rail ----
    zero_coeff=0; tap0_coeff=-24'sd1572864; mic_word=24'sd8000000;
    reset_device(); load_all(); start_run(16'd2048);
    wait(capture_status[0]); repeat(5) @(posedge clk); #1;
    expect_wide_gain=(64'sd14000000*64'sd2048+64'sd2048)>>>12;
    old_clamped_gain=(64'sd8388607*64'sd2048+64'sd2048)>>>12;
    if(wide_seq[3]!==25'sd14000000) $fatal(1,"case A wide residual %0d",$signed(wide_seq[3]));
    if(res_seq[3]!==24'sh7fffff) $fatal(1,"case A clamped residual %h",res_seq[3]);
    if(rsat_seq[3]!==1'b1) $fatal(1,"case A residual_saturated not set");
    if(psat_seq[3]!==1'b0) $fatal(1,"case A prediction must not saturate");
    if(pred_seq[3]!==-24'sd6000000) $fatal(1,"case A prediction %0d",$signed(pred_seq[3]));
    if($signed(gain_seq[3])!==$signed(expect_wide_gain))
        $fatal(1,"case A post-gain %0d, wide-residual result is %0d, old clamped result would be %0d",
               $signed(gain_seq[3]),$signed(expect_wide_gain),$signed(old_clamped_gain));
    if($signed(gain_seq[3])===$signed(old_clamped_gain)) $fatal(1,"case A used the clamped residual");
    if(words[5]!==gain_seq[3]) $fatal(1,"case A DAC word %h did not carry the post-gain value",words[5]);
    if(gain_clip_count!=0) $fatal(1,"case A unexpected post-gain clamp");
    if(capture_status[22]!=0) $fatal(1,"case A input full scale wrongly flagged");
    if(capture_status[17]!=0) $fatal(1,"case A fault bit set");
    if(completed_count!=8) $fatal(1,"case A completed %0d",completed_count);
    $display("WIDE_GAIN_CASE_A: frame3 wide=%0d clamped=%0d pred=%0d gain0.5=%0d old_path_would_be=%0d dac=%0d",
             $signed(wide_seq[3]), $signed(res_seq[3]), $signed(pred_seq[3]),
             $signed(gain_seq[3]), $signed(old_clamped_gain), words[5]);
    $display("WIDE_GAIN_CASE_A_CHAIN: wide0..5=%0d %0d %0d %0d %0d %0d / gain0..5=%0d %0d %0d %0d %0d %0d",
             $signed(wide_seq[0]),$signed(wide_seq[1]),$signed(wide_seq[2]),$signed(wide_seq[3]),$signed(wide_seq[4]),$signed(wide_seq[5]),
             $signed(gain_seq[0]),$signed(gain_seq[1]),$signed(gain_seq[2]),$signed(gain_seq[3]),$signed(gain_seq[4]),$signed(gain_seq[5]));

    // ---- case B: the same shaped overflow at 1.0 gain exceeds the rail, so the POST-gain clamp acts ----
    zero_coeff=0; tap0_coeff=-24'sd1572864; mic_word=24'sd8000000;
    reset_device(); load_all(); start_run(16'd4096);
    wait(capture_status[0]); repeat(5) @(posedge clk); #1;
    if(wide_seq[3]!==25'sd16388608) $fatal(1,"case B wide residual %0d",$signed(wide_seq[3]));
    if(res_seq[3]!==24'sh7fffff) $fatal(1,"case B residual %h",res_seq[3]);
    if(rsat_seq[3]!==1'b1) $fatal(1,"case B residual_saturated not set");
    if($signed(gain_seq[3])!==24'sh7fffff) $fatal(1,"case B post-gain clamp %h",gain_seq[3]);
    if(gain_clip_count==0) $fatal(1,"case B post-gain clamp not counted");
    if(capture_status[21]==0) $fatal(1,"case B clamp not reported in capture_status[21]");
    if(words[5]!==24'h7fffff) $fatal(1,"case B DAC word %h",words[5]);
    $display("WIDE_GAIN_CASE_B: frame3 wide=%0d gain1.0=%0d gain_clip_count=%0d dac=%0d",
             $signed(wide_seq[3]),$signed(gain_seq[3]),gain_clip_count,words[5]);

    // ---- case C: input full scale has its own detector, independent of the residual ----
    zero_coeff=1; mic_word=24'sh7fffff;
    reset_device(); load_all(); start_run(16'd2048);
    wait(capture_status[0]); repeat(5) @(posedge clk); #1;
    if(wide_seq[0]!==25'sd8388607) $fatal(1,"case C wide %0d",$signed(wide_seq[0]));
    if(res_seq[0]!==24'sh7fffff) $fatal(1,"case C residual %h",res_seq[0]);
    if(rsat_seq[0]!==1'b0) $fatal(1,"case C residual must not report saturation");
    if(capture_status[22]==0) $fatal(1,"case C input full scale not reported");
    if(capture_status[20]!=0) $fatal(1,"case C residual clip seen wrongly set");
    if(capture_status[19]!=0) $fatal(1,"case C prediction clip seen wrongly set");
    if(dut.input_clips==0) $fatal(1,"case C input clip counter empty");
    if(dut.rsat!=0) $fatal(1,"case C residual_saturated must stay clear");
    $display("INPUT_FULLSCALE_CASE_C: input_clips=%0d residual_clips=%0d residual_saturated=%0d status=%h",
             dut.input_clips, dut.residual_clips, dut.rsat, capture_status);

    $display("RESIDUAL_REPLAY_WIDE_PASS: multiply-wide-then-clamp + post-gain clamp + independent input full scale");
    $finish;
end
initial begin #20000000;$fatal(1,"timeout");end
endmodule
