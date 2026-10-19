`timescale 1ns/1ps
module tb_audio_frame_path;
reg clk=0; always #5 clk=~clk;
reg resetn=0,valid=0;
reg [31:0] control=0;
reg signed [23:0] left_in=0,right_in=0;
wire signed [23:0] left_out,right_out;
wire [31:0] frame_count; wire active;
integer k,j; integer values[0:5]; integer expected;
audio_frame_path #(.MAX_FRAMES(4),.STALL_CYCLES(16)) dut(.*);
task tick; begin @(posedge clk); #1; end endtask
task arm; begin control=0; tick; control=1; tick; end endtask
task sample(input integer l, input integer r); begin
    left_in=l; right_in=r; valid=1; tick; valid=0;
end endtask
initial begin
    values[0]=0; values[1]=1; values[2]=-1; values[3]=8388607; values[4]=-8388608; values[5]=-257;
    tick; resetn=1; tick;
    if(active || left_out || right_out) $fatal(1,"reset mute");
    for(k=0;k<8;k=k+1) begin
        for(j=0;j<6;j=j+1) begin
            arm; control=1|(k<<1); sample(values[j],values[5-j]);
            // Independent floor division reference, including negative values.
            expected=(values[j]>=0)?values[j]/(1<<k):-((-values[j]+(1<<k)-1)/(1<<k));
            if(left_out!==expected) $fatal(1,"left shift k=%0d value=%0d got=%0d expected=%0d",k,values[j],left_out,expected);
            expected=(values[5-j]>=0)?values[5-j]/(1<<k):-((-values[5-j]+(1<<k)-1)/(1<<k));
            if(right_out!==expected) $fatal(1,"right shift");
        end
    end
    arm; sample(123,-456); sample(123,-456); sample(123,-456);
    if(!active) $fatal(1,"early timeout");
    sample(123,-456); if(active || left_out || right_out) $fatal(1,"frame timeout");
    repeat(4) sample(123,-456);
    if(active) $fatal(1,"must not rearm while enable held");
    arm; repeat(16) tick;
    if(active || left_out || right_out) $fatal(1,"stall timeout");
    arm; sample(-100,200); control=0; tick;
    if(active || left_out || right_out) $fatal(1,"disable mute");
    resetn=0; tick; if(frame_count!==0) $fatal(1,"counter reset");
    $display("FRAME_PATH_PASS: 48 signed stereo cases, timeout, stall, rearm, mute, reset");
    $finish;
end
initial begin #100000; $fatal(1,"test timeout"); end
endmodule
