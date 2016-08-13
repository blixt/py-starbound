# -*- coding: utf-8 -*-

from collections import namedtuple
import hashlib
import io
import struct
import zlib

from . import sbon
from .btreedb5 import BTreeDB5
from .sbasset6 import SBAsset6


# Override range with xrange when running Python 2.x.
try:
    range = xrange
except:
    pass


class CelestialChunks(BTreeDB5):
    def get(self, key):
        key = hashlib.sha256(key.encode('utf-8')).digest()
        data = super(CelestialChunks, self).get(key)
        data = zlib.decompress(data)
        stream = io.BytesIO(data)
        return read_versioned_json(stream)

    def read_header(self):
        super(CelestialChunks, self).read_header()
        assert self.name == 'Celestial2', 'Invalid header'


Tile = namedtuple('Tile', [
    'foreground_material',
    'foreground_hue_shift',
    'foreground_variant',
    'foreground_mod',
    'foreground_mod_hue_shift',
    'background_material',
    'background_hue_shift',
    'background_variant',
    'background_mod',
    'background_mod_hue_shift',
    'liquid',
    'liquid_level',
    'liquid_pressure',
    'liquid_infinite',
    'collision',
    'dungeon_id',
    'biome',
    'biome_2',
    'indestructible',
])


VersionedJSON = namedtuple('VersionedJSON', ['name', 'version', 'data'])


class World(BTreeDB5):
    def get(self, layer, x, y):
        # World keys are based on a layer followed by X and Y coordinates.
        data = super(World, self).get(struct.pack('>BHH', layer, x, y))
        return zlib.decompress(data)

    def get_entities(self, x, y):
        stream = io.BytesIO(self.get(2, x, y))
        count = sbon.read_varint(stream)
        return [read_versioned_json(stream) for _ in range(count)]

    def get_tiles(self, x, y):
        stream = io.BytesIO(self.get(1, x, y))
        # TODO: Figure out what this means.
        unknown = stream.read(3)
        # There are 1024 (32x32) tiles in a region.
        return [self.read_tile(stream) for _ in range(1024)]

    def read_header(self):
        super(World, self).read_header()
        assert self.name == 'World4', 'Not a World4 file'

    def read_metadata(self):
        # World metadata is held at a special layer/x/y combination.
        stream = io.BytesIO(self.get(0, 0, 0))
        self.width, self.height = struct.unpack('>ii', stream.read(8))
        name, version, data = read_versioned_json(stream)
        assert name == 'WorldMetadata', 'Invalid world data'
        self.metadata = data
        self.metadata_version = version

    @classmethod
    def read_tile(cls, stream):
        values = struct.unpack('>hBBhBhBBhBBffBBHBB?', stream.read(30))
        return Tile(*values)


def read_sbvj01(stream):
    assert stream.read(6) == b'SBVJ01', 'Invalid header'
    return read_versioned_json(stream)


def read_versioned_json(stream):
    name = sbon.read_string(stream)
    # Not sure what this part is.
    assert stream.read(1) == b'\x01'
    version, = struct.unpack('>i', stream.read(4))
    data = sbon.read_dynamic(stream)
    return VersionedJSON(name, version, data)


def write_sbvj01(stream, vj):
    stream.write(b'SBVJ01')
    write_versioned_json(stream, vj)


def write_versioned_json(stream, vj):
    sbon.write_string(stream, vj.name)
    stream.write(struct.pack('>bi', 1, vj.version))
    sbon.write_dynamic(stream, vj.data)
