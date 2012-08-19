from unittest import TestCase

from gimlet.backends import RedisBackend, MemcacheBackend


class TestBackendClass(TestCase):
    backend_class = dict

    def setUp(self):
        self.backend = self.backend_class()

    def test_getset(self):
        self.backend['foo'] = 'bar'
        self.assertEqual(self.backend['foo'], 'bar')

    def test_missing(self):
        with self.assertRaises(KeyError):
            self.backend['missing']


class TestRedisBackend(TestBackendClass):
    backend_class = RedisBackend


class TestMemcacheBackend(TestBackendClass):
    backend_class = MemcacheBackend
