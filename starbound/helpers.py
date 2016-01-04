import binascii
import hashlib
import io
import os
import re
import struct
import zlib

from . import btreedb4
from . import sbvj01
from . import sbon

try:
    import builtins
except:
    import __builtin__ as builtins

# Override range with xrange when running Python 2.x.
try:
    range = xrange
except:
    pass


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

    def initialize(self):
        super(CelestialChunks, self).initialize()
        assert self.identifier == 'Celestial2', 'Unsupported celestial chunks file'


class Package(KeyStore):
    """A B-tree database representing a package of files.

    """
    DIGEST_KEY = '_digest'
    INDEX_KEY = '_index'

    def __init__(self, path):
        super(Package, self).__init__(path)
        self._index = None

    def encode_key(self, key):
        return super(Package, self).encode_key(key.lower())

    def get_digest(self):
        return self.get(Package.DIGEST_KEY)

    def get_index(self):
        if self._index:
            return self._index

        stream = io.BytesIO(self.get(Package.INDEX_KEY))
        if self.identifier == 'Assets1':
            self._index = sbon.read_string_list(stream)
        elif self.identifier == 'Assets2':
            self._index = sbon.read_string_digest_map(stream)

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

    def initialize(self):
        super(VariantDatabase, self).initialize()
        assert self.identifier == 'JSON1', 'Unsupported variant database'


class Player(sbvj01.FileSBVJ01):
    """A Starbound character.

    """
    def __init__(self, path):
        super(Player, self).__init__(path)
        self.name = None

    def initialize(self):
        super(Player, self).initialize()
        assert self.identifier == 'PlayerEntity', 'Invalid player file'
        self.name = self.data['identity']['name']


class World(btreedb4.FileBTreeDB4):
    """A single Starbound world.

    """
    METADATA_KEY = (0, 0, 0)

    TILES_X = 32
    TILES_Y = 32
    TILES_PER_REGION = TILES_X * TILES_Y

    def __init__(self, stream):
        super(World, self).__init__(stream)
        self.width = None
        self.height = None
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

        # Read the data and decompress it.
        data = self.get_raw(World.METADATA_KEY)
        if self._world_version >= 4:
            data = zlib.decompress(data)
        stream = io.BytesIO(data)

        self.width, self.height = struct.unpack('>ii', stream.read(8))
        name, version, data = sbon.read_document(stream)
        assert name == 'WorldMetadata', 'Invalid world data'

        self._metadata = data
        self._metadata_version = version

        return data, version

    def get_tiles(self, x, y):
        stream = io.BytesIO(self.get((1, x, y)))
        unknown = stream.read(3)
        # There are 1024 (32x32) tiles in a region.
        return [sbon.read_tile(self._metadata_version, stream)
                for _ in range(World.TILES_PER_REGION)]

    def initialize(self):
        super(World, self).initialize()
        match = re.match('^World(\d+)$', self.identifier)
        if not match:
            raise ValueError('Unexpected BTreeDB4 identifier %s' % (self.identifier,))
        self._world_version = int(match.group(1))


class FailedWorld(World):
    def __init__(self, stream):
        super(FailedWorld, self).__init__(stream)
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


EXTENSION_TO_CLASS = dict(
    chunks=CelestialChunks,
    clientcontext=sbvj01.FileSBVJ01,
    dat=sbvj01.FileSBVJ01,
    db=VariantDatabase,
    fail=FailedWorld,
    modpak=Package,
    pak=Package,
    player=Player,
    shipworld=World,
    world=World,
)


def open(path, override_extension=None):
    """Read the file located at the specified path. The file format will be
    guessed from the extension, or (if provided) using the extension override.

    """
    extension = override_extension or os.path.splitext(path)[1][1:]
    return read_stream(builtins.open(path, 'rb'), extension)

def read_stream(stream, extension):
    cls = EXTENSION_TO_CLASS.get(extension)
    if not cls:
        raise ValueError('Unsupported file extension "%s"' % extension)
    file = cls(stream)
    file.initialize()
    return file
