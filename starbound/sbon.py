# -*- coding: utf-8 -*-

import struct
import sys


if sys.version >= '3':
    _int_type = int
    _str_type = str
    def _byte(x):
        return bytes((x,))
    def _items(d):
        return d.items()
else:
    _int_type = (int, long)
    _str_type = basestring
    range = xrange
    def _byte(x):
        return chr(x)
    def _items(d):
        return d.iteritems()


def read_bytes(stream):
    length = read_varint(stream)
    return stream.read(length)


def read_dynamic(stream):
    type_id = ord(stream.read(1))
    if type_id == 1:
        return None
    elif type_id == 2:
        return struct.unpack('>d', stream.read(8))[0]
    elif type_id == 3:
        return stream.read(1) != b'\0'
    elif type_id == 4:
        return read_varint_signed(stream)
    elif type_id == 5:
        return read_string(stream)
    elif type_id == 6:
        return read_list(stream)
    elif type_id == 7:
        return read_map(stream)
    raise ValueError('Unknown dynamic type 0x%02X' % type_id)


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
        return -(value >> 1) - 1
    else:
        return value >> 1


def write_bytes(stream, value):
    write_varint(stream, len(value))
    stream.write(value)


def write_dynamic(stream, value):
    if value is None:
        stream.write(b'\x01')
    elif isinstance(value, float):
        stream.write(b'\x02')
        stream.write(struct.pack('>d', value))
    elif isinstance(value, bool):
        stream.write(b'\x03\x01' if value else b'\x03\x00')
    elif isinstance(value, _int_type):
        stream.write(b'\x04')
        write_varint_signed(stream, value)
    elif isinstance(value, _str_type):
        stream.write(b'\x05')
        write_string(stream, value)
    elif isinstance(value, list):
        stream.write(b'\x06')
        write_list(stream, value)
    elif isinstance(value, dict):
        stream.write(b'\x07')
        write_map(stream, value)
    else:
        raise ValueError('Cannot write value %r' % (value,))


def write_list(stream, value):
    write_varint(stream, len(value))
    for v in value:
        write_dynamic(stream, v)


def write_map(stream, value):
    write_varint(stream, len(value))
    for k, v in _items(value):
        write_string(stream, k)
        write_dynamic(stream, v)


def write_string(stream, value):
    write_bytes(stream, value.encode('utf-8'))


def write_varint(stream, value):
    buf = _byte(value & 0b01111111)
    value >>= 7
    while value:
        buf = _byte(value & 0b01111111 | 0b10000000) + buf
        value >>= 7
    stream.write(buf)


def write_varint_signed(stream, value):
    write_varint(stream, (-(value + 1) << 1 | 1) if value < 0 else (value << 1))
