"""I call Starbound's binary serialization format SBON because it could've been
BSON, but isn't. :)

"""

import struct

def read_bytes(stream):
    length = read_varlen_number(stream)
    return stream.read(length)

def read_dynamic(stream):
    type = ord(stream.read(1))
    if type == 1:
        return None
    if type == 4:
        return read_varlen_number_signed(stream)
    if type == 5:
        return read_string(stream)
    if type == 6:
        return read_list(stream)
    if type == 7:
        return read_map(stream)

    if type == 2:
        format = '>d'
    elif type == 3:
        format = '?'
    else:
        raise ValueError('Unknown dynamic type 0x%02X' % type)
    return struct.unpack(format, stream.read(struct.calcsize(format)))[0]

def read_list(stream):
    length = read_varlen_number(stream)
    return [read_dynamic(stream) for _ in xrange(length)]

def read_map(stream):
    length = read_varlen_number(stream)

    value = dict()
    for _ in xrange(length):
        key = read_string(stream)
        value[key] = read_dynamic(stream)

    return value

def read_string(stream):
    return read_bytes(stream).decode('utf-8')

def read_varlen_number(stream):
    """Read while the most significant bit is set, then put the 7 least
    significant bits of all read bytes together to create a number.

    """
    value = 0
    while True:
        byte = ord(stream.read(1))
        if not byte & 0b10000000:
            return value << 7 | byte
        value = value << 7 | (byte & 0b01111111)

def read_varlen_number_signed(stream):
    value = read_varlen_number(stream)

    # Least significant bit represents the sign.
    if value & 1:
        return -(value >> 1)
    else:
        return value >> 1
