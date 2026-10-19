// Bounded closed-loop path. Bypass and cancellation share gain and scheduling.
// Register contract: docs/interfaces/audio-closed-v1.md.
module audio_pl_closed #(parameter integer CAPTURE_FRAMES=16384, TAPS=256, MAX_RUN_FRAMES=488281)(
    input wire clk, resetn,
    input wire [31:0] control, capture_cmd, coefficient_cmd, frame_limit,
    input wire sdata_i,
    output wire sdata_o, bclk, lrclk,
    output reg [31:0] frame_count=0,
    output wire active,
    output reg [23:0] capture_left=0, capture_right=0,
    output wire [31:0] capture_status, coefficient_status,
    output reg [31:0] completed_count=0, gain_clip_count=0,
    output wire [31:0] saturation_counts
);
    reg [10:0] divider=0;
    (* ASYNC_REG="TRUE" *) reg [1:0] adc_sync=0;
    reg [15:0] gain_latched=0;
    reg [31:0] limit_latched=0, scheduled=0;
    reg [23:0] u_hold=0;
    reg u_ready=0;
    reg signed [40:0] gain_product=0;
    reg gain_valid=0;
    reg [15:0] prediction_clips=0, residual_clips=0;
    reg arm_d=0, frame_active=0, done=0, fault=0, session=0;
    reg [15:0] captured=0;
    reg [23:0] tx_word=0, reference_hold=0, microphone_hold=0;
    reg [95:0] memory[0:CAPTURE_FRAMES-1];
    reg [95:0] read_word=0;
    reg page_d=0;
    reg [1:0] command_d=0;
    reg fresh=0;
    reg [15:0] loaded_count=0;
    reg prediction_clip_seen=0, residual_clip_seen=0;
    wire arm=control[0];
    wire config_ok=control[31:16]<=32768 && frame_limit>0 && frame_limit<=MAX_RUN_FRAMES;
    wire [40:0] gain_magnitude=gain_product[40] ? -gain_product : gain_product;
    wire [40:0] gain_rounded_mag=(gain_magnitude+41'd2048)>>12;
    wire signed [40:0] gain_rounded=gain_product[40] ? -$signed(gain_rounded_mag) : $signed(gain_rounded_mag);
    wire gain_clipped=gain_rounded>41'sd8388607 || gain_rounded< -41'sd8388608;
    wire [23:0] gain_limited=gain_rounded>41'sd8388607 ? 24'h7fffff :
                               gain_rounded< -41'sd8388608 ? 24'h800000 : gain_rounded[23:0];
    assign saturation_counts={residual_clips,prediction_clips};
    wire [23:0] rx_left, rx_right;
    wire rx_valid, serial_out;
    wire begin_event=coefficient_cmd[25]!=command_d[1];
    wire data_event=coefficient_cmd[24]!=command_d[0];
    wire fir_ready, coeff_ready, fir_valid, fir_error, psat, rsat;
    wire signed [23:0] prediction, residual;
    // Starting a new run requires a COMPLETE fresh coefficient load: history is then zero.
    wire sample_valid=rx_valid && frame_active && session && arm && !fault && !done;
    wire run_ok=session && arm && !done && !fault && !fir_error && config_ok;
    assign bclk=divider[4];
    assign lrclk=divider[10];
    assign active=frame_active && run_ok && resetn;
    assign sdata_o=(run_ok && resetn) ? serial_out : 1'b0;
    assign capture_status={10'd0,(gain_clip_count!=0),residual_clip_seen,prediction_clip_seen,fault|fir_error,
                           (arm && !config_ok),captured,done};
    assign coefficient_status={12'd0,loaded_count,fresh,fir_error,fir_ready,coeff_ready};
    feedback_fir #(.TAPS(TAPS)) fir(.clk(clk),.resetn(resetn),
        .coeff_begin(begin_event && !arm),.coeff_valid(data_event && !arm && !begin_event),
        .coeff_data(coefficient_cmd[23:0]),.coeff_ready(coeff_ready),
        .in_valid(sample_valid),.bypass(control[1]),.reference_pcm(tx_word),.microphone_pcm(rx_left),
        .in_ready(fir_ready),.out_valid(fir_valid),.predicted_pcm(prediction),.residual_pcm(residual),
        .prediction_saturated(psat),.residual_saturated(rsat),.protocol_error(fir_error));
    iis_deser receiver(.CLK_100MHZ(clk),.SCLK(bclk),.LRCLK(lrclk),.SDATA(adc_sync[1]),
        .EN(resetn),.LDATA(rx_left),.RDATA(rx_right),.VALID(rx_valid));
    iis_ser transmitter(.CLK_100MHZ(clk),.SCLK(bclk),.LRCLK(lrclk),.SDATA(serial_out),
        .EN(resetn),.LDATA(tx_word),.RDATA(tx_word));
    always @(posedge clk) begin
        if (!resetn) begin
            divider<=0;adc_sync<=0;frame_count<=0;arm_d<=0;frame_active<=0;
            gain_latched<=0;limit_latched<=0;u_hold<=0;u_ready<=0;gain_product<=0;gain_valid<=0;
            completed_count<=0;gain_clip_count<=0;prediction_clips<=0;residual_clips<=0;done<=0;fault<=0;session<=0;captured<=0;scheduled<=0;
            tx_word<=0;reference_hold<=0;microphone_hold<=0;read_word<=0;page_d<=0;
            capture_left<=0;capture_right<=0;command_d<=0;fresh<=0;loaded_count<=0;
            prediction_clip_seen<=0;residual_clip_seen<=0;
        end else begin
            divider<=divider+1'b1;adc_sync<={adc_sync[0],sdata_i};arm_d<=arm;
            command_d<=coefficient_cmd[25:24];
            if (rx_valid) frame_count<=frame_count+1'b1;
            gain_valid<=0;
            if (arm && session && (control[31:16]!=gain_latched || frame_limit!=limit_latched)) fault<=1;
            if (begin_event && !arm) begin fresh<=0;loaded_count<=0;end
            if (data_event && !arm && !begin_event && coeff_ready) begin
                loaded_count<=loaded_count+1'b1;
                if (loaded_count==TAPS-1) fresh<=1;
            end
            // Any coefficient change while armed is a hard fault, never silently accepted.
            if (arm && (begin_event || data_event)) fault<=1;
            if (!arm) begin
                session<=0;frame_active<=0;tx_word<=0;u_ready<=0;
            end else if (!arm_d) begin
                session<=fresh && fir_ready && config_ok && !fir_error && !fault;
                if (!fresh || !fir_ready || !config_ok) fault<=1;
                fresh<=0;gain_latched<=control[31:16];limit_latched<=frame_limit;
                captured<=0;scheduled<=0;done<=0;completed_count<=0;u_ready<=0;u_hold<=0;
                gain_clip_count<=0;prediction_clips<=0;residual_clips<=0;
                frame_active<=0;tx_word<=0;prediction_clip_seen<=0;residual_clip_seen<=0;
            end else begin
                if (divider==2047) begin
                    // Prepare before the serializer observes falling LRCLK.
                    if (run_ok && scheduled<limit_latched) begin
                        if (u_ready) begin tx_word<=u_hold;u_ready<=0;end
                        else begin tx_word<=0;if(scheduled>=2) fault<=1;end
                        scheduled<=scheduled+1'b1;frame_active<=1;
                    end else begin tx_word<=0;frame_active<=0;end
                end
                if (scheduled==limit_latched && !frame_active && fir_ready && !gain_valid && !fir_valid)
                    done<=1;
                if (gain_valid && run_ok) begin
                    u_hold<=gain_limited;u_ready<=1;
                    if(gain_clipped) gain_clip_count<=gain_clip_count+1'b1;
                end
                if (sample_valid) begin
                    if (!fir_ready) fault<=1;
                    reference_hold<=tx_word;microphone_hold<=rx_left;
                end
                // MAC finishes across a frame boundary; held values identify its own input frame.
                if (fir_valid && session && !fault && !fir_error && !done) begin
                    memory[completed_count % CAPTURE_FRAMES]<={reference_hold,microphone_hold,prediction,residual};
                    completed_count<=completed_count+1'b1;
                    if(captured<CAPTURE_FRAMES) captured<=captured+1'b1;
                    gain_product<=$signed(residual)*$signed({1'b0,gain_latched});gain_valid<=1;
                    if(psat && prediction_clips!=65535) prediction_clips<=prediction_clips+1'b1;
                    if(rsat && residual_clips!=65535) residual_clips<=residual_clips+1'b1;
                    prediction_clip_seen<=prediction_clip_seen|psat;
                    residual_clip_seen<=residual_clip_seen|rsat;

                end
            end
            read_word<=memory[capture_cmd[13:0]];page_d<=capture_cmd[16];
            capture_left<=page_d ? read_word[47:24] : read_word[95:72];
            capture_right<=page_d ? read_word[23:0] : read_word[71:48];
        end
    end
endmodule
