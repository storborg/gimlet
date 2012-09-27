from unittest import TestCase

from gimlet.backends.pyredis import RedisBackend
from gimlet.backends.memcache import MemcacheBackend
from gimlet.backends.sql import SQLBackend


class TestBackendClass(TestCase):
    backend_class = dict
    backend_kwargs = {}

    def setUp(self):
        self.backend = self.backend_class(**self.backend_kwargs)

    def test_getset(self):
        self.backend['foo'] = 'bar'
        self.assertEqual(self.backend['foo'], 'bar')

        self.backend['foo'] = 'baz'
        self.assertEqual(self.backend['foo'], 'baz')

        self.backend['small'] = 'world'
        self.assertEqual(self.backend['small'], 'world')

    def test_missing(self):
        with self.assertRaises(KeyError):
            self.backend['missing']


class TestRedisBackend(TestBackendClass):
    backend_class = RedisBackend


class TestMemcacheBackend(TestBackendClass):
    backend_class = MemcacheBackend


class TestSQLBackend(TestBackendClass):
    backend_class = SQLBackend
    backend_kwargs = dict(url='sqlite://')
