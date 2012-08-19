import cPickle as pickle
from threading import Lock

import pylibmc
from redis import Redis

lock = Lock()


class BaseBackend(object):

    def __init__(self, prefix='gimlet.'):
        self.prefix = prefix

    def prefixed_key(self, key):
        return self.prefix + key


class RedisBackend(BaseBackend):

    def __init__(self, host='localhost', port=6379, db=0, *args, **kw):
        self.client = Redis(host=host, port=port, db=db)
        BaseBackend.__init__(self, *args, **kw)

    def __getitem__(self, key):
        with lock:
            raw = self.client.get(self.prefixed_key(key))
        if raw:
            return pickle.loads(raw)
        else:
            raise KeyError('key %r not found' % key)

    def __setitem__(self, key, value):
        raw = pickle.dumps(value)
        with lock:
            self.client.set(self.prefixed_key(key), raw)


class MemcacheBackend(BaseBackend):

    def __init__(self, hosts=['localhost'], *args, **kw):
        client = pylibmc.Client(hosts)
        self.pool = pylibmc.ThreadMappedPool(client)
        BaseBackend.__init__(self, *args, **kw)

    def __getitem__(self, key):
        with self.pool.reserve() as mc:
            raw = mc.get(key)
        if raw:
            return pickle.loads(raw)
        else:
            raise KeyError('key %r not found' % key)

    def __setitem__(self, key, value):
        raw = pickle.dumps(value)
        with self.pool.reserve() as mc:
            mc.set(key, raw)
