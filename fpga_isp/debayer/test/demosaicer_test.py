#!/usr/bin/env python3
import os
import argparse
import unittest
import copy

from migen import *
from litevideo.isp.debayer.wrapper import *
from litex.soc.interconnect.stream import *
from litex.soc.interconnect.stream_sim import *
from litevideo.csc.test.common import *
from litevideo.csc.common import *


def get_result(algorithm, pattern=Bayer_t.RGGB):
    if algorithm == Demosaic_t.NEAREST:
        if pattern == Bayer_t.RGGB:
            return [
                0x010206, 0x030206, 0x030408, 0x000408,
                0x010506, 0x030706, 0x030708, 0x000008,
                0x010206, 0x030206, 0x030408, 0x000408,
                0x010506, 0x030706, 0x030708, 0x000008,
                0x010206, 0x030206, 0x030408, 0x000408,
                0x000506, 0x000706, 0x000708, 0x000008,
            ]
        elif pattern == Bayer_t.BGGR:
            return [
                0x060201, 0x060203, 0x080403, 0x080400,
                0x060501, 0x060703, 0x080703, 0x080000,
                0x060201, 0x060203, 0x080403, 0x080400,
                0x060501, 0x060703, 0x080703, 0x080000,
                0x060201, 0x060203, 0x080403, 0x080400,
                0x060500, 0x060700, 0x080700, 0x080000,
            ]
        elif pattern == Bayer_t.RGBG:
            return [
                0x010205, 0x030207, 0x030407, 0x000400,
                0x010605, 0x030607, 0x030807, 0x000800,
                0x010205, 0x030207, 0x030407, 0x000400,
                0x010605, 0x030607, 0x030807, 0x000800,
                0x010205, 0x030207, 0x030407, 0x000400,
                0x000605, 0x000607, 0x000807, 0x000800,
            ]
        elif pattern == Bayer_t.GRGB:
            return [
                0x020106, 0x020306, 0x040308, 0x040008,
                0x020506, 0x020706, 0x040708, 0x040008,
                0x020106, 0x020306, 0x040308, 0x040008,
                0x020506, 0x020706, 0x040708, 0x040008,
                0x020106, 0x020306, 0x040308, 0x040008,
                0x000506, 0x000706, 0x000708, 0x000008,
            ]
        raise ValueError

    elif algorithm == Demosaic_t.BILINEAR:
        if pattern == Bayer_t.RGGB:
            return [
                0x010101, 0x020203, 0x030303, 0x010404,
                0x010503, 0x020406, 0x030707, 0x010308,
                0x010303, 0x020206, 0x030507, 0x010408,
                0x010503, 0x020406, 0x030707, 0x010308,
                0x010303, 0x020206, 0x030507, 0x010408,
                0x000503, 0x010306, 0x010707, 0x000208,
            ]
        elif pattern == Bayer_t.BGGR:
            return [
                0x010101, 0x030202, 0x030303, 0x040401,
                0x030501, 0x060402, 0x070703, 0x080301,
                0x030301, 0x060202, 0x070503, 0x080401,
                0x030501, 0x060402, 0x070703, 0x080301,
                0x030301, 0x060202, 0x070503, 0x080401,
                0x030500, 0x060301, 0x070701, 0x080200
            ]
        elif pattern == Bayer_t.RGBG:
            return [
                0x010002, 0x020203, 0x030303, 0x010401,
                0x010205, 0x020606, 0x030507, 0x010803,
                0x010205, 0x020206, 0x030507, 0x010403,
                0x010205, 0x020606, 0x030507, 0x010803,
                0x010205, 0x020206, 0x030507, 0x010403,
                0x000205, 0x010606, 0x010407, 0x000803,
            ]
        elif pattern == Bayer_t.GRGB:
            return [
                0x010101, 0x020203, 0x030303, 0x040204,
                0x010503, 0x020406, 0x030707, 0x040208,
                0x010103, 0x020406, 0x030307, 0x040208,
                0x010503, 0x020406, 0x030707, 0x040208,
                0x010103, 0x020406, 0x030307, 0x040208,
                0x000503, 0x010306, 0x010707, 0x020108
            ]
        raise ValueError

    elif algorithm == Demosaic_t.EDGE_DIRECTED:
        if pattern == Bayer_t.RGGB:
            return [
                0x010101, 0x020203, 0x030303, 0x060404, 0x0a0504, 0x050a05,
                0x010503, 0x020606, 0x030707, 0x070908, 0x0b0b09, 0x050b0b,
                0x010303, 0x020206, 0x030707, 0x070408, 0x0c0c0a, 0x060c0c,
                0x010503, 0x020206, 0x030707, 0x080408, 0x0d0d0a, 0x060d0d,
                0x010303, 0x020206, 0x030707, 0x080408, 0x0e0e0b, 0x070e0e,
                0x010503, 0x020206, 0x030707, 0x080408, 0x0e0f0b, 0x070e0f,
                0x010103, 0x020206, 0x030707, 0x080408, 0x0e0f0b, 0x070e0f,
                0x000503, 0x010606, 0x010707, 0x040b08, 0x070f0b, 0x03070f,
            ]
        elif pattern == Bayer_t.BGGR:
            return [
                0x010101, 0x030202, 0x030303, 0x040406, 0x04050a, 0x050a05,
                0x030501, 0x060602, 0x070703, 0x080907, 0x090b0b, 0x0b0b05,
                0x030301, 0x060202, 0x070703, 0x080407, 0x0a0c0c, 0x0c0c06,
                0x030501, 0x060202, 0x070703, 0x080408, 0x0a0d0d, 0x0d0d06,
                0x030301, 0x060202, 0x070703, 0x080408, 0x0b0e0e, 0x0e0e07,
                0x030501, 0x060202, 0x070703, 0x080408, 0x0b0f0e, 0x0f0e07,
                0x030101, 0x060202, 0x070703, 0x080408, 0x0b0f0e, 0x0f0e07,
                0x030500, 0x060601, 0x070701, 0x080b04, 0x0b0f07, 0x0f0703,
            ]
        elif pattern == Bayer_t.RGBG:
            return [
                0x010102, 0x020203, 0x030303, 0x060405, 0x0a0405, 0x050a00,
                0x010305, 0x020606, 0x030707, 0x070809, 0x0b040b, 0x050b05,
                0x010305, 0x020206, 0x030607, 0x07040a, 0x0c080c, 0x060c05,
                0x010005, 0x020606, 0x030207, 0x08080a, 0x0d040d, 0x060d06,
                0x010305, 0x020206, 0x030607, 0x08040b, 0x0e080e, 0x070e06,
                0x010005, 0x020606, 0x030207, 0x08080b, 0x0e040f, 0x070f07,
                0x010105, 0x020206, 0x030607, 0x08040b, 0x0e080f, 0x070e07,
                0x000305, 0x000606, 0x010707, 0x01080b, 0x07020f,0x070f07,
            ]
        elif pattern == Bayer_t.GRGB:
            return [
                0x010103, 0x020203, 0x030304, 0x040404, 0x070a05, 0x0a0505,
                0x010503, 0x020606, 0x030707, 0x040908, 0x080b09, 0x0b0b0b,
                0x010103, 0x020606, 0x030307, 0x040708, 0x080c0a, 0x0c0c0c,
                0x010503, 0x020106, 0x030707, 0x040308, 0x090d0a, 0x0d0d0d,
                0x010103, 0x020606, 0x030307, 0x040708, 0x090e0b, 0x0e0e0e,
                0x010503, 0x020106, 0x030707, 0x040308, 0x090f0b, 0x0e0e0f,
                0x010103, 0x020206, 0x030307, 0x040708, 0x090e0b, 0x0e0f0f,
                0x000503, 0x010606, 0x010707, 0x020b08, 0x020f0b, 0x07070f
            ]
        raise ValueError

