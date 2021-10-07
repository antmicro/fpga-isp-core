========
FPGA ISP
========

Copyright (c) 2020-2021 `Antmicro <https://www.antmicro.com>`_

FPGA ISP is a collection of ISP cores dedicated for real time video processing in FPGAs.
The code is vendor independent and is intended to be used with LiteX SoC builder.

The package can be easily installed with pip::

   pip3 install git+https://github.com/antmicro/fpga-isp

The cores can be instantiated in the migen code.
Here is an example of simple instantiation of the Bilinear debayering core:

.. code-block:: python

   from fpga_isp.debayer.bilinear import *
   from fpga_isp.debayer.common import Bayer_t

   self.submodules.bilinear = Bilinear(im_w=300, im_h=300,
                                       pattern = Bayer_t.BGGR,
                                       streamout=streamout,
                                       enable=1,
                                       streamin=streamin,
                                       cache=None)

   # streamin and streamout are LiteX stream interfaces

