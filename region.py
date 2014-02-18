#!/usr/bin/env python

import json
import optparse
import signal

import starbound

# Don't break on pipe signal.
signal.signal(signal.SIGPIPE, signal.SIG_DFL)

def main():
    p = optparse.OptionParser()

    p.add_option('-c', '--tile-coords', dest='tile_coords',
                 action='store_true', default=False,
                 help='X, Y is for a tile instead of a region')

    p.add_option('-e', '--entities', dest='entities',
                 action='store_true', default=False,
                 help='Output entity data instead of tile data')

    p.add_option('-r', '--raw', dest='raw',
                 action='store_true', default=False,
                 help='Output data in a raw format')

    options, arguments = p.parse_args()

    # Get the path and coordinates from arguments.
    if len(arguments) == 1:
        path = arguments[0]
        x, y = None, None
    elif len(arguments) == 3:
        x, y, path = arguments
        x, y = int(x), int(y)

        if options.tile_coords:
            x //= 32
            y //= 32
    else:
        raise ValueError('Usage: ./region.py <x> <y> <path>')

    with starbound.open_file(path) as world:
        # Get information about the world.
        metadata, version = world.get_metadata()
        if version == 1:
            size = metadata['planet']['size']
            spawn = metadata['playerStart']
        elif version == 2:
            size = metadata['worldTemplate']['size']
            spawn = metadata['playerStart']
        else:
            raise NotImplementedError('Unsupported metadata version %d' % version)

        # Default coordinates to spawn point.
        if x is None or y is None:
            x, y = int(spawn[0] / 32), int(spawn[1] / 32)

        # Only print the pure data if --raw is specified.
        if options.raw:
            if options.entities:
                print json.dumps(world.get_entities(x, y))
            else:
                print world.get_region_data(x, y)
            return

        print 'World size:          %d by %d regions' % (size[0] / 32, size[1] / 32)
        print 'Spawn point region:  %d, %d' % (spawn[0] // 32, spawn[1] // 32)
        print 'Outputting region:   %d, %d' % (x, y)
        print

        if options.entities:
            data = world.get_entities(x, y)
            print json.dumps(data, indent=2, sort_keys=True, separators=(',', ': '))
        else:
            pretty_print_tiles(world, x, y)

def pretty_print_tiles(world, x, y, index=0):
    lines = []
    line = ''
    for i, tile in enumerate(world.get_tiles(x, y)):
        # Create a new line after every 32 tiles.
        if i > 0 and i % 32 == 0:
            lines.append(line)
            line = ''

        value = tile[index]

        # Create a uniquely colored block with the tile value.
        bg_color = abs(value) % 255
        fg_color = abs(255 - bg_color * 6) % 255
        line += '\033[48;5;%dm\033[38;5;%dm%03X\033[000m' % (bg_color, fg_color, value)

    print '\n'.join(reversed(lines))
    print

if __name__ == '__main__':
    main()
