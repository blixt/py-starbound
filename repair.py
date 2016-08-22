#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import io
import math
import optparse
import os
import os.path
import signal
import struct
import zlib

import starbound
import starbound.btreedb5


try:
    # Don't break on pipe signal.
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except:
    # Probably a Windows machine.
    pass


# Override range with xrange when running Python 2.x.
try:
    range = xrange
except:
    pass


def main():
    p = optparse.OptionParser('Usage: %prog [options] <input file>')
    p.add_option('-f', '--force', dest='force',
                 action='store_true', default=False,
                 help='ignore some errors')
    p.add_option('-o', '--output', dest='output',
                 help='where to output repaired world (defaults to input file '
                      'path with .repaired added to the end)')
    p.add_option('-w', '--blank-world', dest='world',
                 help='the blank .world file that was created in place of the '
                      '.fail one (for metadata recovery)')
    options, arguments = p.parse_args()
    # Get the path from arguments.
    if len(arguments) != 1:
        p.error('incorrect number of arguments')
    try:
        fh = open(arguments[0], 'rb')
        file_size = os.fstat(fh.fileno()).st_size
        world = starbound.World(fh)
    except Exception as e:
        p.error('could not open fail file ({})'.format(e))
    # Output path (defaults to fail file + .repaired).
    if options.output:
        out_name = options.output
    else:
        out_name = arguments[0] + '.repaired'
    # Ensure the user doesn't accidentally overwrite existing files.
    if os.path.isfile(out_name):
        if options.force:
            print('warning: overwriting existing file')
        else:
            p.error('"{}" already exists'.format(out_name))
    # Allow user to use the fresh world for metadata (which should be the same).
    if options.world:
        fail_name = os.path.basename(arguments[0])
        world_name = os.path.basename(options.world)
        if fail_name[:len(world_name)] != world_name:
            if options.force:
                print('warning: .fail and .world filenames do not match')
            else:
                p.error('.fail and .world filenames do not match')
        try:
            blank_world = starbound.World(open(options.world, 'rb'))
        except Exception as e:
            p.error('could not open blank world ({})'.format(e))
    # This dict will contain all the keys and their data.
    data = dict()
    try:
        world.read_metadata()
        metadata, version = world.metadata, world.metadata_version
    except Exception as e:
        if options.world:
            try:
                print('warning: restoring metadata using blank world')
                blank_world.read_metadata()
                metadata, version = blank_world.metadata, blank_world.metadata_version
            except Exception as e:
                p.error('failed to restore metadata ({})'.format(e))
        else:
            p.error('metadata section is corrupt ({})'.format(e))
    try:
        size = metadata['worldTemplate']['size']
    except Exception as e:
        size = [-1, -1]
        print('warning: failed to read world size ({})'.format(e))
    regions_x = int(math.ceil(size[0] / 32))
    regions_y = int(math.ceil(size[1] / 32))
    print('attempting to recover {}×{} regions...'.format(regions_x, regions_y))
    block_count = int((file_size - starbound.btreedb5.HEADER_SIZE) / world.block_size)
    blocks_per_percent = block_count // 100 + 1
    nodes_recovered = 0
    percent = 0
    # Find all leaves and try to read them individually.
    for index in range(block_count):
        if index % blocks_per_percent == 0:
            print('{}% ({} nodes recovered)'.format(percent, nodes_recovered))
            percent += 1
        # Seek to the block and only process it if it's a leaf.
        world.stream.seek(starbound.btreedb5.HEADER_SIZE + world.block_size * index)
        if world.stream.read(2) != starbound.btreedb5.LEAF:
            continue
        stream = starbound.btreedb5.LeafReader(world)
        try:
            num_keys, = struct.unpack('>i', stream.read(4))
        except Exception as e:
            print('failed to read keys of leaf block #{}: {}'.format(index, e))
            continue
        # Ensure that the number of keys makes sense, otherwise skip the leaf.
        if num_keys > 100:
            continue
        for i in range(num_keys):
            try:
                cur_key = stream.read(world.key_size)
                cur_data = starbound.sbon.read_bytes(stream)
            except Exception as e:
                print('could not read key/data: {}'.format(e))
                break
            layer, x, y = struct.unpack('>BHH', cur_key)
            # Skip this leaf if we encounter impossible indexes.
            if layer == 0 and (x != 0 or y != 0):
                break
            if layer not in (0, 1, 2) or x >= regions_x or y >= regions_y:
                break
            result = None
            if cur_key in data:
                # Duplicates should be checked up against the index, which always wins.
                # TODO: Make this code run again.
                try:
                    #result = world.get(layer, x, y)
                    result = None
                except Exception:
                    world.swap_root()
                    try:
                        #result = world.get(layer, x, y)
                        result = None
                    except Exception:
                        pass
                    world.swap_root()
            # Use the data from this leaf if not using the index.
            if not result:
                try:
                    result = zlib.decompress(cur_data)
                except Exception as e:
                    print('broken leaf node: {}'.format(e))
                    continue
            # Validate the data before storing it.
            try:
                if layer == 0:
                    temp_stream = io.BytesIO(result)
                    temp_stream.seek(8)
                    name, _, _ = starbound.read_versioned_json(temp_stream)
                    assert name == 'WorldMetadata', 'broken world metadata'
                elif layer == 1:
                    assert len(result) == 3 + 32 * 32 * 30, 'broken region data'
                elif layer == 2:
                    temp_stream = io.BytesIO(result)
                    for _ in range(starbound.sbon.read_varint(temp_stream)):
                        starbound.read_versioned_json(temp_stream)
            except Exception as e:
                print('invalid key data: {}'.format(e))
                continue
            # Count the node the first time it's stored.
            if cur_key not in data:
                nodes_recovered += 1
            data[cur_key] = zlib.compress(result)
    METADATA_KEY = b'\x00\x00\x00\x00\x00'
    # Ensure that the metadata key is in the data.
    if METADATA_KEY not in data:
        if options.world:
            try:
                data[METADATA_KEY] = blank_world.get(0, 0, 0)
            except Exception:
                p.error('failed to recover metadata from alternate world')
        else:
            if options.force:
                try:
                    data[METADATA_KEY] = world.get(0, 0, 0)
                    print('warning: using partially recovered metadata')
                except Exception:
                    p.error('failed to recover partial metadata')
            else:
                p.error('failed to recover metadata; use -w to load metadata '
                        'from another world, or -f to attempt partial recovery')
    print('done! {} nodes recovered'.format(nodes_recovered))
    print('creating BTree database...')
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
        starbound.sbon.write_bytes(buffer, data[key])
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
    print('created {} blocks containing world data'.format(len(blocks)))

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
        print('- created {} index(es) for level {}'.format(len(new_ranges), level))
        return new_ranges

    # Build the indexes in multiple levels up to a single root node.
    print('creating root node...')
    root_is_leaf = True
    level = 0
    current_index = range_to_leaf
    while len(current_index) > 1:
        current_index = build_index_level(current_index, level)
        root_is_leaf = False
        level += 1
    root_node = list(current_index.values())[0]
    # Also build an alternative root node.
    print('creating alternate root node...')
    alternate_root_is_leaf = True
    level = 0
    current_index = range_to_leaf
    while len(current_index) > 1:
        current_index = build_index_level(current_index, level)
        alternate_root_is_leaf = False
        level += 1
    alternate_root_node = list(current_index.values())[0]
    # The last two blocks will be free blocks.
    blocks.append(b'FF\xFF\xFF\xFF\xFF' + b'\x00' * (world.block_size - 6))
    blocks.append(b'FF\xFF\xFF\xFF\xFF' + b'\x00' * (world.block_size - 6))
    print('writing all the data to disk...')
    with open(out_name, 'wb') as f:
        header = struct.pack(starbound.btreedb5.HEADER,
            b'BTreeDB5',
            world.block_size,
            world.name.encode('utf-8') + b'\x00' * (16 - len(world.name)),
            world.key_size,
            False,
            len(blocks) - 1,
            14282,  # XXX: Unknown value!
            root_node,
            root_is_leaf,
            len(blocks) - 2,
            14274,  # XXX: Unknown value!
            alternate_root_node,
            alternate_root_is_leaf)
        f.write(header)
        for block in blocks:
            f.write(block)
    print('done!')


if __name__ == '__main__':
    main()
