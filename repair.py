#!/usr/bin/env python
# -*- coding: utf-8 -*-

import io
import math
import optparse
import os.path
import signal
import struct
import zlib

import starbound
import starbound.btreedb4


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

    # TODO
    #p.add_option('-r', '--replace', action='append',
    #             dest='replace', metavar='FROM,TO',
    #             help='replace one tile material with another')

    p.add_option('-w', '--blank-world', dest='world',
                 help='the blank .world file that was created in place of the '
                      '.fail one (for metadata recovery)')

    options, arguments = p.parse_args()

    if len(arguments) != 1:
        p.error('Incorrect number of arguments')

    try:
        world = starbound.open_file(arguments[0])
        if not isinstance(world, starbound.World):
            raise Exception('Not a world')
    except Exception as e:
        p.error('Could not open fail file (%s)' % e)

    if options.output:
        out_name = options.output
    else:
        out_name = arguments[0] + '.repaired'

    if os.path.isfile(out_name):
        if options.force:
            print 'warning: overwriting existing file'
        else:
            p.error('"%s" already exists' % out_name)

    if options.world:
        fail_name = os.path.basename(arguments[0])
        world_name = os.path.basename(options.world)

        if fail_name[:len(world_name)] != world_name:
            if options.force:
                print 'warning: .fail and .world filenames do not match'
            else:
                p.error('.fail and .world filenames do not match')

        try:
            blank_world = starbound.open_file(options.world)
        except Exception as e:
            p.error('Could not open blank world (%s)' % e)

    # This dict will contain all the keys and their data.
    data = dict()

    try:
        metadata, version = world.get_metadata()
    except Exception as e:
        if options.world:
            try:
                print 'warning: restoring metadata using blank world'
                metadata, version = blank_world.get_metadata()
            except Exception as e:
                p.error('Failed to restore metadata (%s)' % e)
        else:
            p.error('Metadata section is corrupt (%s)' % e)

    if version == 1:
        size = metadata['planet']['size']
    elif version in (2, 3):
        size = metadata['worldTemplate']['size']
    else:
        p.error('Unsupported metadata version %d' % version)

    regions_x = int(math.ceil(size[0] / 32))
    regions_y = int(math.ceil(size[1] / 32))
    print 'Attempting to recover %d×%d regions...' % (regions_x, regions_y)

    blocks_per_percent = world.num_blocks // 100 + 1
    entries_recovered = 0
    percent = 0

    # Find all leaves and try to read them individually.
    for index in range(world.num_blocks):
        if index % blocks_per_percent == 0:
            print '%d%% (%d entries recovered)' % (percent, entries_recovered)
            percent += 1

        block = world.get_block(index)
        if not isinstance(block, starbound.btreedb4.BTreeLeaf):
            continue

        stream = starbound.btreedb4.LeafReader(world, block)
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
                cur_data = starbound.sbon.read_bytes(stream)
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
            # TODO: This is where we would do the tile replace.
            try:
                if layer == 0:
                    temp_stream = io.BytesIO(result)
                    temp_stream.seek(8)
                    name, _, _ = starbound.sbon.read_document(temp_stream)
                    assert name == 'WorldMetadata', 'Invalid world data'
                else:
                    temp_stream = io.BytesIO(zlib.decompress(result))

                if layer == 1:
                    if len(temp_stream.getvalue()) != 3 + 32 * 32 * 23:
                        continue
                elif layer == 2:
                    starbound.sbon.read_document_list(temp_stream)
            except Exception:
                continue

            # Count the entry the first time it's stored.
            if cur_key not in data:
                entries_recovered += 1

            data[cur_key] = result

    METADATA_KEY = '\x00\x00\x00\x00\x00'

    # Ensure that the metadata key is in the data.
    if METADATA_KEY not in data:
        if options.world:
            try:
                data[METADATA_KEY] = blank_world.get_raw((0, 0, 0))
            except Exception:
                p.error('Failed to recover metadata from alternate world')
        else:
            if options.force:
                try:
                    data[METADATA_KEY] = world.get_raw((0, 0, 0))
                    print 'warning: using partially recovered metadata'
                except Exception:
                    p.error('Failed to recover partial metadata')
            else:
                p.error('Failed to recover metadata, use -f to recover partial')

    print 'Done! %d entries recovered. Creating BTree database...' % entries_recovered

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
    keys = sorted(data.keys())

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

    print 'Created %d blocks containing world data' % len(blocks)

    def build_index_level(range_to_block, level=0):
        # Get a list of ranges that this index level needs to point to.
        index_ranges = sorted(range_to_block.keys())

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

        print '- Created %d index(es) for level %d' % (len(new_ranges), level)
        return new_ranges

    # Build the indexes in multiple levels up to a single root node.
    print 'Creating root node...'
    root_is_leaf = True
    level = 0
    current_index = range_to_leaf
    while len(current_index) > 1:
        current_index = build_index_level(current_index, level)
        root_is_leaf = False
        level += 1
    root_node = current_index.itervalues().next()

    # Also build an alternative root node.
    print 'Creating alternate root node...'
    alternate_root_is_leaf = True
    level = 0
    current_index = range_to_leaf
    while len(current_index) > 1:
        current_index = build_index_level(current_index, level)
        alternate_root_is_leaf = False
        level += 1
    alternate_root_node = current_index.itervalues().next()

    # The last block will be a free block.
    blocks.append(b'FF\xFF\xFF\xFF\xFF' + b'\x00' * (world.block_size - 6))

    print 'Writing all the data to disk...'

    with open(out_name, 'w') as f:
        f.write(b'SBBF02')
        f.write(struct.pack('>ii?i', world.header_size, world.block_size, True, len(blocks) - 1))
        f.write('\x00' * (32 - f.tell()))
        f.write(b'BTreeDB4\x00\x00\x00\x00')
        f.write(world.identifier + '\x00' * (12 - len(world.identifier)))
        f.write(struct.pack('>i?xi?xxxi?', world.key_size, False, root_node, root_is_leaf,
                            alternate_root_node, alternate_root_is_leaf))
        f.write('\x00' * (world.header_size - f.tell()))

        for block in blocks:
            f.write(block)

    print 'Done!'

if __name__ == '__main__':
    main()
