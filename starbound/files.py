import hashlib
import io
import os
import sbbf02
import sbon
import struct


class StarKeyStore(sbbf02.StarFile):
    def get(self, key):
        # Get the SHA-256 hash of the key.
        key = hashlib.sha256(key.encode('utf-8')).digest()
        return super(StarPackage, self).get(key)


class StarPackage(StarKeyStore):
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


class StarWorld(sbbf02.StarFile):
    WORLD_DATA_KEY = '\x00\x00\x00\x00\x00'

    def __init__(self, path):
        super(StarWorld, self).__init__(path)
        self._world_data = None

    def get_world_data(self):
        if self._world_data:
            return self._world_data

        stream = io.BytesIO(self.get(StarWorld.WORLD_DATA_KEY))

        # Not sure what these values mean.
        unknown_1, unknown_2 = struct.unpack('>ii', stream.read(8))

        assert sbon.read_string(stream) == 'WorldMetadata', 'Invalid world data'

        # Skip 5 unknown bytes before world data starts.
        stream.seek(5, 1)

        # Read the huge world data map.
        self._world_data = sbon.read_dynamic(stream)

        return self._world_data

    def open(self):
        super(StarWorld, self).open()
        assert self.name == 'World2', 'Tried to open non-world SBBF02 file'


def open(path):
    _, extension = os.path.splitext(path)
    if extension == '.db':
        file = StarKeyStore(path)
    elif extension == '.pak':
        file = StarPackage(path)
    elif extension in ('.shipworld', '.world'):
        file = StarWorld(path)
    else:
        raise ValueError('Unrecognized file extension')

    file.open()
    return file
