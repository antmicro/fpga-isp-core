from migen import *
import math

from litex.soc.interconnect.csr import *
from litex.soc.interconnect import stream

class MemoryBank(Module):
    def __init__(self, slots, width, depth):
        # Memory
        mems  = [None]*slots
        ports = [None]*slots
        for i in range(slots):
            mems[i] = Memory(width, depth)
            ports[i] = mems[i].get_port(write_capable=True, async_read=True)
            self.specials += ports[i], mems[i]
        self.mem_size = slots*width*(depth/8)
        self.mems = mems
        self.ports = ports

class DemosaicCache(Module):
    def __init__(self, bpp, mem_chunks, streamin, im_w, im_h, mem_treshold, u_reset=Signal(), enable=None):
        assert(mem_chunks>2 and mem_chunks%2 ==0)
        self.bpp = bpp
        self.mem_chunks = mem_chunks

        self.raw_ready = Signal(reset=1)
        self.raw_valid = Signal(reset=0)
        self.raw_last = Signal(reset=0)
        self.raw_first = Signal(reset=0)
        self.raw_data = Signal(len(streamin.data))

        self.submodules.mem_bank = MemoryBank(slots=self.mem_chunks, width=self.bpp, depth=2**len(im_w))
        self.adrs = [Signal(len(im_w)+1) for _ in range(self.mem_chunks)]
        self.r_data = [Signal(self.bpp) for _ in range(self.mem_chunks)]
        self.current_chunk = Signal(int(math.log(self.mem_chunks,2))+1)
        self.collected_lines = Signal(len(im_h)+1, reset=0)
        self.processed_lines = Signal(len(im_h)+1, reset=0)
        self.memory_reset = Signal(1, reset=0)
        self.push_zeros = Signal(1, reset=0)
        self.force_reset = Signal()
        self.hold_reset = Signal()
        # vars to check if line has underflow or overflow
        self.columns_caputred = Signal(len(im_w)+1, reset=0)
        self.underflow = Signal()
        self.overflow = Signal()
        self.error = Signal()
        self.frame_sync_incorrect = Signal()
        self.comb += [self.error.eq((self.overflow | self.underflow))]

        if enable is None:
            self.comb += [
               #connect raw signals with local signals
               streamin.ready.eq(self.raw_ready),
               self.raw_valid.eq(streamin.valid),
               self.raw_last.eq(streamin.last),
               self.raw_first.eq(streamin.first),
               self.raw_data.eq(streamin.data),
            ]
        else:
            self.comb += [
                #connect raw signals with local signals
                If(enable,
                    streamin.ready.eq(self.raw_ready),
                    self.raw_valid.eq(streamin.valid),
                    self.raw_last.eq(streamin.last),
                    self.raw_first.eq(streamin.first),
                    self.raw_data.eq(streamin.data),
                )
            ]
        self.f_reset = Signal()
        self.wait_for_reset = Signal()
        self.sync += [
            If(u_reset | self.wait_for_reset,
                self.wait_for_reset.eq(1),
            ),
            If(self.wait_for_reset & ~u_reset,
                self.wait_for_reset.eq(0),
                self.f_reset.eq(1),
            ),
            If((self.wait_for_reset & ~u_reset) | self.raw_first,
                [self.adrs[i].eq(0) for i in range(self.mem_chunks)],
                self.processed_lines.eq(0),
                self.current_chunk.eq(0),
                self.collected_lines.eq(0),
                self.wait_for_reset.eq(0),
            ),
        ]
        self.ch_nrdy = Signal()
        self.adr_nrdy = Signal()
        self.comb += [
            self.ch_nrdy.eq(self.current_chunk != 0),
            self.adr_nrdy.eq(self.adrs[0] > 0),
            self.frame_sync_incorrect.eq((self.raw_first & self.ch_nrdy)
                                        | (self.raw_first & self.adr_nrdy))
        ]

        self.comb += [
            self.force_reset.eq(self.hold_reset | self.raw_first | self.f_reset),
            self.memory_reset.eq(self.force_reset),
        ]

        self.comb += [
            If(self.raw_last,
                If(self.columns_caputred > (im_w-1),
                    self.overflow.eq(1),
                ).Elif(self.columns_caputred < (im_w-1),
                    self.underflow.eq(1),
                ).Else(
                    self.underflow.eq(0),
                    self.overflow.eq(0),
                )
            ).Elif(self.columns_caputred >= (im_w),
                self.overflow.eq(1),
            ).Else(
                self.underflow.eq(0),
                self.overflow.eq(0),
            )
        ]

        self.sync += [
            If(self.raw_valid & self.raw_ready,
                If(~self.raw_last & ~u_reset,
                    self.columns_caputred.eq(self.columns_caputred +1),
                ).Else(
                    self.columns_caputred.eq(0),
                )
            ).Elif((self.columns_caputred > im_w) | self.frame_sync_incorrect,
                self.columns_caputred.eq(0),
            )
        ]

        # fill ememory with zeros
        self.comb += [
            If(self.collected_lines - self.processed_lines < self.mem_chunks-mem_treshold,
               self.raw_ready.eq(~self.push_zeros & ~self.f_reset & ~self.frame_sync_incorrect),
            ).Else(
               self.raw_ready.eq(0),
            )
        ]
        # fill last few lines with zeros
        # this in neccessary to correctly decode last few lines
        # depends on the decoded kernel size
        self.comb += [
           self.push_zeros.eq((self.collected_lines >= im_h) 
               & (self.collected_lines <= (im_h+mem_treshold))),
        ]

        #reset all cache line except the first one
        for i in range(1, len(self.mem_bank.ports)):
            self.sync += [
                If(self.memory_reset,
                    self.hold_reset.eq(1), 
                    If(~self.frame_sync_incorrect,
                        If((self.adrs[i] < im_w-1) ,
                            self.adrs[i].eq(self.adrs[i]+1),
                        ).Elif(self.adrs[i] == im_w-1,
                            self.f_reset.eq(0), 
                            self.hold_reset.eq(0), 
                            self.adrs[i].eq(0),
                        )
                    )
                )
            ]
            self.comb += [
                If(self.memory_reset,
                    self.mem_bank.ports[i].we.eq(1),
                )
            ]

        for i in range(len(self.mem_bank.ports)):
            self.comb += [
                self.mem_bank.ports[i].adr.eq(self.adrs[i]),
                self.r_data[i].eq(self.mem_bank.ports[i].dat_r),
            ]

        #receive data from stream
        cases = {}
        for i in range(len(self.mem_bank.ports)):
            cases[i] = [
                If(self.push_zeros,
                    self.mem_bank.ports[i].dat_w.eq(0),
                ).Elif(~self.memory_reset,
                    self.mem_bank.ports[i].dat_w.eq(self.raw_data),
                ).Else(
                    self.mem_bank.ports[0].dat_w.eq(self.raw_data),
                    [self.mem_bank.ports[i].dat_w.eq(0)] if i != 0 else [],
                ),
                If(self.collected_lines - self.processed_lines < self.mem_chunks-mem_treshold,
                   If((self.raw_valid | self.push_zeros) & ~self.f_reset,
                       If(self.adrs[i] < im_w,
                          self.mem_bank.ports[i].we.eq(1),
                       ).Else(
                          self.mem_bank.ports[(i+1)%self.mem_chunks].we.eq(1),
                       )
                   ).Else(
                       self.mem_bank.ports[i].we.eq(0),
                   )
                ).Else(
                   self.mem_bank.ports[i].we.eq(0),
                )
            ]
        self.comb += Case(self.current_chunk, cases)

        cases = {}
        for i in range(self.mem_chunks):
            cases[i] = [
                If(self.collected_lines - self.processed_lines < self.mem_chunks-mem_treshold,
                    If((self.raw_valid | self.push_zeros) & ~self.f_reset & ~self.frame_sync_incorrect,
                        If(self.adrs[i] < im_w-1,
                           self.adrs[i].eq(self.adrs[i]+1),
                        ).Elif((self.current_chunk < self.mem_chunks-1),
                            self.adrs[i].eq(0), # set addr to 0, cause FSM requires it
                            self.current_chunk.eq(self.current_chunk+1),
                            self.collected_lines.eq(self.collected_lines+1),
                        ).Else(
                            self.collected_lines.eq(self.collected_lines+1),
                            self.adrs[i].eq(0),
                            self.current_chunk.eq(0),
                        ),
                    ).Elif(self.f_reset,
                        self.adrs[i].eq(0), # set addr to 0, cause FSM requires it
                    )
                )
            ]
        self.sync += Case(self.current_chunk, cases)