def get_img_description(algorithm):
    if algorithm == Demosaic_t.NEAREST:
        return {
            "name"    : "dummy",
            "width"   : 4,
            "height"  : 6,
            "pattern" : Bayer_t.RGGB,
            "data"    : []
        }
    elif algorithm == Demosaic_t.BILINEAR:
        return {
            "name"    : "dummy",
            "width"   : 4,
            "height"  : 6,
            "pattern" : Bayer_t.RGGB,
            "data"    : []
        }
    elif algorithm == Demosaic_t.EDGE_DIRECTED:
        return {
            "name"    : "dummy",
            "width"   : 6,
            "height"  : 8,
            "pattern" : Bayer_t.RGGB,
            "data"    : []
        }

def get_img_data(algorithm):
    if algorithm == Demosaic_t.NEAREST:
        return [
            0x01020304,
            0x05060708,
            0x01020304,
            0x05060708,
            0x01020304,
            0x05060708
        ]
    elif algorithm == Demosaic_t.BILINEAR:
        return [
            0x01020304,
            0x05060708,
            0x01020304,
            0x05060708,
            0x01020304,
            0x05060708
        ]
    elif algorithm == Demosaic_t.EDGE_DIRECTED:
        return [
            0x01020304,
            0x0a0a0506,
            0x07080b0b,
            0x01020304,
            0x0c0c0506,
            0x07080d0d,
            0x01020304,
            0x0e0e0506,
            0x07080f0f,
            0x01020304,
            0x0e0e0506,
            0x07080f0f
        ]
