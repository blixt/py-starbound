#!/usr/bin/env python

import optparse
import starbound

def main():
    p = optparse.OptionParser()
    options, arguments = p.parse_args()

    x, y, layer, path = arguments
    with starbound.open_file(path) as world:
        print world.get_region_data(int(x) // 32, int(y) // 32, int(layer))

if __name__ == '__main__':
    main()
