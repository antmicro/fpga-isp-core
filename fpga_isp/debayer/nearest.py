from migen import *
import math

from litex.soc.interconnect.csr import *
from litex.soc.interconnect import stream
from fpga_isp.debayer.base import *
from fpga_isp.debayer.common import *
from fpga_isp.debayer.cache import *
from litex.soc.interconnect.csr_eventmanager import *

class NearestNeighbour(DemosaicBase):
    def __init__(self, im_w, im_h, pattern, streamout, enable=Signal(1,reset=1), streamin=None, cache=None):
        def fetch_next_col(i):
            return [[NextValue(colors.row(r), Cat(cache.r_data[(i+r)%cache.mem_chunks], colors.row(r))) for r in range(0,2)],
                    [NextValue(cache.adrs[(i+r)%cache.mem_chunks], cache.adrs[(i+r)%cache.mem_chunks]+1) for r in range(0,2)],]

        def fetch_null_col(i):
            return [[NextValue(colors.row(r), Cat(Signal(cache.bpp), colors.row(r))) for r in range(0,2)],
                    [NextValue(cache.adrs[(i+r)%cache.mem_chunks], 0) for r in range(0,2)],]

        def fetch_col_on_new_line(i):
            return [[NextValue(colors.row(r), Cat(cache.r_data[(i+(r+1))%cache.mem_chunks], colors.row(r))) for r in range(0,2)],
                    [NextValue(cache.adrs[(i+(r+1))%cache.mem_chunks], cache.adrs[(i+(r+1))%cache.mem_chunks]+1) for r in range(0,2)],]

        def reset_algorithm():
            return [
                    NextValue(self.working, 0),
                    NextValue(self.first_pixel, 1),
                    NextValue(self.rgb_first, 0),
                    NextValue(last_color_decoded,0),
                    NextValue(self.rgb_valid, 0),
                    [NextValue(colors.row(r), Signal(cache.bpp*kernel_width)) for r in range(2)],
                    NextState("FETCH_SYNC0"),
                ]

        def get_decoder(pattern, state):
            if state == "DECODE_R":
                return [If((pattern == Bayer_t.RGGB) | pattern == Bayer_t.BGGR,
                            NextValue(r_val, colors.cell(0,1)),
                            NextValue(g_val, colors.cell(0,0)),
                            NextValue(b_val, colors.cell(1,0)),
                        ).Else(
                            NextValue(r_val, colors.cell(0,1)),
                            NextValue(g_val, colors.cell(0,0)),
                            NextValue(b_val, colors.cell(1,1)),
                        ),]
            elif state == "DECODE_G0":
                return [If((pattern == Bayer_t.RGGB) | pattern == Bayer_t.BGGR,
                            NextValue(r_val, colors.cell(0,0)),
                            NextValue(g_val, colors.cell(0,1)),
                            NextValue(b_val, colors.cell(1,1)),
                        ).Else(
                            NextValue(r_val, colors.cell(0,0)),
                            NextValue(g_val, colors.cell(0,1)),
                            NextValue(b_val, colors.cell(1,0)),
                        ),]
            elif state == "DECODE_G1":
                return [If((pattern == Bayer_t.RGGB) | pattern == Bayer_t.BGGR,
                            NextValue(r_val, colors.cell(1,1)),
                            NextValue(g_val, colors.cell(0,1)),
                            NextValue(b_val, colors.cell(0,0)),
                        ).Else(
                            NextValue(r_val, colors.cell(1,0)),
                            NextValue(g_val, colors.cell(0,1)),
                            NextValue(b_val, colors.cell(0,0)),
                        ),]
            elif state == "DECODE_B":
                return [If((pattern == Bayer_t.RGGB) | pattern == Bayer_t.BGGR,
                            NextValue(r_val, colors.cell(1,0)),
                            NextValue(g_val, colors.cell(0,0)),
                            NextValue(b_val, colors.cell(0,1)),
                        ).Else(
                            NextValue(r_val, colors.cell(1,1)),
                            NextValue(g_val, colors.cell(0,0)),
                            NextValue(b_val, colors.cell(0,1)),
                        ),]

        assert(streamin != None and cache == None or streamin == None and cache != None)
        if streamin != None:
            self.submodules.ev = EventManager()
            self.ev.error = EventSourcePulse(description="data underflow/overflow")
            self.submodules.cache = cache = DemosaicCache(bpp=8,
                                                          mem_chunks=4,
                                                          streamin=streamin,
                                                          im_w=im_w,
                                                          im_h=im_h,
                                                          mem_treshold=Signal(1,reset=0),
                                                          enable=enable,
                                                          u_reset=self.ev.irq)
        super().__init__(cache=cache, im_w=im_w, im_h=im_h, min_lines_req=1, streamout=streamout, active=enable)
        assert(cache.mem_chunks > self.min_lines_required)

        kernel_width=2
        kernel_height=2
        colors = Bayer_kernel(cache.bpp, kernel_width, kernel_height)

        last_color_decoded = Signal(reset=0)
        r_val = Signal(cache.bpp)
        g_val = Signal(cache.bpp)
        b_val = Signal(cache.bpp)
        self.comb += [
                If(enable,
                    self.rgb_data.eq(Cat(b_val, g_val, r_val))
                )
        ]
        self.sync +=[
            If(cache.force_reset & ~cache.hold_reset & ~cache.raw_first,
                self.working.eq(0),
                self.first_pixel.eq(1),
                self.rgb_first.eq(0),
                self.rgb_valid.eq(0),
                last_color_decoded.eq(0),
                [colors.row(r).eq(Signal(cache.bpp*kernel_width)) for r in range(2)],
            )
        ]

        self.submodules.demo_fsm = demo_fsm = FSM(reset_state="FETCH_SYNC0")

        for i in range(cache.mem_chunks):
            demo_fsm.act("FETCH_SYNC{}".format(i),
                If(enable,
                    If(self.rgb_ready,
                        NextValue(self.working, 1),
                        NextValue(self.rgb_valid, 0),
                        NextValue(self.rgb_last,0),
                        If(cache.processed_lines == im_h,
                            reset_algorithm(),
                        ).Else(
                            If((cache.collected_lines - cache.processed_lines > self.min_lines_required) | (cache.processed_lines == im_h-1),
                                If(~cache.frame_sync_incorrect, fetch_next_col(i)),
                                If(cache.adrs[i] == kernel_width-1,
                                    If(pattern == Bayer_t.RGGB,
                                        NextState(["FETCH_DECODE_R{}", "FETCH_DECODE_G1{}"][i%2].format(i)),
                                    ).Elif(pattern == Bayer_t.BGGR,
                                        NextState(["FETCH_DECODE_B{}", "FETCH_DECODE_G0{}"][i%2].format(i)),
                                    ).Elif(pattern == Bayer_t.RGBG,
                                        NextState(["FETCH_DECODE_R{}", "FETCH_DECODE_B{}"][i%2].format(i)),
                                    ).Else(
                                        NextState(["FETCH_DECODE_G0{}", "FETCH_DECODE_G1{}"][i%2].format(i)),
                                    )
                                )
                            )
                        )
                    )
                )
            )
            demo_fsm.act("FETCH_DECODE_R{}".format(i),
                If(~cache.force_reset & ~cache.frame_sync_incorrect,
                    If(enable,
                        If(self.rgb_ready ,
                            get_decoder(pattern, "DECODE_R"),
                            NextValue(self.rgb_valid, 1),
                            If(~last_color_decoded,
                                If(cache.adrs[i] < im_w,
                                    fetch_next_col(i),
                                    self.first_pix(),
                                    NextState("FETCH_DECODE_G0{}".format(i)),
                                ).Else(
                                    fetch_null_col(i),
                                    NextValue(last_color_decoded,1),
                                    NextState("FETCH_DECODE_G0{}".format(i)),
                                )
                            ).Else(
                                NextValue(cache.processed_lines, cache.processed_lines+1),
                                NextValue(last_color_decoded,0),
                                NextValue(self.rgb_last,1),
                                fetch_col_on_new_line(i),
                                NextState("FETCH_SYNC{}".format((i+1)%cache.mem_chunks)),
                            )
                        )
                    )
                ).Else(
                    reset_algorithm(),
                )
            )

            demo_fsm.act("FETCH_DECODE_G0{}".format(i),
                If(~cache.force_reset& ~cache.frame_sync_incorrect,
                    If(enable,
                        If(self.rgb_ready ,
                            get_decoder(pattern, "DECODE_G0"),
                            NextValue(self.rgb_valid, 1),
                            If(~last_color_decoded,
                                If(cache.adrs[i] < im_w,
                                    fetch_next_col(i),
                                    self.first_pix(),
                                    NextState("FETCH_DECODE_R{}".format(i)),
                                ).Else(
                                    fetch_null_col(i),
                                    NextValue(last_color_decoded,1),
                                    NextState("FETCH_DECODE_R{}".format(i)),
                                )
                            ).Else(
                                NextValue(cache.processed_lines, cache.processed_lines+1),
                                NextValue(last_color_decoded,0),
                                NextValue(self.rgb_last,1),
                                fetch_col_on_new_line(i),
                                NextState("FETCH_SYNC{}".format((i+1)%cache.mem_chunks)),
                            )
                        )
                    )
                ).Else(
                    reset_algorithm(),
                )
            )

            demo_fsm.act("FETCH_DECODE_G1{}".format(i),
                If(~cache.force_reset& ~cache.frame_sync_incorrect,
                    If(enable,
                        If(self.rgb_ready ,
                            get_decoder(pattern, "DECODE_G1"),
                            NextValue(self.rgb_valid, 1),
                            If(~last_color_decoded,
                                If(cache.adrs[i] < im_w,
                                    fetch_next_col(i),
                                    self.first_pix(),
                                    NextState("FETCH_DECODE_B{}".format(i)),
                                ).Else(
                                    fetch_null_col(i),
                                    NextValue(last_color_decoded,1),
                                    NextState("FETCH_DECODE_B{}".format(i)),
                                )
                            ).Else(
                                NextValue(cache.processed_lines, cache.processed_lines+1),
                                NextValue(last_color_decoded,0),
                                NextValue(self.rgb_last,1),
                                fetch_col_on_new_line(i),
                                NextState("FETCH_SYNC{}".format((i+1)%cache.mem_chunks)),
                            )
                        )
                    )
                ).Else(
                    reset_algorithm(),
                )
            )

            demo_fsm.act("FETCH_DECODE_B{}".format(i),
                If(~cache.force_reset & ~cache.frame_sync_incorrect,
                    If(enable,
                        If(self.rgb_ready,
                            get_decoder(pattern, "DECODE_B"),
                            NextValue(self.rgb_valid, 1),
                            If(~last_color_decoded,
                                If(cache.adrs[i] < im_w,
                                    fetch_next_col(i),
                                    self.first_pix(),
                                    NextState("FETCH_DECODE_G1{}".format(i)),
                                ).Else(
                                    fetch_null_col(i),
                                    NextValue(last_color_decoded,1),
                                    NextState("FETCH_DECODE_G1{}".format(i)),
                                )
                            ).Else(
                                NextValue(cache.processed_lines, cache.processed_lines+1),
                                NextValue(last_color_decoded,0),
                                NextValue(self.rgb_last,1),
                                fetch_col_on_new_line(i),
                                NextState("FETCH_SYNC{}".format((i+1)%cache.mem_chunks)),
                            )
                        )
                    )
                ).Else(
                    reset_algorithm(),
                )
            )
