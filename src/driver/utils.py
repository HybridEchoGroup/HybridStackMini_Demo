from enum import IntEnum
import logging


class StatusLog(dict):
    """A dict that logs every status update through the central 'driver' logger.

    Usage: replace  self.status = {}  with  self.status = StatusLog()
    All existing  self.status["key"] = value  lines work unchanged.
    Output is handled by the root logger configured in log.setup().
    """

    def __init__(self) -> None:
        super().__init__()
        self._logger = logging.getLogger("driver")

    def __setitem__(self, key, value) -> None:
        super().__setitem__(key, value)
        self._logger.debug("%s = %s", key, value)

class channels(IntEnum):
    """
    Enumeration of available PicoScope input channels.

    This enum provides symbolic names for the physical input channels
    of the PicoScope device and is used when configuring channels,
    triggers, and data acquisition.
    """
    Channel_A = 0
    Channel_B = 1
    Channel_C = 2
    Channel_D = 3
    TRIGGER_AUX = 1001



_VOLTAGE_VOLTS = {0: 0.010, 1: 0.020, 2: 0.050, 3: 0.100, 4: 0.200,
                  5: 0.500, 6: 1.0, 7: 2.0, 8: 5.0, 9: 10.0, 10: 20.0}

class voltage_level(IntEnum):
    """
    Enumeration of supported input voltage ranges.

    The integer value is the PicoScope API range identifier.
    Use .volts to get the physical voltage when needed.
    """
    V10_mv  = 0
    V20_mv  = 1
    V50_mv  = 2
    V100_mv = 3
    V200_mv = 4
    V500_mv = 5
    V1_v    = 6
    V2_v    = 7
    V5_v    = 8
    V10_v   = 9
    V20_v   = 10

    @property
    def volts(self):
        return _VOLTAGE_VOLTS[self]

    @classmethod
    def from_volts(cls, v):
        for member in cls:
            if _VOLTAGE_VOLTS[member] == v:
                return member
        raise ValueError(f"No entry for {v}V")


class timebase(IntEnum):
    """
    Enumeration of PicoScope timebase settings. (Only correct for 6000 series)

    Each value represents a predefined sampling frequency as defined
    by the PicoScope timebase index and is used when starting
    block-mode acquisitions.
    """
    Freq_625MHz = 3
    Freq_312_5MHz = 4
    Freq_156_25MHz = 5
    Freq_78_125MHz = 6
    Freq_39_0625MHz = 7

class timebase_3000(IntEnum):
    Freq_250MHz = 2
    Freq_125MHz = 3
    Freq_62_5MHz = 4
    Freq_41_66MHz = 5
    Freq_31_25MHz = 6
    Freq_25MHz = 7