# Starbound utilities for Python

This is a library to parse Starbound's file formats which are used to
store worlds, player characters, assets, etc.

Feel free to contribute either via submitting pull requests or writing
up issues with suggestions and/or bugs.

## File & data formats

Check out [FORMATS.md](./FORMATS.md) for technical information on
Starbound's file and data formats.

## Installation

py-starbound can be installed (either to your system, user account, or
virtualenv) using the usual `setup.py` script:

```bash
$ python setup.py install
```

After installation, the commandline utilities (described below) should
be available in your `$PATH` can can be run like any other app:

```bash
$ pystarbound-export [args]
$ pystarbound-region [args]
```

If you wish to run these utilities from the git checkout itself (without
installing first), the syntax is slightly more verbose:

```bash
$ python -m starbound.cliexport [args]
$ python -m starbound.cliregion [args]
```

## Command line utilities

### Extracting `.pak` files

You can use the `pystarbound-export` script to extract all the files in a `.pak`
(or `.modpak`) file.

Example:

```bash
$ pystarbound-export -d assets /Starbound/assets/packed.pak
```

Or from the git checkout directly:

```bash
$ python -m starbound.cliexport -d assets /Starbound/assets/packed.pak
```

### Getting world info

If you want information about a region in a world (planet or ship), you
can use the `region.py` script. For example, here's how to pretty print
the tiles in a region:

```bash
$ pystarbound-region /Starbound/storage/universe/-382912739_-582615456_-73870035_3.world
World size:        3000×2000
Spawn point:       (1224.0, 676.0)
Outputting region: (37, 21)
Outputting value:  foreground_material
```

Or from the git checkout directly:

```bash
$ python -m starbound.cliregion /Starbound/storage/universe/-382912739_-582615456_-73870035_3.world
```

Outputs something like this:

![](http://i.imgur.com/b4ZitYX.png)

If you don't provide X and Y coordinates after the path, it will
default to the region that the spawn point is in.

You can also output specific tile values (instead of the foreground)
using `--value-index` (or `-v`):

```bash
$ pystarbound-region --value-index=12 /Starbound/storage/universe/-382912739_-582615456_-73870035_3.world 69 27
World size:        3000×2000
Spawn point:       (1224.0, 676.0)
Outputting region: (69, 27)
Outputting value:  liquid_pressure
```

Outputs something like this:

![](http://i.imgur.com/XZ3OYTO.png)

And here's how to print the entities in a region:

```bash
$ pystarbound-region --entities /Starbound/storage/universe/-382912739_-582615456_-73870035_3.world 69 27
World size:        3000×2000
Spawn point:       (1224.0, 676.0)
Outputting region: (69, 27)

[
  [
    "ObjectEntity",
    8,
    {
      "direction": "left",
      "inputWireNodes": [],
      "interactive": true,
      "name": "wiringstation",
      "orientationIndex": 0,
      "outputWireNodes": [],
      "parameters": {
        "owner": "916d5878483e3a40d10467dc419982c2"
      },
      "scriptStorage": {},
...
```

## Using the Python package

The Python package lets you read data from Starbound's various file
formats. The classes and functions expect file objects to read from.

You can use the `mmap` package to improve performance for large files,
such as `packed.pak` and world files.

### Example: Reading a player file

Here's how to print the name of a player:

```python
import starbound

with open('player/11475cedd80ead373c19a91de2e2c4d3.player', 'rb') as fh:
  player = starbound.read_sbvj01(fh)
  print('Hello, {}!'.format(player.data['identity']['name']))
```

### Example: World files

In the following example the `mmap` package is used for faster access:

```python
import mmap, starbound

with open('universe/43619853_198908799_-9440367_6_3.world', 'rb') as fh:
  mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)

  world = starbound.World(mm)
  world.read_metadata()

  print('World size: {}×{}'.format(world.width, world.height))
  x, y = world.metadata['playerStart']
  print('Player spawns at ({}, {})'.format(x, y))

  # Regions consist of 32×32 tiles.
  rx, ry = x // 32, y // 32
  print('An entity: {}'.format(world.get_entities(rx, ry)[0]))
```

### Example: Easy access to various world attributes

A vast amount of information about loaded Worlds is available via the
`metadata` attribute (as seen in the above section), but some
information is also abstracted out into an `info` attribute. For instance:

```python
world = starbound.World(fh)
print('World Name: {}'.format(world.info.name))
print('World Description: {}'.format(world.info.description))
print('World Coordinates: ({}, {})'.format(world.info.coords[0], world.info.coords[1]))
```

The full list of attributes currently available are:

| Attribute      | Description                                                                                                                                                     |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `biomes`       | The full set of biomes found on the world. This should be a complete list, regardless of how much of the world has been explored.                               |
| `coords`       | World coordinates, as a tuple. The first two elements are the in-map coordinates of the system, the third is effectively random but describes the world itself. |
| `description`  | The internal description of the world. Will often include text describing the tier of the world.                                                                |
| `dungeons`     | The full set of dungeons found on the world. This should be a complete list, regardless of how much of the world has been explored.                             |
| `name`         | The name of the world. Will often include Starbound coloration markup.                                                                                          |
| `size`         | A tuple describing the width and height of the world.                                                                                                           |
| `world_biomes` | A set of the main biome IDs of the world, of the sort reported in the ingame navigation screen.                                                                 |

### Example: Finding an entity by UUID/ID

Many entities in Starbound, such as bookmarked flags, mech beacons,
quest markers, etc, have UUIDs or IDs which the game can use to find
where they are in the map without having to have all regions loaded.
Player bookmark UUIDs can be found in the `player.data['universeMap']`
dict, underneath `teleportBookmarks`. One object type which does
_not_ use UUIDs is a level's mech beacon, which instead uses the magic
string `mechbeacon`. To find the ingame coordinates for a level's
beacon (if one is present), this can be used:

```python
mechbeacon_coords = world.get_entity_uuid_coords('mechbeacon')
if mechbeacon_coords:
  print('Mech beacon found at ({}, {})'.format(*mechbeacon_coords))
else:
  print('No mech beacon in level!')
```

### Example: Getting assets from `packed.pak`

Starbound keeps most of the assets (images, configuration files,
dungeons, etc.) in a file called `packed.pak`. This file uses a special
format which can be read by py-starbound, as you can see below.

```python
import starbound

with open('assets/packed.pak', 'rb') as fh:
  package = starbound.SBAsset6(fh)

  # Print the contents of a file in the asset package.
  print(package.get('/lighting.config'))
```

### Example: Modifying Starbound files

Currently, only the SBVJ01 file format can be written by py-starbound.
This means player files, client context files, and the statistics file.

Here's an example that renames a player (WARNING: Always back up files
before writing to them!):

```python
import starbound

with open('player/420ed511f83b3760dead42a173339b3e.player', 'r+b') as fh:
  player = starbound.read_sbvj01(fh)

  old_name = player.data['identity']['name']
  new_name = old_name.encode('rot13')
  player.data['identity']['name'] = new_name
  print('Updating name: {} -> {}'.format(old_name, new_name))

  # Go back to the beginning of the file and write the updated data.
  fh.seek(0)
  starbound.write_sbvj01(fh, player)
  # If the file got shorter, truncate away the remaining content.
  fh.truncate()
```

## License

[MIT License](./LICENSE)
