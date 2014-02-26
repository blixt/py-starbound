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
    def encode_key(self, key):
        return hashlib.sha256(key.encode('utf-8')).digest()


class KeyStoreCompressed(KeyStore):
    """A B-tree database that uses SHA-256 hashes for key lookup, and inflates
    the data before returning it.

    """
    def deserialize_data(self, data):
        return zlib.decompress(data)


class CelestialChunks(KeyStoreCompressed):
    def deserialize_data(self, data):
        data = super(CelestialChunks, self).deserialize_data(data)
        stream = io.BytesIO(data)
        return sbon.read_document(stream)

    def open(self):
        super(CelestialChunks, self).open()
        assert self.identifier == 'Celestial2', 'Unsupported celestial chunks file'


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


class VariantDatabase(KeyStoreCompressed):
    """A B-tree database where each key is a SHA-256 hash and the value is
    compressed Starbound Variant data.

    """
    def deserialize_data(self, data):
        data = super(VariantDatabase, self).deserialize_data(data)
        stream = io.BytesIO(data)
        return sbon.read_dynamic(stream)

    def encode_key(self, key):
        # TODO: The key encoding for this may be SBON-encoded SHA-256 hash.
        return super(VariantDatabase, self).encode_key(key)

    def open(self):
        super(VariantDatabase, self).open()
        assert self.identifier == 'JSON1', 'Unsupported variant database'


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
    METADATA_KEY = (0, 0, 0)

    TILES_X = 32
    TILES_Y = 32
    TILES_PER_REGION = TILES_X * TILES_Y

    def __init__(self, path):
        super(World, self).__init__(path)
        self._metadata = None
        self._metadata_version = None

    def deserialize_data(self, data):
        return zlib.decompress(data)

    def encode_key(self, key):
        return struct.pack('>BHH', *key)

    def get_entities(self, x, y):
        stream = io.BytesIO(self.get((2, x, y)))
        return sbon.read_document_list(stream)

    def get_metadata(self):
        if self._metadata:
            return self._metadata, self._metadata_version

        stream = io.BytesIO(self.get_raw(World.METADATA_KEY))

        # Not sure what these values mean.
        unknown_1, unknown_2 = struct.unpack('>ii', stream.read(8))

        name, version, data = sbon.read_document(stream)
        assert name == 'WorldMetadata', 'Invalid world data'

        self._metadata = data
        self._metadata_version = version

        return data, version

    def get_tiles(self, x, y):
        stream = io.BytesIO(self.get((1, x, y)))
        unknown = stream.read(3)
        # There are 1024 (32x32) tiles in a region.
        return [sbon.read_tile(stream) for _ in xrange(World.TILES_PER_REGION)]

    def open(self):
        super(World, self).open()
        assert self.identifier == 'World2', 'Tried to open non-world BTreeDB4 file'


class FailedWorld(World):
    def __init__(self, path):
        super(FailedWorld, self).__init__(path)
        self.repair = True

    def get_metadata(self):
        try:
            stream = io.BytesIO(self.get_raw(World.METADATA_KEY))
        except:
            stream = btreedb4.LeafReader.last_buffer
            stream.seek(0)

        # Not sure what these values mean.
        unknown_1, unknown_2 = struct.unpack('>ii', stream.read(8))

        name, version, data = sbon.read_document(stream, True)
        assert name == 'WorldMetadata', 'Invalid world data'

        self._metadata = data
        self._metadata_version = version

        return data, version


def open(path):
    _, extension = os.path.splitext(path)
    if extension == '.chunks':
        file = CelestialChunks(path)
    elif extension in ('.clientcontext', '.dat'):
        file = sbvj01.FileSBVJ01(path)
    elif extension == '.db':
        file = VariantDatabase(path)
    elif extension == '.fail':
        file = FailedWorld(path)
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
