import hashlib
import io
import os
import struct
import zlib

import sbbf02
import sbvj01
import sbon


class StarKeyStore(sbbf02.StarFileSBBF02):
    """A B-tree database that uses SHA-256 hashes for key lookup.

    """
    def get(self, key):
        # Get the SHA-256 hash of the key.
        key = hashlib.sha256(key.encode('utf-8')).digest()
        return super(StarKeyStore, self).get(key)


class StarPackage(StarKeyStore):
    """A B-tree database representing a package of files.

    """
    DIGEST_KEY = '_digest'
    INDEX_KEY = '_index'

    def __init__(self, path):
        super(StarPackage, self).__init__(path)
        self._index = None

    def get_digest(self):
        return self.get(StarPackage.DIGEST_KEY)

    def get_index(self):
        if self._index:
            return self._index

        stream = io.BytesIO(self.get(StarPackage.INDEX_KEY))
        self._index = sbon.read_string_list(stream)
        return self._index


class StarPlayer(sbvj01.StarFileSBVJ01):
    """A Starbound character.

    """
    def __init__(self, path):
        super(StarPlayer, self).__init__(path)
        self.name = None

    def open(self):
        super(StarPlayer, self).open()
        assert self.identifier == 'PlayerEntity', 'Invalid player file'
        self.name = self.data['identity']['name']


class StarWorld(sbbf02.StarFileSBBF02):
    """A single Starbound world.

    """
    WORLD_DATA_KEY = '\x00\x00\x00\x00\x00'

    def __init__(self, path):
        super(StarWorld, self).__init__(path)
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

    def get_world_data(self):
        if self._world_data:
            return self._world_data

        stream = io.BytesIO(self.get(StarWorld.WORLD_DATA_KEY))

        # Not sure what these values mean.
        unknown_1, unknown_2 = struct.unpack('>ii', stream.read(8))

        name, data = sbon.read_document(stream)
        assert name == 'WorldMetadata', 'Invalid world data'

        self._world_data = data
        return data

    def open(self):
        super(StarWorld, self).open()
        assert self.identifier == 'World2', 'Tried to open non-world SBBF02 file'


def open(path):
    _, extension = os.path.splitext(path)
    if extension == '.db':
        file = StarKeyStore(path)
    elif extension == '.pak':
        file = StarPackage(path)
    elif extension == '.player':
        file = StarPlayer(path)
    elif extension in ('.shipworld', '.world'):
        file = StarWorld(path)
    else:
        raise ValueError('Unrecognized file extension')

    file.open()
    return file
