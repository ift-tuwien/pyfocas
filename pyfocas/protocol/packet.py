"""Code for working with packet data"""

from dataclasses import dataclass
import doctest
import struct
from enum import Enum
from struct import pack, unpack


class DecodingError(Exception):
    """Exception raised for errors in the decoding of a packet"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class FOCASError(Exception):
    """Exception raised for errors in the FOCAS protocol"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class PacketOrigin(int, Enum):
    """Packet origin."""

    CLIENT = 0x01
    SERVER = 0x02


class PacketType(int, Enum):
    """Packet type."""

    GENERIC_REQUEST = 0x2101
    GENERIC_RESPONSE = 0x2102
    OPEN_REQUEST = 0x0101
    OPEN_RESPONSE = 0x0102
    CLOSE_REQUEST = 0x0201
    CLOSE_RESPONSE = 0x0202


class ControlDevice(int, Enum):
    """Control device."""

    CNC = 0x01
    PMC = 0x02


SYNC_PREFIX = b"\xa0\xa0\xa0\xa0"  # Sync for request & response
RESPONSE_BUFFER_SIZE = 1500


def decode_scaled_integer(byte_string: bytes) -> float | None:
    """
    Decode 8 byte scaled integer to float

    The decoding treats the value's bytes as a scaled integer, meaning:

    Bytes 0-3:  big endian signed integer
    Byte 4:     0x00 (unused)
    Byte 5:     0x02 or 0x0A (base 2 or 10)
    Byte 6:     0x00 (OK) or 0xFF (invalid)
    Byte 7:     Exponent or 0xFF (invalid)

    :param byte_string: Byte string of 8 bytes.
    :return: Float if decoded, None if not decoded.

    Examples:
        Valid:
        >>> decode_scaled_integer(b'\\x0b\\xc7q \\x00\\n\\x00\\x06')
        197.62

        Invalid: length not equal to 8 (too short)
        >>> decode_scaled_integer(b'\\x00'*7)
        Traceback (most recent call last):
        ...
        packet.DecodingError: Length not equal to 8

        Invalid: length not equal to 8 (too long)
        >>> decode_scaled_integer(b'\\x00'*9)
        Traceback (most recent call last):
        ...
        packet.DecodingError: Length not equal to 8

        Invalid: sentinel 0xFFFF at the end (bytes 6–7)
        >>> decode_scaled_integer(b'\\x00\\x00\\x00\\x01\\x00\\n\\xff\\xff')
        Traceback (most recent call last):
        ...
        packet.DecodingError: Sentinel value (FF FF) at the end

        Invalid: scaling base not 2 or 10 (here: 3)
        >>> decode_scaled_integer(b'\\x00\\x00\\x00\\x01\\x00\\x03\\x00\\x01')
        Traceback (most recent call last):
        ...
        packet.DecodingError: Invalid scaling base
    """

    # Only take 8 bytes
    if len(byte_string) != 8:
        raise DecodingError("Length not equal to 8")

    # Check for sentinel value (FF FF) at the end --> invalid
    if byte_string[-2:] == b"\xff" * 2:
        raise DecodingError("Sentinel value (FF FF) at the end")

    # Check for valid scaling base (2 or 10)
    if byte_string[5] not in [2, 10]:
        raise DecodingError("Invalid scaling base")

    mantissa = unpack(">i", byte_string[0:4])[0]
    base = byte_string[5]
    exponent = byte_string[7]

    return mantissa / (base**exponent)


def create_packet(
    origin: PacketOrigin, packet_type: PacketType, payload: bytes
) -> bytes:
    """
    Create a packet with a payload and origin.

    :param origin: The origin of the packet (e.g., CLIENT).
    :param packet_type: The packet type (e.g., GENERIC_REQUEST).
    :param payload: The payload of the packet as bytes

    :return: The packet as bytes assembled with the sync prefix.

    Examples:
        >>> list(create_packet(PacketOrigin.CLIENT,
        ...                    PacketType.GENERIC_REQUEST, b'\x01'))
        [160, 160, 160, 160, 0, 1, 33, 1, 0, 5, 0, 1, 0, 3, 1]

        >>> list(create_packet(PacketOrigin.CLIENT,
        ...                    PacketType.OPEN_REQUEST, b'\x02'))
        [160, 160, 160, 160, 0, 1, 1, 1, 0, 1, 2]

        >>> list(create_packet(PacketOrigin.CLIENT,
        ...                    PacketType.CLOSE_REQUEST, b''))
        [160, 160, 160, 160, 0, 1, 2, 1, 0, 0]

    """
    if packet_type == PacketType.GENERIC_REQUEST:
        # Create payload for generic request
        if isinstance(payload, list):
            temp = []
            for item in payload:
                temp.append(pack(">H", len(item) + 2) + item)
            payload = pack(">H", len(temp)) + b"".join(temp)
        else:
            payload = pack(">HH", 1, len(payload) + 2) + payload

    return (
        SYNC_PREFIX + pack(">HHH", origin, packet_type, len(payload)) + payload
    )


# short addinfo;            // 2
# short max_axis;           // 2
# char  cnc_type[2];        // 2
# char  mt_type[2];         // 2
# char  series[4];          // 4
# char  version[4];         // 4
# char  axes[2];            // 2
# ------------------------- = 18 bytes
# https://www.inventcom.net/fanuc-focas-library/misc/cnc_sysinfo
_FOCAS_SYSINFO_STRUCT = struct.Struct(">hh2s2s4s4s2s")

