import struct

def read_bytes(stream):
    length = read_varlen_number(stream)
    return stream.read(length)

def read_document(stream):
    name = read_string(stream)

    # Not sure what this part is.
    assert stream.read(5) == '\x01\x00\x00\x00\x01'

    data = read_dynamic(stream)

    return name, data

def read_dynamic(stream):
    type = ord(stream.read(1))
    if type == 1:
        return None
    elif type == 2:
        format = '>d'
    elif type == 3:
        format = '?'
    elif type == 4:
        return read_varlen_number_signed(stream)
    elif type == 5:
        return read_string(stream)
    elif type == 6:
        return read_list(stream)
    elif type == 7:
        return read_map(stream)
    else:
        raise ValueError('Unknown dynamic type 0x%02X' % type)

    # Anything that passes through is assumed to have set a format to unpack.
    return struct.unpack(format, stream.read(struct.calcsize(format)))[0]

def read_fixlen_string(stream, length):
    return stream.read(length).rstrip('\x00').decode('utf-8')

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

def read_string_list(stream):
    """Optimized structure that doesn't have a type byte for every item.

    """
    length = read_varlen_number(stream)
    return [read_string(stream) for _ in xrange(length)]

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
