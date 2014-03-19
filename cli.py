#!/usr/bin/env python

import binascii
import json
import optparse
import signal
import struct
import sys

import starbound
import starbound.btreedb4
import starbound.sbon

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

def print_leaves(file, block_number=None, depth=0, prefix=None):
    """Prints out the full B-tree of accessible leaves"""

    if block_number is None:
        block_number = file.root_node
    block = file.get_block(block_number)

    sys.stdout.write('   ' * depth)
    if prefix:
        sys.stdout.write(prefix + ': ')
    print block, '@', block_number

    if isinstance(block, starbound.btreedb4.BTreeIndex):
        for index, block_reference in enumerate(block.values):
            if index == 0:
                key_hex = '^' * file.key_size * 2
            else:
                key_hex = block.keys[index - 1].encode('hex')

            print_leaves(file, block_reference, depth + 1, prefix=key_hex)

    if isinstance(block, starbound.btreedb4.BTreeLeaf):
        stream = starbound.btreedb4.LeafReader(file, block)
        num_keys, = struct.unpack('>i', stream.read(4))

        indent = '    ' * (depth + 1)
        try:
            for _ in range(num_keys):
                cur_key = stream.read(file.key_size)
                value_length = starbound.sbon.read_varlen_number(stream)
                print indent + '%s = %s byte(s)' % (cur_key.encode('hex'), value_length)
                value = stream.read(value_length)
        except Exception, e:
            print indent + '!!! CORRUPT (%s)' % e

def get_file(file, filename):
    """Get the contents of a file in a package."""
    assert isinstance(file, starbound.Package), 'Can only get files out of packages'
    sys.stdout.write(file.get(filename))

def get_file_list(file):
    """Get the list of files in a package."""
    assert isinstance(file, starbound.Package), 'Can only get file list out of packages'
    print '\n'.join(file.get_index())

def get_leaf(file, hex_key):
    """Gets the data in the specified leaf."""
    data = file.get_using_encoded_key(binascii.unhexlify(hex_key))
    if isinstance(data, (dict, list, tuple)):
        print json.dumps(data, indent=2, separators=(',', ': '), sort_keys=True)
    else:
        print data

def get_value(file, key_path):
    """Get a value out of the file's metadata"""

    if isinstance(file, starbound.FileSBVJ01):
        data = file.data
    elif isinstance(file, starbound.World):
        data, _ = file.get_metadata()
    else:
        raise ValueError('--get-value requires a player or world file')

    if key_path != '.':
        key_parts = key_path.split('.')
        for key in key_parts:
            data = data[key]
    print key_path, '=', json.dumps(data, indent=2, separators=(',', ': '), sort_keys=True)


def main():
    p = optparse.OptionParser()

    p.add_option('-f', '--get-file', dest='path',
                 help=get_file.__doc__)

    p.add_option('-i', '--get-file-list', dest='get_file_list',
                 action='store_true', default=False,
                 help=get_file_list.__doc__)

    p.add_option('-d', '--get-leaf', dest='leaf_key',
                 help=get_leaf.__doc__)

    p.add_option('-g', '--get-value', dest='key',
                 help=get_value.__doc__)

    p.add_option('-l', '--print-leaves', dest='print_leaves',
                 action='store_true', default=False,
                 help=print_leaves.__doc__)

    options, arguments = p.parse_args()

    for path in arguments:
        with starbound.open_file(path) as file:
            if options.path:
                get_file(file, options.path)
                return

            print file
            print

            if options.get_file_list:
                get_file_list(file)
                print

            if options.leaf_key:
                get_leaf(file, options.leaf_key)
                print

            if options.key:
                get_value(file, options.key)
                print

            if options.print_leaves:
                print_leaves(file)
                print

if __name__ == '__main__':
    main()
