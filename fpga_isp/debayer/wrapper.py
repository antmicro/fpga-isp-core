from migen import *
import math

from litex.soc.interconnect.csr import *
from litex.soc.interconnect import stream
from fpga_isp.debayer.nearest import *
from fpga_isp.debayer.bilinear import *
from fpga_isp.debayer.edge_directed import *
from fpga_isp.debayer.cache import *
from fpga_isp.debayer.common import *
from litex.soc.interconnect.csr_eventmanager import *

class DemosaicWrapper(Module, AutoCSR):
    axi_width = 32
    raw_width = 8
    input_layout  = [("data",   raw_width)]
    output_layout = [("data",   axi_width)]

    def __init__(self, demosiacer_type, streamin, streamout, cols, rows, pattern, in_reverse=False, out_reverse=False):
        im_w_bits = 13
        im_h_bits = 13
        self.submodules.raw_converter = raw_converter = stream.Converter(self.axi_width,
                                                                          self.raw_width,
                                                                          reverse=in_reverse)
        self.input  = input  = stream.Endpoint(self.input_layout)
        self.output = output = stream.Endpoint(self.output_layout)
        self.comb += [
            raw_converter.sink.data.eq(streamin.data),
            raw_converter.sink.valid.eq(streamin.valid),
            streamin.ready.eq(raw_converter.sink.ready),
            raw_converter.sink.last.eq(streamin.last),
            raw_converter.sink.first.eq(streamin.first),

            output.ready.eq(streamout.ready),
            streamout.valid.eq(output.valid),
            streamout.last.eq(output.last),
            streamout.first.eq(output.first),

            input.first.eq(raw_converter.source.first),
            raw_converter.source.ready.eq(input.ready),
            input.valid.eq(raw_converter.source.valid),
            input.data.eq(raw_converter.source.data),
        ]

        self.demo_ctl = CSRStorage(description="Demosaicer control regiser",
            fields=[
                CSRField("algorithm", size=3, description="Enable specified demosaicer. 0x1 - nearest, 0x2 - bilinear, 0x4 - edge", reset=int(demosiacer_type)),
                CSRField("busy", size=1, description="Light up when one of implemented algorithms work", reset=0),
                CSRField("pattern", size=2, description="Set decoding pattern", reset=pattern),
                CSRField("bgr", size=1, description="If set, output the data in BGR format, normaly RGB", reset=out_reverse),
        ])

        self.demo_im_ctl = CSRStorage(description="Demosaicer control image size regiser",
            fields=[
                CSRField("cols", size=im_w_bits, description="Set currently processing image width", reset=cols),
                CSRField("rows", size=im_h_bits, description="Set currently processing image height", reset=rows),
        ])

        last_cnt = Signal(im_w_bits)
        working  = Signal()
        cache_reset = Signal()
        self.sync += [
            If(raw_converter.source.valid & raw_converter.source.ready & working,
                last_cnt.eq(last_cnt+1),
            ),
            If((last_cnt == (self.demo_im_ctl.fields.cols-1)) & streamin.last,
                last_cnt.eq(0),
            ),
            If(raw_converter.source.first,
                If(~cache_reset,
                    last_cnt.eq(1),
                ).Else(
                    last_cnt.eq(0),
                )
            ),
        ]
        self.comb += [
            If((last_cnt == (self.demo_im_ctl.fields.cols-1)) & streamin.last,
                input.last.eq(1),
            ).Else(
                input.last.eq(0),
            ),
        ]

        self.submodules.ev = EventManager()
        self.ev.error = EventSourcePulse(description="data underflow/overflow")

        treshold = Signal(2)
        self.submodules.cache = DemosaicCache(bpp=8,
                                              mem_chunks=6,
                                              streamin=input,
                                              im_w=self.demo_im_ctl.fields.cols,
                                              im_h=self.demo_im_ctl.fields.rows,
                                              mem_treshold=treshold,
                                              u_reset=self.ev.irq)
        self.comb += [
            cache_reset.eq(self.cache.frame_sync_incorrect),
            self.ev.error.trigger.eq(self.cache.error),
        ]

        self.comb += [
            If(self.demo_ctl.fields.bgr,
                streamout.data.eq(Cat(output.data[24:32],
                                  output.data[16:24],
                                  output.data[8:16],
                                  output.data[0:8],)),
            ).Else(
                streamout.data.eq(output.data)
            ),
        ]

        self.active = Signal(3)
        self.busy = Signal()
        self.submodules.nearest = NearestNeighbour(
                self.demo_im_ctl.fields.cols,
                self.demo_im_ctl.fields.rows,
                self.demo_ctl.fields.pattern,
                output,
                enable=self.active[0],
                cache=self.cache)
        self.submodules.bilinear = Bilinear(
                self.demo_im_ctl.fields.cols,
                self.demo_im_ctl.fields.rows,
                self.demo_ctl.fields.pattern,
                output,
                enable=self.active[1],
                cache=self.cache)
        self.submodules.edge = Edge_directed(
                self.demo_im_ctl.fields.cols,
                self.demo_im_ctl.fields.rows,
                self.demo_ctl.fields.pattern,
                output,
                enable=self.active[2],
                cache=self.cache)

        self.comb += [
            self.active[0].eq(self.demo_ctl.fields.algorithm[0] & ~self.bilinear.working & ~self.edge.working | self.nearest.working),
            self.active[1].eq(self.demo_ctl.fields.algorithm[1] & ~self.nearest.working & ~self.edge.working | self.bilinear.working),
            self.active[2].eq(self.demo_ctl.fields.algorithm[2] & ~self.nearest.working & ~self.bilinear.working | self.edge.working),
            working.eq(self.nearest.working | self.bilinear.working | self.edge.working),
            self.demo_ctl.fields.busy.eq(working),
            self.busy.eq(self.demo_ctl.fields.busy),

            If(self.active[0],
                treshold.eq(0),
            ).Elif(self.active[1],
                treshold.eq(1),
            ).Else(
                treshold.eq(2),
            )
        ]