def load_image():
    with open("im.gray", "rb") as f:
        im = f.read()
        im_c = []
        val=0
        i=0
        axi_w=0x4
        for p in im:
            val |= (p<<(8*(axi_w-i-1)))
            i+=1
            if i == axi_w:
                im_c.append(val)
                i=0
                val=0
        return im_c


class TB(Module):
    bayer_raw_layout = [("data",   32)]
    bayer_rgb_layout = [("data",   32)]
    AXI_W=4
    def __init__(self, im, algorithm):
        # create image streams
        self.raw = raw = stream.Endpoint(self.bayer_raw_layout) # input raw bayer image
        self.rgb = rgb = stream.Endpoint(self.bayer_rgb_layout) # outpur processed rgb image
        self.wrapper = DemosaicWrapper(algorithm,
                                       raw,
                                       rgb,
                                       im["width"],
                                       im["height"],
                                       im["pattern"],
                                       in_reverse=True,
                                       out_reverse=False)
        self.error_occured=0
    def set_algorithm(self, algorithm):
        return self.wrapper.demo_ctl.fields.algorithm.eq(algorithm)

    def enable_irq(self):
        return self.wrapper.ev.enable.write(1)
    
    def disable_irq(self):
        return self.wrapper.ev.enable.write(1)
    
    def read_irq(self):
        return self.wrapper.ev.irq

    def clear_err(self):
        return self.wrapper.ev.pending.write(1)
    
    def set_im_w(self, cols):
        return self.wrapper.demo_im_ctl.fields.cols.eq(cols)

    def set_im_h(self, rows):
        return self.wrapper.demo_im_ctl.fields.rows.eq(rows)

    def set_pattern(self, pattern):
        return self.wrapper.demo_ctl.fields.pattern.eq(pattern)

    def get_algorithm(self):
        return (self.wrapper.demo_ctl.fields.algorithm)

    def get_busy(self):
        return (self.wrapper.demo_ctl.fields.busy)

