class File(object):
    def __init__(self, path):
        self._stream = None

        self.path = path
        self.identifier = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.is_open():
            self.close()

    def __str__(self):
        if self.is_open():
            return 'open File(identifier="{}", path="{}")'.format(self.identifier, self.path)
        else:
            return 'closed File(path="{}")'.format(self.path)

    def close(self):
        assert self._stream, 'File is not open'
        self._stream.close()
        self._stream = None

    def is_open(self):
        return self._stream is not None

    def open(self):
        assert self._stream is None, 'File is already open'
        stream = open(self.path)
        self._stream = stream

    def read(self, length):
        return self._stream.read(length)
