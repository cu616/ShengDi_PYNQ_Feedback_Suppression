// Diagnostic variant of audio_pl_bringup. Output remains muted by default.
module audio_pl_diag(
    input wire clk, input wire resetn, input wire [31:0] control,
    input wire sdata_i, output wire sdata_o,
    output wire bclk, output wire lrclk,
    output wire [31:0] frame_count, output wire active,
    output reg [23:0] sample_left = 0, sample_right = 0,
    output reg [31:0] tx_nonzero_frames = 0, serial_one_edges = 0
);
    reg [10:0] divider = 0;
    (* ASYNC_REG = "TRUE" *) reg [1:0] adc_sync = 0;
    always @(posedge clk) begin
        if (!resetn) begin divider <= 0; adc_sync <= 0; end
        else begin divider <= divider + 1'b1; adc_sync <= {adc_sync[0],sdata_i}; end
    end
    assign bclk = divider[4];
    assign lrclk = divider[10];
    wire [23:0] rx_left, rx_right, tx_left, tx_right;
    wire rx_valid, serial_out;
    iis_deser receiver(.CLK_100MHZ(clk), .SCLK(bclk), .LRCLK(lrclk),
        .SDATA(adc_sync[1]), .EN(resetn), .LDATA(rx_left), .RDATA(rx_right), .VALID(rx_valid));
    audio_frame_path path(.clk(clk), .resetn(resetn), .control(control),
        .valid(rx_valid), .left_in(rx_left), .right_in(rx_right),
        .left_out(tx_left), .right_out(tx_right), .frame_count(frame_count), .active(active));
    always @(posedge clk) begin
        if (!resetn) begin sample_left <= 0; sample_right <= 0; end
        else if (rx_valid) begin sample_left <= rx_left; sample_right <= rx_right; end
    end
    iis_ser transmitter(.CLK_100MHZ(clk), .SCLK(bclk), .LRCLK(lrclk),
        .SDATA(serial_out), .EN(resetn), .LDATA(tx_left), .RDATA(tx_right));
    // Diagnostic mode (control[4]) keeps the physical DAC data pin at zero
    // while the internal frame path and serializer continue to run.
    assign sdata_o = (resetn && control[0] && active && !control[4]) ? serial_out : 1'b0;
    reg bclk_prev = 0;
    always @(posedge clk) begin
        if (!resetn) begin
            bclk_prev <= 0;
            tx_nonzero_frames <= 0;
            serial_one_edges <= 0;
        end else begin
            bclk_prev <= bclk;
            if (rx_valid && control[0] && active && ((|tx_left) || (|tx_right)))
                tx_nonzero_frames <= tx_nonzero_frames + 1'b1;
            if (bclk_prev && !bclk && control[0] && active && serial_out)
                serial_one_edges <= serial_one_edges + 1'b1;
        end
    end
endmodule
