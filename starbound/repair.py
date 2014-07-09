import math
import io
import struct
import zlib

from . import btreedb4, helpers, sbon

class RepairError(Exception):
    pass

def repair_world(world, blank_world=None):
    if not isinstance(world, helpers.FailedWorld):
        raise ValueError('A FailedWorld object must be provided')
    if blank_world and not isinstance(blank_world, helpers.World):
        raise ValueError('Second argument was not a World object')

    warnings = []

    # This dict will contain all the keys and their data.
    data = dict()

    try:
        metadata, version = world.get_metadata()
        assert metadata, 'Metadata missing'
    except Exception as e:
        if blank_world:
            try:
                warnings.append('Restored metadata using blank world')
                metadata, version = blank_world.get_metadata()
            except Exception as e:
                raise RepairError('Failed to restore metadata (%s)' % e)
        else:
            raise RepairError('Metadata section is corrupt (%s)' % e)

    try:
        if version == 1:
            size = metadata['planet']['size']
        elif version in (2, 3):
            size = metadata['worldTemplate']['size']
        else:
            size = [-1, -1]
            warnings.append('Unsupported metadata version %d' % version)
    except Exception as e:
        size = [-1, -1]
        warnings.append('Failed to read world size (%s)' % e)

    regions_x = int(math.ceil(size[0] / 32))
    regions_y = int(math.ceil(size[1] / 32))

    # Find all leaves and try to read them individually.
    for index in range(world.num_blocks):
        block = world.get_block(index)
        if not isinstance(block, btreedb4.BTreeLeaf):
            continue

        stream = btreedb4.LeafReader(world, block)
        try:
            num_keys, = struct.unpack('>i', stream.read(4))
        except Exception:
            continue

        # Ensure that the number of keys makes sense, otherwise skip the leaf.
        if num_keys > 100:
            continue

        for i in range(num_keys):
            try:
                cur_key = stream.read(world.key_size)
                cur_data = sbon.read_bytes(stream)
            except Exception:
                break

            layer, x, y = struct.unpack('>BHH', cur_key)

            # Skip this leaf if we encounter impossible indexes.
            if layer == 0 and (x != 0 or y != 0):
                break
            if layer not in (0, 1, 2) or x >= regions_x or y >= regions_y:
                break

            result = None
            if cur_key in data:
                # Duplicates should be checked up against the index, which
                # always wins.
                try:
                    result = world.get_raw((layer, x, y))
                except Exception:
                    world.commit()
                    try:
                        result = world.get_raw((layer, x, y))
                    except Exception:
                        pass
                    world.commit()

            # Use the data from this leaf if not using the index.
            if not result:
                result = cur_data

            # Validate the data before storing it.
            try:
                if layer == 0:
                    temp_stream = io.BytesIO(result)
                    temp_stream.seek(8)
                    name, _, _ = sbon.read_document(temp_stream)
                    assert name == 'WorldMetadata', 'Invalid world data'
                else:
                    temp_stream = io.BytesIO(zlib.decompress(result))

                if layer == 1:
                    if len(temp_stream.getvalue()) != 3 + 32 * 32 * 23:
                        continue
                elif layer == 2:
                    sbon.read_document_list(temp_stream)
            except Exception:
                continue

            data[cur_key] = result

    METADATA_KEY = b'\x00\x00\x00\x00\x00'

    # Ensure that the metadata key is in the data.
    if METADATA_KEY not in data:
        if blank_world:
            try:
                data[METADATA_KEY] = blank_world.get_raw((0, 0, 0))
            except Exception:
                raise RepairError('Failed to recover metadata from blank world')
        else:
            try:
                data[METADATA_KEY] = world.get_raw((0, 0, 0))
                warnings.append('Used partially recovered metadata')
            except Exception:
                raise RepairError('Failed to recover partial metadata')

    # Try not to exceed this number of keys per leaf.
    LEAF_KEYS_TRESHOLD = 10
    # Try not to exceed this size for a leaf.
    LEAF_SIZE_TRESHOLD = world.block_size * .8
    # Fill indexes up to this ratio.
    INDEX_FILL = .9

    # 6 is the number of bytes used for signature + next block pointer.
    LEAF_BYTES = world.block_size - 6

    # 11 is the number of bytes in the index header.
    INDEX_BYTES = world.block_size - 11

    # Maximum number of keys that can go into an index.
    INDEX_MAX_KEYS = int(INDEX_BYTES // (world.key_size + 4) * INDEX_FILL)

    # The data of individual blocks will be stored in this list.
    blocks = []

    buffer = io.BytesIO()

    # This will create an initial leaf and connect it to following leaves which
    # will all contain the data currently in the buffer.
    def dump_buffer():
        buffer_size = buffer.tell()
        buffer.seek(0)

        block_data = b'LL' + struct.pack('>i', num_keys) + buffer.read(LEAF_BYTES - 4)
        while buffer.tell() < buffer_size:
            blocks.append(block_data + struct.pack('>i', len(blocks) + 1))
            block_data = b'LL' + buffer.read(LEAF_BYTES)
        blocks.append(block_data.ljust(world.block_size - 4, b'\x00') + struct.pack('>i', -1))

        # Empty the buffer.
        buffer.seek(0)
        buffer.truncate()

    # The number of keys that will be stored in the next created leaf.
    num_keys = 0

    # Map of key range to leaf block pointer.
    range_to_leaf = dict()

    # All the keys, sorted (important).
    keys = sorted(data)

    # Build all the leaf blocks.
    min_key = None
    for key in keys:
        if not num_keys:
            # Remember the first key of the leaf.
            min_key = key

        buffer.write(key)
        sbon.write_bytes(buffer, data[key])
        num_keys += 1

        # Empty buffer once one of the tresholds is reached.
        if num_keys >= LEAF_KEYS_TRESHOLD or buffer.tell() >= LEAF_SIZE_TRESHOLD:
            range_to_leaf[(min_key, key)] = len(blocks)
            dump_buffer()
            num_keys = 0

    # Empty any remaining data in the buffer.
    if buffer.tell():
        range_to_leaf[(min_key, key)] = len(blocks)
        dump_buffer()

    def build_index_level(range_to_block, level=0):
        # Get a list of ranges that this index level needs to point to.
        index_ranges = sorted(range_to_block)

        # The new list of ranges that the next level of indexes can use.
        new_ranges = dict()

        for i in range(0, len(index_ranges), INDEX_MAX_KEYS):
            ranges = index_ranges[i:i + INDEX_MAX_KEYS]

            min_key, _ = ranges[0]
            _, max_key = ranges[-1]

            left_block = range_to_block[ranges.pop(0)]

            index_data = io.BytesIO()
            index_data.write(b'II' + struct.pack('>Bii', level, len(ranges), left_block))
            for key_range in ranges:
                index_data.write(key_range[0] + struct.pack('>i', range_to_block[key_range]))

            new_ranges[(min_key, max_key)] = len(blocks)
            blocks.append(index_data.getvalue().ljust(world.block_size, b'\x00'))

        return new_ranges

    # Build the indexes in multiple levels up to a single root node.
    root_is_leaf = True
    level = 0
    current_index = range_to_leaf
    while len(current_index) > 1:
        current_index = build_index_level(current_index, level)
        root_is_leaf = False
        level += 1
    root_node = list(current_index.values())[0]

    # Also build an alternative root node.
    alternate_root_is_leaf = True
    level = 0
    current_index = range_to_leaf
    while len(current_index) > 1:
        current_index = build_index_level(current_index, level)
        alternate_root_is_leaf = False
        level += 1
    alternate_root_node = list(current_index.values())[0]

    # The last block will be a free block.
    blocks.append(b'FF\xFF\xFF\xFF\xFF' + b'\x00' * (world.block_size - 6))

    output = io.BytesIO()
    output.write(b'SBBF02')
    output.write(struct.pack('>ii?i', world.header_size, world.block_size, True, len(blocks) - 1))
    output.write(b'\x00' * (32 - output.tell()))
    output.write(b'BTreeDB4\x00\x00\x00\x00')
    output.write(world.identifier.encode('utf-8') + b'\x00' * (12 - len(world.identifier)))
    output.write(struct.pack('>i?xi?xxxi?', world.key_size, False, root_node, root_is_leaf,
                             alternate_root_node, alternate_root_is_leaf))
    output.write(b'\x00' * (world.header_size - output.tell()))

    for block in blocks:
        output.write(block)

    return output, warnings
