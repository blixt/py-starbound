# -*- coding: utf-8 -*-

from collections import namedtuple
import hashlib
import io
import struct
import zlib

from . import sbon
from .btreedb5 import BTreeDB5
from .sbasset6 import SBAsset6

__version__ = '1.0.0'

# Override range with xrange when running Python 2.x.
try:
    range = xrange
except:
    pass


# Utility descriptor for memoized properties.
class lazyproperty(object):
    def __init__(self, fget):
        self.fget = fget
        self.__doc__ = fget.__doc__
        self.propname = '_lazyproperty_{}'.format(self.fget.__name__)

    def __delete__(self, obj):
        if hasattr(obj, self.propname):
            delattr(obj, self.propname)

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        if not hasattr(obj, self.propname):
            setattr(obj, self.propname, self.fget(obj))
        return getattr(obj, self.propname)

    def __set__(self, obj, value):
        setattr(obj, self.propname, value)


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
    @lazyproperty
    def info(self):
        if not hasattr(self, 'metadata'):
            self.read_metadata()
        return WorldInfo(self.metadata)

    def get(self, layer, x, y):
        # World keys are based on a layer followed by X and Y coordinates.
        data = super(World, self).get(struct.pack('>BHH', layer, x, y))
        return zlib.decompress(data)

    def get_all_regions_with_tiles(self):
        """
        Generator which yields a set of (rx, ry) tuples which describe
        all regions for which the world has tile data
        """
        for key in self.get_all_keys():
            (layer, rx, ry) = struct.unpack('>BHH', key)
            if layer == 1:
                yield (rx, ry)

    def get_entities(self, x, y):
        stream = io.BytesIO(self.get(2, x, y))
        count = sbon.read_varint(stream)
        return [read_versioned_json(stream) for _ in range(count)]

    def get_entity_uuid_coords(self, uuid):
        """
        Returns the coordinates of the given entity UUID inside this world, or
        `None` if the UUID is not found.
        """
        if uuid in self._entity_to_region_map:
            coords = self._entity_to_region_map[uuid]
            entities = self.get_entities(*coords)
            for entity in entities:
                if 'uniqueId' in entity.data and entity.data['uniqueId'] == uuid:
                    return tuple(entity.data['tilePosition'])
        return None

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
        values = struct.unpack('>hBBhBhBBhBBffBBHBB?x', stream.read(31))
        return Tile(*values)

    @lazyproperty
    def _entity_to_region_map(self):
        """
        A dict whose keys are the UUIDs (or just IDs, in some cases) of
        entities, and whose values are the `(rx, ry)` coordinates in which that
        entity can be found. This can be used to easily locate particular
        entities inside the world.
        """
        entity_to_region = {}
        for key in self.get_all_keys():
            layer, rx, ry = struct.unpack('>BHH', key)
            if layer != 4:
                continue
            stream = io.BytesIO(self.get(layer, rx, ry))
            num_entities = sbon.read_varint(stream)
            for _ in range(num_entities):
                uuid = sbon.read_string(stream)
                if uuid in entity_to_region:
                    raise ValueError('Duplicate UUID {}'.format(uuid))
                entity_to_region[uuid] = (rx, ry)
        return entity_to_region


class WorldInfo(object):
    """
    Convenience class to provide some information about a World without having
    to know which keys to look at.
    """

    def __init__(self, metadata):
        self.metadata = metadata

    @property
    def biomes(self):
        """
        Returns a set of all biomes found in the world.  This should be a
        complete list even if the world isn't fully-explored.
        """
        return self._worldParameters.biomes

    @property
    def coords(self):
        """
        The coordinates of the system. The first two elements of the tuple will
        be the `(x, y)` coordinates in the universe map, and the third is
        largely useless.
        """
        return self._celestialParameters.coords

    @property
    def description(self):
        """
        A description of the world - will include a "Tier" ranking for
        planets/moons.
        """
        return self._celestialParameters.description

    @property
    def dungeons(self):
        """
        Returns a set of all dungeons found in the world. This should be a
        complete list even if the world isn't fully-explored.
        """
        return self._worldParameters.dungeons

    @property
    def name(self):
        """
        The name of the world. Note that this will often include coloration
        markup.
        """
        return self._celestialParameters.name

    @lazyproperty
    def size(self):
        """
        The size of the world, as a tuple.
        """
        return tuple(self.metadata.get('worldTemplate', {})['size'])

    @property
    def world_biomes(self):
        """
        A set of main biomes which define the world as a whole. This will be a
        much shorter list than the full list of biomes found in the world --
        generally only a couple of entries.
        """
        return self._celestialParameters.biomes

    @lazyproperty
    def _celestialParameters(self):
        t = namedtuple('celestialParameters', 'name description coords biomes')
        name = None
        description = None
        coords = None
        biomes = set()
        cp = self.metadata.get('worldTemplate', {}).get('celestialParameters')
        if cp:
            name = cp.get('name')
            if 'parameters' in cp:
                description = cp['parameters'].get('description')
                if 'terrestrialType' in cp['parameters']:
                    biomes.update(cp['parameters']['terrestrialType'])
            if 'coordinate' in cp and 'location' in cp['coordinate']:
                coords = tuple(cp['coordinate']['location'])
        return t(name, description, coords, biomes)

    @lazyproperty
    def _worldParameters(self):
        t = namedtuple('worldParameters', 'biomes dungeons')
        biomes = set()
        dungeons = set()
        wp = self.metadata.get('worldTemplate', {}).get('worldParameters')
        if wp:
            SCAN_LAYERS = [
                ('atmosphereLayer', False),
                ('coreLayer', False),
                ('spaceLayer', False),
                ('subsurfaceLayer', False),
                ('surfaceLayer', False),
                ('undergroundLayers', True),
            ]
            for name, is_list in SCAN_LAYERS:
                if name not in wp:
                    continue
                layers = wp[name] if is_list else [wp[name]]
                for layer in layers:
                    dungeons.update(layer['dungeons'])
                    for label in ['primaryRegion', 'primarySubRegion']:
                        biomes.add(layer[label]['biome'])
                    for label in ['secondaryRegions', 'secondarySubRegions']:
                        for inner_region in layer[label]:
                            biomes.add(inner_region['biome'])
        return t(biomes, dungeons)


def read_sbvj01(stream):
    assert stream.read(6) == b'SBVJ01', 'Invalid header'
    return read_versioned_json(stream)


def read_versioned_json(stream):
    name = sbon.read_string(stream)
    # The object only has a version if the following bool is true.
    if stream.read(1) == b'\x00':
        version = None
    else:
        version, = struct.unpack('>i', stream.read(4))
    data = sbon.read_dynamic(stream)
    return VersionedJSON(name, version, data)


def write_sbvj01(stream, vj):
    stream.write(b'SBVJ01')
    write_versioned_json(stream, vj)


def write_versioned_json(stream, vj):
    sbon.write_string(stream, vj.name)
    if vj.version is None:
        stream.write(struct.pack('>b', 0))
    else:
        stream.write(struct.pack('>bi', 1, vj.version))
    sbon.write_dynamic(stream, vj.data)
