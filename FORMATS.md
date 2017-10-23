Starbound data formats
======================

This document is intended to describe Starbound's various data structures.

* [File formats](#file-formats)
* [SBON](#sbon)
* [Celestial data](#celestial-data)
* [World data](#world-data)


File formats
------------

Starbound uses regular JSON and Lua files for some things, but this
document will only focus on the custom file formats.

* [BTreeDB5](#btreedb5)
* [SBAsset6](#sbasset6)
* [SBVJ01](#sbvj01)

### BTreeDB5

A B-tree database format which enables quick scanning and updating.
It's used by Starbound to save world and universe data.

#### Header

The header consists of 512 bytes, representing the following fields:

| Field # | Type        | Description
| ------: | ----------- | -----------
| 1       | `char[8]`   | The string "BTreeDB5"
| 2       | `int32`     | Byte size of blocks (see below)
| 3       | `char[16]`  | The name of the database (null padded)
| 4       | `int32`     | Byte size of index keys
| 5       | `bool`      | Whether to use root node #2 instead
| 6       | `int32`     | Free node #1 block index
| –       | `byte[4]`   | Unknown
| 7       | `int32`     | Offset in file of end of free block #1
| 8       | `int32`     | Root node #1 block index
| 9       | `boolean`   | Whether root node #1 is a leaf
| 10      | `int32`     | Free node #2 block index
| –       | `byte[4]`   | Unknown
| 11      | `int32`     | Offset in file of end of free block #2
| 12      | `int32`     | Root node #2 block index
| 13      | `boolean`   | Whether root node #2 is a leaf
| –       | `byte[445]` | Unused bytes

In the BTreeDB4 format there was also a "free node is dirty" boolean
which is not accounted for above. It may be one of the "Unknown"
values.

#### Blocks

The most primitive structure in the BTreeDB5 format is the block. It's
a chunk of bytes of a fixed size (defined in the header) which plays a
certain role in the database.

A lot of fields in the BTreeDB5 format references blocks by their index
which means an offset of `header_size + index * block_size`.

##### Root nodes

The root node is the entry point when scanning for a specific key. The
root node can be either an index block or a leaf block, depending on
how large the database is. Usually, it will be an index block.

Since BTreeDB5 databases are meant to be updated on the fly, the root
node may alternate to allow for transactional updates to the index.
If the *alternate root block index* flag is true, the alternate root
index should be used for entry instead when scanning for a key.

##### Index block

The index block always starts with the characters `II`.

##### Leaf block

The leaf block always starts with the characters `LL`.

##### Free block

The free block always starts with the characters `FF`.

Free blocks may be either brand new blocks (after growing the file), or
reclaimed blocks that were no longer in use.

#### Scanning for a key

This section will contain information on how to retrieve a value from a
BTreeDB5 database.

### SBAsset6

A large file that contains an index pointing to many small files within
it. The main asset file (`packed.pak`) and mods are of this type.

#### Header

The header for SBAsset6 is very straightforward:

| Field # | Type      | Description
| ------: | --------- | -----------
| 1       | `char[8]` | The string "SBAsset6"
| 2       | `uint64`  | Metadata offset

The metadata offset points to another location in the file where the
metadata can be read. Seek to that point in the file and find:

| Field # | Type        | Description
| ------: | ----------- | -----------
| 1       | `char[5]`   | The string "INDEX"
| 2       | SBON map    | Information about the file
| 3       | SBON varint | Number of files in the index
| 4 + 3n  | SBON string | SBON UTF-8 encoded string
| 5 + 3n  | `uint64`    | Offset where file starts
| 6 + 3n  | `uint64`    | Length of file

Once the index has been parsed into memory, it can be used to seek to
various files in the SBAsset6 file.

### SBVJ01

Versioned JSON-like data. Used for player data files and the like. The
data structures themselves use a custom binary form of JSON which will
be referred to as "SBON" in this document.

The file structure is simply the string `"SBVJ01"` followed by a single
versioned JSON object (see below).


SBON
----

(I'm calling this "Starbound Binary Object Notation", but don't know
what the Starbound developers call it internally.)

This format is similar to other binary formats for JSON (e.g., BSON).
SBON is used in most file formats to represent complex data such as
metadata and entities.

### Data types

* Variable length integer (also known as [VLQ][vlq])
* Bytes (varint for length + the bytes)
* String (bytes with UTF-8 encoding)
* List (varint for count, dynamic for values)
* Map (varint for count, string/dynamic pairs for entries)
* Dynamic (byte for type + value)
  * `0x01`: Nil value
  * `0x02`: Double-precision float (a.k.a. `double`)
  * `0x03`: Boolean
  * `0x04`: Signed varint (see below)
  * `0x05`: String
  * `0x06`: List
  * `0x07`: Map

#### Varint

A variable length (in bytes) integer, also known as [VLQ][vlq]. As long as the most significant bit is set read the next byte and concatenate its 7 other bits with the 7 bits of the previous bytes. The resulting string of bits is the binary representation of the number.

The purposes of this data type is to allow (common) lower values 0...127 to only use up one byte, 128...16383 two bytes, and so on.

#### Signed varint

A signed varint is just a regular varint, except that the least significant bit (the very last bit in the data stream) is used to represent the sign of the number. If the bit is 1, the number should be considered negative and also have one subtracted from its value (because there is no negative 0). If the bit is 0, the number is positive. In both cases, the least significant bit should not be considered part of the number.

### Versioned JSON

Starbound has a data structure known as "versioned JSON" which consists
of SBON. In addition to arbitrary data, it also holds a name and a
version.

Most complex data structures are represented as versioned JSON and may
have Lua scripts that upgrade older versions to the current one.

| Field         | Type         | Description
| ------------- | ------------ | -----------
| Name          | SBON string  | The name or type of the data structure.
| Is versioned? | `bool`       | Flag indicating that there’s a version.
| Version       | `int32`      | Version (only if previous field is `true`).
| Data          | SBON dynamic | The data itself, usually a map.


Celestial data
--------------

Celestial files are BTreeDB5 databases that contain generated
information about the universe.

Little is currently known about this format as the keys are hashes of
some key that has not yet been reverse engineered.


World data
----------

World files (this includes the player ship) are BTreeDB5 databases that
contain the metadata, entities, and tile regions of the world.

### Regions

Regions are indexed by *type*, *X*, and *Y* values. The *type* value is
`1` for tile data and `2` for entity data. There's a special key,
{0, 0, 0} which points to the world metadata. All values are gzip
deflated and must be inflated before they can be read.

The BTreeDB5 key for a region is represented in binary as a byte for
*type* followed by two shorts for the *X* and *Y* coordinates.

The X axis goes from left to right and the Y axis goes from down to up.

#### World metadata

Once inflated, the {0, 0, 0} value starts with two integers (8 bytes)
holding the number of tiles along the X and Y axes, followed by an SBON
data structure containing all the world's metadata.

#### Tile data

The {1, X, Y} value contains three bytes followed by the data for 32×32
tiles. The purpose of the three bytes is currently unknown.

A single tile is made up of 30 bytes of binary data:

| Field #  | Bytes | Type     | Description
| -------: | ----: | -------- | -----------
| 1        | 1–2   | `int16`  | Foreground material¹
| 2        | 3     | `uint8`  | Foreground hue shift
| 3        | 4     | `uint8`  | Foreground color variant
| 4        | 5–6   | `int16`  | Foreground mod
| 5        | 7     | `uint8`  | Foreground mod hue shift
| 6        | 8–9   | `int16`  | Background material¹
| 7        | 10    | `uint8`  | Background hue shift
| 8        | 11    | `uint8`  | Background color variant
| 9        | 12–13 | `int16`  | Background mod
| 10       | 14    | `uint8`  | Background mod hue shift
| 11       | 15    | `uint8`  | Liquid
| 12       | 16–19 | `float`  | Liquid level
| 13       | 20–23 | `float`  | Liquid pressure
| 14       | 24    | `bool`   | Liquid is infinite
| 15       | 25    | `uint8`  | Collision map²
| 16       | 26–27 | `uint16` | Dungeon ID³
| 17       | 28    | `uint8`  | "Biome"⁴
| 18       | 29    | `uint8`  | "Environment Biome"⁴
| 19       | 30    | `bool`   | Indestructible (tree/vine base)
| 20       | 31    | `unknown`| Unknown?

¹ Refers to a material by its id. Additional constants:

| Constant | Meaning
| -------: | -------
| -36      | Unknown (seen on ships)
| -9       | Unknown (possibly dungeon related)
| -8       | Unknown (possibly dungeon related)
| -7       | Unknown (possibly dungeon related)
| -3       | Not placeable
| -2       | Not generated (or outside world bounds)
| -1       | Empty

² Used by the game to block the player's movement. Constants:

| Constant | Meaning
| -------: | -------
| 1        | Empty space
| 2        | Platform (floor that player can pass through)
| 3        | Dynamic (e.g., closed door)
| 5        | Solid

³ Dungeon info is stored in the world metadata. Additional constants:

| Constant | Meaning
| -------: | -------
| 65,531   | Tile removed by player
| 65,532   | Tile placed by player
| 65,533   | Microdungeon
| 65,535   | Not associated with anything

⁴ Unverified, simply quoting from this page: http://seancode.com/galileo/format/tile.html

#### Entity data

Values for {2, X, Y} keys are a sequence of various entities in the
region at (X, Y). Each entity is a versioned JSON object.

The data, once inflated, consists of an SBON varint for the count and
then the versioned JSON objects, one after the other.


[vlq]: https://en.wikipedia.org/wiki/Variable-length_quantity
