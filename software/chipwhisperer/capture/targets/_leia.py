import ctypes
from collections.abc import Iterable
import time

class Leia:
    COMMAND_LEN_SIZE = 4
    RESPONSE_LEN_SIZE = 4
    TRIGGER_DEPTH = 10
    STRATEGY_MAX = 4

    #########################################################################################
    TRIG_GET_ATR_PRE = 1
    TRIG_GET_ATR_POST = 2

    TRIG_PRE_SEND_APDU_FRAGMENTED_T0 = 3
    TRIG_PRE_SEND_APDU_SIMPLE_T0 = 4
    TRIG_PRE_GET_RESP_FRAGMENTED_T0 = 5
    TRIG_PRE_GET_RESP_SIMPLE_T0 = 6

    TRIG_IRQ_PUTC = 7
    TRIG_IRQ_GETC = 8

    TRIG_AFTER_1ST_BYTE_SEND_SIMPLE_APDU_T0 = [
        TRIG_PRE_SEND_APDU_SIMPLE_T0,
        TRIG_IRQ_PUTC,
    ]
    # TRIG_BEFORE_SEND_SIMPLE_APDU_T1      = [TRIG_SEND_APDU_SIMPLE_T1_PRE, TRIG_IRQ_PUTC]

    TRIG_AFTER_1ST_BYTE_SEND_FRAGMENTED_APDU_T0 = [
        TRIG_PRE_SEND_APDU_FRAGMENTED_T0,
        TRIG_IRQ_PUTC,
    ]
    # TRIG_BEFORE_SEND_FRAGMENTED_APDU_T1  = [TRIG_SEND_APDU_FRAGMENTED_T1_PRE, TRIG_IRQ_PUTC]
    #########################################################################################

    ERR_FLAGS = {
        0x00: "OK",
        0x01: "PLATFORM_ERR_CARD_NOT_INSERTED",
        0xFF: "UNKNOWN_ERROR",
    }

    def __init__(self):
        # self.ser = serial.Serial(port, timeout=10, baudrate=115200)
        pass

    def _testWaitingFlag(self):
        self.read_all()
        self.write(b" ")
        time.sleep(0.1)
        d = self.read() + self.read_all()

        if len(d) == 0 or d[-1] != ord("W"):  # b"W"
            print(f"buffer = {d}")
            raise ConnectionError("Can not connect to LEIA.")

    def _checkAck(self):
        if self.read() != b"R":
            raise IOError("No response ack received.")

    def _checkStatus(self):
        s = self.read()

        if len(s)==0:
            raise IOError("No status flag received.")

        if s != b"S":
            raise IOError(f"Invalid status flag '{s}' received.")

        status = self.read()

        if status == b"":
            raise IOError("Status not received.")
        elif status != b"\x00":
            raise IOError(self.ERR_FLAGS[ord(status)])
        return status

    def _read_response_size(self):
        return (
            ResponseSizeStruct().unpack(self.read(self.RESPONSE_LEN_SIZE)).response_size
        )

    def reset(self):
        self._testWaitingFlag()

        self.write(b"r")
        self.write((0).to_bytes(self.COMMAND_LEN_SIZE, byteorder="big"))

        self._checkStatus()
        self._checkAck()

    def configure(
        self,
        protocol_to_use=None,
        ETU_to_use=None,
        freq_to_use=None,
        negotiate_pts=True,
        negotiate_baudrate=True,
        struct=None,
    ):
        """
        Args:
            protocol_to_use : (None, 0, 1, ...)
            ETU_to_use : (None, x)
            freq_to_use : (None, x)
            ---------
            negotiate_pts: (True, False)
            negotiate_baudrate: (True, False)
        """
        self._testWaitingFlag()

        if struct == None:
            if protocol_to_use is None:
                protocol_to_use = 0
            else:
                protocol_to_use += 1

            if ETU_to_use is None:
                ETU_to_use = 0

            if freq_to_use is None:
                freq_to_use = 0

            negotiate_pts = 1 if negotiate_pts else 0
            negotiate_baudrate = 1 if negotiate_baudrate else 0

            struct = ConfigureAPDU(
                protocol_to_use,
                ETU_to_use,
                freq_to_use,
                negotiate_pts,
                negotiate_baudrate,
            )

        compacted = struct.pack()
        size = len(compacted).to_bytes(self.COMMAND_LEN_SIZE, byteorder="big")
        self.write(b"c")
        self.write(size)
        self.write(compacted)

        self._checkStatus()
        self._checkAck()

    def get_trigger_strategy(self, SID):
        self._testWaitingFlag()

        self.write(b"o")
        self.write((1).to_bytes(self.COMMAND_LEN_SIZE, byteorder="big"))
        self.write(SID.to_bytes(1, byteorder="big"))

        self._checkStatus()
        self._checkAck()

        r_size = self._read_response_size()
        r = TriggerStrategyStruct(self.TRIGGER_DEPTH)().unpack(self.read(r_size))

        return r

    def set_trigger_strategy(self, SID, list, delay=0):
        self._testWaitingFlag()

        self.write(b"O")
        try:
            size = len(list)
        except TypeError:
            size = 1
            list = [list]

        sts = SetTriggerStrategyStruct(self.TRIGGER_DEPTH)()
        sts.index = SID
        sts.strategy.size = size
        for i in range(size):
            sts.strategy.list[i] = list[i]

        sts.strategy.delay = delay

        payload = sts.pack()

        size = len(payload).to_bytes(self.COMMAND_LEN_SIZE, byteorder="big")
        self.write(size)
        self.write(payload)

        self._checkStatus()
        self._checkAck()

        return sts

    def get_ATR(self):
        self._testWaitingFlag()

        self.write(b"t")
        self.write((0).to_bytes(self.COMMAND_LEN_SIZE, byteorder="big"))

        self._checkStatus()
        self._checkAck()

        r_size = self._read_response_size()
        r = ResponseATRStruct().unpack(self.read(r_size))

        return r

    def is_card_inserted(self):
        self._testWaitingFlag()

        self.write(b"?")
        self.write((0).to_bytes(self.COMMAND_LEN_SIZE, byteorder="big"))

        self._checkStatus()
        self._checkAck()

        r_size = self._read_response_size()
        if r_size != 1:
            raise Exception("Invalid response size for 'is_card_inserted' (?) command.")
        r = self.read(1)

        return True if r == b"\x01" else False

    def send_APDU(self, apdu):
        self._testWaitingFlag()

        compacted = apdu.pack()
        size = len(compacted).to_bytes(self.COMMAND_LEN_SIZE, byteorder="big")
        self.write(b"a")
        self.write(size)
        self.write(compacted)

        self._checkStatus()
        self._checkAck()

        r_size = self._read_response_size()
        r = ResponseAPDUStruct().unpack(self.read(r_size))

        return r




