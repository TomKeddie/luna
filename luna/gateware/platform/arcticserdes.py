#
# This file is part of LUNA.
#
# Copyright (c) 2020 Great Scott Gadgets <info@greatscottgadgets.com>
# SPDX-License-Identifier: BSD-3-Clause

""" Arctic Serdes (artix7.tomk.in) board platform definitions.

This is a non-core platform. To use it, you'll need to set your LUNA_PLATFORM variable:

    > export LUNA_PLATFORM="luna.gateware.platform.arcticserdes:ArcticSerdes35Platform"
"""

import os
import subprocess

from nmigen import *
from nmigen.build import *
from nmigen.vendor.xilinx_7series import Xilinx7SeriesPlatform
from nmigen_boards.resources import *

from .core import LUNAPlatform


class ArcticSerdesClockDomainGenerator(Elaboratable):
    """ Clock/Reset Controller for the Arctic Serdes. """

    def __init__(self, *, clock_frequencies=None, clock_signal_name=None):
        pass

    def elaborate(self, platform):
        m = Module()

        # Create our domains; but don't do anything else for them, for now.
        m.domains.usb     = ClockDomain()
        m.domains.usb_io  = ClockDomain()
        m.domains.sync    = ClockDomain()
        m.domains.ss      = ClockDomain()
        m.domains.fast    = ClockDomain()

        # Grab our main clock.
        clk50 = platform.request(platform.default_clk)

        # USB2 PLL connections.
        clk12         = Signal()
        clk48         = Signal()
        usb2_locked   = Signal()
        usb2_feedback = Signal()
        m.submodules.usb2_pll = Instance("PLLE2_ADV",
            p_BANDWIDTH            = "OPTIMIZED",
            p_COMPENSATION         = "ZHOLD",
            p_STARTUP_WAIT         = "FALSE",
            p_DIVCLK_DIVIDE        = 1,
            p_CLKFBOUT_MULT        = 24,
            p_CLKFBOUT_PHASE       = 0.000,
            p_CLKOUT0_DIVIDE       = 100,
            p_CLKOUT0_PHASE        = 0.000,
            p_CLKOUT0_DUTY_CYCLE   = 0.500,
            p_CLKOUT1_DIVIDE       = 25,
            p_CLKOUT1_PHASE        = 0.000,
            p_CLKOUT1_DUTY_CYCLE   = 0.500,
            p_CLKIN1_PERIOD        = 20.000,
            i_CLKFBIN              = usb2_feedback,
            o_CLKFBOUT             = usb2_feedback,
            i_CLKIN1               = clk50,
            o_CLKOUT0              = clk12,
            o_CLKOUT1              = clk48,
            o_LOCKED               = usb2_locked,
        )


        # USB3 PLL connections.
        clk16         = Signal()
        clk125        = Signal()
        clk250        = Signal()
        usb3_locked   = Signal()
        usb3_feedback = Signal()
        m.submodules.usb3_pll = Instance("PLLE2_ADV",
            p_BANDWIDTH            = "OPTIMIZED",
            p_COMPENSATION         = "ZHOLD",
            p_STARTUP_WAIT         = "FALSE",
            p_DIVCLK_DIVIDE        = 1,
            p_CLKFBOUT_MULT        = 20,    # VCO = 1000 MHz
            p_CLKFBOUT_PHASE       = 0.000,
            p_CLKOUT0_DIVIDE       = 4,     # CLKOUT0 = 250 MHz (1000/4)
            p_CLKOUT0_PHASE        = 0.000,
            p_CLKOUT0_DUTY_CYCLE   = 0.500,
            p_CLKOUT1_DIVIDE       = 8,     # CLKOUT1 = 125 MHz (1000/8)
            p_CLKOUT1_PHASE        = 0.000,
            p_CLKOUT1_DUTY_CYCLE   = 0.500,
            p_CLKOUT2_DIVIDE       = 64,    # CLKOUT2 = 16 MHz  (1000/64)
            p_CLKOUT2_PHASE        = 0.000,
            p_CLKOUT2_DUTY_CYCLE   = 0.500,
            p_CLKIN1_PERIOD        = 20.000,
            i_CLKFBIN              = usb3_feedback,
            o_CLKFBOUT             = usb3_feedback,
            i_CLKIN1               = clk50,
            o_CLKOUT0              = clk250,
            o_CLKOUT1              = clk125,
            o_CLKOUT2              = clk16,
            o_LOCKED               = usb3_locked,
        )

        # Connect up our clock domains.
        m.d.comb += [
            ClockSignal("usb")      .eq(clk12),
            ClockSignal("usb_io")   .eq(clk48),
            ClockSignal("sync")     .eq(clk125),
            ClockSignal("ss")       .eq(clk125),
            ClockSignal("fast")     .eq(clk250),

            ResetSignal("usb")      .eq(~usb2_locked),
            ResetSignal("usb_io")   .eq(~usb2_locked),
            ResetSignal("sync")     .eq(~usb3_locked),
            ResetSignal("ss")       .eq(~usb3_locked),
            ResetSignal("fast")     .eq(~usb3_locked),
        ]

        return m


class ArcticSerdes35Platform(Xilinx7SeriesPlatform, LUNAPlatform):
    """ Board description for ArcticSerdes board. """

    name        = "ArcticSerdes"

    device      = "xc7a35t"
    package     = "fgg484"
    speed       = "3"

    default_clk = "clkin"

    clock_domain_generator = ArcticSerdesClockDomainGenerator

    default_usb_connection = "usb_micro"

    #
    # I/O resources.
    #
    resources   = [
        Resource("clkin", 0, DiffPairs("Y18", "Y19", dir="i"),
                 Clock(50e6),
                 Attrs(IOStandard="LVDS_25"),
        ),
        RGBLEDResource(0, r="P15", g="P16", b="P14", invert=True, attrs=Attrs(IOStandard="LVCMOS33")),
        DirectUSBResource("usb_micro", 0, d_p="V18", d_n="V19", pullup="U18", attrs=Attrs(IOStandard="LVCMOS33")),
        UARTResource(0,
            rx="W19", tx="V17",
            attrs=Attrs(IOSTANDARD="LVCMOS33")
        ),
        UARTResource(1,
            rx="W20", tx="W17",
            attrs=Attrs(IOSTANDARD="LVCMOS33")
        ),
    ]

    connectors = []


    def toolchain_prepare(self, fragment, name, **kwargs):
        overrides = {
            "script_before_bitstream":
                "set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]",
            "script_after_bitstream":
                "write_cfgmem -force -format bin -interface spix4 -size 16 "
                "-loadbit \"up 0x0 {name}.bit\" -file {name}.bin".format(name=name),
            "add_constraints": """
                set_clock_groups -asynchronous -group [get_clocks -of_objects [get_pins -regexp .*/usb3_pll/CLKOUT0]] -group [get_clocks -of_objects [get_pins -regexp .*/usb3_pll/CLKOUT1]] -group [get_clocks -of_objects [get_pins -regexp .*/usb3_pll/CLKOUT2]]
                set_clock_groups -asynchronous -group [get_clocks -of_objects [get_pins -regexp .*/usb2_pll/CLKOUT0]] -group [get_clocks -of_objects [get_pins -regexp .*/usb2_pll/CLKOUT1]]
                
        """} 
        return super().toolchain_prepare(fragment, name, **overrides, **kwargs)

    def toolchain_program(self, products, name):
        xc3sprog = os.environ.get("XC3SPROG", "xc3sprog")
        with products.extract("{}.bit".format(name)) as bitstream_filename:
            subprocess.run([xc3sprog, "-c", "xpc", bitstream_filename], check=True)
