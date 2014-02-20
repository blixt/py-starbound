#!/usr/bin/env python

import optparse
import signal
import struct
import sys

import starbound
import starbound.btreedb4
import starbound.sbon

# Don't break on pipe signal.
signal.signal(signal.SIGPIPE, signal.SIG_DFL)

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
        for _ in xrange(num_keys):
            cur_key = stream.read(file.key_size)
            value_length = starbound.sbon.read_varlen_number(stream)
            value = stream.read(value_length)
            sys.stdout.write('    ' * (depth + 1))
            print cur_key.encode('hex'), '=', len(value), 'byte(s)'

def get_file(file, filename):
    """Get the contents of a file in a package."""
    assert isinstance(file, starbound.Package), 'Can only get files out of packages'
    sys.stdout.write(file.get(filename))

def get_file_list(file):
    """Get the list of files in a package."""
    assert isinstance(file, starbound.Package), 'Can only get file list out of packages'
    print '\n'.join(file.get_index())

def get_value(file, key_path):
    """Get a value out of the file's metadata"""

    if isinstance(file, starbound.FileSBVJ01):
        data = file.data
    elif isinstance(file, starbound.World):
        data, _ = file.get_metadata()
    else:
        raise ValueError('--get-value requires a player or world file')

    key_parts = key_path.split('.')
    for key in key_parts:
        data = data[key]
    print key_path, '=', data


def main():
    p = optparse.OptionParser()

    p.add_option('-f', '--get-file', dest='path',
                 help=get_file.__doc__)

    p.add_option('-i', '--get-file-list', dest='get_file_list',
                 action='store_true', default=False,
                 help=get_file_list.__doc__)

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

            if options.key:
                get_value(file, options.key)
                print

            if options.print_leaves:
                print_leaves(file)
                print

if __name__ == '__main__':
    main()
