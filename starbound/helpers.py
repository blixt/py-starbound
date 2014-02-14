import hashlib
import binascii
import io
import os
import struct
import zlib

import btreedb4
import sbvj01
import sbon


class KeyStore(btreedb4.FileBTreeDB4):
    """A B-tree database that uses SHA-256 hashes for key lookup.

    """
    def get(self, key):
        # Get the SHA-256 hash of the key.
        hashed_key = hashlib.sha256(key.encode('utf-8')).digest()
        try:
            return super(KeyStore, self).get(hashed_key)
        except KeyError:
            raise KeyError('%s (%s)' % (key, binascii.hexlify(hashed_key)))


class Package(KeyStore):
    """A B-tree database representing a package of files.

    """
    DIGEST_KEY = '_digest'
    INDEX_KEY = '_index'

    def __init__(self, path):
        super(Package, self).__init__(path)
        self._index = None

    def get_digest(self):
        return self.get(Package.DIGEST_KEY)

    def get_index(self):
        if self._index:
            return self._index

        stream = io.BytesIO(self.get(Package.INDEX_KEY))
        self._index = sbon.read_string_list(stream)
        return self._index


class Player(sbvj01.FileSBVJ01):
    """A Starbound character.

    """
    def __init__(self, path):
        super(Player, self).__init__(path)
        self.name = None

    def open(self):
        super(Player, self).open()
        assert self.identifier == 'PlayerEntity', 'Invalid player file'
        self.name = self.data['identity']['name']


class World(btreedb4.FileBTreeDB4):
    """A single Starbound world.

    """
    DATA_KEY = '\x00\x00\x00\x00\x00'

    TILES_X = 32
    TILES_Y = 32
    TILES_PER_REGION = TILES_X * TILES_Y

    def __init__(self, path):
        super(World, self).__init__(path)
        self._world_data = None

    def get_entities(self, x, y):
        stream = io.BytesIO(self.get_region_data(x, y, 2))
        return sbon.read_document_list(stream)

    def get_region_data(self, x, y, layer=1):
        """Get the raw data for a region. Regions are sets of 32x32 in-game
        tiles. Layer 1 holds tile data and layer 2 holds entity data.

        """
        key = struct.pack('>BHH', layer, x, y)
        return zlib.decompress(self.get(key))

    def get_tiles(self, x, y):
        stream = io.BytesIO(self.get_region_data(x, y, 1))
        unknown = stream.read(3)
        # There are 1024 (32x32) tiles in a region.
        return [sbon.read_tile(stream) for _ in xrange(World.TILES_PER_REGION)]

    def get_world_data(self):
        if self._world_data:
            return self._world_data

        stream = io.BytesIO(self.get(World.DATA_KEY))

        # Not sure what these values mean.
        unknown_1, unknown_2 = struct.unpack('>ii', stream.read(8))

        name, data = sbon.read_document(stream)
        assert name == 'WorldMetadata', 'Invalid world data'

        self._world_data = data
        return data

    def open(self):
        super(World, self).open()
        assert self.identifier == 'World2', 'Tried to open non-world BTreeDB4 file'


def open(path):
    _, extension = os.path.splitext(path)
    if extension == '.clientcontext':
        file = sbvj01.FileSBVJ01(path)
    elif extension == '.db':
        file = KeyStore(path)
    elif extension in ('.modpak', '.pak'):
        file = Package(path)
    elif extension == '.player':
        file = Player(path)
    elif extension in ('.shipworld', '.world'):
        file = World(path)
    else:
        raise ValueError('Unrecognized file extension')

    file.open()
    return file
