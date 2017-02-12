#!/usr/bin/env python
#
# Decode the pulse/space output of `mode2` into bits and bytes
#
# Usage:
#    mode2 -d /dev/lirc0 | irdecode.py


# timings are currently somewhat hardcoded here.

from __future__ import print_function

import logging
import select
import sys

# the min and max dirations of the pulse and space parts of the header
MIN_HEADER_PULSE_WIDTH=4400
MAX_HEADER_PULSE_WIDTH=4800
MIN_HEADER_SPACE_WIDTH=MIN_HEADER_PULSE_WIDTH
MAX_HEADER_SPACE_WIDTH=MAX_HEADER_PULSE_WIDTH

# the min and max durations of the pulse part of a one, zero, or trailer
MIN_PULSE_WIDTH=400
MAX_PULSE_WIDTH=750

# the min and max durations of the space part of a zero
MIN_ZERO_SPACE_WIDTH=350
MAX_ZERO_SPACE_WIDTH=750

# the min and max durations of the space part of a one
MIN_ONE_SPACE_WIDTH=1500
MAX_ONE_SPACE_WIDTH=1820



def read(f):
    pulse_width = None

    logger = logging.getLogger("reader")

    pulseDecoder = PulseDecoder()

    while True:
        r, w, e = select.select([f], [], [f], 0.1)

        if f in e:
            return

        if f not in r:
            # timeout
            if pulse_width:
                pulseDecoder.pulse(pulse_width, None)
                pulse_width = None
            continue

        line = f.readline().strip()
        if line is None:
            return

        try:
            (t, d) = line.split(" ", 1)
            d = int(d)
        except:
            logger.warn("Cannot parse %s", line)
            continue

        if t == "pulse":
            pulse_width = d
            space_width = 0
            continue

        if t != "space":
            logger.error("Cannot parse %s (%s)", line, t)
            continue

        space_width = d

        if pulse_width is None:
            logger.info("gap %s us", space_width)
            continue

        pulseDecoder.pulse(pulse_width, space_width)
        pulse_width = None


class PulseDecoder:
    def __init__(self):
        self.logger = logging.getLogger("PulseDecoder")
        self.bitDecoder = BitDecoder()

    def pulse(self, pulse_width, space_width):
        if (pulse_width > MIN_PULSE_WIDTH and
            pulse_width < MAX_PULSE_WIDTH and
            (space_width is None or space_width > 10000)):
            self.logger.info("gap %s us", space_width)
            self.bitDecoder.gap()
            return

        if (pulse_width > MIN_HEADER_PULSE_WIDTH and
            pulse_width < MAX_HEADER_PULSE_WIDTH and
            space_width > MIN_HEADER_SPACE_WIDTH and
            space_width < MAX_HEADER_SPACE_WIDTH):
            self.logger.debug("header")
            return

        if (pulse_width > MIN_PULSE_WIDTH and
            pulse_width < MAX_PULSE_WIDTH and
            space_width > MIN_ONE_SPACE_WIDTH and
            space_width < MAX_ONE_SPACE_WIDTH):
            self.logger.debug("one")
            self.bitDecoder.bit(1)
            return

        if (pulse_width > MIN_PULSE_WIDTH and
            pulse_width < MAX_PULSE_WIDTH and
            space_width > MIN_ZERO_SPACE_WIDTH and
            space_width < MAX_ZERO_SPACE_WIDTH):
            self.logger.debug("zero")
            self.bitDecoder.bit(0)
            return


        self.logger.warn("Unknown %d %d", pulse_width, space_width)


class BitDecoder:
    def __init__(self):
        self._reset()
        self.logger = logging.getLogger("bitdecoder")
        self.byte_buffer = ""

    def _reset(self):
        self.bit_count = 0
        self.bit_buffer = 0

    def bit(self, val):
        self.bit_buffer = (self.bit_buffer << 1) | (val & 0x1)
        self.bit_count += 1
        if self.bit_count >= 8:
            self.logger.debug("Byte: %02x", self.bit_buffer)
            self.byte_buffer += "%02x" % self.bit_buffer
            self._reset()

    def gap(self):
        if self.bit_count != 0:
            self.logger.warn("Discarding %i bits", self.bit_count)
        self.logger.info("Read: %s" % self.byte_buffer)
        self._reset()
        self.byte_buffer=""


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    #logging.getLogger("reader").setLevel(logging.WARN)
    #logging.getLogger("PulseDecoder").setLevel(logging.DEBUG)
    read(sys.stdin)
