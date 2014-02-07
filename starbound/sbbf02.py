import bisect
import io
import struct

import filebase
import sbon


class StarBlock(object):
    @staticmethod
    def read(file):
        signature = file.read(2)

        if signature == '\x00\x00':
            return None

        for block_type in (StarBlockFree, StarBlockIndex, StarBlockLeaf):
            if signature == block_type.SIGNATURE:
                return block_type(file)

        raise ValueError('Unrecognized block type')

class StarBlockFree(StarBlock):
    SIGNATURE = 'FF'

    __slots__ = ['next_free_block']

    def __init__(self, file):
        value, = struct.unpack('>i', file.read(4))
        self.next_free_block = value if value != -1 else None

    def __str__(self):
        return 'Free(next_free_block={})'.format(self.next_free_block)

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
        return 'Index(level={}, num_keys={})'.format(self.level, self.num_keys)

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
        return 'Leaf(next_block={})'.format(self.next_block)


class LeafReader(object):
    """A pseudo-reader that will cross over block boundaries if necessary.

    """
    __slots__ = ['_file', '_leaf', '_offset']

    def __init__(self, file, leaf):
        assert isinstance(file, StarFileSBBF02), 'File is not a StarFileSBBF02 instance'
        assert isinstance(leaf, StarBlockLeaf), 'Leaf is not a StarBlockLeaf instance'

        self._file = file
        self._leaf = leaf
        self._offset = 0

    def read(self, length):
        offset = self._offset

        if offset + length <= len(self._leaf.data):
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


class StarFileSBBF02(filebase.StarFile):
    def __init__(self, path):
        super(StarFileSBBF02, self).__init__(path)

        self.block_size = None
        self.header_size = None
        self.free_block_is_dirty = None
        self.free_block = None

        # TODO: Move into new class (BTreeDB4)
        self.key_size = None
        self.root_node = None

    def get(self, key):
        assert self.is_open(), 'Tried to get from closed file'
        assert len(key) == self.key_size, 'Invalid key length'

        block = self.get_block(self.root_node)

        # Scan down the B-tree until we reach a leaf.
        while isinstance(block, StarBlockIndex):
            block_number = block.get_block_for_key(key)
            block = self.get_block(block_number)
        assert isinstance(block, StarBlockLeaf), 'Did not reach a leaf'

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
            value = sbon.read_bytes(stream)

            if cur_key == key:
                return value

        raise KeyError(key)

    def open(self):
        """Opens the file and reads its header data.

        """
        super(StarFileSBBF02, self).open()
        stream = self._stream

        assert stream.read(6) == 'SBBF02', 'Invalid file format'

        # Block header data.
        fields = struct.unpack('>ii?i', stream.read(13))
        self.header_size = fields[0]
        self.block_size = fields[1]
        self.free_block_is_dirty = fields[2]
        self.free_block = fields[3]

        # Skip ahead to user header.
        stream.seek(32)

        # TODO: Move into new class (BTreeDB4)
        # Require that the format of the content is BTreeDB4.
        db_format = sbon.read_fixlen_string(stream, 12)
        assert db_format == 'BTreeDB4', 'Expected binary tree database'

        # Name of the database.
        self.identifier = sbon.read_fixlen_string(stream, 12)

        fields = struct.unpack('>i?xi?xxxi?', stream.read(19))
        self.key_size = fields[0]

        # Whether to use the alternate root node index.
        if fields[1]:
            self.root_node, self.root_node_is_leaf = fields[4:6]
        else:
            self.root_node, self.root_node_is_leaf = fields[2:4]
