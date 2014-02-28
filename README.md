Starbound utilities for Python
==============================

This is a library to parse Starbound's file formats, SBBF02 and SBVJ01,
which are used to store worlds, player characters, assets, etc.

Feel free to contribute either via submitting pull requests or writing
up issues with suggestions and/or bugs.


Using the command line interface
--------------------------------

The command line interface will let you inspect various Starbound
files.


### Getting metadata from world or player files

Use the `--get-value` option to retrieve a metadata value. Example:

```bash
$ ./cli.py --get-value planet.config.gravity /Starbound/player/11475cedd80ead373c19a91de2e2c4d3.shipworld
open File(identifier="World2", path="/Starbound/player/11475cedd80ead373c19a91de2e2c4d3.shipworld")

planet.config.gravity = 80.0
```

Another example for getting the name of a player:

```bash
/cli.py --get-value identity.name /Starbound/player/11475cedd80ead373c19a91de2e2c4d3.player
open File(identifier="PlayerEntity", path="/Starbound/player/11475cedd80ead373c19a91de2e2c4d3.player")

identity.name = Fleur
```


### Inspecting Starbound packages

Starbound packages are essentially sets of packed (but uncompressed)
files. Here's how to get the contents of a file in a .pak package:

```bash
$ ./cli.py --get-file /tiles/mods/sand.matmod /Starbound/assets/packed.pak
{
  "modId" : 4,
  "modName" : "sand",
  "frames" : "sand.png",
  "variants" : 5,
  "Description" : "Scattered sand.",
  "footstepSound" : "/sfx/blocks/footstep_sand.wav",
  "health" : 0
}
```

You can also get the list of the files in a .pak file:

```bash
$ ./cli.py --get-file-list /Starbound/assets/packed.pak
open File(identifier="Assets1", path="/Starbound/assets/packed.pak")

/animations/1hswordhitspark/1hswordhitspark.animation
/animations/1hswordhitspark/1hswordhitspark.frames
/animations/1hswordhitspark/1hswordhitspark.png
/animations/2hswordhitspark/2hswordhitspark.animation
/animations/2hswordhitspark/2hswordhitspark.frames
/animations/2hswordhitspark/2hswordhitspark.png
/animations/axehitspark/axehitspark.animation
/animations/axehitspark/axehitspark.frames
# ...and so on.
```


Using the Python package
------------------------

The easiest way to get started with the package is to use the helper
function `open_file`:

```python
import starbound
player = starbound.open_file('player/11475cedd80ead373c19a91de2e2c4d3.player')
print('Hello, %s!' % player.name)
```

The `open_file` function will look at the file extension and choose the
appropriate file format as well as parse additional metadata about that
file type. To be more specific, you can use the file type classes:

```python
import io
import starbound

world = starbound.FileBTreeDB4('universe/beta_73998977_11092106_-913658_12_10.world')
world.open()

# Get the raw data out of the database, then parse it.
raw_data = world.get(b'\x00\x00\x00\x00\x00')
stream = io.BytesIO(raw_data)
stream.seek(8) # Ignore prefix
name, version, data = starbound.sbon.read_document(stream)

print(data['worldTemplate']['size'])
```


Extracting `.pak` files
-----------------------

You can use the `export.py` script to extract all the files in a `.pak`
(or `.modpak`) file.

Example:

```bash
./extract.py -d assets /Starbound/assets/packed.pak
```


Getting world data
------------------

If you want information about a region in a world (planet or ship), you
can use the `region.py` script. For example, here's how to pretty print
the tiles in a region:

```bash
$ ./region.py /Starbound/universe/beta_73998977_11092106_-913658_12_8.world
World size:          250 by 156 regions
Spawn point region:  0, 51
Outputting region:   0, 51

# Outputs colored tiles that can't be displayed on here.
```

If you don't provide X and Y coordinates before the path, it will
default to the region that the spawn point is in.

And here's how to print the entities in a region:

```bash
$ ./region.py --entities 249 52 /Starbound/universe/beta_73998977_11092106_-913658_12_8.world
World size:          250 by 156 regions
Spawn point region:  0, 51
Outputting region:   249, 52

[
  [
    "ObjectEntity",
    {
      "crafting": false,
      "craftingProgress": 0.0,
      "currentState": 0,
      "direction": "right",
      "initialized": true,
      "items": [
        {
          "count": 100,
          "data": {},
          "name": "fabric"
        },
        null,
...
```
