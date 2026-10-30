// Simulator-only Verilog stand-ins for the two vendor I2S modules.
//
// WHY THIS FILE EXISTS: the synthesis flow builds src/vendor/pynq_v2_4/iis_ser.vhd and
// iis_deser.vhd (see build/scripts/create_audio_replay.tcl). Icarus Verilog cannot compile
// VHDL, so it also cannot elaborate any RTL that instantiates them. This file lets the
// Icarus testbenches run the real RTL; it is NOT part of the bitstream and must never be
// added to a Vivado file set.
//
// FAITHFULNESS: each module below is a one-to-one translation of the corresponding VHDL
// architecture -- same state list, same bit-counter compare value, same edge detectors
// (SCLK rising for the receiver, SCLK falling for the serializer, LRCLK both edges), same
// register update order. The VHDL has three clocked processes that all read pre-edge
// values; a single always block with non-blocking assignments reads pre-edge values too,
// so the translation is behaviourally identical rather than merely similar.
// VALID / SDATA keep their VHDL concurrent-assignment meaning (combinational functions of
// the current registers).
//
// The regression cross-check is that the pre-existing sim/audio/tb_audio_replay.v, which was
// written against the vendor VHDL under Vivado xsim, also passes with these models.

// iis_deser: serial ADC data -> 24-bit left/right words plus a one-cycle VALID.
module iis_deser (
    input  wire        CLK_100MHZ,
    input  wire        SCLK,
    input  wire        LRCLK,
    input  wire        SDATA,
    input  wire        EN,
    output wire [23:0] LDATA,
    output wire [23:0] RDATA,
    output wire        VALID
);
    localparam [2:0] RESET=0, WAIT_LEFT=1, SKIP_LEFT=2, READ_LEFT=3,
                     WAIT_RIGHT=4, SKIP_RIGHT=5, READ_RIGHT=6;
    localparam [4:0] BIT_MAX=5'd24;   // "11000" in iis_deser.vhd

    reg [2:0]  iis_state=RESET;
    reg        sclk_d1=0, lrclk_d1=0;
    reg [4:0]  bit_cntr=0;
    reg [23:0] ldata_reg=0, rdata_reg=0;

    wire start_left  = lrclk_d1 & ~LRCLK;   // falling edge on LRCLK
    wire start_right = ~lrclk_d1 & LRCLK;   // rising edge on LRCLK
    wire bit_rdy     = ~sclk_d1 & SCLK;     // rising edge on SCLK

    always @(posedge CLK_100MHZ) begin
        sclk_d1  <= SCLK;
        lrclk_d1 <= LRCLK;
        // Next-state logic.
        case (iis_state)
            RESET:      if (EN) iis_state <= WAIT_LEFT;
            WAIT_LEFT:  if (!EN) iis_state <= RESET;
                        else if (start_left) iis_state <= SKIP_LEFT;
            SKIP_LEFT:  if (!EN) iis_state <= RESET;
                        else if (bit_rdy) iis_state <= READ_LEFT;
            READ_LEFT:  if (!EN) iis_state <= RESET;
                        else if (bit_cntr == BIT_MAX) iis_state <= WAIT_RIGHT;
            WAIT_RIGHT: if (!EN) iis_state <= RESET;
                        else if (start_right) iis_state <= SKIP_RIGHT;
            SKIP_RIGHT: if (!EN) iis_state <= RESET;
                        else if (bit_rdy) iis_state <= READ_RIGHT;
            READ_RIGHT: if (!EN) iis_state <= RESET;
                        else if (bit_cntr == BIT_MAX) iis_state <= WAIT_LEFT;
            default:    iis_state <= RESET;
        endcase
        // Bit counter: counts received bits while in a READ state, cleared otherwise.
        if (iis_state == READ_RIGHT || iis_state == READ_LEFT) begin
            if (bit_rdy) bit_cntr <= bit_cntr + 5'd1;
        end else begin
            bit_cntr <= 5'd0;
        end
        // Shift registers.
        if (iis_state == RESET) begin
            ldata_reg <= 24'd0;
            rdata_reg <= 24'd0;
        end else begin
            if (iis_state == READ_LEFT && bit_rdy) begin
                ldata_reg <= {ldata_reg[22:0], SDATA};
            end
            if (iis_state == READ_RIGHT && bit_rdy) begin
                rdata_reg <= {rdata_reg[22:0], SDATA};
            end
        end
    end

    assign VALID = (iis_state == READ_RIGHT && bit_cntr == BIT_MAX) ? 1'b1 : 1'b0;
    assign LDATA = ldata_reg;
    assign RDATA = rdata_reg;