class LEIAStructure(ctypes.Structure):
    def __init__(self, *args, **kwargs):
        for i, x in enumerate(args):
            if isinstance(x, list):
                raise Exception(
                    f"Lists (here {x}) without keyword name are not accepted for the moment."
                )

        lists2 = []
        for x in kwargs:
            if isinstance(kwargs[x], Iterable):
                lists2.append((x, kwargs[x]))

        for x in lists2:
            del kwargs[x[0]]

        ctypes.Structure.__init__(self, *args, **kwargs)
        for x in lists2:
            name = x[0]
            value = x[1]
            el = getattr(self, name)
            for i, data in enumerate(value):
                el[i] = data

    def pack(self):
        return bytes(self)[:]

    def unpack(self, by):
        fit = min(len(by), ctypes.sizeof(self))
        ctypes.memmove(ctypes.addressof(self), by, fit)
        return self

    def normalized(self):
        return bytes(self)

    def __repr__(self):
        return str(self)

    def __str__(self):
        return " ".join(["{:02x}".format(x) for x in self.normalized()])


class ResponseSizeStruct(LEIAStructure):
    _fields_ = [("response_size", ctypes.c_uint32)]


def create_APDU_from_bytes(_bytes):
    apdu = CommandAPDUStruct()
    apdu.cla, apdu.ins, apdu.p1, apdu.p2 = _bytes[:4]

    if len(_bytes) == 5:
        apdu.lc, apdu.le = 0, _bytes[4]
    else:
        apdu.lc, apdu.le = _bytes[4], 0
        if apdu.lc != 0:
            for i in range(apdu.lc):
                apdu.data[i] = _bytes[5 + i]
            if len(_bytes) == 5 + apdu.lc + 1:
                apdu.le = _bytes[5 + apdu.lc]
    return apdu


class CommandAPDUStruct(LEIAStructure):

    _fields_ = [
        ("cla", ctypes.c_uint8),
        ("ins", ctypes.c_uint8),
        ("p1", ctypes.c_uint8),
        ("p2", ctypes.c_uint8),
        ("lc", ctypes.c_uint16),
        ("le", ctypes.c_uint32),
        ("send_le", ctypes.c_uint8),
        ("data", ctypes.c_uint8 * 512),
    ]

    def pack(self):
        return LEIAStructure.pack(self)[: CommandAPDUStruct.data.offset + self.lc]

    def __str__(self):
        return (
            f"CommandAPDUStruct(cla={hex(self.cla)}, ins={hex(self.ins)}, p1={hex(self.p1)}, p2={hex(self.p2)}, lc={self.lc}, le={self.le}, send_le={self.send_le} "
            + (f", data={list(self.data)[0:self.lc]}" if self.lc != 0 else "")
            + ")"
        )

    def normalized(self):
        b = b""
        b += ctypes.string_at(ctypes.addressof(self), CommandAPDUStruct.lc.offset)
        if self.lc != 0:
            b += ctypes.string_at(
                ctypes.addressof(self) + CommandAPDUStruct.lc.offset,
                CommandAPDUStruct.lc.size,
            )
            b += ctypes.string_at(
                ctypes.addressof(self) + CommandAPDUStruct.data.offset, self.lc
            )
        if self.send_le != 0:
            b += ctypes.string_at(
                ctypes.addressof(self) + CommandAPDUStruct.le.offset,
                CommandAPDUStruct.le.size,
            )
        if self.lc == 0 and self.send_le == 0:
            b += ctypes.string_at(
                ctypes.addressof(self) + CommandAPDUStruct.lc.offset,
                CommandAPDUStruct.lc.size,
            )
        return b


