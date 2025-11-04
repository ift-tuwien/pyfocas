# pyfocas

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
| ------- | -------------------- | ---------------- | ------------------ | --------------------------------- | -------------------- |
| PURPOSE | Start of each packet | Server or Client | Open, Close, Other | Length of packet incl. subpackets | Number of subpackets |
| LENGTH  | 4 bytes              | 2 bytes          | 2 bytes            | 2 bytes                           | 2 bytes              |

`Sync Prefix` marks the start of a packet and is always `A0 A0 A0 A0`.

`Packet Origin` marks if the packet is a request to the FOCAS server (`00 01`)
or a response from it (different from `00 01`).

`Packet Type` differentiates the packets between:

- Trying to open a connection to the FOCAS server:
  - Request: `01 01`
  - Response: `01 02`
- Trying to close the connection:
  - Request: `02 01`
  - Response: `02 02`
- Trying to execute a generic command:
  - Request: `21 01`
  - Response: `21 02`

> There are other packet types as can be seen in [diohpix/pyfanuc](https://github.com/diohpix/pyfanuc/blob/da8d9a73148f637276ed1e86b5f04f9965a01b75/README.md#programmtransfer)
> which are not covered in this project (yet).

`Packet Length` contains the total length of bytes coming after it, including
the size of the `Subpacket Count` (2 bytes) and all the subpackets in bytes.

> Note that this results in the `Packet Length` always being larger than the
> sum of all subpacket's `Subpacket Length` by exactly 2 bytes (size of the
> `Subpacket Count`).

`Subpacket Count` holds the number of subpackets in this packet.

### Subpacket

Subpackets are of varying length and data types. There are some reused sizes
and packing / types.

#### Default Payload: 5x 4-Byte INT32

The subpackets are always of length `1c` / 28 bytes. They each contain three
pieces of information about the subpacket totalling 8 bytes followed by a
payload of 20 bytes which can be split into multiple regions.

| NAME    | Subpacket Length        | Control Device | Function                                  | Payload                          |
| ------- | ----------------------- | -------------- | ----------------------------------------- | -------------------------------- |
| PURPOSE | Length of the subpacket | CNC or PMC     | Command to execute or which was executed. | Data transmittable via subpacket |
| LENGTH  | 2 bytes                 | 2 bytes        | 4 bytes                                   | 20 bytes                         |

## Implemented Functions

### Initialize Connection

This needs to be done to create the connection with the FOCAS server.

#### Request

| Sync Prefix   | Packet Origin | Packet Type | Packet Length            | Subpacket Count          |
| ------------- | ------------- | ----------- | ------------------------ | ------------------------ |
| `A0 A0 A0 A0` | `00 01`       | `01 01`     | `00 02` (unclear reason) | `00 02` (unclear reason) |

#### Response

| Sync Prefix   | Packet Origin | Packet Type | Packet Length            | Subpacket Count          |
| ------------- | ------------- | ----------- | ------------------------ | ------------------------ |
| `A0 A0 A0 A0` | `00 04`       | `01 02`     | `01 68` (unclear reason) | `00 08` (unclear reason) |

The response contains 360 Bytes of (as of yet) unclear subpacket content.

### Status Info

#### Request

| Sync Prefix   | Packet Origin | Packet Type | Packet Length | Subpacket Count |
| ------------- | ------------- | ----------- | ------------- | --------------- |
| `A0 A0 A0 A0` | `00 01`       | `21 01`     | `00 1E`       | `00 01`         |

With the single subpacket being:

| Subpacket Length | Control Device | Function      | Payload       |
| ---------------- | -------------- | ------------- | ------------- |
| `00 1C`          | `00 01`        | `00 01 00 19` | 20 times `00` |

#### Response

| Sync Prefix   | Packet Origin | Packet Type | Packet Length | Subpacket Count |
| ------------- | ------------- | ----------- | ------------- | --------------- |
| `A0 A0 A0 A0` | `00 04`       | `21 02`     | `00 20`       | `00 01`         |

With the single subpacket being:

| Subpacket Length | Control Device | Function      | Payload                     |
| ---------------- | -------------- | ------------- | --------------------------- |
| `00 1E`          | `00 01`        | `00 01 00 19` | See \_FOCAS_STATINFO_STRUCT |

### System Info

#### Request

