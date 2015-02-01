#!/usr/bin/env python
# -*- coding: utf-8

import json
import optparse
import signal

import starbound

try:
    # Don't break on pipe signal.
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except:
    # Probably a Windows machine.
    pass

def main():
    p = optparse.OptionParser('Usage: %prog [<x> <y>] <path>')

    p.add_option('-c', '--tile-coords', dest='tile_coords',
                 action='store_true', default=False,
                 help='X, Y is for a tile instead of a region')

    p.add_option('-e', '--entities', dest='entities',
                 action='store_true', default=False,
                 help='Output entity data instead of tile data')

    p.add_option('-r', '--raw', dest='raw',
                 action='store_true', default=False,
                 help='Output data in a raw format')

    p.add_option('-v', '--value-index', dest='value_index',
                 type=int, default=0,
                 help='The value in the tile data to output')

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
        p.error('Incorrect number of arguments')

    with starbound.open_file(path) as world:
        # Get information about the world.
        metadata, version = world.get_metadata()
        if version == 1:
            size = metadata['planet']['size']
            spawn = metadata.get('playerStart')
        else:
            size = metadata['worldTemplate']['size']
            spawn = metadata.get('playerStart')

        # Default coordinates to spawn point.
        if x is None or y is None:
            x, y = int(spawn[0] / 32), int(spawn[1] / 32)

        # Only print the pure data if --raw is specified.
        if options.raw:
            if options.entities:
                print json.dumps(world.get_entities(x, y),
                                 indent=2,
                                 separators=(',', ': '),
                                 sort_keys=True)
            else:
                print world.get_region_data(x, y)
            return

        print 'World size:          %d by %d regions' % (size[0] / 32, size[1] / 32)
        if spawn:
            print 'Spawn point region:  %d, %d' % (spawn[0] // 32, spawn[1] // 32)
        print 'Outputting region:   %d, %d' % (x, y)

        if options.entities:
            data = world.get_entities(x, y)
            print
            print json.dumps(data, indent=2, separators=(',', ': '), sort_keys=True)
        else:
            try:
                print 'Outputting value:    %s' % starbound.sbon.Tile._fields[options.value_index]
            except:
                print
                print 'Unsupported value index! Pick one of these indices:'
                index = 0
                for field in starbound.sbon.Tile._fields:
                    print '> %d (%s)' % (index, field)
                    index += 1
            else:
                print
                pretty_print_tiles(world, x, y, options.value_index)


_fraction_to_string = (
    (1.0 / 2, '½'),
    (1.0 / 3, '⅓'),
    (1.0 / 4, '¼'),
    (1.0 / 5, '⅕'),
    (1.0 / 6, '⅙'),
    (1.0 / 8, '⅛'),
    (2.0 / 3, '⅔'),
    (2.0 / 5, '⅖'),
    (3.0 / 4, '¾'),
    (3.0 / 5, '⅗'),
    (3.0 / 8, '⅜'),
    (4.0 / 5, '⅘'),
    (5.0 / 6, '⅚'),
    (5.0 / 8, '⅝'),
    (7.0 / 8, '⅞'),
)

def fraction_to_string(number):
    fraction = number - int(number)
    string = '?'
    min_diff = 1.0
    for value, character in _fraction_to_string:
        diff = abs(fraction - value)
        if diff < min_diff:
            min_diff = diff
            string = character
    return string


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
        if isinstance(value, (int, long)):
            line += '\033[48;5;%dm\033[38;5;%dm%03X\033[000m' % (bg_color, fg_color, value)
        elif isinstance(value, float):
            line += '\033[48;5;%dm\033[38;5;%dm%02X%s\033[000m' % (bg_color, fg_color, int(value),
                                                                   fraction_to_string(value))
        else:
            line += '\033[48;5;%dm\033[38;5;%dm???\033[000m' % (bg_color, fg_color)
    lines.append(line)

    print '\n'.join(reversed(lines))
    print

if __name__ == '__main__':
    main()