def main_generator(dut, ims, algorithm, image=False, irqs=[]):
    if irqs == []:
       irqs = [0 for _ in range(len(ims))]
       breaked = False
    for c, pack in enumerate(zip(ims, irqs)):
        im = pack[0]
        irq = pack[1]
        im["data"] = get_img_data(algorithm) if not image else load_image()
        yield dut.raw.last.eq(~irq)
        if irq:
            yield from dut.enable_irq()
        else:
            yield from dut.disable_irq()
        while (yield dut.get_busy()) and not breaked:
            yield
        breaked = False
        yield dut.set_pattern(im["pattern"])
        size = im["width"]*im["height"]/4
        i = 0
        while i < size:
            val = im["data"][i]
            yield dut.raw.data.eq(val)
            yield dut.raw.valid.eq(1)
            if i == 0:
                yield dut.raw.first.eq(1)
            yield
            yield dut.raw.first.eq(0)
            # wait untill the line is being processed
            while (yield dut.raw.ready == 0):
                yield
            if irq:
                if (yield dut.read_irq()):
                    dut.error_occured = 1
                    breaked = True
                    yield dut.raw.valid.eq(0)
                    yield from dut.clear_err()
                    break
            i+=1

        yield dut.raw.valid.eq(0)
        yield dut.raw.last.eq(0)
        yield
        while dut.error_occured != 0:
            yield;
        print("Gnerator DONE {}/{}".format(c+1, len(ims)))


def rec_save(dut, to_rec, rec_times=1):
    data = []
    yield dut.rgb.ready.eq(1)
    yield
    for c in range(rec_times):
        for i in range(int(to_rec)):
            while(yield dut.rgb.valid == 0):
                yield
            data.append((yield dut.rgb.data))
            yield

        with open("deb{}.rgb".format(c), "wb") as f:
            for d in data:
                r = (d & 0xff0000) >>16
                g = (d & 0x00ff00) >>8
                b = (d & 0x0000ff)
                payload = bytearray([r,g,b])
                f.write(payload)
        data = []
        print("Receiver DONE {}/{}".format(c+1, rec_times))

def rec_compare(dut, to_rec, algorithm, ims, rec_times=1):
    chunks = []
    data = []
    yield dut.rgb.ready.eq(1)
    for c in range(rec_times):
        for i in range(int(to_rec)):
            while(yield dut.rgb.valid == 0):
                yield
            data.append((yield dut.rgb.data))
            yield
        chunks.append(data)
        data = []
        print("Receiver DONE {}/{}".format(c+1, rec_times))
        #each chunk has to be same
        for chunk, im in zip(chunks, ims):
            good_res = get_result(algorithm, im["pattern"])
            if good_res != chunk:
                print("Chunks differ")
                for i in range(len(good_res)):
                    print(hex(good_res[i])," -- ", hex(chunk[i]))
                    if (i+1)%4 == 0:
                        print("\n")
                exit(1)

def rec_compare_irq(dut, to_rec, algorithm, ims, irqs):
    chunks = []
    data = []
    for c in range(len(irqs)):
        yield dut.rgb.ready.eq(1)
        for i in range(int(to_rec)):
            while(yield dut.rgb.valid == 0) and not dut.error_occured:
                yield
            data.append((yield dut.rgb.data))
            yield
            if dut.error_occured:
                dut.error_occured=0
                data=[]
                yield dut.rgb.ready.eq(0)
                yield from dut.clear_err()
                break
        chunks.append(data)
        data = []

        print("Receiver DONE {}/{}".format(c+1, len(irqs)))
        #each chunk has to be same
        for chunk, im, irq in zip(chunks, ims, irqs):
            good_res = get_result(algorithm, im["pattern"])
            if irq != 1:
                if good_res != chunk:
                    print("Chunks differ")
                    for i in range(len(good_res)):
                        print(hex(good_res[i])," -- ", hex(chunk[i]))
                        if (i+1)%4 == 0:
                            print("\n")
                    exit(1)
            else:
                if good_res == chunk:
                    print("chunks shoud differ")
                    for i in range(len(good_res)):
                        print(hex(good_res[i])," -- ", hex(chunk[i]))
                        if (i+1)%4 == 0:
                            print("\n")
                    exit(1)

