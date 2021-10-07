from migen import *
import math

from litex.soc.interconnect.csr import *
from litex.soc.interconnect import stream

class DemosaicBase(Module):
    def first_pix(self):
        return [If(self.first_pixel,
                NextValue(self.rgb_first,1),
                NextValue(self.first_pixel,0),
            ).Else(
                NextValue(self.rgb_first,0),
            )]

    def __init__(self, cache, im_w, im_h, min_lines_req, streamout, active):

        self.rgb_ready = Signal(reset=0)
        self.rgb_valid = Signal(reset=0)
        self.rgb_first = Signal(reset=0)
        self.rgb_last = Signal(reset=0)
        self.rgb_data = Signal(len(streamout.data))
        self.min_lines_required = min_lines_req
        self.working = Signal(reset=0)
        self.first_pixel = Signal(reset=1)

        self.comb += [
           If(active,
               #connect rgb stream with local signals
               self.rgb_ready.eq(streamout.ready),
               streamout.valid.eq(self.rgb_valid),
               streamout.last.eq(self.rgb_last),
               streamout.first.eq(self.rgb_first),
               streamout.data.eq(self.rgb_data),
            )
        ]
