// 可加载系数的串行MAC反馈预测与残差核；接口见feedback-fir-v1.md。
module feedback_fir #(parameter integer TAPS = 256)(
    input wire clk, resetn,
    input wire coeff_begin, coeff_valid,
    input wire signed [23:0] coeff_data,
    output wire coeff_ready,
    input wire in_valid, bypass,
    input wire signed [23:0] reference_pcm, microphone_pcm,
    output wire in_ready,
    output reg out_valid,
    output reg signed [23:0] predicted_pcm, residual_pcm,
    output reg prediction_saturated, residual_saturated,
    output reg protocol_error
);
    localparam IDLE=0, MULTIPLY=1, ACCUMULATE=2, ROUND=3, CLIP=4, FINISH=5, FETCH=6;
    reg [2:0] state;
    reg loading, loaded, bypass_hold;
    integer load_index, write_index, read_index, tap_index, history_count;
    reg signed [23:0] coefficients [0:TAPS-1];
    reg signed [23:0] history [0:TAPS-1];
    reg signed [23:0] reference_hold, microphone_hold;
    reg signed [47:0] product;
    reg signed [23:0] sample_operand, coefficient_operand;
    reg signed [57:0] accumulator;
    reg signed [57:0] rounded_hold;
    reg signed [23:0] prediction_hold;
    reg prediction_clip_hold;
    wire signed [57:0] extended_product = {{10{product[47]}},product};
    wire [57:0] magnitude = accumulator[57] ? -accumulator : accumulator;
    wire [57:0] rounded_magnitude = (magnitude + 58'd524288) >> 20;
    wire signed [57:0] rounded = accumulator[57] ? -$signed(rounded_magnitude) : $signed(rounded_magnitude);
    wire prediction_clip = rounded_hold > 58'sd8388607 || rounded_hold < -58'sd8388608;
    wire signed [23:0] prediction = rounded_hold > 58'sd8388607 ? 24'sh7fffff :
        rounded_hold < -58'sd8388608 ? 24'sh800000 : rounded_hold[23:0];
    wire signed [24:0] difference = {microphone_hold[23],microphone_hold} - {prediction_hold[23],prediction_hold};
    wire difference_clip = difference > 25'sd8388607 || difference < -25'sd8388608;
    wire signed [23:0] difference_limited = difference > 25'sd8388607 ? 24'sh7fffff :
        difference < -25'sd8388608 ? 24'sh800000 : difference[23:0];
    assign coeff_ready = resetn && state==IDLE && loading && !coeff_begin;
    assign in_ready = resetn && state==IDLE && loaded && !loading && !coeff_begin;

    always @(posedge clk) begin
        if (!resetn) begin
            state<=IDLE; loading<=0; loaded<=0; bypass_hold<=0;
            load_index<=0; write_index<=0; read_index<=0; tap_index<=0; history_count<=0;
            reference_hold<=0; microphone_hold<=0; product<=0; accumulator<=0;
            rounded_hold<=0; prediction_hold<=0; prediction_clip_hold<=0;
            sample_operand<=0; coefficient_operand<=0;
            out_valid<=0; predicted_pcm<=0; residual_pcm<=0;
            prediction_saturated<=0; residual_saturated<=0; protocol_error<=0;
        end else begin
            out_valid<=0;
            if (in_valid && !in_ready) protocol_error<=1;
            if (coeff_valid && !coeff_ready) protocol_error<=1;
            if (coeff_begin && state!=IDLE) protocol_error<=1;
            case (state)
                IDLE: begin
                    if (coeff_begin) begin
                        loading<=1; loaded<=0; load_index<=0;
                        history_count<=0; write_index<=0;
                    end else if (coeff_valid && coeff_ready) begin
                        coefficients[load_index]<=coeff_data;
                        if (load_index==TAPS-1) begin loading<=0; loaded<=1; end
                        else load_index<=load_index+1;
                    end else if (in_valid && in_ready) begin
                        reference_hold<=reference_pcm; microphone_hold<=microphone_pcm;
                        bypass_hold<=bypass; accumulator<=0; tap_index<=0;
                        read_index<=write_index==0 ? TAPS-1 : write_index-1;
                        state<=FETCH;
                    end
                end
                FETCH: begin
                    // RAM寻址与乘法分拍，避免地址译码/数据选择接上两级DSP成为长路径。
                    sample_operand<=tap_index<history_count ? history[read_index] : 24'sd0;
                    coefficient_operand<=coefficients[tap_index];
                    state<=MULTIPLY;
                end
                MULTIPLY: begin
                    product <= sample_operand*coefficient_operand;
                    state<=ACCUMULATE;
                end
                ACCUMULATE: begin
                    accumulator<=accumulator+extended_product;
                    if (tap_index==TAPS-1) state<=ROUND;
                    else begin
                        tap_index<=tap_index+1;
                        read_index<=read_index==0 ? TAPS-1 : read_index-1;
                        state<=FETCH;
                    end
                end
                // 将舍入、预测饱和、残差相减分拍，避免58位算术贯穿到输出。
                ROUND: begin rounded_hold<=rounded; state<=CLIP; end
                CLIP: begin
                    prediction_hold<=prediction; prediction_clip_hold<=prediction_clip;
                    state<=FINISH;
                end
                FINISH: begin
                    predicted_pcm<=prediction_hold;
                    residual_pcm<=bypass_hold ? microphone_hold : difference_limited;
                    prediction_saturated<=prediction_clip_hold;
                    residual_saturated<=!bypass_hold && difference_clip;
                    out_valid<=1;
                    // 到此才写当前参考，保证最老一帧尚未被覆盖时已完成计算。
                    history[write_index]<=reference_hold;
                    write_index<=write_index==TAPS-1 ? 0 : write_index+1;
                    if (history_count<TAPS) history_count<=history_count+1;
                    state<=IDLE;
                end
            endcase
        end
    end
endmodule