def generator_shuffle(dut, algs):
    for n, algorithm in enumerate(algs):
        i = 0
        already_shuffled = False
        im = get_img_description(algorithm)
        im["data"] = get_img_data(algorithm)
        size = len(im["data"])
        yield dut.raw.last.eq(0)
        while (yield dut.get_busy()):
            yield
        yield dut.set_im_w(im["width"])
        yield dut.set_im_h(im["height"])

        while i < size:
            val = im["data"][i]
            yield dut.raw.data.eq(val)
            yield dut.raw.valid.eq(1)
            if i == 0:
                yield dut.raw.first.eq(1)
            yield
            yield dut.raw.first.eq(0)
            # wait untill the line is being processed
            while (yield dut.raw.ready == 0):
                yield
            i+=1
            if not already_shuffled:
                already_shuffled = True
                yield dut.set_algorithm(algs[(n+1)%len(algs)])

        yield dut.raw.valid.eq(0)
        yield dut.raw.last.eq(0)
        yield
        print("Gnerator DONE {}/{}".format(n+1, len(algs)))

def rec_shuffle(dut, algs):
    data = []
    yield dut.rgb.ready.eq(1)
    for n, algorithm in enumerate(algs):
        im = get_img_description(algorithm)
        to_rec = im["width"]*im["height"]

        for i in range(int(to_rec)):
            while(yield dut.rgb.valid == 0):
                yield
            data.append((yield dut.rgb.data))
            yield
        print("Receiver DONE {}/{}".format(n+1, len(algs)))

        #each chunk has to be same
        good_res = get_result(algorithm)
        if good_res != data:
            print("Chunks differ")
            exit(1)
        data = []


def generator_with_im_break(dut, ims, algorithm, image=False, bim=[]):
    if bim == []:
       bim = [-1 for _ in range(len(ims))]
       breaked = False
    for c, pack in enumerate(zip(ims, bim)):
        im = pack[0]
        b = pack[1]
        im["data"] = get_img_data(algorithm) if not image else load_image()
        yield dut.raw.last.eq(1)
        while (yield dut.get_busy()) and not breaked:
            yield
        breaked = False
        yield dut.set_pattern(im["pattern"])
        size = im["width"]*im["height"]/4
        i = 0
        while i < size:
            val = im["data"][i]
            yield dut.raw.data.eq(val)
            yield dut.raw.valid.eq(1)
            if i == 0:
                yield dut.raw.first.eq(1)
            yield
            yield dut.raw.first.eq(0)
            # wait untill the line is being processed
            while (yield dut.raw.ready == 0):
                yield
            if b != -1 and i == b:
                dut.error_occured = 1
                breaked = True
                break
            i+=1

        yield dut.raw.valid.eq(0)
        yield dut.raw.last.eq(0)
        yield
        while dut.error_occured != 0:
            yield;
        print("Gnerator DONE {}/{}".format(c+1, len(ims)))

