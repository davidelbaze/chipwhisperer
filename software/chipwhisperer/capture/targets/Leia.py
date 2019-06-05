#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# =================================================
import logging

from ._leia import *

import binascii
from ._base import TargetTemplate
from .simpleserial_readers.cwlite import SimpleSerial_ChipWhispererLite
from chipwhisperer.common.utils import util

import time

class LeiaTarget(TargetTemplate, util.DisableNewAttr, Leia):
    _name = "Leia"
    ser_timeout = 10_000

    def __init__(self):
        TargetTemplate.__init__(self)

        self.ser = SimpleSerial_ChipWhispererLite()
        self.disable_newattr()
        
        Leia.__init__(self)

    def close(self):
        if self.ser != None:
            self.ser.close()

    def init(self):
        # TODO : A remonter dans Leia
        while True:
            d = self.read_all()
            if len(d) == 0:
                break

        self._testWaitingFlag()

    def reinit(self):
        pass

    def test(self):
        self._testWaitingFlag()

    def _con(self, scope=None):
        if not scope:
            Warning("You need a scope connected to use this Target")
        scope.scope_disconnected_signal.connect(self.dis)
        # self.outstanding_ack = False

        self.ser.con(scope)
        self.ser.flush()

        # 'x' flushes everything & sets system back to idle
        self.write(b" "*10)

    ####################################################################################

    def read_all(self):
        if hasattr(self.ser, "read_all"):
            ret = self.ser.read_all()
        else:
            ret = self.read(num=self.ser.inWaiting())

        if isinstance(ret, str):
            ret = bytes(ret, "latin")

        return ret

    def read(self, num=1, timeout=None):
        if timeout is None:
            timeout = self.ser_timeout

        if hasattr(self.ser, "read_all"):
            ret = self.ser.read(num=num)
        else:
            ret = self.ser.read(num=num, timeout=timeout)

        if isinstance(ret, str):
            ret = bytes(ret, "latin")

        return ret

    def write(self, b):
        if isinstance(b, str):
            b = bytes(b, "latin")
        ret = self.ser.write(b)
        #if hasattr(self.ser, 'flush'):
        #    self.ser.flush()

        return ret

    ####################################################################################


