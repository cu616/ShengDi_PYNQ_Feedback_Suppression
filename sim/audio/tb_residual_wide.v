// Targeted check for the wide-residual change in feedback_fir.
// Proves: (1) residual_wide equals the unclamped difference; (2) the legacy 24-bit residual_pcm
// and its overflow flag keep their original meaning; (3) bypass sign-extends the microphone.
`timescale 1ns/1ps
module tb_residual_wide;
    reg clk=0, resetn=0, coeff_begin=0, coeff_valid=0, in_valid=0, bypass=0;
    reg signed [23:0] coeff_data=0, reference_pcm=0, microphone_pcm=0;
    wire coeff_ready, in_ready, out_valid, psat, rsat, protocol_error;
    wire signed [23:0] pred, res;
    wire signed [24:0] res_wide;

    feedback_fir #(.TAPS(256)) dut(.clk(clk),.resetn(resetn),
        .coeff_begin(coeff_begin),.coeff_valid(coeff_valid),.coeff_data(coeff_data),
        .coeff_ready(coeff_ready),.in_valid(in_valid),.bypass(bypass),
        .reference_pcm(reference_pcm),.microphone_pcm(microphone_pcm),.in_ready(in_ready),
        .out_valid(out_valid),.predicted_pcm(pred),.residual_pcm(res),.residual_wide_pcm(res_wide),
        .prediction_saturated(psat),.residual_saturated(rsat),.protocol_error(protocol_error));

    always #5 clk = ~clk;
    integer i, errors=0, checked=0;

    task load_unit_coeff;
        begin
            @(negedge clk); coeff_begin=1; @(negedge clk); coeff_begin=0;
            for (i=0;i<256;i=i+1) begin
                coeff_valid=1; coeff_data=(i==0)?24'sd1048576:24'sd0; @(negedge clk);
            end
            coeff_valid=0;
            repeat (2) @(negedge clk);
        end
    endtask

    task one_frame(input signed [23:0] mic, input b);
        begin
            while (!in_ready) @(negedge clk);
            in_valid=1; microphone_pcm=mic; reference_pcm=-24'sd1000; bypass=b;
            @(negedge clk); in_valid=0;
            while (!out_valid) @(negedge clk);
        end
    endtask

    task check(input signed [23:0] mic, input b, input signed [24:0] want_wide,
               input signed [23:0] want_res, input want_sat, input [8*28-1:0] label);
        begin
            one_frame(mic, b);
            #1;
            if (res_wide !== want_wide) begin
                $display("FAIL %0s residual_wide=%0d want %0d", label, res_wide, want_wide);
                errors=errors+1;
            end
            if (res !== want_res) begin
                $display("FAIL %0s residual=%0d want %0d", label, res, want_res);
                errors=errors+1;
            end
            if (rsat !== want_sat) begin
                $display("FAIL %0s residual_saturated=%b want %b", label, rsat, want_sat);
                errors=errors+1;
            end
            checked=checked+1;
        end
    endtask

    initial begin
        if ($test$plusargs("vcd")) begin
            $dumpfile("tb_residual_wide.vcd"); $dumpvars(0, tb_residual_wide);
        end
        resetn=0; repeat(4) @(negedge clk); resetn=1;
        load_unit_coeff;

        // frame 1: seed the history with a negative reference so later predictions are negative
        while (!in_ready) @(negedge clk);
        in_valid=1; microphone_pcm=24'sd0; reference_pcm=-24'sd1000; bypass=1'b0;
        @(negedge clk); in_valid=0;
        while (!out_valid) @(negedge clk);
        in_valid=0; reference_pcm=24'sd0;
        // frame 2: q[0]=1.0 turns that -1000 reference into prediction = -1000
        check(24'sd0, 1'b0, 25'sd1000, 24'sd1000, 1'b0, "no_overflow");
        // frame 3: microphone at the positive rail with a negative prediction -> difference overflows
        check(24'sh7fffff, 1'b0, 25'sd8389607, 24'sh7fffff, 1'b1, "pos_overflow");
        // frame 4: microphone at the negative rail with a negative prediction -> still inside
        check(24'sh800000, 1'b0, -25'sd8387608, -24'sd8387608, 1'b0, "neg_inside");
        // bypass: the microphone is the residual, sign-extended
        one_frame(24'sd7, 1'b1);
        if (res_wide !== 25'sd7) begin
            $display("FAIL bypass residual_wide=%0d", res_wide); errors=errors+1;
        end
        checked=checked+1;
        if (errors==0) $display("RESIDUAL_WIDE_PASS checked=%0d (legacy residual and its flag unchanged, wide residual exact)", checked);
        else $display("RESIDUAL_WIDE_FAIL errors=%0d", errors);
        $finish;
    end

    initial begin
        #20000000;
        $display("RESIDUAL_WIDE_FAIL timeout");
        $finish;
    end
endmodule
