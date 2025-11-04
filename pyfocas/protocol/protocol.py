"""This is heavily inspired by github.com/diohpix/pyfanuc"""

import logging
import socket
import struct
from typing import Optional

from pyfocas.protocol.functions import FOCASFunction
from pyfocas.protocol.packet import (
    ControlDevice,
    FOCASError,
    FOCASPacket,
    FOCASStatInfo,
    FOCASSysInfo,
    PacketType,
    PacketOrigin,
    RESPONSE_BUFFER_SIZE,
    extract_focas_packet,
    decode_scaled_integer,
    create_packet,
)

logger = logging.getLogger(__name__)


class FOCAS:
    """Main FOCAS communication class"""

    def __init__(self, hostname: str, port: int):
        self.hostname = hostname
        self.port = port
        self.connected: bool = False
        self.socket: Optional[socket.socket] = None

    def connect(self) -> bool:
        """Create Connection to FOCAS via UNIX socket"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error as err:
            logger.error("Failed to create socket: %s", err)
            return False

        # Increase timeout for connection
        self.socket.settimeout(5)

        # Try connection
        try:
            self.socket.connect((self.hostname, self.port))
        except TimeoutError:
            logger.error(
                "Connection to %s:%s timed out", self.hostname, self.port
            )
            return False

        # Reset timeout
        self.socket.settimeout(1)

        focas_open_request = create_packet(
            PacketOrigin.CLIENT,
            PacketType.OPEN_REQUEST,
            struct.pack(">H", PacketOrigin.SERVER),
        )
        self.socket.sendall(focas_open_request)
        data = extract_focas_packet(self.socket.recv(RESPONSE_BUFFER_SIZE))

        if data.packet_type == PacketType.OPEN_RESPONSE:
            self.connected = True

        return self.connected

    def request_single_command(
        self,
        control_device: ControlDevice,
        function: FOCASFunction,
        payload: list[int],
    ):
        """Send request for command"""

        command = struct.pack(">HHH", control_device, *function)
        if len(payload) != 5:
            raise ValueError("Payload must be a list of 5 integers")
        assert self.socket is not None
        self.socket.sendall(
            create_packet(
                PacketOrigin.CLIENT,
                PacketType.GENERIC_REQUEST,
                command + struct.pack(">iiiii", *payload),
            )
        )

        response = extract_focas_packet(self.socket.recv(RESPONSE_BUFFER_SIZE))

        if response.payload_length == 0:
            raise FOCASError("Payload is of length 0")

        if response.packet_type != PacketType.GENERIC_RESPONSE:
            raise FOCASError("Packet type is not GENERIC_RESPONSE")

        assert response.data is not None
        assert len(response.data) >= 1
        assert isinstance(response.data[0], (bytes, bytearray))
        if response.data[0].startswith(command + b"\x00" * 6):
            return FOCASPacket(
                payload_length=struct.unpack(">H", response.data[0][12:14])[0],
                data=response.data[0][14:],
                packet_type=response.packet_type,
                packet_origin=response.packet_origin,
            )

        raise FOCASError("Payload does not match command")

    def get_status_info(self):
        """Get status information"""

        response = self.request_single_command(
            ControlDevice.CNC, FOCASFunction.GetStatInfo, [0, 0, 0, 0, 0]
        )
        return FOCASStatInfo.from_bytes(response.data)

    def read_macro(
        self, first_macro_number: int, last_macro_number: int | None = None
    ) -> dict[int, float]:
        """Read macro"""

        first = first_macro_number
        last = last_macro_number or first_macro_number

        if first > last:
            raise ValueError(
                "First macro number must be smaller than last macro number"
            )

        response = self.request_single_command(
            ControlDevice.CNC, FOCASFunction.ReadMacro, [first, last, 0, 0, 0]
        )
        if response.payload_length == 0:
            return {}

        macros: dict[int, float] = {}
        for pos in range(0, response.payload_length, 8):
            number = decode_scaled_integer(response.data[pos : pos + 8])
            assert number is not None
            macros[first] = number
            first += 1

        return macros

    def write_macro_double(
        self, macro_number: int, value: float
    ) -> FOCASPacket:
        """Write macro"""

        if macro_number < 1 or macro_number > 1000:
            raise ValueError("Macro number must be between 1 and 1000")

        command = struct.pack(
            ">HHH", ControlDevice.CNC, *FOCASFunction.WriteMacroDouble
        )

        assert self.socket is not None
        self.socket.sendall(
            create_packet(
                PacketOrigin.CLIENT,
                PacketType.GENERIC_REQUEST,
                command
                + struct.pack(">iiiiid", macro_number, 0, 0, 0, 8, value),
            )
        )

        return extract_focas_packet(self.socket.recv(RESPONSE_BUFFER_SIZE))

    def get_sys_info(self):
        """Get system information"""

        response = self.request_single_command(
            ControlDevice.CNC, FOCASFunction.GetSysInfo, [0, 0, 0, 0, 0]
        )
        return FOCASSysInfo.from_bytes(response.data)
