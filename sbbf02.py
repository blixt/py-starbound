import bisect
import io
import struct


def read_fixlen_string(stream, length):
    return stream.read(length).rstrip('\x00').decode('utf-8')

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


class StarBlock(object):
    @staticmethod
    def read(file):
        signature = file.read(2)

        if signature == '\x00\x00':
            return None

        for block_type in (StarBlockFreeIndex, StarBlockIndex, StarBlockLeaf):
            if signature == block_type.SIGNATURE:
                return block_type(file)

        raise ValueError('Unrecognized block type')

class StarBlockFreeIndex(StarBlock):
    SIGNATURE = 'FF'

    __slots__ = ['next_free_block']

    def __init__(self, file):
        value, = struct.unpack('>i', file.read(4))
        self.next_free_block = value if value != -1 else None

    def __str__(self):
        return '<FreeIndex, next_free_block={}>'.format(self.next_free_block)

class StarBlockIndex(StarBlock):
    SIGNATURE = 'II'

    __slots__ = ['keys', 'level', 'num_keys', 'values']

    def __init__(self, file):
        self.level, self.num_keys, left_block = struct.unpack('>Bii', file.read(9))

        self.keys = []
        self.values = [left_block]

        for i in xrange(self.num_keys):
            key = file.read(file.key_size)
            block, = struct.unpack('>i', file.read(4))

            self.keys.append(key)
            self.values.append(block)

    def __str__(self):
        return '<Index, level={}, num_keys={}>'.format(self.level, self.num_keys)

    def get_block_for_key(self, key):
        i = bisect.bisect_right(self.keys, key)
        return self.values[i]

class StarBlockLeaf(StarBlock):
    SIGNATURE = 'LL'

    __slots__ = ['data', 'next_block']

    def __init__(self, file):
        # Substract 6 for signature and next_block.
        self.data = file.read(file.block_size - 6)

        value, = struct.unpack('>i', file.read(4))
        self.next_block = value if value != -1 else None

    def __str__(self):
        return '<Leaf, next_block={}>'.format(self.next_block)


class LeafReader(object):
    """A pseudo-reader that will cross over block boundaries if necessary.

    """
    __slots__ = ['_file', '_leaf', '_offset']

    def __init__(self, file, leaf):
        assert isinstance(file, StarFile), 'File is not a StarFile instance'
        assert isinstance(leaf, StarBlockLeaf), 'Leaf is not a StarBlockLeaf instance'

        self._file = file
        self._leaf = leaf
        self._offset = 0

    def read(self, length):
        offset = self._offset

        if offset + length < len(self._leaf.data):
            self._offset += length
            return self._leaf.data[offset:offset + length]

        buffer = io.BytesIO()

        # Exhaust current leaf.
        num_read = buffer.write(self._leaf.data[offset:])
        length -= num_read

        # Keep moving onto the next leaf until we have read the desired amount.
        while length > 0:
            assert self._leaf.next_block is not None, 'Tried to read too far'
            self._leaf = self._file.get_block(self._leaf.next_block)
            assert isinstance(self._leaf, StarBlockLeaf), 'Leaf pointed to non-leaf'

            num_read = buffer.write(self._leaf.data[:length])
            length -= num_read

        # The new offset will be how much was read from the current leaf.
        self._offset = num_read

        data = buffer.getvalue()
        buffer.close()

        return data


class StarFile(object):
    def __init__(self, path):
        self._stream = None

        self.path = path
        self.name = None

        self.block_size = None
        self.header_size = None
        self.key_size = None

        self.free_index_block = None
        self.root_block = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.is_open():
            self.close()

    def __str__(self):
        if self.is_open():
            return '<{}: "{}">'.format(self.path, self.name)
        else:
            return '<{}: closed>'.format(self.path)

    def close(self):
        assert self._stream, 'File is not open'
        self._stream.close()
        self._stream = None

    def get(self, key):
        block = self.get_block(self.root_block)
        while not isinstance(block, StarBlockLeaf):
            block_number = block.get_block_for_key(key)
            block = self.get_block(block_number)
        return self.get_leaf_value(block, key)

    def get_block(self, block):
        self._stream.seek(self.header_size + self.block_size * block)
        return StarBlock.read(self)

    def get_leaf_value(self, leaf, key):
        stream = LeafReader(self, leaf)

        # The number of keys is read on-demand because only leaves pointed to
        # by an index contain this number (others just contain arbitrary data).
        num_keys, = struct.unpack('>i', stream.read(4))
        for i in xrange(num_keys):
            cur_key = stream.read(self.key_size)
            value_length = read_varlen_number(stream)
            value = stream.read(value_length)

            if cur_key == key:
                return value

        raise KeyError(key)

    def is_open(self):
        return self._stream is not None

    def open(self):
        """Opens the file and reads its header data.

        """
        assert self._stream is None, 'File is already open'
        stream = open(self.path)
        self._stream = stream

        assert stream.read(6) == 'SBBF02', 'Invalid file format'

        # Header and block size.
        self.header_size, self.block_size, self.bool_1, self.free_index_block = struct.unpack('>ii?i', stream.read(13))

        # Skip ahead to content header.
        stream.seek(32)

        # Require that the format of the content is BTreeDB4.
        db_format = read_fixlen_string(stream, 12)
        assert db_format == 'BTreeDB4', 'Expected binary tree database'

        # Name of the database.
        self.name = read_fixlen_string(stream, 12)

        self.key_size, use_second_value, value_1, value_1_bool, value_2, value_2_bool = struct.unpack('>i?xi?xxxi?', stream.read(19))

        if use_second_value:
            self.root_block = value_2
        else:
            self.root_block = value_1

    def read(self, length):
        return self._stream.read(length)
