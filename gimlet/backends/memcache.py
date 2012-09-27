import pylibmc

from .base import BaseBackend


class MemcacheBackend(BaseBackend):

    def __init__(self, hosts=['localhost'], *args, **kw):
        client = pylibmc.Client(hosts)
        self.pool = pylibmc.ThreadMappedPool(client)
        BaseBackend.__init__(self, *args, **kw)

    def __getitem__(self, key):
        with self.pool.reserve() as mc:
            raw = mc.get(key)
        if raw:
            return self.deserialize(raw)
        else:
            raise KeyError('key %r not found' % key)

    def __setitem__(self, key, value):
        raw = self.serialize(value)
        with self.pool.reserve() as mc:
            mc.set(key, raw)
