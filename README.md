Starbound utilities for Python
==============================

This is a library to parse Starbound's file formats, SBBF02 and SBVJ01,
which are used to store worlds, player characters, assets, etc.

Feel free to contribute either via submitting pull requests or writing
up issues with suggestions and/or bugs.

Usage
-----

The easiest way to get started with the package is to use the helper
function `open_file`:

```python
import starbound
player = starbound.open_file('player/11475cedd80ead373c19a91de2e2c4d3.player')
print 'Hello, %s!' % player.name
```

The `open_file` function will look at the file extension and choose the
appropriate file format as well as parse additional metadata about that
file type. To be more specific, you can use the file type classes:

```python
import io
import starbound

world = starbound.StarFileSBBF02('universe/beta_73998977_11092106_-913658_12_10.world')
world.open()

# Get the raw data out of the database, then parse it.
raw_data = world.get('\x00\x00\x00\x00\x00')
stream = io.BytesIO(raw_data)
stream.seek(8) # Ignore prefix
name, data = starbound.sbon.read_document(stream)

print data['planet']['size']
```


Trying it out
-------------

You can test this library using the `cli.py` script. Here's an example
on how to get a value out of a world's metadata:

```bash
$ ./cli.py --get-value planet.config.gravity /Starbound/player/11475cedd80ead373c19a91de2e2c4d3.shipworld
open StarboundFile(identifier="World2", path="/Starbound/player/11475cedd80ead373c19a91de2e2c4d3.shipworld")

planet.config.gravity = 80.0
```

Here's another example that prints the B-tree of the data for a
player's ship:

```bash
$ ./cli.py --print-leaves /Starbound/player/11475cedd80ead373c19a91de2e2c4d3.shipworld
open StarboundFile(identifier="World2", path="/Starbound/player/11475cedd80ead373c19a91de2e2c4d3.shipworld")

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


Getting region data
-------------------

If you want to export the binary data for a specific region, you can
use the `region.py` script:

```bash
# First get the spawn position on target planet...
$ ./cli.py --get-value playerStart /Starbound/universe/beta_73998977_11092106_-913658_12_10.world
open StarboundFile(identifier="World2", path="/Starbound/universe/beta_73998977_11092106_-913658_12_10.world")

playerStart = [0.0, 1247.5]

# ...then export layer 1 at those coordinates to a file.
# Arguments are: ./region.py <x> <y> <layer> <path>
$ ./region.py 0 1247 1 /Starbound/universe/beta_73998977_11092106_-913658_12_10.world > startregion.dat
```
