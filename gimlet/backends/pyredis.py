from threading import Lock

from redis import Redis

from .base import BaseBackend

lock = Lock()


class RedisBackend(BaseBackend):

    def __init__(self, host='localhost', port=6379, db=0, *args, **kw):
        self.client = Redis(host=host, port=port, db=db)
        BaseBackend.__init__(self, *args, **kw)

    def __getitem__(self, key):
        with lock:
            raw = self.client.get(self.prefixed_key(key))
        if raw:
            return self.deserialize(raw)
        else:
            raise KeyError('key %r not found' % key)

    def __setitem__(self, key, value):
        raw = self.serialize(value)
        with lock:
            self.client.set(self.prefixed_key(key), raw)
