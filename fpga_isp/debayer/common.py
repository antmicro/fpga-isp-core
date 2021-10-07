from migen import *
from enum import Enum, IntEnum

class Bayer_t(IntEnum):
    RGGB = 0
    BGGR = 1
    GRGB = 2
    RGBG = 3

class Demosaic_t(IntEnum):
    RESET = 0
    NEAREST = 1
    BILINEAR = 2
    EDGE_DIRECTED = 4

class Bayer_kernel:
    def __init__(self, bpp, width, height):
        self.bpp = bpp
        self.colors = Array(Signal(bpp*width) for _ in range(height))

    def row(self, row):
        return self.colors[row]

    def cell(self, row, col):
        idx = self.bpp*col
        return self.colors[row][idx:idx+self.bpp]
