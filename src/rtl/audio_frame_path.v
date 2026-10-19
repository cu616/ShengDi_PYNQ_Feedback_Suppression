// Bring-up only: signed attenuation, bounded run, default mute.
module audio_frame_path #(
    // 基础直通：24位补码按帧衰减输出；尚无反馈估计或抵消减法器。
    parameter integer MAX_FRAMES = 244141,
    parameter integer STALL_CYCLES = 4096
    // MAX_FRAMES在标称采样率下约5秒；帧预算及停帧保护都依赖clk继续运行。
)(
    input wire clk, input wire resetn,
    input wire [31:0] control,
    input wire valid,
    // valid表示一对左右采样有效，不是每个100MHz时钟都有效。
    input wire signed [23:0] left_in, right_in,
    output reg signed [23:0] left_out, right_out,
    output reg [31:0] frame_count,
    output reg active
);
    reg enable_d;
    reg [31:0] remaining;
    reg [31:0] stall;
    always @(posedge clk) begin
        if (!resetn) begin
            enable_d <= 0; remaining <= 0; stall <= 0;
            active <= 0; frame_count <= 0; left_out <= 0; right_out <= 0;
        end else begin
            enable_d <= control[0];
            if (valid) frame_count <= frame_count + 1;
            // 静音期间计数也增长，不能据此证明输出了有效声音。
            if (!control[0]) begin
                active <= 0; left_out <= 0; right_out <= 0;
                remaining <= 0; stall <= 0;
            end else if (!enable_d) begin
                // control[0]上升沿启动；预算耗尽后需先拉低再拉高才能重新启动。
                active <= 1; remaining <= MAX_FRAMES; stall <= 0;
                left_out <= 0; right_out <= 0;
            end else if (active) begin
                if (valid) begin
                    stall <= 0;
                    if (remaining > 1) begin
                        // 最后一份预算用于归零，传送输入的事件数最多为MAX_FRAMES-1。
                        remaining <= remaining - 1;
                        left_out <= left_in >>> control[3:1];
                        // >>>保留符号；每右移一位幅度约减半，这是降增益而非反馈抵消。
                        right_out <= right_in >>> control[3:1];
                    end else begin
                        remaining <= 0; active <= 0;
                        left_out <= 0; right_out <= 0;
                    end
                end else if (stall >= STALL_CYCLES-1) begin
                    active <= 0; left_out <= 0; right_out <= 0;
                end else stall <= stall + 1;
            end else begin
                left_out <= 0; right_out <= 0;
            end
        end
    end
endmodule
