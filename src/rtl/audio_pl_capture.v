// Muted 4096-frame ADC capture for real-board I2S diagnosis.
// Reuses the already-built probe path; capture never enables DAC output.
module audio_pl_capture #(
    parameter integer CAPTURE_FRAMES = 4096
)(
    input wire clk, input wire resetn, input wire [31:0] control,
    input wire [31:0] capture_cmd,
    input wire sdata_i, output wire sdata_o,
    output wire bclk, output wire lrclk,
    output wire [31:0] frame_count, output wire active,
    output reg [23:0] capture_left = 0, capture_right = 0,
    output wire [31:0] capture_status
);
    wire [23:0] sample_left, sample_right;
    audio_pl_probe probe(.clk(clk), .resetn(resetn), .control(control),
        .sdata_i(sdata_i), .sdata_o(sdata_o), .bclk(bclk), .lrclk(lrclk),
        .frame_count(frame_count), .active(active),
        .sample_left(sample_left), .sample_right(sample_right));

    reg [47:0] capture_mem [0:CAPTURE_FRAMES-1];
    reg [12:0] captured = 0;
    reg done = 0;
    reg arm_d = 0;
    reg [31:0] frame_d = 0;
    wire arm = capture_cmd[16];
    wire [11:0] read_index = capture_cmd[11:0];
    reg [47:0] read_word = 0;
    assign capture_status = {18'd0, captured, done};

    always @(posedge clk) begin
        if (!resetn) begin
            captured <= 0;
            done <= 0;
            arm_d <= 0;
            frame_d <= 0;
            read_word <= 0;
            capture_left <= 0;
            capture_right <= 0;
        end else begin
            arm_d <= arm;
            frame_d <= frame_count;
            if (!arm || !arm_d) begin
                captured <= 0;
                done <= 0;
            end else if (!done && frame_count != frame_d) begin
                capture_mem[captured[11:0]] <= {sample_left, sample_right};
                captured <= captured + 1'b1;
                if (captured == CAPTURE_FRAMES-1) done <= 1;
            end
            read_word <= capture_mem[read_index];
            capture_left <= read_word[47:24];
            capture_right <= read_word[23:0];
        end
    end
endmodule
