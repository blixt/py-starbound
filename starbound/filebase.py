class File(object):
    @classmethod
    def open(cls, path):
        return cls(open(path, 'rb'))

    def __init__(self, stream):
        self._stream = stream
        self.identifier = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def __str__(self):
        return 'File(identifier=%r, stream=%r)' % (self.identifier, self._stream)

    def close(self):
        self._stream.close()

    def initialize(self):
        self._stream.seek(0)

    def read(self, length):
        return self._stream.read(length)
