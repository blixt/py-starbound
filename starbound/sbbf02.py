import io
import struct

import filebase


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


class Block(object):
    __metaclass__ = BlockMeta

    types = dict()

    @staticmethod
    def read(file):
        signature = file.read(2)

        if signature == '\x00\x00':
            return None

        if signature not in Block.types:
            raise ValueError('Unrecognized block type')

        # Return a new instance of the appropriate block type.
        return Block.types[signature](file)


class BlockFree(Block):
    SIGNATURE = 'FF'

    __slots__ = ['next_free_block']

    def __init__(self, file):
        value, = struct.unpack('>i', file.read(4))
        self.next_free_block = value if value != -1 else None

    def __str__(self):
        return 'Free(next_free_block={})'.format(self.next_free_block)


class FileSBBF02(filebase.File):
    def __init__(self, path):
        super(FileSBBF02, self).__init__(path)

        self._user_header = None

        self.block_size = None
        self.header_size = None
        self.free_block_is_dirty = None
        self.free_block = None

    def get_block(self, block):
        self._stream.seek(self.header_size + self.block_size * block)
        return Block.read(self)

    def get_user_header(self):
        assert self.is_open(), 'File must be open to get user header'
        return io.BytesIO(self._user_header)

    def open(self):
        """Opens the file and reads its header data.

        """
        super(FileSBBF02, self).open()
        stream = self._stream

        assert stream.read(6) == 'SBBF02', 'Invalid file format'

        # Block header data.
        fields = struct.unpack('>ii?i', stream.read(13))
        self.header_size = fields[0]
        self.block_size = fields[1]
        self.free_block_is_dirty = fields[2]
        self.free_block = fields[3]

        # Read the user header data.
        stream.seek(32)
        self._user_header = stream.read(self.header_size - 32)