| Sync Prefix   | Packet Origin | Packet Type | Packet Length | Subpacket Count |
| ------------- | ------------- | ----------- | ------------- | --------------- |
| `A0 A0 A0 A0` | `00 01`       | `21 01`     | `00 1E`       | `00 01`         |

With the single subpacket being:

| Subpacket Length | Control Device | Function      | Payload       |
| ---------------- | -------------- | ------------- | ------------- |
| `00 1C`          | `00 01`        | `00 01 00 18` | 20 times `00` |

#### Response

| Sync Prefix   | Packet Origin | Packet Type | Packet Length | Subpacket Count |
| ------------- | ------------- | ----------- | ------------- | --------------- |
| `A0 A0 A0 A0` | `00 04`       | `21 02`     | `00 24`       | `00 01`         |

With the single subpacket being:

| Subpacket Length | Control Device | Function      | Payload                    |
| ---------------- | -------------- | ------------- | -------------------------- |
| `00 22`          | `00 01`        | `00 01 00 18` | See \_FOCAS_SYSINFO_STRUCT |

### Read Macro

#### Request

| Sync Prefix   | Packet Origin | Packet Type | Packet Length | Subpacket Count |
| ------------- | ------------- | ----------- | ------------- | --------------- |
| `A0 A0 A0 A0` | `00 01`       | `21 01`     | `00 1E`       | `00 01`         |

With the single subpacket being:

| Subpacket Length | Control Device | Function      | Payload                                |
| ---------------- | -------------- | ------------- | -------------------------------------- |
| `00 1C`          | `00 01`        | `00 01 00 15` | `00 00 01 F6` `00 00 01 F6` + 12x `00` |

This reads macro variable #502 (`01 F6`).

#### Response

| Sync Prefix   | Packet Origin | Packet Type | Packet Length | Subpacket Count |
| ------------- | ------------- | ----------- | ------------- | --------------- |
| `A0 A0 A0 A0` | `00 04`       | `21 02`     | `00 1A`       | `00 01`         |

With the single subpacket being:

| Subpacket Length | Control Device | Function      | Payload                                                                                                                                                                |
| ---------------- | -------------- | ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `00 18`          | `00 01`        | `00 01 00 15` | `00 00 00 00` (Fill) `00 00 00 10` (#Bytes coming after this) `29 7C 1E 00 00 0A 00 06` (First 8-Byte Scaled Int) `05 F5 E1 00 00 0A 00 08` (Second 8-Byte Scaled Int) |

### Write Macro (Double)

Writes a macro variable with a double value (not scaled integer)

#### Request

| Sync Prefix   | Packet Origin | Packet Type | Packet Length | Subpacket Count |
| ------------- | ------------- | ----------- | ------------- | --------------- |
| `A0 A0 A0 A0` | `00 01`       | `21 01`     | `00 38`       | `00 01`         |

With the single subpacket being:

| Subpacket Length | Control Device | Function      | Payload                                                                                                                                |
| ---------------- | -------------- | ------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `00 24`          | `00 01`        | `00 01 00 A8` | `00 00 01 F6` (Var. 502) `00` (12x Filling Bytes) `00 00 00 08` (#Bytes coming after this) `40 59 00 00 00 00 00 00` (Value as double) |

This writes 100.0 to #502.

## Development

### Release

In the steps below we assume that you

- installed [`uv`](https://docs.astral.sh/uv/), and
- execute commands in the root of the repository.

Please replace `<VERSION>` with the version number of the package that you want to release (e.g. `0.2.0`).

#### PyPI

To release a new version on [PyPI](https://pypi.org/project/icostate/) please use the commands below:

```sh
uv version <VERSION>
export pyfocas_version="$(uv version --short)"
git commit -a -m "Release: Release version $pyfocas_version"
git tag "$pyfocas_version"
git push && git push --tags
```

#### GitHub

Open the [release notes](https://github.com/MyTooliT/pyfocas/doc/release) for the latest version and [create a new release](https://github.com/MyTooliT/pyfocas/releases/new):

1.  Paste the release notes into the main text of the release web page
2.  Insert the version number into the tag field
3.  For the release title use “Version <VERSION>”, where `<VERSION>` specifies the version number (e.g. “Version 0.2”)
4.  Click on “Publish Release”

**Note:** Alternatively you can also use the [`gh`](https://cli.github.com) command:

```sh
gh release create
```

to create the release.
