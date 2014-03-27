#!/usr/bin/env python

import optparse
import os
import sys

import starbound

def main():
    p = optparse.OptionParser()
    p.add_option('-d', '--destination', dest='path',
                 help='Destination directory')
    options, arguments = p.parse_args()

    if len(arguments) != 1:
        raise ValueError('Only one argument is supported (package path)')
    package_path = arguments[0]

    base = options.path if options.path else '.'

    with starbound.open_file(package_path) as package:
        if not isinstance(package, starbound.Package):
            raise ValueError('Provided path is not a package')

        print 'Loading index...'

        # Get the paths from the index in the database.
        paths = list(package.get_index())

        print 'Index loaded. Extracting %d files...' % len(paths)

        num_files = 0
        percentage_count = max(len(paths) // 100, 1)

        for path in paths:
            dest_path = base + path

            dir_path = os.path.dirname(dest_path)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)

            try:
                data = package.get(path)
            except:
                # break the dots in case std{out,err} are the same tty:
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

    print
    print 'Extracted %d files.' % num_files

if __name__ == '__main__':
    main()
