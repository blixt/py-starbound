import struct
import sys


def read_null_terminated_string(handle):
    """Super naive implementation..."""
    value = ''
    while True:
        char = handle.read(1)
        if char == '\x00':
            return value
        value += char


class StarBlock(object):
    @staticmethod
    def read_id(data):
        if data == '\xff\xff\xff\xff':
            return None
        return struct.unpack('>I', data)[0]

    @staticmethod
    def create(data):
        signature = data[:2]

        if signature == 'FF':
            return StarBlockFreeIndex(data)
        elif signature == 'II':
            return StarBlockIndex(data)
        elif signature == 'LL':
            return StarBlockLeaf(data)
        elif signature == '\x00\x00':
            return None
        else:
            raise ValueError('Unrecognized block type')

class StarBlockFreeIndex(StarBlock):
    """The root block is always of this type."""
    SIGNATURE = 'FF'

    def __init__(self, data):
        self.next_id = StarBlock.read_id(data[2:6])

    def __str__(self):
        return 'StarBlockFreeIndex(next_id={})'.format(self.next_id)

class StarBlockIndex(StarBlock):
    SIGNATURE = 'II'

    def __init__(self, data):
        self.v1 = struct.unpack('>B', data[2])[0]
        self.v2 = struct.unpack('>I', data[3:7])[0]
        self.v3 = struct.unpack('>I', data[7:11])[0]

    def __str__(self):
        return ''

class StarBlockLeaf(StarBlock):
    """The blocks that contain actual data."""
    SIGNATURE = 'LL'

    def __init__(self, data):
        self.next_id = StarBlock.read_id(data[-4:])
        # TODO: Is it possible to exclude trailing 0x00?
        self.data = data[2:-4]


class StarFile(object):
    def __init__(self, path):
        self.path = path

        self.name = None
        self.header_size = None
        self.block_size = None

        self.root_id = None
        self.blocks = []

    def _read_user_header(self, handle):
        assert handle.read(6) == 'SBBF02', 'Invalid file format'

        # Size of this header.
        self.header_size = struct.unpack('>I', handle.read(4))[0]
        assert self.header_size == 512, 'Unknown header size'

        # Size of all following blocks.
        self.block_size = struct.unpack('>I', handle.read(4))[0]
        assert self.block_size in (512, 2048), 'Unknown block size'

        # Not sure what this byte is.
        self.unknown = handle.read(1)
        assert self.unknown in ('\x00', '\x01')

        # The id of the root node in the binary tree.
        self.root_id = struct.unpack('>I', handle.read(4))[0]

        # We could seek to byte 32, but let's verify there's no data we haven't parsed.
        assert handle.read(13) == '\x00' * 13

        # Validate database format header.
        assert handle.read(8) == 'BTreeDB4', 'Expected binary tree database'
        assert handle.read(4) == '\x00' * 4

        # Name of the database.
        self.name = read_null_terminated_string(handle)

        # Read remainder of block.
        handle.read(self.header_size - handle.tell())

    def _read_blocks(self, handle):
        # TODO: In the future, this should probably start with the root block
        # work down the tree.
        while True:
            data = handle.read(self.block_size)
            if not data:
                break
            assert len(data) == self.block_size, 'Encountered incomplete block'

            try:
                block = StarBlock.create(data)
            except Exception, e:
                raise Exception('Encountered unknown block at block #{} ({})'.format(len(self.blocks), e))

            if block is None:
                sys.stdout.write('0')
            else:
                sys.stdout.write(block.SIGNATURE[0])

            self.blocks.append(block)

    def get_root(self):
        assert self.root_id is not None, 'No known root'
        return self.blocks[self.root_id]

    def parse(self):
        with open(self.path) as handle:
            self._read_user_header(handle)
            print '{} ({})'.format(self.name, self.path)
            print 'Header size: {}   Block size: {}   Root block id: {}'.format(self.header_size, self.block_size, self.root_id)
            self._read_blocks(handle)
            print
            print 'Read {} blocks.'.format(len(self.blocks))
        return True
