#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import hashlib
import json
import mmap
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
    p = optparse.OptionParser('Usage: %prog <world path> [<x> <y>]')
    p.add_option('-e', '--entities', dest='entities',
                 action='store_true', default=False,
                 help='Output entity data instead of tile data')
    p.add_option('-v', '--value-index', dest='value_index',
                 type=int, default=0,
                 help='The value in the tile data to output')
    options, arguments = p.parse_args()
    # Get the path and coordinates from arguments.
    if len(arguments) == 1:
        path = arguments[0]
        x, y = None, None
    elif len(arguments) == 3:
        path, x, y = arguments
        x, y = int(x), int(y)
    else:
        p.error('Incorrect number of arguments')
    # Load up the world file.
    with open(path, 'rb') as fh:
        mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        world = starbound.World(mm)
        world.read_metadata()
        spawn = world.metadata['playerStart']
        # Default coordinates to spawn point.
        if x is None or y is None:
            x, y = int(spawn[0] / 32), int(spawn[1] / 32)
        # Print world metadata.
        print('World size:        {}×{}'.format(world.width, world.height))
        print('Metadata version:  {}'.format(world.metadata_version))
        if spawn:
            print('Spawn point:       ({}, {})'.format(spawn[0], spawn[1]))
        print('')
        # Print either entities or tile data depending on options.
        if options.entities:
            entities = [{'type': e.name, 'version': e.version, 'data': e.data}
                        for e in world.get_entities(x, y)]
            print('Entities in region ({}, {}):'.format(x, y))
            print(json.dumps(entities, indent=2, separators=(',', ': '), sort_keys=True))
        else:
            try:
                print('Tiles ({}) in region ({}, {}):'.format(
                    starbound.Tile._fields[options.value_index], x, y))
            except:
                print('Unsupported value index! Pick one of these indices:')
                index = 0
                for field in starbound.Tile._fields:
                    print('> {} ({})'.format(index, field))
                    index += 1
            else:
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
    (1.0 / 100, '.'),
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


def get_colors(value):
    # More complicated due to Python 2/3 support.
    b = hashlib.md5(str(value).encode('utf-8')).digest()[1]
    x = ord(b) if isinstance(b, str) else b
    if x < 16:
        return x, 15 if x < 8 else 0
    elif x < 232:
        return x, 15 if (x - 16) % 36 < 18 else 0
    else:
        return x, 15 if x < 244 else 0


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
        if isinstance(value, float):
            v = '{:02X}{}'.format(int(value), fraction_to_string(value))
        else:
            v = '{:03X}'.format(value)
            if len(v) > 3:
                v = '-…' + v[-1] if value < 0 else '…' + v[-2:]
        bg, fg = get_colors(value)
        line += '\033[48;5;{:d}m\033[38;5;{:d}m{}\033[000m'.format(bg, fg, v)
    lines.append(line)
    print('\n'.join(reversed(lines)))
    print('')


if __name__ == '__main__':
    main()