endmodule

// iis_ser: 24-bit left/right words -> serial DAC data. Latch happens on the falling LRCLK
// edge while waiting for the left channel, so the word presented during a frame is the one
// the design loaded before that edge.
module iis_ser (
    input  wire        CLK_100MHZ,
    input  wire        SCLK,
    input  wire        LRCLK,
    output wire        SDATA,
    input  wire        EN,
    input  wire [23:0] LDATA,
    input  wire [23:0] RDATA
);
    localparam [2:0] RESET=0, WAIT_LEFT=1, WRITE_LEFT=2, WAIT_RIGHT=3, WRITE_RIGHT=4;
    localparam [4:0] BIT_MAX=5'd25;   // "11001" in iis_ser.vhd

    reg [2:0]  iis_state=RESET;
    reg        sclk_d1=0, lrclk_d1=0;
    reg [4:0]  bit_cntr=0;
    reg [23:0] ldata_reg=0, rdata_reg=0;
    reg        sdata_reg=0;

    wire start_left  = lrclk_d1 & ~LRCLK;   // falling edge on LRCLK
    wire start_right = ~lrclk_d1 & LRCLK;   // rising edge on LRCLK
    wire write_bit   = sclk_d1 & ~SCLK;     // falling edge on SCLK

    always @(posedge CLK_100MHZ) begin
        sclk_d1  <= SCLK;
        lrclk_d1 <= LRCLK;
        case (iis_state)
            RESET:       if (EN) iis_state <= WAIT_LEFT;
            WAIT_LEFT:   if (!EN) iis_state <= RESET;
                         else if (start_left) iis_state <= WRITE_LEFT;
            WRITE_LEFT:  if (!EN) iis_state <= RESET;
                         else if (bit_cntr == BIT_MAX) iis_state <= WAIT_RIGHT;
            WAIT_RIGHT:  if (!EN) iis_state <= RESET;
                         else if (start_right) iis_state <= WRITE_RIGHT;
            WRITE_RIGHT: if (!EN) iis_state <= RESET;
                         else if (bit_cntr == BIT_MAX) iis_state <= WAIT_LEFT;
            default:     iis_state <= RESET;
        endcase
        if (iis_state == WRITE_RIGHT || iis_state == WRITE_LEFT) begin
            if (write_bit) bit_cntr <= bit_cntr + 5'd1;
        end else begin
            bit_cntr <= 5'd0;
        end
        if (iis_state == RESET) begin
            ldata_reg <= 24'd0;
            rdata_reg <= 24'd0;
        end else if (iis_state == WAIT_LEFT && start_left) begin
            ldata_reg <= LDATA;
            rdata_reg <= RDATA;
        end else begin
            if (iis_state == WRITE_LEFT && write_bit) begin
                ldata_reg <= {ldata_reg[22:0], 1'b0};
            end
            if (iis_state == WRITE_RIGHT && write_bit) begin
                rdata_reg <= {rdata_reg[22:0], 1'b0};
            end
        end
        if (iis_state == RESET) begin
            sdata_reg <= 1'b0;
        end else if (iis_state == WRITE_LEFT && write_bit) begin
            sdata_reg <= ldata_reg[23];
        end else if (iis_state == WRITE_RIGHT && write_bit) begin
            sdata_reg <= rdata_reg[23];
        end
    end

    assign SDATA = sdata_reg;
endmodule
