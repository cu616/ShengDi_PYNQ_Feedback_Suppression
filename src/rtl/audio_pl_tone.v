// Bounded open-loop PL tone source for isolating the DAC/output path.
module audio_pl_tone(
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
    // control[5] selects a 1.017 kHz, 24-frame half-period square wave.
    // Three 250 ms bursts are generated within 1.5 s. The amplitude is
    // approximately -18 dBFS before the existing arithmetic shift.
    reg [16:0] tone_frames = 0;
    reg [5:0] tone_phase = 0;
    always @(posedge clk) begin
        if (!resetn || !control[0] || !control[5]) begin
            tone_frames <= 0;
            tone_phase <= 0;
        end else if (rx_valid) begin
            if (tone_frames < 17'd73242) tone_frames <= tone_frames + 1'b1;
            if (tone_phase == 6'd47) tone_phase <= 0;
            else tone_phase <= tone_phase + 1'b1;
        end
    end
    wire tone_on = (tone_frames >= 17'd9766 && tone_frames < 17'd21973) ||
                   (tone_frames >= 17'd31738 && tone_frames < 17'd43945) ||
                   (tone_frames >= 17'd53711 && tone_frames < 17'd65918);
    wire signed [23:0] tone_word = !tone_on ? 24'sd0 :
        (tone_phase < 6'd24 ? 24'sd1056063 : -24'sd1056063);
    wire signed [23:0] path_left = control[5] ? tone_word : rx_left;
    wire signed [23:0] path_right = control[5] ? tone_word : rx_right;
    audio_frame_path path(.clk(clk), .resetn(resetn), .control(control),
        .valid(rx_valid), .left_in(path_left), .right_in(path_right),
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
