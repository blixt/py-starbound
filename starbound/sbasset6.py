# -*- coding: utf-8 -*-

from collections import namedtuple
import struct

from starbound import sbon


# Override range with xrange when running Python 2.x.
try:
    range = xrange
except:
    pass


HEADER = '>8sQ'
HEADER_SIZE = struct.calcsize(HEADER)


IndexEntry = namedtuple('IndexEntry', ['offset', 'length'])


class SBAsset6(object):
    def __init__(self, stream):
        self.stream = stream

    def get(self, path):
        if not hasattr(self, 'index'):
            self.read_index()
        offset, length = self.index[path]
        self.stream.seek(offset)
        return self.stream.read(length)

    def read_header(self):
        self.stream.seek(0)
        data = struct.unpack(HEADER, self.stream.read(HEADER_SIZE))
        assert data[0] == b'SBAsset6', 'Invalid header'
        self.metadata_offset = data[1]
        # Read the metadata as well.
        self.stream.seek(self.metadata_offset)
        assert self.stream.read(5) == b'INDEX', 'Invalid index data'
        self.metadata = sbon.read_map(self.stream)
        self.file_count = sbon.read_varint(self.stream)
        # Store the offset of where the file index starts.
        self.index_offset = self.stream.tell()

    def read_index(self):
        if not hasattr(self, 'index_offset'):
            self.read_header()
        self.stream.seek(self.index_offset)
        self.index = {}
        for i in range(self.file_count):
            path = sbon.read_string(self.stream)
            offset, length = struct.unpack('>QQ', self.stream.read(16))
            self.index[path] = IndexEntry(offset, length)
