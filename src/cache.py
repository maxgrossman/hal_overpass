from json import dumps, loads
from os import SEEK_END

class Cache:
    def __init__(self, cache_source):
        self._cache = cache_source or {}
    def get(self, key):
        return self._cache[key]
    def set(self, key, value):
        self._cache[key] = value
        self.update_source()
    def has(self, key):
        return key in self._cache
    def update_source(self):
        pass

class FileCache(Cache):
    def __init__(self, cache_source_file):
        with open(cache_source_file, 'a+') as f:
            super().__init__(loads(f.read()) if self.is_json(f) else {})
        self.cache_source_file = cache_source_file

    # excellent json validation going here.
    def is_json(self, f):
        # make sure there's actually data in the file.
        f.seek(0, SEEK_END)
        if f.tell() == 0:
            return False

        # go back to first char and make sure its json opening bracket
        f.seek(0)
        if f.read(1) != '{':
            return False;

        # go back to first char again so we can read the file
        f.seek(0)
        return True
        
    def update_source(self):
        with open(self.cache_source_file, 'w+') as f:
            f.seek(0)
            f.write(dumps(self._cache))
            f.truncate()
