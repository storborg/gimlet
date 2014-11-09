from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import sys
from unittest import TestCase, skipIf

from gimlet.backends.pyredis import RedisBackend
from gimlet.backends.sql import SQLBackend
from gimlet.backends.memcache import MemcacheBackend

PY3 = sys.version_info[0] > 2


class TestBackendClass(TestCase):
    backend_class = dict
    backend_kwargs = {}

    def setUp(self):
        self.backend = self.backend_class(**self.backend_kwargs)

    def test_getset(self):
        self.backend[b'foo'] = b'bar'
        self.assertEqual(self.backend[b'foo'], b'bar')

        self.backend[b'foo'] = b'baz'
        self.assertEqual(self.backend[b'foo'], b'baz')

        self.backend[b'small'] = b'world'
        self.assertEqual(self.backend[b'small'], b'world')

    def test_missing(self):
        with self.assertRaises(KeyError):
            self.backend[b'missing']


class TestRedisBackend(TestBackendClass):
    backend_class = RedisBackend


@skipIf(PY3, "memcached backend is not supported on python 3")
class TestMemcacheBackend(TestBackendClass):
    backend_class = MemcacheBackend


class TestSQLBackend(TestBackendClass):
    backend_class = SQLBackend
    backend_kwargs = dict(url='sqlite://')
