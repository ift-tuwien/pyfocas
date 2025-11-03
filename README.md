# ICOfocas

This project is a barebones reimplementation of the FANUC FOCAS protocol for
communicating with a CNC machine. 

It only uses UNIX sockets and sends the proper messages / packets instead of 
relying on vendor libraries.

## Sources / Based On

This project relies on the reverse engineering of the FANUC FOCAS protocol by
[diohpix](https://github.com/diohpix). 
The relevant library is [pyfanuc](https://github.com/diohpix/pyfanuc).

This reimplementation of the protocol is currently the only way of reliably 
using FOCAS on a 64bit ARM (aarch64) system as no library for that architecture
exists.

## Protocol

The protocol is a big endian request-response protocol via UNIX sockets. A full
message (either request or response) will be called _packet_. A packet has
headers and at least one subpacket, which in turn consist of multiple blocks
detailing the purpose of the packet.

### Header

The header looks similar for request and response. A typical header contains 
the following blocks, with a _block_ being a part of the header or subpacket:

| NAME    | Sync Prefix          | Packet Origin    | Packet Type        | Packet Length                     | Subpacket Count      |
|---------|----------------------|------------------|--------------------|-----------------------------------|----------------------|
| PURPOSE | Start of each packet | Server or Client | Open, Close, Other | Length of packet incl. subpackets | Number of subpackets |
| LENGTH  | 4 bytes              | 2 bytes          | 2 bytes            | 2 bytes                           | 2 bytes              |

`Sync Prefix` marks the start of a packet and is always `A0 A0 A0 A0`.

`Packet Origin` marks if the packet is a request to the FOCAS server (`00 01`)
or a response from it (different from `00 01`).

``Packet Type`` differentiates the packets between:
- Trying to open a connection to the FOCAS server:
  - Request: ``01 01``
  - Response: ``01 02``
- Trying to close the connection:
  - Request: ``02 01``
  - Response: ``02 02``
- Trying to execute a generic command:
  - Request: ``21 01``
  - Response: ``21 02``

> There are other packet types as can be seen in [diohpix/pyfanuc](https://github.com/diohpix/pyfanuc/blob/da8d9a73148f637276ed1e86b5f04f9965a01b75/README.md#programmtransfer)
which are not covered in this project (yet).

``Packet Length`` contains the total length of bytes coming after it, including
the size of the ``Subpacket Count`` (2 bytes) and all the subpackets in bytes.

> Note that this results in the ``Packet Length`` always being larger than the
sum of all subpacket's ``Subpacket Length`` by exactly 2 bytes (size of the 
`Subpacket Count`).

``Subpacket Count`` holds the number of subpackets in this packet.

### Subpacket

Subpackets are of varying length and data types. There are some reused sizes
and packing / types.

#### Default Payload: 5x 4-Byte INT32

The subpackets are always of length ``1c`` / 28 bytes. They each contain three
pieces of information about the subpacket totalling 8 bytes followed by a 
payload of 20 bytes which can be split into multiple regions.

| NAME    | Subpacket Length        | Control Device | Function                                  | Payload                          |
|---------|-------------------------|----------------|-------------------------------------------|----------------------------------|
| PURPOSE | Length of the subpacket | CNC or PMC     | Command to execute or which was executed. | Data transmittable via subpacket |
| LENGTH  | 2 bytes                 | 2 bytes        | 4 bytes                                   | 20 bytes                         |

