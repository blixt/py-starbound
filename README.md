Starbound utilities for Python
==============================

This is a library to parse Starbound's SBBF02 format. The SBBF02 format
is what makes up the `.world` files, for example.

Feel free to contribute either via submitting pull requests or writing
up issues with suggestions and/or bugs.

Trying it out
-------------

You can test this library using the `cli.py` script. Here's an example
that prints the B-tree of the data for a player's ship:

```bash
$ ./cli.py --print-leaves /Starbound/player/11475cedd80ead373c19a91de2e2c4d3.shipworld
open StarboundFile(name="World2", path="/Starbound/player/11475cedd80ead373c19a91de2e2c4d3.shipworld")

Index(level=0, num_keys=34) @ 847
   ^^^^^^^^^^: Leaf(next_block=930) @ 927
        0000000000 = 237921 byte(s)
   01000a000a: Leaf(next_block=None) @ 361
        01000a000a = 96 byte(s)
   01000a000b: Leaf(next_block=265) @ 127
        01000a000b = 96 byte(s)
        01000a000c = 96 byte(s)
        01000a000d = 96 byte(s)
        01000a000e = 96 byte(s)
        01000a000f = 96 byte(s)
# ...and 310 more lines.
```

Here's another example for getting a value out of a world's metadata:

```bash
$ ./cli.py --get-world-value planet.config.gravity /Starbound/player/11475cedd80ead373c19a91de2e2c4d3.shipworld

planet.config.gravity = 80.0
```
