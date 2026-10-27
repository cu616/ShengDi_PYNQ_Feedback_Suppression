`timescale 1ns/1ps
module tb_feedback_fir;
    reg clk=0; always #5 clk=~clk;
    reg resetn=0, coeff_begin=0, coeff_valid=0, in_valid=0, bypass=0;
    reg signed [23:0] coeff_data=0, reference_pcm=0, microphone_pcm=0;
    wire coeff_ready,in_ready,out_valid,psat,rsat,protocol_error;
wire signed [24:0] res_wide;
    wire signed [23:0] pred,res;
    // The golden vectors are 256 taps (scripts/make_fir_vectors.py); the RTL default is 512.
    feedback_fir #(.TAPS(256)) dut(clk,resetn,coeff_begin,coeff_valid,coeff_data,coeff_ready,
        in_valid,bypass,reference_pcm,microphone_pcm,in_ready,out_valid,pred,res,res_wide,psat,rsat,protocol_error);
    reg [23:0] h[0:255],u[0:767],mic[0:767],expected_pred[0:767],expected_res[0:767];
    reg [3:0] flags[0:767];
    string base,filename;
    integer c,n,k,cycles,checked=0;
    // Exact 25-bit difference oracle for the wide residual output: the vectors were produced by
    // scripts/make_fir_vectors.py from the Python integer reference, and `pred` is checked against
    // that same oracle above, so the expected wide value is simply mic - pred (or the
    // sign-extended microphone in bypass) with no rounding of its own.
    reg signed [24:0] expected_wide;
    task load_coefficients;
        begin
            @(negedge clk); coeff_begin=1;
            @(negedge clk); coeff_begin=0; #1;
            for(k=0;k<256;k=k+1) begin
                if(!coeff_ready) $fatal(1,"coefficient not ready");
                coeff_valid=1; coeff_data=h[k]; @(negedge clk);
            end
            coeff_valid=0;
            if(!in_ready) $fatal(1,"incomplete coefficient loading");
        end
    endtask
    initial begin
        if(!$value$plusargs("vectors=%s",base)) $fatal(1,"missing vectors path");
        repeat(3) @(negedge clk); resetn=1;
        if(in_ready) $fatal(1,"must not run before loading");
        for(c=0;c<3;c=c+1) begin
            filename=$sformatf("%s/h%0d.mem",base,c); $readmemh(filename,h);
            filename=$sformatf("%s/u%0d.mem",base,c); $readmemh(filename,u);
            filename=$sformatf("%s/mic%0d.mem",base,c); $readmemh(filename,mic);
            filename=$sformatf("%s/pred%0d.mem",base,c); $readmemh(filename,expected_pred);
            filename=$sformatf("%s/res%0d.mem",base,c); $readmemh(filename,expected_res);
            filename=$sformatf("%s/flags%0d.mem",base,c); $readmemh(filename,flags);
            load_coefficients(); // no reset between cases: reload must invalidate history
            for(n=0;n<768;n=n+1) begin
                if(!in_ready) $fatal(1,"sample not ready");
                reference_pcm=u[n]; microphone_pcm=mic[n]; bypass=flags[n][2]; in_valid=1;
                @(negedge clk); in_valid=0; cycles=0;
                while(!out_valid && cycles<780) begin @(negedge clk); cycles=cycles+1; end
                if(cycles!=771 || !out_valid) $fatal(1,"latency %0d",cycles);
                if(pred!==expected_pred[n] || res!==expected_res[n] || psat!==flags[n][1] || rsat!==flags[n][0])
                    $fatal(1,"case %0d frame %0d pred %h/%h residual %h/%h flags %b%b/%b",c,n,pred,expected_pred[n],res,expected_res[n],psat,rsat,flags[n]);
                expected_wide = flags[n][2] ? $signed({mic[n][23],mic[n]}) :
                                $signed({mic[n][23],mic[n]})-($signed({pred[23],pred}));
                if(res_wide!==expected_wide)
                    $fatal(1,"case %0d frame %0d wide %h/%h (mic %h pred %h bypass %b)",c,n,res_wide,expected_wide,mic[n],pred,flags[n][2]);
                if(protocol_error) $fatal(1,"unexpected protocol error");
                checked=checked+1;
                @(negedge clk);
            end
        end
        // Busy input is rejected and flagged. Reset must cancel the in-flight frame.
        in_valid=1; @(negedge clk); @(negedge clk); in_valid=0;
        if(!protocol_error) $fatal(1,"busy input not flagged");
        resetn=0; @(negedge clk); resetn=1;
        repeat(780) begin @(negedge clk); if(out_valid || in_ready || protocol_error) $fatal(1,"reset failed"); end
        $display("FEEDBACK_FIR_PASS samples=%0d latency=771 reload,bypass,saturation,busy,reset checked",checked);
        $finish;
    end
    initial begin #30000000; $fatal(1,"global simulation timeout"); end
endmodule
