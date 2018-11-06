#!/usr/bin/env python
# -*- coding: utf-8 -*-

import mmap
import optparse
import os
import sys
import time

import starbound


def main():
    p = optparse.OptionParser('Usage: %prog <package path>')
    p.add_option('-d', '--destination', dest='path',
                 help='Destination directory')
    options, arguments = p.parse_args()
    # Validate the arguments.
    if len(arguments) != 1:
        p.error('Only one argument is supported (package path)')
    package_path = arguments[0]
    base = options.path if options.path else '.'
    # Load the assets file and its index.
    start = time.clock()
    with open(package_path, 'rb') as fh:
        mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        package = starbound.SBAsset6(mm)
        print('Loading index...')
        # Get the paths from the index in the database.
        package.read_index()
        print('Index loaded. Extracting {} files...'.format(package.file_count))
        # Start extracting everything.
        num_files = 0
        percentage_count = max(package.file_count // 100, 1)
        for path in package.index:
            dest_path = base + path
            dir_path = os.path.dirname(dest_path)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
            try:
                data = package.get(path)
            except:
                # Break the dots in case std{out,err} are the same tty:
                sys.stdout.write('\n')
                sys.stdout.flush()
                print >>sys.stderr, 'W: Failed to read', path
                continue
            with open(dest_path, 'wb') as file:
                file.write(data)
            num_files += 1
            if not num_files % percentage_count:
                sys.stdout.write('.')
                sys.stdout.flush()
    elapsed = time.clock() - start
    print('')
    print('Extracted {} files in {:.1f} seconds.'.format(num_files, elapsed))


if __name__ == '__main__':
    main()
