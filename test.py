import hashlib
import sbbf02

def hash_key(key):
    return hashlib.sha256(key.encode('utf-8')).digest()

with sbbf02.StarFile('assets/packed.pak') as assets:
    assets.open()

    # Print the string containing a list of files in assets.pak.
    key = hash_key('_index')
    print assets.get(key)