class ConfigureAPDU(LEIAStructure):

    _fields_ = [
        ("protocol", ctypes.c_uint8),
        ("etu", ctypes.c_uint32),
        ("freq", ctypes.c_uint32),
        ("negotiate_pts", ctypes.c_uint8),
        ("negotiate_baudrate", ctypes.c_uint8),
    ]


class ResponseAPDUStruct(LEIAStructure):

    _fields_ = [
        ("le", ctypes.c_uint32),
        ("sw1", ctypes.c_uint8),
        ("sw2", ctypes.c_uint8),
        ("data", ctypes.c_uint8 * 514),
    ]

    def __str__(self):
        return (
            f"ResponseAPDUStruct(sw1={hex(self.sw1)}, sw2={hex(self.sw2)}, le={hex(self.le)}"
            + (f", data={list(self.data)[0:self.le]}" if self.le != 0 else "")
            + ")"
        )

    def normalized(self):
        b = b""
        b += ctypes.string_at(
            ctypes.addressof(self) + ResponseAPDUStruct.data.offset, self.le
        )
        b += ctypes.string_at(
            ctypes.addressof(self) + ResponseAPDUStruct.sw1.offset,
            ResponseAPDUStruct.sw1.size,
        )
        b += ctypes.string_at(
            ctypes.addressof(self) + ResponseAPDUStruct.sw2.offset,
            ResponseAPDUStruct.sw2.size,
        )
        return b


def TriggerStrategyStruct(size):
    if hasattr(TriggerStrategyStruct, "cache"):
        if size in TriggerStrategyStruct.cache:
            return TriggerStrategyStruct.cache[size]
    else:
        TriggerStrategyStruct.cache = {}

    class _TriggerStrategyStruct(LEIAStructure):

        _fields_ = [
            ("size", ctypes.c_uint8),
            ("delay", ctypes.c_uint32),
            ("delay_cnt", ctypes.c_uint32),
            ("list", ctypes.c_uint8 * size),
        ]

        def __str__(self):
            return f"TriggerStrategyStruct(delay={self.delay}, list={list(self.list)[0:self.size]})"

    TriggerStrategyStruct.cache[size] = _TriggerStrategyStruct
    return TriggerStrategyStruct.cache[size]


def SetTriggerStrategyStruct(size):
    if hasattr(SetTriggerStrategyStruct, "cache"):
        if size in SetTriggerStrategyStruct.cache:
            return SetTriggerStrategyStruct.cache[size]
    else:
        SetTriggerStrategyStruct.cache = {}

    class _SetTriggerStrategyStruct(LEIAStructure):

        _fields_ = [
            ("index", ctypes.c_uint8),
            ("strategy", TriggerStrategyStruct(size)),
        ]

        def __str__(self):
            return f"SetTriggerStrategyStruct(index={self.index}, strategy={self.strategy})"

    SetTriggerStrategyStruct.cache[size] = _SetTriggerStrategyStruct
    return SetTriggerStrategyStruct.cache[size]


class ResponseATRStruct(LEIAStructure):

    _fields_ = [
        ("ts", ctypes.c_uint8),
        ("t0", ctypes.c_uint8),
        ("ta", ctypes.c_uint8 * 4),
        ("tb", ctypes.c_uint8 * 4),
        ("tc", ctypes.c_uint8 * 4),
        ("td", ctypes.c_uint8 * 4),
        ("h", ctypes.c_uint8 * 16),
        ("t_mask", ctypes.c_uint8 * 4),
        ("h_num", ctypes.c_uint8),
        ("tck", ctypes.c_uint8),
        ("tck_present", ctypes.c_uint8),
        ("D_i_curr", ctypes.c_uint32),
        ("F_i_curr", ctypes.c_uint32),
        ("f_max_curr", ctypes.c_uint32),
        ("T_protocol_curr", ctypes.c_uint8),
        ("ifsc", ctypes.c_uint8),
    ]

    def normalized(self):
        b = b""
        b += ctypes.string_at(
            ctypes.addressof(self),
            ResponseATRStruct.ts.size + ResponseATRStruct.t0.size,
        )
        b += ctypes.string_at(ctypes.addressof(self) + ResponseATRStruct.ta.offset, 1)
        b += ctypes.string_at(ctypes.addressof(self) + ResponseATRStruct.tb.offset, 1)
        b += ctypes.string_at(ctypes.addressof(self) + ResponseATRStruct.tc.offset, 1)
        b += ctypes.string_at(
            ctypes.addressof(self) + ResponseATRStruct.h.offset, self.h_num
        )
        return b
