`timescale 1ns/1ps
module tb_audio_probe;
reg clk=0; always #5 clk=~clk;
reg resetn=0; reg [31:0] control=0;
reg sdata_i=0; wire sdata_o,bclk,lrclk,active; wire [31:0] frame_count; wire [23:0] sample_left,sample_right;
audio_pl_probe dut(.*);
reg last_lr=0, monitor_lr=0;
integer tx_index=0,rx_index=0,checked=0;
reg [23:0] decoded=0;
reg signed [23:0] source_word;
// Independent wire-level source: one I2S delay bit followed by 24 MSB-first bits.
always @(negedge bclk) begin
    if(lrclk!=last_lr) begin tx_index=0; last_lr=lrclk; end
    else tx_index=tx_index+1;
    source_word=lrclk ? -24'sd74565 : 24'sh654321;
    // ADAU1761 Rev. F Table 7 permits up to 50 ns ADC_SDATA delay
    // after BCLK falling. Exercise that worst-case edge in this test.
    #50;
    if(tx_index>=1 && tx_index<=24) sdata_i=source_word[24-tx_index];
    else sdata_i=0;
end
always @(posedge bclk) begin
    if(lrclk!=monitor_lr) begin rx_index=0; monitor_lr=lrclk; decoded=0; end
    else rx_index=rx_index+1;
    if(rx_index>=1 && rx_index<=24) decoded={decoded[22:0],sdata_o};
    if(rx_index==24 && frame_count>=5 && control[0]) begin
        if(lrclk && decoded!==24'hff6e5d) $fatal(1,"right I2S mismatch %h",decoded);
        if(!lrclk && decoded!==24'h32a190) $fatal(1,"left I2S mismatch %h",decoded);
        checked=checked+1;
    end
end
initial begin
    repeat(10) @(posedge clk); #1; resetn=1; control=3; // divide by two
    wait(checked>=12);
    if(sample_left !== 24'h654321 || sample_right !== -24'sd74565)
        $fatal(1,"ADC snapshot mismatch left=%h right=%h",sample_left,sample_right);
    control=0; #1;
    if(sdata_o!==0) $fatal(1,"serial output not muted");
    repeat(2200) @(posedge clk);
    if(sdata_o!==0 || active) $fatal(1,"mute not persistent");
    $display("I2S_PATH_PASS: 12 channel words, signed attenuation, serial mute; frames=%0d",frame_count);
    $finish;
end
initial begin #1000000; $fatal(1,"I2S test timed out"); end
endmodule

