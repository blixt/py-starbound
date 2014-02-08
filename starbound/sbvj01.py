import sbon
import filebase


class FileSBVJ01(filebase.File):
    def __init__(self, path):
        super(FileSBVJ01, self).__init__(path)
        self.data = None

    def open(self):
        """Opens the file and reads its contents.

        """
        super(FileSBVJ01, self).open()

        assert self.read(6) == 'SBVJ01', 'Invalid file format'
        self.identifier, self.data = sbon.read_document(self._stream)

        # Technically, we could already close the file at this point. Need to
        # think about this.
