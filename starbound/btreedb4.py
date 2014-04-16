import binascii
import bisect
import io
import struct

from . import sbbf02
from . import sbon


# Override range with xrange when running Python 2.x.
try:
    range = xrange
except:
    pass


class FileBTreeDB4(sbbf02.FileSBBF02):
    """A B-tree database format on top of the SBBF02 block format.

    Note: The developers of this format probably intended for the underlying
    file format to be arbitrary, but this database has pretty strong
    connections to SBBF02 right now so it's been implemented as inheriting from
    that file format. In the future we may want to split away from the
    inheritance chain and instead use the SBBF02 file as an API.

    """
    def __init__(self, stream):
        super(FileBTreeDB4, self).__init__(stream)

        self.key_size = None

        # Set this attribute to True to make reading more forgiving.
        self.repair = False

        self.alternate_root_node = None
        self.root_node = None
        self.root_node_is_leaf = None
        self.other_root_node = None
        self.other_root_node_is_leaf = None

    def commit(self):
        """Alternates the root node.

        """
        self.root_node, self.other_root_node = self.other_root_node, self.root_node
        self.alternate_root_node = not self.alternate_root_node

    def deserialize_data(self, data):
        """Can be overridden to deserialize data before returning it.

        """
        return data

    def encode_key(self, key):
        """Can be overridden to encode a key before looking for it in the
        database (for example if the key needs to be hashed).

        """
        return key

    def get(self, key):
        """Returns the deserialized data for the provided key.

        """
        encoded_key = self.encode_key(key)
        try:
            return self.deserialize_data(self.get_binary(encoded_key))
        except KeyError:
            if encoded_key == key:
                raise KeyError(binascii.hexlify(key))
            else:
                raise KeyError(key, binascii.hexlify(encoded_key))

    def get_binary(self, key):
        """Returns the binary data for the provided pre-encoded key.

        """
        assert len(key) == self.key_size, 'Invalid key length'

        block = self.get_block(self.root_node)

        # Scan down the B-tree until we reach a leaf.
        while isinstance(block, BTreeIndex):
            block_number = block.get_block_for_key(key)
            block = self.get_block(block_number)
        assert isinstance(block, BTreeLeaf), 'Did not reach a leaf'

        return self.get_leaf_value(block, key)

    def get_leaf_value(self, leaf, key):
        stream = LeafReader(self, leaf)

        # The number of keys is read on-demand because only leaves pointed to
        # by an index contain this number (others just contain arbitrary data).
        num_keys, = struct.unpack('>i', stream.read(4))
        assert num_keys < 1000, 'Leaf had unexpectedly high number of keys'
        for i in range(num_keys):
            cur_key = stream.read(self.key_size)
            value = sbon.read_bytes(stream)

            if cur_key == key:
                return value

        raise KeyError(key)

    def get_raw(self, key):
        """Returns the raw data for the provided key.

        """
        return self.get_binary(self.encode_key(key))

    def get_using_encoded_key(self, key):
        """Returns the deserialized data for the provided pre-encoded key.

        """
        return self.deserialize_data(self.get_binary(key))

    def initialize(self):
        super(FileBTreeDB4, self).initialize()
        stream = self.get_user_header()

        # Require that the format of the content is BTreeDB4.
        db_format = sbon.read_fixlen_string(stream, 12)
        assert db_format == 'BTreeDB4', 'Expected binary tree database'

        # Name of the database.
        self.identifier = sbon.read_fixlen_string(stream, 12)

        fields = struct.unpack('>i?xi?xxxi?', stream.read(19))
        self.key_size = fields[0]

        # Whether to use the alternate root node index.
        self.alternate_root_node = fields[1]
        if self.alternate_root_node:
            self.root_node, self.root_node_is_leaf = fields[4:6]
            self.other_root_node, self.other_root_node_is_leaf = fields[2:4]
        else:
            self.root_node, self.root_node_is_leaf = fields[2:4]
            self.other_root_node, self.other_root_node_is_leaf = fields[4:6]


class BTreeIndex(sbbf02.Block):
    SIGNATURE = b'II'

    __slots__ = ['keys', 'level', 'num_keys', 'values']

    def __init__(self, file, block_index):
        self.level, self.num_keys, left_block = struct.unpack('>Bii', file.read(9))

        self.keys = []
        self.values = [left_block]

        for i in range(self.num_keys):
            key = file.read(file.key_size)
            block, = struct.unpack('>i', file.read(4))

            self.keys.append(key)
            self.values.append(block)

    def __str__(self):
        return 'Index(level={}, num_keys={})'.format(self.level, self.num_keys)

    def get_block_for_key(self, key):
        i = bisect.bisect_right(self.keys, key)
        return self.values[i]


class BTreeLeaf(sbbf02.Block):
    SIGNATURE = b'LL'

    __slots__ = ['data', 'next_block']

    def __init__(self, file, block_index):
        # Substract 6 for signature and next_block.
        self.data = file.read(file.block_size - 6)

        value, = struct.unpack('>i', file.read(4))
        self.next_block = value if value != -1 else None

    def __str__(self):
        return 'Leaf(next_block={})'.format(self.next_block)


class BTreeRestoredLeaf(BTreeLeaf):
    def __init__(self, free_block):
        assert isinstance(free_block, sbbf02.BlockFree), 'Expected free block'
        self.data = free_block.raw_data[:-4]

        value, = struct.unpack('>i', free_block.raw_data[-4:])
        self.next_block = value if value != -1 else None

    def __str__(self):
        return 'RestoredLeaf(next_block={})'.format(self.next_block)


class LeafReader(object):
    """A pseudo-reader that will cross over block boundaries if necessary.

    """
    __slots__ = ['_file', '_leaf', '_offset', '_visited']

    def __init__(self, file, leaf):
        assert isinstance(file, FileBTreeDB4), 'File is not a FileBTreeDB4 instance'
        assert isinstance(leaf, BTreeLeaf), 'Leaf is not a BTreeLeaf instance'

        self._file = file
        self._leaf = leaf
        self._offset = 0
        self._visited = [leaf.index]

    def read(self, length):
        offset = self._offset

        if offset + length <= len(self._leaf.data):
            self._offset += length
            return self._leaf.data[offset:offset + length]

        buffer = io.BytesIO()

        # If the file is in repair mode, make the buffer available globally.
        if self._file.repair:
            LeafReader.last_buffer = buffer

        # Exhaust current leaf.
        num_read = buffer.write(self._leaf.data[offset:])
        length -= num_read

        # Keep moving onto the next leaf until we have read the desired amount.
        while length > 0:
            next_block = self._leaf.next_block

            assert next_block is not None, 'Tried to read too far'
            assert next_block not in self._visited, 'Tried to read visited block'
            self._visited.append(next_block)

            self._leaf = self._file.get_block(next_block)
            if self._file.repair and isinstance(self._leaf, sbbf02.BlockFree):
                self._leaf = BTreeRestoredLeaf(self._leaf)

            assert isinstance(self._leaf, BTreeLeaf), \
                'Leaf pointed to non-leaf %s after reading %d byte(s)' % (
                        next_block, buffer.tell())

            num_read = buffer.write(self._leaf.data[:length])
            length -= num_read

        # The new offset will be how much was read from the current leaf.
        self._offset = num_read

        data = buffer.getvalue()
        buffer.close()

        return data