def rec_compare_im_b(dut, to_rec, algorithm, ims, bim):
    chunks = []
    data = []
    for c in range(len(bim)):
        yield dut.rgb.ready.eq(1)
        for i in range(int(to_rec)):
            while (yield dut.rgb.valid == 0) and not dut.error_occured:
                yield
            data.append((yield dut.rgb.data))
            yield
            if dut.error_occured:
                dut.error_occured=0
                data=[]
                while not (yield dut.rgb.first) or (yield dut.raw.first):
                    yield
                yield dut.rgb.ready.eq(0)
                break
        chunks.append(data)
        data = []
        print("Receiver DONE {}/{}".format(c+1, len(bim)))
        #each chunk has to be same
        for chunk, im, bp in zip(chunks, ims, bim):
            good_res = get_result(algorithm, im["pattern"])
            if bp == im["height"]*im["width"]/TB.AXI_W:
                if good_res != chunk:
                    print("Chunks differ")
                    if len(good_res) != len(chunk):
                        print("Chunk size differ")
                    for i in range(min(len(good_res), len(chunk))):
                        print(hex(good_res[i])," -- ", hex(chunk[i]))
                        if (i+1)%4 == 0:
                            print("\n")
                    exit(1)
            else:
                if good_res == chunk:
                    print("chunks shoud differ")
                    for i in range(min(len(good_res), len(chunk))):
                        print(hex(good_res[i])," -- ", hex(chunk[i]))
                        if (i+1)%4 == 0:
                            print("\n")
                    exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LiteX SoC on Zybo Z7")
    parser.add_argument("--algorithm", help="one of Nearest, Bilinear, Edge")
    parser.add_argument("--shuffle", action="store_true", help="test force algorihtm switch")
    parser.add_argument("--test_patterns", action="store_true", help="test all algorithms with avaliable patterns")
    parser.add_argument("--image", action="store_true", help="debayer real image")
    parser.add_argument("--irqs", action="store_true", help="debayer with irq enabled, simulate error")
    parser.add_argument("--imb", action="store_true", help="test unexpected image height")
    args = parser.parse_args()
    algorithm = None

    if args.algorithm and not args.shuffle:
        if args.algorithm == "Nearest":
            algorithm=Demosaic_t.NEAREST
        elif args.algorithm == "Bilinear":
            algorithm=Demosaic_t.BILINEAR
        elif args.algorithm == "Edge":
            algorithm=Demosaic_t.EDGE_DIRECTED
        else:
            raise ValueError

    tb = None
    generators = []
    if args.image:
        im = {
            "name"    : "im.gray",
            "width"   : 600,
            "height"  : 398,
            "pattern" : Bayer_t.RGGB,
            "data"    : []
        }
        tb = TB(im, algorithm)
        ims = [im]
        generators = [
            main_generator(tb, ims, algorithm, image=True),
            rec_save(tb, im["width"]*im["height"], len(ims))
        ]
    elif args.shuffle:
        algs = [Demosaic_t.NEAREST,
                Demosaic_t.EDGE_DIRECTED,
                Demosaic_t.BILINEAR,
                Demosaic_t.NEAREST,
                Demosaic_t.EDGE_DIRECTED]
        algorithm = algs[0]
        im = get_img_description(algorithm)
        tb = TB(im, algorithm)
        generators = [
            generator_shuffle(tb, algs),
            rec_shuffle(tb, algs)
        ]
    elif args.test_patterns and args.algorithm:
        rggb = get_img_description(algorithm)
        bggr = copy.deepcopy(rggb)
        bggr["pattern"] = Bayer_t.BGGR
        rgbg = copy.deepcopy(rggb)
        rgbg["pattern"] = Bayer_t.RGBG
        grgb = copy.deepcopy(rggb)
        grgb["pattern"] = Bayer_t.GRGB
        tb = TB(rggb, algorithm)
        ims = [rggb, bggr, rgbg, grgb]
        generators = [
            main_generator(tb, ims, algorithm),
            rec_compare(tb, rggb["width"]*rggb["height"], algorithm, ims, len(ims))
        ]
    elif args.irqs and args.algorithm:
        im = get_img_description(algorithm)
        tb = TB(im, algorithm)
        irqs = [  1,  0,  0,  1,  0, 1, 0, 1, 1, 1, 0, 0, 0]
        ims  = [ im, im, im, im, im, im, im, im, im, im, im, im ,im]
        generators = [
            main_generator(tb, ims, algorithm, irqs=irqs),
            rec_compare_irq(tb, im["width"]*im["height"], algorithm, ims, irqs)
        ]
    elif args.imb and args.algorithm:
        im = get_img_description(algorithm)
        tb = TB(im, algorithm)
        break_im_line= [4, im["height"]*im["width"]/TB.AXI_W, 2, im["height"]*im["width"]/TB.AXI_W]
        ims  = [im, im, im, im]
        generators = [
            generator_with_im_break(tb, ims, algorithm, bim=break_im_line),
            rec_compare_im_b(tb, im["width"]*im["height"], algorithm, ims, break_im_line)
        ]
    else:
        im = get_img_description(algorithm)
        tb = TB(im, algorithm)
        ims = [im, im]
        generators = [
            main_generator(tb, ims, algorithm),
            rec_compare(tb, im["width"]*im["height"], algorithm, ims, len(ims))
        ]

    run_simulation(tb.wrapper, generators, vcd_name="sim.vcd")
