"""Derived from https://github.com/diohpix/pyfanuc/blob/master/protocol.txt"""

import dataclasses
from enum import Enum


@dataclasses.dataclass
class FOCASFunction(tuple, Enum):
    """Constants for accessing Focas functionality"""

    GetSysInfo = (0x01, 0x18)
    GetStatInfo = (0x01, 0x19)
    ReadMacro = (0x01, 0x15)
    WriteMacroDouble = (0x01, 0xA8)
