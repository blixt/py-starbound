# -*- coding: utf-8 -*-

import struct


# Override range with xrange when running Python 2.x.
try:
    range = xrange
except:
    pass


def read_bytes(stream):
    length = read_varint(stream)
    return stream.read(length)


def read_dynamic(stream):
    type_id = ord(stream.read(1))
    if type_id == 1:
        return None
    elif type_id == 2:
        fmt = '>d'
    elif type_id == 3:
        fmt = '?'
    elif type_id == 4:
        return read_varint_signed(stream)
    elif type_id == 5:
        return read_string(stream)
    elif type_id == 6:
        return read_list(stream)
    elif type_id == 7:
        return read_map(stream)
    else:
        raise ValueError('Unknown dynamic type 0x%02X' % type_id)
    # Anything that passes through is assumed to have set a format to unpack.
    return struct.unpack(fmt, stream.read(struct.calcsize(fmt)))[0]


def read_list(stream):
    length = read_varint(stream)
    return [read_dynamic(stream) for _ in range(length)]


def read_map(stream):
    length = read_varint(stream)
    value = dict()
    for _ in range(length):
        key = read_string(stream)
        value[key] = read_dynamic(stream)
    return value


def read_string(stream):
    return read_bytes(stream).decode('utf-8')


def read_varint(stream):
    """Read while the most significant bit is set, then put the 7 least
    significant bits of all read bytes together to create a number.

    """
    value = 0
    while True:
        byte = ord(stream.read(1))
        if not byte & 0b10000000:
            return value << 7 | byte
        value = value << 7 | (byte & 0b01111111)


def read_varint_signed(stream):
    value = read_varint(stream)
    # Least significant bit represents the sign.
    if value & 1:
        return -(value >> 1)
    else:
        return value >> 1


def write_bytes(stream, bytes):
    write_varint(stream, len(bytes))
    stream.write(bytes)


def write_varint(stream, value):
    if value == 0:
        stream.write(b'\x00')
        return
    pieces = []
    while value:
        x, value = value & 0b01111111, value >> 7
        if len(pieces):
            x |= 0b10000000
        pieces.insert(0, x)
        if len(pieces) > 4096:
            raise ValueError('Number too large')
    stream.write(struct.pack('%dB' % len(pieces), *pieces))


def write_varint_signed(stream, value):
    has_sign = 1 if value < 0 else 0
    write_varint(stream, value << 1 | has_sign)
