import io
import struct

from . import filebase


class BlockMeta(type):
    """Metaclass that registers all subclasses of Block as block types.

    """
    def __new__(mcs, name, bases, dict):
        cls = type.__new__(mcs, name, bases, dict)
        try:
            if Block in bases:
                sig = dict.get('SIGNATURE')
                assert sig and len(sig) == 2, 'Invalid signature'
                assert sig not in Block.types, 'Duplicate signature'
                Block.types[sig] = cls
        except NameError:
            # The first time this function is called, Block will not be
            # defined.
            pass
        return cls


# This is a hacky way of implementing the metaclass, but it works for both
# Python 2.x and 3.
class Block(BlockMeta('Block', (object,), {})):
    types = dict()

    __slots__ = ['index']

    @staticmethod
    def read(file, block_index):
        signature = file.read(2)

        if signature == b'\x00\x00':
            return None

        if signature not in Block.types:
            raise ValueError('Unrecognized block type')

        # Return a new instance of the appropriate block type.
        block = Block.types[signature](file, block_index)
        block.index = block_index
        return block


class BlockFree(Block):
    SIGNATURE = b'FF'

    __slots__ = ['next_free_block', 'raw_data']

    def __init__(self, file, block_index):
        self.raw_data = file.read(file.block_size - 2)
        value, = struct.unpack('>i', self.raw_data[:4])
        self.next_free_block = value if value != -1 else None

    def __str__(self):
        return 'Free(next_free_block={})'.format(self.next_free_block)


class FileSBBF02(filebase.File):
    def __init__(self, stream):
        super(FileSBBF02, self).__init__(stream)

        self._user_header = None

        self.block_size = None
        self.header_size = None
        self.free_block_is_dirty = None
        self.free_block = None
        self.num_blocks = None

    def get_block(self, block_index):
        self._stream.seek(self.header_size + self.block_size * block_index)
        return Block.read(self, block_index)

    def get_user_header(self):
        return io.BytesIO(self._user_header)

    def initialize(self):
        """Reads the header data.

        """
        super(FileSBBF02, self).initialize()
        stream = self._stream

        assert stream.read(6) == b'SBBF03', 'Invalid file format'

        # Block header data.
        fields = struct.unpack('>ii?i', stream.read(13))
        self.header_size = fields[0]
        self.block_size = fields[1]
        self.free_block_is_dirty = fields[2]
        self.free_block = fields[3]

        # Calculate the number of blocks in the file.
        stream.seek(0, 2)
        self.num_blocks = (stream.tell() - self.header_size) // self.block_size

        # Read the user header data.
        stream.seek(32)
        self._user_header = stream.read(self.header_size - 32)
