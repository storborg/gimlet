import os
from unittest import TestCase, skipUnless

from webtest import TestApp

try:
    from Crypto.Cipher import AES
except ImportError:
    encryption_available = False
else:
    encryption_available = AES

from gimlet.middleware import SessionMiddleware

from .test_middleware import SampleApp

inner_app = SampleApp()


class TestEncryptedSession(TestCase):
    def setUp(self):
        self.inner_app = inner_app
        test_key = os.urandom(32).encode('hex')
        wrapped_app = SessionMiddleware(inner_app, 's3krit',
                                        encryption_key=test_key)
        self.app = TestApp(wrapped_app)

    @skipUnless(encryption_available, "pycrypto not available")
    def test_getset_basic(self):
        self.app.get('/get/foo', status=404)

        resp = self.app.get('/set/foo/bar')
        resp.mustcontain('ok')

        resp = self.app.get('/get/foo')
        resp.mustcontain('bar')

        with self.assertRaises(ValueError):
            self.app.get('/set/quux/bogus-value?clientside=0')

    @skipUnless(encryption_available, "pycrypto not available")
    def test_wrong_key_length(self):
        with self.assertRaises(ValueError):
            SessionMiddleware(self.inner_app, 's3krit',
                              encryption_key=os.urandom(20).encode('hex'))

    @skipUnless(encryption_available, "pycrypto not available")
    def test_non_hex_key(self):
        with self.assertRaises(ValueError):
            SessionMiddleware(self.inner_app, 's3krit',
                              encryption_key=('s' * 64))