# short aut;                // 2
# short run;                // 2
# short motion;             // 2
# short mstb;               // 2
# short emergency;          // 2
# short alarm;              // 2
# short edit;               // 2
# ------------------------- = 14 bytes
# https://www.inventcom.net/fanuc-focas-library/misc/cnc_statinfo
_FOCAS_STATINFO_STRUCT = struct.Struct(">HHHHHHH")


def _decode_ascii(raw: bytes) -> str:
    return raw.decode("ascii", errors="replace").rstrip("\x00 ").strip()


def _encode_ascii(s: str, length: int) -> bytes:
    b = (s or "").encode("ascii", errors="replace")[:length]
    return b + b"\x00" * (length - len(b))


@dataclass(slots=True)
class FOCASSysInfo:
    """System information"""

    addinfo: int  # short (signed)
    max_axis: int  # short (signed)
    cnc_type: str  # 2 chars ASCII
    mt_type: str  # 2 chars ASCII
    series: str  # 4 chars ASCII
    version: str  # 4 chars ASCII
    axes: str  # 2 chars ASCII

    @classmethod
    def from_bytes(cls, data: bytes) -> "FOCASSysInfo":
        """Convert bytes to FOCAS system information object"""

        if len(data) < _FOCAS_SYSINFO_STRUCT.size:
            raise ValueError(
                f"Need {_FOCAS_SYSINFO_STRUCT.size} bytes, got {len(data)}"
            )
        addinfo, max_axis, cnc, mt, series, version, axes = (
            _FOCAS_SYSINFO_STRUCT.unpack_from(data)
        )
        return cls(
            addinfo=addinfo,
            max_axis=max_axis,
            cnc_type=_decode_ascii(cnc),
            mt_type=_decode_ascii(mt),
            series=_decode_ascii(series),
            version=_decode_ascii(version),
            axes=_decode_ascii(axes),
        )

    def to_bytes(self) -> bytes:
        """Convert FOCAS system information object into bytes"""

        return _FOCAS_SYSINFO_STRUCT.pack(
            int(self.addinfo),
            int(self.max_axis),
            _encode_ascii(self.cnc_type, 2),
            _encode_ascii(self.mt_type, 2),
            _encode_ascii(self.series, 4),
            _encode_ascii(self.version, 4),
            _encode_ascii(self.axes, 2),
        )


@dataclass
class FOCASStatInfo:
    """Status information"""

    aut: int
    run: int
    motion: int
    mstb: int
    emergency: int
    alarm: int
    edit: int

    @classmethod
    def from_bytes(cls, data: bytes) -> "FOCASStatInfo":
        """Convert bytes to Focas status information"""
        if len(data) < _FOCAS_STATINFO_STRUCT.size:
            raise ValueError(
                f"Need {_FOCAS_STATINFO_STRUCT.size} bytes, got {len(data)}"
            )
        return cls(*_FOCAS_STATINFO_STRUCT.unpack_from(data))


@dataclass
class FOCASPacket:
    """Focas message data"""

    payload_length: int
    packet_type: PacketType
    packet_origin: PacketOrigin
    data: bytes | list | None = None


def extract_focas_packet(data: bytes) -> FOCASPacket:
    """
    Decapsulate a packet from bytes into a FOCASPacket object.

    The packet layout is:
      [0:4 ] --> 4 Bytes SYNC_PREFIX
      [4:10] --> 2 Bytes each: packet_origin, packet_type, packet_length
      [10: ] --> payload (length = payload_length)

    Then we strip the first 10 Bytes and from then on:
    For PacketType.GENERIC_RESPONSE the payload layout is:
      [0:2 ] --> 2 Bytes subpacket_count
      then for each item i in 0..subpacket_count-1:
        [n:n+2] --> 2 Bytes subpacket_length INCLUDING these 2 length bytes
        [n+2:n+subpacket_length] --> actual subpacket data

    :param data: bytes of the packet to be decoded
    :return: FOCASPacket object
    """
    packet_length = len(data)
    if packet_length < 10:
        raise FOCASError("Data Frame too short")

    if not data.startswith(SYNC_PREFIX):
        raise FOCASError("Data Frame does not start with sync bytes")

    packet_origin, packet_type, payload_length = unpack(">HHH", data[4:10])
    if payload_length + 10 != packet_length:
        raise FOCASError("Data Frame length does not match payload length")

    if payload_length == 0:
        return FOCASPacket(payload_length, packet_type, packet_origin, None)

    data = data[10:]
    if packet_type == PacketType.GENERIC_RESPONSE:
        temp_data = []
        subpacket_count = unpack(">H", data[0:2])[0]
        n = 2
        for _ in range(subpacket_count):
            subpacket_length = unpack(">H", data[n : n + 2])[0]
            temp_data.append(data[n + 2 : n + subpacket_length])
            n += subpacket_length
        return FOCASPacket(
            payload_length, packet_type, packet_origin, temp_data
        )

    return FOCASPacket(payload_length, packet_type, packet_origin, data)


if __name__ == "__main__":
    doctest.testmod()
